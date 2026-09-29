"""Booking-scoped tracking helpers shared by REST, GPS ingestion and Channels."""
import math
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from ambulance.models import Ambulance, BookingTrackingState, TrackingRoute, UserProfile
from bookings.models import Booking
from hospitals.models import Hospital
from hospitals.models import HospitalStaff


EVENT_TYPES = {
    "location": "AMBULANCE_LOCATION_UPDATED",
    "route": "ROUTE_UPDATED",
    "eta": "ETA_UPDATED",
    "status": "BOOKING_STATUS_CHANGED",
    "pickup": "PICKUP_COMPLETED",
    "hospital": "HOSPITAL_CHANGED",
    "transfer": "AMBULANCE_TRANSFERRED",
}


def haversine_m(a_lat, a_lng, b_lat, b_lng):
    r = 6371000.0
    p1, p2 = math.radians(float(a_lat)), math.radians(float(b_lat))
    dp = math.radians(float(b_lat) - float(a_lat))
    dl = math.radians(float(b_lng) - float(a_lng))
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1, math.sqrt(h)))


def valid_coord(lat, lng):
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return False
    return -90 <= lat <= 90 and -180 <= lng <= 180 and not (lat == 0 and lng == 0)


def acceptable_jump(previous, lat, lng):
    if not previous or not valid_coord(previous[0], previous[1]):
        return True
    try:
        return haversine_m(previous[0], previous[1], lat, lng) <= settings.TRACKING_LOCATION_MAX_JUMP_METERS
    except (TypeError, ValueError):
        return False


def bearing(a_lat, a_lng, b_lat, b_lng):
    p1, p2 = math.radians(float(a_lat)), math.radians(float(b_lat))
    dl = math.radians(float(b_lng) - float(a_lng))
    return (math.degrees(math.atan2(math.sin(dl) * math.cos(p2), math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))) + 360) % 360


def _decode_polyline(encoded):
    index = lat = lng = 0
    points = []
    while index < len(encoded):
        result = shift = 0
        while index < len(encoded):
            byte = ord(encoded[index]) - 63; index += 1; result |= (byte & 0x1f) << shift; shift += 5
            if byte < 0x20: break
        lat += ~(result >> 1) if result & 1 else result >> 1
        result = shift = 0
        while index < len(encoded):
            byte = ord(encoded[index]) - 63; index += 1; result |= (byte & 0x1f) << shift; shift += 5
            if byte < 0x20: break
        lng += ~(result >> 1) if result & 1 else result >> 1
        points.append((lat / 1e5, lng / 1e5))
    return points


def _route_deviation_m(route, lat, lng):
    if not route or not route.encoded_polyline:
        return 0
    points = _decode_polyline(route.encoded_polyline)
    return min((haversine_m(lat, lng, p_lat, p_lng) for p_lat, p_lng in points), default=0)


def _hospital_for(booking):
    if booking.assigned_hospital_id:
        return Hospital.objects.filter(id=booking.assigned_hospital_id).first()
    return None


def _phase(booking):
    if booking.status == "completed":
        return "completed"
    return "to_hospital" if booking.patient_reached else "to_patient"


def snapshot_for_booking(booking_id):
    booking = Booking.objects.filter(id=booking_id).first()
    if not booking:
        return None
    ambulance = Ambulance.objects.filter(id=booking.ambulance_id).first()
    hospital = _hospital_for(booking)
    state, _ = BookingTrackingState.objects.get_or_create(booking_id=booking.id)
    phase = _phase(booking)
    state.phase = phase
    state.ambulance_id = ambulance.id if ambulance else booking.ambulance_id
    state.patient_lat = booking.pickup_latitude
    state.patient_lng = booking.pickup_longitude
    state.hospital_lat = float(hospital.latitude) if hospital and valid_coord(hospital.latitude, hospital.longitude) else None
    state.hospital_lng = float(hospital.longitude) if hospital and valid_coord(hospital.latitude, hospital.longitude) else None
    if ambulance:
        state.ambulance_lat, state.ambulance_lng = ambulance.latitude, ambulance.longitude
    state.save(update_fields=["phase", "ambulance_id", "patient_lat", "patient_lng", "hospital_lat", "hospital_lng", "ambulance_lat", "ambulance_lng", "updated_at"])
    active_route = TrackingRoute.objects.filter(booking_id=booking.id, is_active=True).order_by("-version").first()
    return {
        "booking_id": booking.id,
        "status": booking.status,
        "phase": phase,
        "patient": {"lat": state.patient_lat, "lng": state.patient_lng, "label": booking.pickup_location},
        "ambulance": {"id": state.ambulance_id, "number": getattr(ambulance, "ambulance_number", ""), "lat": state.ambulance_lat, "lng": state.ambulance_lng, "heading": state.ambulance_heading, "driver": getattr(ambulance, "driver", "")},
        "hospital": {"id": booking.assigned_hospital_id, "name": booking.assigned_hospital_name, "lat": state.hospital_lat, "lng": state.hospital_lng},
        "route": route_dict(active_route),
        "last_location_at": state.last_location_at.isoformat() if state.last_location_at else None,
        "sequence": state.sequence,
    }


