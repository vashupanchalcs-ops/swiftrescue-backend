"""Google Routes API adapter with normalized, versioned persistence."""
import json
import urllib.request
import urllib.error

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ambulance.models import Ambulance, BookingTrackingState, TrackingRoute
from ambulance.tracking_service import valid_coord
from hospitals.models import Hospital


def _encode_polyline(points):
    """Encode [lng, lat] GeoJSON coordinates into Google's polyline format."""
    result, last_lat, last_lng = [], 0, 0
    for lng, lat in points:
        for value, previous, axis in ((round(float(lat) * 1e5), last_lat, "lat"), (round(float(lng) * 1e5), last_lng, "lng")):
            delta = int(value - previous)
            if axis == "lat": last_lat = value
            else: last_lng = value
            encoded = ~(delta << 1) if delta < 0 else delta << 1
            while encoded >= 0x20:
                result.append(chr((0x20 | (encoded & 0x1f)) + 63))
                encoded >>= 5
            result.append(chr(encoded + 63))
    return ''.join(result)


def _duration(value):
    if not value:
        return None
    try:
        return int(float(str(value).rstrip("s")))
    except (TypeError, ValueError):
        return None


def _google(origin, destination):
    key = getattr(settings, "GOOGLE_ROUTES_API_KEY", "")
    if not key:
        return None
    body = {
        "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
        "destination": {"location": {"latLng": {"latitude": destination[0], "longitude": destination[1]}}},
        "travelMode": "DRIVE", "routingPreference": "TRAFFIC_AWARE_OPTIMAL", "computeAlternativeRoutes": False,
        "languageCode": "en-US", "units": "METRIC",
    }
    req = urllib.request.Request("https://routes.googleapis.com/directions/v2:computeRoutes", data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "X-Goog-Api-Key": key, "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.staticDuration,routes.polyline.encodedPolyline"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.loads(response.read())
        route = (data.get("routes") or [None])[0]
        if not route:
            raise ValueError("Google Routes returned no route")
        return {"distance_m": int(route.get("distanceMeters") or 0), "duration_s": _duration(route.get("staticDuration")), "traffic_duration_s": _duration(route.get("duration")), "encoded_polyline": ((route.get("polyline") or {}).get("encodedPolyline") or ""), "provider": "google_routes"}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError(f"Google Routes unavailable: {exc}") from exc


def _points_for(booking):
    ambulance = Ambulance.objects.filter(id=booking.ambulance_id).first()
    hospital = Hospital.objects.filter(id=booking.assigned_hospital_id).first() if booking.assigned_hospital_id else None
    patient = (booking.pickup_latitude, booking.pickup_longitude)
    destination = (float(hospital.latitude), float(hospital.longitude)) if hospital and valid_coord(hospital.latitude, hospital.longitude) else None
    current = (ambulance.latitude, ambulance.longitude) if ambulance and valid_coord(ambulance.latitude, ambulance.longitude) else patient
    if not valid_coord(*patient) or not destination or not valid_coord(*current):
        raise ValueError("Tracking coordinates are incomplete; route cannot be calculated")
    return ambulance, current, patient, destination


def calculate_booking_route(booking, force=False, reason=""):
    ambulance, current, patient, destination = _points_for(booking)
    phase = "to_hospital" if booking.patient_reached else "to_patient"
    origin, target = (current, destination) if phase == "to_hospital" else (current, patient)
    latest = TrackingRoute.objects.filter(booking_id=booking.id, phase=phase).order_by("-version").first()
    if latest and not force and (timezone.now() - latest.created_at).total_seconds() < 45:
        return latest
    result = _google(origin, target)
    if result is None:
        # Keep existing OSRM/TomTom fallback usable, but explicitly mark that
        # traffic data is unavailable instead of inventing traffic ETA.
        from routing_provider import default_provider
        legacy = default_provider.calculate_route(origin[0], origin[1], target[0], target[1], travel_mode="car")
        geometry = legacy.get("geometry") or {}
        coordinates = geometry.get("coordinates") or [[origin[1], origin[0]], [target[1], target[0]]]
        result = {"distance_m": int(legacy.get("distance_m") or 0), "duration_s": int(legacy.get("duration_s") or 0), "traffic_duration_s": None, "encoded_polyline": _encode_polyline(coordinates), "provider": legacy.get("provider", "fallback")}
    with transaction.atomic():
        locked_latest = TrackingRoute.objects.select_for_update().filter(booking_id=booking.id, phase=phase).order_by("-version").first()
        TrackingRoute.objects.filter(booking_id=booking.id, is_active=True).update(is_active=False)
        route = TrackingRoute.objects.create(booking_id=booking.id, version=(locked_latest.version + 1 if locked_latest else 1), phase=phase, origin_lat=origin[0], origin_lng=origin[1], destination_lat=target[0], destination_lng=target[1], distance_m=result["distance_m"], duration_s=result["duration_s"] or 0, traffic_duration_s=result.get("traffic_duration_s"), encoded_polyline=result.get("encoded_polyline", ""), provider=result.get("provider", "fallback"))
    return route
