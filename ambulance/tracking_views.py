"""
ambulance/tracking_views.py
Real-time GPS tracking, route suggestion, and driver ping APIs
"""
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from ambulance.models import Ambulance, DriverLocation, SuggestedRoute
import json
import urllib.request
import urllib.parse


def _route_dict(r):
    if not r:
        return None
    return {
        "id":              r.id,
        "ambulance_id":    r.ambulance_id,
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
    data   = json.loads(request.body)
    email  = data.get("driver_email", "")
    amb_id = data.get("ambulance_id")
    lat    = data.get("latitude")
    lng    = data.get("longitude")
    speed  = data.get("speed", 0)
    if not all([email, amb_id, lat, lng]):
        return JsonResponse({"error": "driver_email, ambulance_id, latitude, longitude required"}, status=400)
    try:
        amb = Ambulance.objects.get(id=amb_id)
    except Ambulance.DoesNotExist:
        return JsonResponse({"error": "Ambulance not found"}, status=404)
    amb.latitude  = lat
    amb.longitude = lng
    amb.speed     = str(speed)
    amb.save(update_fields=["latitude", "longitude", "speed", "last_updated"])
    DriverLocation.objects.create(ambulance=amb, driver_email=email, latitude=lat, longitude=lng, speed=speed)
    pending = SuggestedRoute.objects.filter(ambulance=amb, status__in=["pending", "accepted"]).order_by("-created_at").first()
    return JsonResponse({"status": "ok", "timestamp": timezone.now().isoformat(), "pending_route": _route_dict(pending)})


@csrf_exempt
def all_live_locations(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    ambulances = Ambulance.objects.exclude(latitude=None).exclude(longitude=None)
    result = []
    for a in ambulances:
        active = SuggestedRoute.objects.filter(ambulance=a, status__in=["pending", "accepted"]).order_by("-created_at").first()
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
        pickup_location=data.get("pickup_location", ""),
        destination=data.get("destination", ""),
        polyline=data.get("polyline", ""),
        distance_km=data.get("distance_km", ""),
        duration=data.get("duration", ""),
        status="pending",
    )
    # Store coords if provided (for driver map rendering)
    if data.get("pickup_lat"):
        route.pickup_lat = data.get("pickup_lat")
        route.pickup_lng = data.get("pickup_lng")
        route.dest_lat   = data.get("dest_lat")
        route.dest_lng   = data.get("dest_lng")
        try: route.save(update_fields=["pickup_lat","pickup_lng","dest_lat","dest_lng"])
        except: pass
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
    email = request.GET.get("driver_email", "")
    if not email:
        return JsonResponse({"error": "driver_email required"}, status=400)
    try:
        amb = Ambulance.objects.get(driver_email=email)
    except Ambulance.DoesNotExist:
        return JsonResponse({"error": "No ambulance found"}, status=404)
    route = SuggestedRoute.objects.filter(ambulance=amb, status__in=["pending", "accepted"]).order_by("-created_at").first()
    return JsonResponse(_route_dict(route) if route else {})


@csrf_exempt
def get_traffic_route(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    data    = json.loads(request.body)
    api_key = data.get("api_key", "")
    if not api_key:
        return JsonResponse({"error": "api_key required"}, status=400)
    origin      = f"{data['origin_lat']},{data['origin_lng']}"
    pickup      = f"{data['pickup_lat']},{data['pickup_lng']}"
    destination = f"{data['dest_lat']},{data['dest_lng']}"
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
    routes.sort(key=lambda x: x["duration_sec"])
    return JsonResponse({"routes": routes, "best": routes[0], "total": len(routes)})