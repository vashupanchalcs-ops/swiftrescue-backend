import json
import urllib.request
import urllib.parse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

GOOGLE_API_KEY = "YOUR_GOOGLE_API_KEY_HERE"


def _geocode(address):
    params = {"address": address, "key": GOOGLE_API_KEY}
    url = "https://maps.googleapis.com/maps/api/geocode/json?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=6) as resp:
        data = json.loads(resp.read())
    if data.get("status") == "OK":
        loc = data["results"][0]["geometry"]["location"]
        return f"{loc['lat']},{loc['lng']}"
    return None


def _directions(origin, destination, waypoints=None):
    params = {
        "origin":         origin,
        "destination":    destination,
        "mode":           "driving",
        "departure_time": "now",
        "traffic_model":  "best_guess",
        "alternatives":   "true",
        "key":            GOOGLE_API_KEY,
    }
    if waypoints:
        params["waypoints"] = "optimize:false|" + "|".join(waypoints)
    url = "https://maps.googleapis.com/maps/api/directions/json?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())


def _fmt_secs(secs):
    m = secs // 60
    return f"{m} min" if m < 60 else f"{m//60}h {m%60}min"


def _parse_route(route):
    all_steps = []
    total_dist_m = total_dur_s = total_traf_s = 0
    for leg in route["legs"]:
        total_dist_m += leg["distance"]["value"]
        total_dur_s  += leg["duration"]["value"]
        traf          = leg.get("duration_in_traffic", leg["duration"])
        total_traf_s += traf["value"]
        for s in leg["steps"]:
            all_steps.append({
                "instruction": s.get("html_instructions", ""),
                "distance":    s["distance"]["text"],
                "duration":    s["duration"]["text"],
                "maneuver":    s.get("maneuver", "straight"),
                "start_lat":   s["start_location"]["lat"],
                "start_lng":   s["start_location"]["lng"],
                "end_lat":     s["end_location"]["lat"],
                "end_lng":     s["end_location"]["lng"],
            })
    return {
        "summary":              route.get("summary", ""),
        "distance":             f"{total_dist_m/1000:.1f} km",
        "distance_m":           total_dist_m,
        "duration_normal":      _fmt_secs(total_dur_s),
        "duration_traffic":     _fmt_secs(total_traf_s),
        "duration_traffic_sec": total_traf_s,
        "start_address":        route["legs"][0]["start_address"],
        "end_address":          route["legs"][-1]["end_address"],
        "polyline":             route["overview_polyline"]["points"],
        "steps":                all_steps,
        "bounds": {
            "ne_lat": route["bounds"]["northeast"]["lat"],
            "ne_lng": route["bounds"]["northeast"]["lng"],
            "sw_lat": route["bounds"]["southwest"]["lat"],
            "sw_lng": route["bounds"]["southwest"]["lng"],
        },
    }


@csrf_exempt
def get_route(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        data   = json.loads(request.body)
        pickup = f"{data['pickup_lat']},{data['pickup_lng']}"
        hosp   = f"{data['hospital_lat']},{data['hospital_lng']}"
        amb    = f"{data['ambulance_lat']},{data['ambulance_lng']}" if data.get("ambulance_lat") else None
    except (KeyError, json.JSONDecodeError) as e:
        return JsonResponse({"error": f"Missing: {e}"}, status=400)

    origin, waypoints, destination = (amb, [pickup], hosp) if amb else (pickup, None, hosp)
    try:
        api_data = _directions(origin, destination, waypoints)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=502)
    if api_data.get("status") != "OK":
        return JsonResponse({"error": api_data.get("status"), "detail": api_data.get("error_message","")}, status=400)

    routes = sorted([_parse_route(r) for r in api_data["routes"]], key=lambda r: r["duration_traffic_sec"])
    return JsonResponse({"best_route": routes[0], "alternatives": routes[1:], "total_routes": len(routes)})


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
        return JsonResponse({"error": "Koi active hospital nahi mila"}, status=404)

    amb_latlon = None
    if amb.latitude and amb.longitude:
        try:
            amb_latlon = f"{float(amb.latitude)},{float(amb.longitude)}"
        except (ValueError, TypeError):
            pass

    pickup_latlon = None
    if booking.pickup_location:
        try:
            pickup_latlon = _geocode(booking.pickup_location)
        except Exception:
            pickup_latlon = booking.pickup_location
    if not pickup_latlon:
        return JsonResponse({"error": "Pickup geocode nahi hua"}, status=400)

    try:
        hosp_latlon = f"{float(hospital.latitude)},{float(hospital.longitude)}"
    except (ValueError, TypeError, AttributeError):
        try:
            hosp_latlon = _geocode(f"{hospital.name}, {hospital.address}")
        except Exception:
            return JsonResponse({"error": "Hospital location resolve nahi hua"}, status=400)

    if amb_latlon:
        origin, waypoints, destination = amb_latlon, [pickup_latlon], hosp_latlon
    else:
        origin, waypoints, destination = pickup_latlon, None, hosp_latlon

    try:
        api_data = _directions(origin, destination, waypoints)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=502)
    if api_data.get("status") != "OK":
        return JsonResponse({"error": api_data.get("status"), "detail": api_data.get("error_message","")}, status=400)

    routes = sorted([_parse_route(r) for r in api_data["routes"]], key=lambda r: r["duration_traffic_sec"])
    return JsonResponse({
        "booking_id":       booking_id,
        "ambulance":        amb.ambulance_number,
        "ambulance_gps":    amb_latlon,
        "pickup":           booking.pickup_location,
        "hospital":         hospital.name,
        "hospital_address": hospital.address,
        "best_route":       routes[0],
        "alternatives":     routes[1:],
        "total_routes":     len(routes),
    })