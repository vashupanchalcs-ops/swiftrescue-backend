"""
ambulance/tracking_views.py
Real-time GPS tracking, route suggestion, and driver ping APIs
"""
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from ambulance.models import Ambulance, DriverLocation, SuggestedRoute
import json
import math
import hashlib
import time
import urllib.request
import urllib.parse


def _resolve_ambulance(raw_id):
    """Resolve an ambulance by database id, fleet number, or contract id."""
    value = str(raw_id or "").strip()
    if not value:
        return None
    if value.isdigit():
        ambulance = Ambulance.objects.filter(id=int(value)).first()
        if ambulance:
            return ambulance
    ambulance = Ambulance.objects.filter(ambulance_number__iexact=value).first()
    if ambulance:
        return ambulance
    return Ambulance.objects.filter(ambulance_contract_id__iexact=value).first()


@csrf_exempt
def update_battery(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        data = json.loads(request.body or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    ambulance_id = data.get("ambulance_id")
    battery_percentage = data.get("battery_percentage")
    if ambulance_id is None or battery_percentage is None:
        return JsonResponse({"error": "ambulance_id and battery_percentage are required"}, status=400)

    ambulance = _resolve_ambulance(ambulance_id)
    if not ambulance:
        return JsonResponse({"error": "Ambulance not found"}, status=404)
    try:
        battery_value = max(0, min(100, int(battery_percentage)))
    except (TypeError, ValueError):
        return JsonResponse({"error": "battery_percentage must be an integer"}, status=400)

    ambulance.battery_percentage = battery_value
    ambulance.save(update_fields=["battery_percentage", "last_updated"])
    return JsonResponse({
        "status": "ok",
        "ambulance_id": ambulance.id,
        "battery_percentage": ambulance.battery_percentage,
        "last_updated": ambulance.last_updated.isoformat(),
    })


def _route_dict(r):
    if not r:
        return None
    return {
        "id":              r.id,
        "ambulance_id":    r.ambulance_id,
        "booking_id":      getattr(r, "booking_id", None),
        "pickup_location": r.pickup_location,
        "destination":     r.destination,
        "polyline":        r.polyline,
        "distance_km":     r.distance_km,
        "duration":        r.duration,
        "status":          r.status,
        # Coordinates for driver map rendering
        "pickup_lat":      getattr(r, "pickup_lat", None),
        "pickup_lng":      getattr(r, "pickup_lng", None),
        "dest_lat":        getattr(r, "dest_lat", None),
        "dest_lng":        getattr(r, "dest_lng", None),
        "created_at":      r.created_at.isoformat(),
        "accepted_at":     r.accepted_at.isoformat() if r.accepted_at else None,
        "completed_at":    r.completed_at.isoformat() if r.completed_at else None,
    }


@csrf_exempt
def driver_ping(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        data = json.loads(request.body or b"{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    email  = str(data.get("driver_email", "")).strip().lower()
    amb_id = data.get("ambulance_id")
    lat    = data.get("latitude")
    lng    = data.get("longitude")
    speed  = data.get("speed", 0)
    if not all([email, amb_id, lat is not None, lng is not None]):
        return JsonResponse({"error": "driver_email, ambulance_id, latitude, longitude required"}, status=400)
    amb = _resolve_ambulance(amb_id)
    if not amb:
        return JsonResponse({"error": "Ambulance not found"}, status=404)
    try:
        lat, lng = float(lat), float(lng)
        speed = float(speed or 0)
    except (TypeError, ValueError):
        return JsonResponse({"error": "latitude, longitude and speed must be numeric"}, status=400)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180) or not math.isfinite(lat) or not math.isfinite(lng):
        return JsonResponse({"error": "Invalid latitude/longitude"}, status=400)
    if str(amb.driver_email or "").strip().lower() != email:
        return JsonResponse({"error": "Driver is not assigned to this ambulance"}, status=403)
    amb.latitude  = lat
    amb.longitude = lng
    amb.speed     = str(speed)
    amb.save(update_fields=["latitude", "longitude", "speed", "last_updated"])
    sample_key = f"driver-location-sampled:{amb.id}"
    sampled = cache.add(sample_key, True, timeout=10)
    if sampled:
        DriverLocation.objects.create(ambulance=amb, driver_email=email, latitude=lat, longitude=lng, speed=speed)
    pending = SuggestedRoute.objects.filter(ambulance=amb, status__in=["pending", "accepted"]).order_by("-created_at").first()
    timestamp = timezone.now().isoformat()
    location_payload = {
        "type": "location_update",
        "ambulance_id": amb.id,
        "ambulance_number": amb.ambulance_number,
        "driver": amb.driver,
        "status": amb.status,
        "latitude": lat,
        "longitude": lng,
        "speed": speed,
        "last_updated": timestamp,
        "pending_route": _route_dict(pending),
    }
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"ambulance_{amb.id}",
            {"type": "tracking.location", "payload": location_payload},
        )
        from bookings.models import Booking
        active_booking_ids = Booking.objects.filter(
            ambulance_id=amb.id, status__in=["pending", "confirmed"]
        ).values_list("id", flat=True)
        for booking_id in active_booking_ids:
            async_to_sync(channel_layer.group_send)(
                f"booking_{booking_id}",
                {"type": "tracking.location", "payload": location_payload},
            )
    except Exception:
        # GPS persistence must not fail just because Redis/Channels is down.
        pass
    return JsonResponse({"status": "ok", "sampled": sampled, "timestamp": timestamp, "pending_route": _route_dict(pending)})


@csrf_exempt
def all_live_locations(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    ambulances = list(Ambulance.objects.exclude(latitude=None).exclude(longitude=None))
    routes_by_ambulance = {}
    route_rows = SuggestedRoute.objects.filter(
        ambulance_id__in=[a.id for a in ambulances], status__in=["pending", "accepted"]
    ).order_by("-created_at")
    for route in route_rows:
        routes_by_ambulance.setdefault(route.ambulance_id, route)
    result = []
    for a in ambulances:
        active = routes_by_ambulance.get(a.id)
        result.append({
            "ambulance_id":     a.id,
            "ambulance_number": a.ambulance_number,
            "driver":           a.driver,
            "driver_email":     a.driver_email or "",
            "status":           a.status,
            "latitude":         a.latitude,
            "longitude":        a.longitude,
            "speed":            a.speed,
            "last_updated":     a.last_updated.isoformat(),
            "active_route":     _route_dict(active),
        })
    return JsonResponse(result, safe=False)


@csrf_exempt
def suggest_route(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    data = json.loads(request.body)
    try:
        amb = Ambulance.objects.get(id=data.get("ambulance_id"))
    except Ambulance.DoesNotExist:
        return JsonResponse({"error": "Ambulance not found"}, status=404)
    SuggestedRoute.objects.filter(ambulance=amb, status="pending").update(status="rejected")
    route = SuggestedRoute.objects.create(
        ambulance=amb,
        booking_id=data.get("booking_id"),
        pickup_location=data.get("pickup_location", ""),
        destination=data.get("destination", ""),
        polyline=data.get("polyline", ""),
        distance_km=data.get("distance_km", ""),
        duration=data.get("duration", ""),
        status="pending",
        pickup_lat=data.get("pickup_lat"),
        pickup_lng=data.get("pickup_lng"),
        dest_lat=data.get("dest_lat"),
        dest_lng=data.get("dest_lng"),
    )
    return JsonResponse(_route_dict(route), status=201)


@csrf_exempt
def respond_route(request, route_id):
    if request.method != "PATCH":
        return JsonResponse({"error": "PATCH only"}, status=405)
    try:
        route = SuggestedRoute.objects.get(id=route_id)
    except SuggestedRoute.DoesNotExist:
        return JsonResponse({"error": "Route not found"}, status=404)
    data      = json.loads(request.body)
    newstatus = data.get("status")
    if newstatus not in {"accepted", "rejected", "completed"}:
        return JsonResponse({"error": "Invalid status"}, status=400)
    route.status = newstatus
    if newstatus == "accepted":
        route.accepted_at = timezone.now()
    elif newstatus == "completed":
        route.completed_at = timezone.now()
        route.ambulance.status = "available"
        route.ambulance.save(update_fields=["status"])
    route.save()
    return JsonResponse(_route_dict(route))


@csrf_exempt
def driver_active_route(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    email = request.GET.get("driver_email", "").strip().lower()
    try:
        ambulance_id = int(request.GET.get("ambulance_id", "0"))
    except (TypeError, ValueError):
        ambulance_id = 0
    if not email and ambulance_id <= 0:
        return JsonResponse({"error": "driver_email or ambulance_id required"}, status=400)
    amb = Ambulance.objects.filter(id=ambulance_id).first() if ambulance_id > 0 else None
    if not amb and email:
        amb = Ambulance.objects.filter(driver_email__iexact=email).first()
    if not amb:
        return JsonResponse({"error": "No ambulance found"}, status=404)
    if email and str(amb.driver_email or "").strip().lower() != email:
        return JsonResponse({"error": "Driver is not assigned to this ambulance"}, status=403)
    try:
        route = SuggestedRoute.objects.filter(ambulance=amb, status__in=["pending", "accepted"]).order_by("-created_at").first()
    except Exception:
        # A missing/stale route record must not make the whole driver portal
        # fail; the client can keep showing its cached route and retry.
        return JsonResponse({})
    return JsonResponse(_route_dict(route) if route else {})


@csrf_exempt
def get_traffic_route(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        data = json.loads(request.body or b"{}")
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    client = forwarded.split(",", 1)[0].strip() or request.META.get("REMOTE_ADDR", "unknown")
    rate_key = f"traffic-route-rate:{client}:{int(time.time() // 60)}"
    try:
        allowed = cache.add(rate_key, 1, timeout=65) or int(cache.incr(rate_key)) <= 30
    except Exception:
        allowed = True
    if not allowed:
        return JsonResponse({"error": "Traffic route rate limit exceeded; retry shortly"}, status=429)
    api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        return JsonResponse({"error": "Traffic routing is not configured on the server"}, status=503)
    required = ("origin_lat", "origin_lng", "pickup_lat", "pickup_lng", "dest_lat", "dest_lng")
    if any(key not in data for key in required):
        return JsonResponse({"error": "origin, pickup and destination coordinates are required"}, status=400)
    origin      = f"{data['origin_lat']},{data['origin_lng']}"
    pickup      = f"{data['pickup_lat']},{data['pickup_lng']}"
    destination = f"{data['dest_lat']},{data['dest_lng']}"
    cache_key = "traffic-route:" + hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
    try:
        cached = cache.get(cache_key)
    except Exception:
        cached = None
    if cached:
        cached = dict(cached)
        cached["cached"] = True
        return JsonResponse(cached)
    params = {
        "origin":         origin,
        "destination":    destination,
        "waypoints":      f"optimize:false|{pickup}",
        "mode":           "driving",
        "departure_time": "now",
        "traffic_model":  "best_guess",
        "alternatives":   "true",
        "key":            api_key,
    }
    url = "https://maps.googleapis.com/maps/api/directions/json?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            result = json.loads(resp.read())
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=502)
    if result.get("status") != "OK":
        return JsonResponse({"error": result.get("status"), "detail": result.get("error_message", "")}, status=400)
    routes = []
    for r in result["routes"]:
        total_dist = sum(leg["distance"]["value"] for leg in r["legs"])
        total_dur  = sum(leg.get("duration_in_traffic", leg["duration"])["value"] for leg in r["legs"])
        routes.append({
            "summary":      r.get("summary", ""),
            "polyline":     r["overview_polyline"]["points"],
            "distance_km":  f"{total_dist / 1000:.1f} km",
            "duration":     f"{total_dur // 60} min",
            "duration_sec": total_dur,
        })
    if not routes:
        return JsonResponse({"error": "Traffic provider returned no routes"}, status=502)
    routes.sort(key=lambda x: x["duration_sec"])
    payload = {"routes": routes, "best": routes[0], "total": len(routes), "cached": False}
    try:
        cache.set(cache_key, payload, timeout=45)
    except Exception:
        pass
    return JsonResponse(payload)


@csrf_exempt
def active_route_by_booking(request, booking_id):
    """Return the active SuggestedRoute for a given booking_id.
    Used by user/hospital portals to show the same route the admin sent to the driver."""
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    route = SuggestedRoute.objects.filter(
        booking_id=booking_id,
        status__in=["pending", "accepted"],
    ).order_by("-created_at").first()
    if not route:
        # Fallback: find by ambulance linked to this booking
        from bookings.models import Booking
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return JsonResponse({})
        route = SuggestedRoute.objects.filter(
            ambulance_id=booking.ambulance_id,
            status__in=["pending", "accepted"],
        ).order_by("-created_at").first()
    return JsonResponse(_route_dict(route) if route else {})
