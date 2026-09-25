import json
import urllib.request
import urllib.parse
import hashlib
import time
from datetime import datetime, timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.cache import cache

GOOGLE_API_KEY = getattr(settings, "GOOGLE_MAPS_API_KEY", "").strip()


def _allow_route_request(request, limit=30):
    """Bound expensive route calls per client while allowing cache hits."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    client = forwarded.split(",", 1)[0].strip() or request.META.get("REMOTE_ADDR", "unknown")
    bucket = int(time.time() // 60)
    key = f"route-rate:{client}:{bucket}"
    try:
        if cache.add(key, 1, timeout=65):
            return True
        return int(cache.incr(key)) <= limit
    except Exception:
        return True


def _annotate_route(route_data):
    provider = str(route_data.get("provider", "fallback")).lower()
    traffic_available = provider in {"tomtom", "google"}
    route_data["traffic_available"] = traffic_available
    route_data["trafficAvailable"] = traffic_available
    route_data["last_calculated_at"] = datetime.now(timezone.utc).isoformat()
    return route_data


def _is_india_coord(lat, lng):
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return False
    return 6 <= lat <= 38 and 68 <= lng <= 98


def _geocode(address):
    if not GOOGLE_API_KEY:
        return None
    params = {"address": address, "key": GOOGLE_API_KEY}
    url = "https://maps.googleapis.com/maps/api/geocode/json?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=6) as resp:
            data = json.loads(resp.read())
        if data.get("status") == "OK":
            loc = data["results"][0]["geometry"]["location"]
            return f"{loc['lat']},{loc['lng']}"
    except Exception:
        pass
    return None


@csrf_exempt
def get_route(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        data = json.loads(request.body)
    except (KeyError, json.JSONDecodeError) as e:
        return JsonResponse({"error": f"Invalid JSON: {e}"}, status=400)
    if not _allow_route_request(request):
        return JsonResponse({"error": "Route request rate limit exceeded; retry shortly"}, status=429)

    origin_lat = data.get("origin_lat") or data.get("ambulance_lat") or data.get("pickup_lat")
    origin_lng = data.get("origin_lng") or data.get("ambulance_lng") or data.get("pickup_lng")
    dest_lat = data.get("dest_lat") or data.get("hospital_lat") or data.get("destination_lat")
    dest_lng = data.get("dest_lng") or data.get("hospital_lng") or data.get("destination_lng")

    if origin_lat is None or origin_lng is None or dest_lat is None or dest_lng is None:
        return JsonResponse({"error": "Missing coordinates: origin_lat, origin_lng, dest_lat, dest_lng required."}, status=400)

    # Check if there is an intermediate waypoint, e.g. pickup between ambulance and hospital
    waypoints = []
    pickup_lat = data.get("pickup_lat")
    pickup_lng = data.get("pickup_lng")
    amb_lat = data.get("ambulance_lat")
    amb_lng = data.get("ambulance_lng")
    hosp_lat = data.get("hospital_lat") or data.get("dest_lat")
    hosp_lng = data.get("hospital_lng") or data.get("dest_lng")

    if amb_lat is not None and pickup_lat is not None and hosp_lat is not None:
        try:
            o_lat, o_lng = float(amb_lat), float(amb_lng)
            p_lat, p_lng = float(pickup_lat), float(pickup_lng)
            d_lat, d_lng = float(hosp_lat), float(hosp_lng)
            if (abs(o_lat - p_lat) > 0.0001 or abs(o_lng - p_lng) > 0.0001) and (abs(p_lat - d_lat) > 0.0001 or abs(p_lng - d_lng) > 0.0001):
                origin_lat, origin_lng = o_lat, o_lng
                dest_lat, dest_lng = d_lat, d_lng
                waypoints = [(p_lat, p_lng)]
        except (ValueError, TypeError):
            pass

    try:
        from routing_provider import default_provider
        route_data = default_provider.calculate_route(
            origin_lat=float(origin_lat),
            origin_lng=float(origin_lng),
            dest_lat=float(dest_lat),
            dest_lng=float(dest_lng),
            waypoints=waypoints,
            travel_mode=data.get("travel_mode", "car"),
            max_alternatives=int(data.get("max_alternatives", 1)),
        )
        return JsonResponse(route_data)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def get_route_by_booking(request, booking_id):
    from bookings.models import Booking
    from hospitals.models import Hospital
    from ambulance.models import Ambulance

    try:
        booking = Booking.objects.get(id=booking_id)
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Booking not found"}, status=404)
    try:
        amb = Ambulance.objects.get(id=booking.ambulance_id)
    except Ambulance.DoesNotExist:
        return JsonResponse({"error": "Ambulance not found"}, status=404)

    hospital = None
    if booking.destination and booking.destination.strip():
        hospital = Hospital.objects.filter(name__icontains=booking.destination.strip(), is_active=True).first()
    if not hospital:
        hospital = Hospital.objects.filter(is_active=True, status="active").first()
    if not hospital:
        return JsonResponse({"error": "No active hospital found"}, status=404)

    pickup_lat = getattr(booking, "pickup_latitude", None)
    pickup_lng = getattr(booking, "pickup_longitude", None)
    hosp_lat = getattr(hospital, "latitude", None)
    hosp_lng = getattr(hospital, "longitude", None)
    amb_lat = getattr(amb, "latitude", None)
    amb_lng = getattr(amb, "longitude", None)

    try:
        p_lat = float(pickup_lat) if pickup_lat else 28.7371
        p_lng = float(pickup_lng) if pickup_lng else 77.3041
        d_lat = float(hosp_lat) if hosp_lat else 28.5355
        d_lng = float(hosp_lng) if hosp_lng else 77.3910
    except (ValueError, TypeError):
        p_lat, p_lng = 28.7371, 77.3041
        d_lat, d_lng = 28.5355, 77.3910

    origin_lat, origin_lng = p_lat, p_lng
    waypoints = []
    if amb_lat and amb_lng:
        try:
            a_lat, a_lng = float(amb_lat), float(amb_lng)
            if _is_india_coord(a_lat, a_lng):
                origin_lat, origin_lng = a_lat, a_lng
                waypoints = [(p_lat, p_lng)]
        except (ValueError, TypeError):
            pass

    from routing_provider import default_provider
    route_data = default_provider.calculate_route(
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        dest_lat=d_lat,
        dest_lng=d_lng,
        waypoints=waypoints,
        travel_mode="car"
    )

    return JsonResponse({
        "booking_id":       booking_id,
        "ambulance":        amb.ambulance_number,
        "pickup":           booking.pickup_location,
        "hospital":         hospital.name,
        "hospital_address": hospital.address,
        "best_route":       route_data,
        "alternatives":     route_data.get("alternatives", []),
        "total_routes":     1 + len(route_data.get("alternatives", [])),
    })