def route_dict(route):
    if not route:
        return None
    return {
        "route_id": str(route.route_id), "booking_id": route.booking_id, "version": route.version, "phase": route.phase,
        "distance_m": route.distance_m, "duration_s": route.duration_s, "traffic_duration_s": route.traffic_duration_s,
        "traffic_available": route.traffic_duration_s is not None, "encoded_polyline": route.encoded_polyline,
        "provider": route.provider, "updated_at": route.created_at.isoformat(),
    }


def broadcast(booking_id, event_type, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(f"booking_tracking_{booking_id}", {"type": "tracking.event", "event": {"type": event_type, "booking_id": booking_id, "payload": payload, "sent_at": timezone.now().isoformat()}})


def checkpoint_location(booking_id, ambulance, lat, lng, heading=None, speed=0):
    """Validate, broadcast immediately, and checkpoint to PostgreSQL at most every N seconds."""
    state = BookingTrackingState.objects.filter(booking_id=booking_id).first()
    previous = (state.ambulance_lat, state.ambulance_lng) if state and state.ambulance_lat is not None else (ambulance.latitude, ambulance.longitude)
    if not acceptable_jump(previous, lat, lng):
        return {"accepted": False, "reason": "gps_jump_rejected"}
    now = timezone.now()
    inferred = heading
    if inferred is None and previous and valid_coord(previous[0], previous[1]) and haversine_m(previous[0], previous[1], lat, lng) > 2:
        inferred = bearing(previous[0], previous[1], lat, lng)
    payload = {"ambulance_id": ambulance.id, "lat": float(lat), "lng": float(lng), "heading": inferred, "speed_kmh": float(speed or 0), "sequence": (state.sequence + 1 if state else 1), "updated_at": now.isoformat()}
    broadcast(booking_id, EVENT_TYPES["location"], payload)
    should_checkpoint = not state or not state.last_checkpoint_at or now - state.last_checkpoint_at >= timedelta(seconds=settings.TRACKING_LOCATION_CHECKPOINT_SECONDS)
    if should_checkpoint:
        state, _ = BookingTrackingState.objects.get_or_create(booking_id=booking_id)
        state.ambulance_id, state.ambulance_lat, state.ambulance_lng = ambulance.id, float(lat), float(lng)
        state.ambulance_heading, state.last_location_at, state.last_checkpoint_at = inferred, now, now
        state.sequence = (state.sequence or 0) + 1
        state.save(update_fields=["ambulance_id", "ambulance_lat", "ambulance_lng", "ambulance_heading", "last_location_at", "last_checkpoint_at", "sequence", "updated_at"])
        ambulance.latitude, ambulance.longitude, ambulance.speed = float(lat), float(lng), str(speed or 0)
        ambulance.save(update_fields=["latitude", "longitude", "speed", "last_updated"])
    else:
        cache.set(f"tracking:last:{booking_id}", payload, timeout=30)
    if should_checkpoint:
        active = TrackingRoute.objects.filter(booking_id=booking_id, is_active=True).order_by("-version").first()
        deviation = _route_deviation_m(active, lat, lng)
        route_is_stale = bool(active and (now - active.created_at).total_seconds() > 120)
        if (deviation > 300 or route_is_stale) and cache.add(f"tracking:reroute:{booking_id}", "1", timeout=45):
            try:
                from ambulance.route_service import calculate_booking_route
                updated_route = calculate_booking_route(Booking.objects.get(id=booking_id), force=True, reason="deviation" if deviation > 300 else "stale")
                normalized = route_dict(updated_route)
                broadcast(booking_id, EVENT_TYPES["route"], normalized)
                broadcast(booking_id, EVENT_TYPES["eta"], {"distance_m": normalized["distance_m"], "duration_s": normalized["duration_s"], "traffic_duration_s": normalized["traffic_duration_s"], "traffic_available": normalized["traffic_available"]})
            except Exception:
                pass
    return {"accepted": True, "checkpointed": should_checkpoint, "payload": payload}


def is_authorized(booking, role, email="", ambulance_id="", hospital_id="", staff_id=""):
    role, email = (role or "").lower().strip(), (email or "").lower().strip()
    if not booking or role not in {"user", "driver", "hospital", "staff", "admin"}:
        return False
    if role == "user":
        return bool(email and email == (booking.booked_by_email or "").lower())
    if role == "driver":
        return str(booking.ambulance_id) == str(ambulance_id) or email == (getattr(booking, "driver_email", "") or "").lower()
    if role == "hospital":
        return str(booking.assigned_hospital_id or "") == str(hospital_id)
    if role == "staff":
        return HospitalStaff.objects.filter(staff_id__iexact=staff_id, email__iexact=email, is_active=True, hospital_id=booking.assigned_hospital_id).exists()
    return UserProfile.objects.filter(email__iexact=email, role="admin").exists() or (settings.DEBUG and not email)
