"""Race-safe ambulance and hospital assignment.

The service deliberately does a cheap database shortlist first.  A traffic
route is calculated only for the final ambulance/hospital pair, which keeps
the external routing provider out of the candidate loop.
"""

import math
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from ambulance.models import Ambulance
from hospitals.cache import invalidate_hospital_cache
from hospitals.models import Hospital, HospitalBed, HospitalStaff

from .models import Booking


ACTIVE_BOOKING_STATUSES = ("pending", "confirmed")


@dataclass(frozen=True)
class Candidate:
    row: object
    distance_km: float


class AssignmentError(Exception):
    """A dispatch-safe failure with a user-facing reason."""


def _coordinate(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def haversine_km(lat1, lng1, lat2, lng2):
    values = [_coordinate(value) for value in (lat1, lng1, lat2, lng2)]
    if any(value is None for value in values):
        return None
    lat1, lng1, lat2, lng2 = values
    radius_km = 6371.0088
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0, 1 - a)))


def _bbox(lat, lng, radius_km):
    # A latitude/longitude bounding box is a cheap PostgreSQL pre-filter.
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / max(1.0, 111.0 * math.cos(math.radians(lat)))
    return lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta


def find_nearby_ambulances(pickup_lat, pickup_lng, *, booking_id=None, radius_km=50, limit=8):
    lat = _coordinate(pickup_lat)
    lng = _coordinate(pickup_lng)
    if lat is None or lng is None:
        return []
    min_lat, max_lat, min_lng, max_lng = _bbox(lat, lng, radius_km)
    active_booking = Booking.objects.filter(
        ambulance_id=OuterRef("pk"), status__in=ACTIVE_BOOKING_STATUSES
    )
    if booking_id:
        active_booking = active_booking.exclude(id=booking_id)
    rows = (
        Ambulance.objects.filter(
            status="available",
            latitude__isnull=False,
            longitude__isnull=False,
            latitude__gte=min_lat,
            latitude__lte=max_lat,
            longitude__gte=min_lng,
            longitude__lte=max_lng,
        )
        .annotate(has_active_booking=Exists(active_booking))
        .filter(has_active_booking=False)
        .only("id", "ambulance_number", "driver", "driver_contact", "driver_email", "latitude", "longitude", "status")
    )
    candidates = []
    for row in rows:
        distance = haversine_km(lat, lng, row.latitude, row.longitude)
        if distance is not None and distance <= radius_km:
            candidates.append(Candidate(row, distance))
    return sorted(candidates, key=lambda item: item.distance_km)[:limit]


def find_suitable_hospitals(
    pickup_lat,
    pickup_lng,
    *,
    icu_required=False,
    required_specialization="",
    radius_km=100,
    limit=8,
):
    lat = _coordinate(pickup_lat)
    lng = _coordinate(pickup_lng)
    if lat is None or lng is None:
        return []
    staff_available = HospitalStaff.objects.filter(
        hospital_id=OuterRef("pk"), is_active=True, is_busy=False,
    ).filter(role__in=("doctor", "nurse", "coordinator"))
    capacity_field = "available_icu_beds__gt" if icu_required else "available_beds__gt"
    filters = {
        "is_active": True,
        "status__in": ("active", "critical"),
        capacity_field: 0,
    }
    hospitals = (
        Hospital.objects.filter(**filters)
        .filter(Q(emergency_services=True) | Q(status="critical"))
        .annotate(has_available_staff=Exists(staff_available))
        .filter(has_available_staff=True)
        .only(
            "id", "name", "address", "contact_number", "email", "latitude", "longitude",
            "available_beds", "available_icu_beds", "emergency_services", "specializations", "status",
        )
    )
    required = str(required_specialization or "").strip().lower()
    candidates = []
    for hospital in hospitals:
        if required and required not in (hospital.specializations or "").lower():
            continue
        distance = haversine_km(lat, lng, hospital.latitude, hospital.longitude)
        if distance is not None and distance <= radius_km:
            candidates.append(Candidate(hospital, distance))
    return sorted(candidates, key=lambda item: item.distance_km)[:limit]


def _route_metrics(ambulance, pickup_lat, pickup_lng, hospital):
    """Return ETA/route metadata without making assignment depend on the API."""
    origin_lat = _coordinate(ambulance.latitude)
    origin_lng = _coordinate(ambulance.longitude)
    pickup_lat = _coordinate(pickup_lat)
    pickup_lng = _coordinate(pickup_lng)
    dest_lat = _coordinate(hospital.latitude)
    dest_lng = _coordinate(hospital.longitude)
    if None in (origin_lat, origin_lng, pickup_lat, pickup_lng, dest_lat, dest_lng):
        return None
    try:
        from routing_provider import default_provider

        route = default_provider.calculate_route(
            origin_lat=origin_lat,
            origin_lng=origin_lng,
            dest_lat=dest_lat,
            dest_lng=dest_lng,
            waypoints=[(pickup_lat, pickup_lng)],
            travel_mode="car",
            max_alternatives=0,
        )
        return {
            "distance_km": round(float(route.get("distance_m", 0)) / 1000, 2),
            "eta_seconds": max(0, int(route.get("duration_s", 0) or 0)),
            "provider": str(route.get("provider", "fallback"))[:40],
        }
    except Exception:
        distance = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng) or 0
        return {
            "distance_km": round(distance, 2),
            "eta_seconds": max(60, int(distance * 60)),
            "provider": "haversine_fallback",
        }


def assign_booking(booking, *, preferred_ambulance_id=None, preferred_hospital_id=None, icu_required=False, required_specialization=""):
    """Assign one available ambulance and capable hospital atomically."""
    with transaction.atomic():
        locked_booking = Booking.objects.select_for_update().get(id=booking.id)
        pickup_lat = locked_booking.pickup_latitude
        pickup_lng = locked_booking.pickup_longitude
        if _coordinate(pickup_lat) is None or _coordinate(pickup_lng) is None:
            raise AssignmentError("Pickup latitude and longitude are required for automatic assignment")

        ambulances = find_nearby_ambulances(pickup_lat, pickup_lng, booking_id=locked_booking.id)
        if preferred_ambulance_id:
            ambulances = [candidate for candidate in ambulances if candidate.row.id == int(preferred_ambulance_id)]
        if not ambulances:
            raise AssignmentError("No available ambulance with a recent location was found nearby")

        # Lock and re-check status after the shortlist to prevent double booking.
        ambulance_ids = [candidate.row.id for candidate in ambulances]
        locked_rows = list(
            Ambulance.objects.select_for_update()
            .filter(id__in=ambulance_ids, status="available")
        )
        locked_by_id = {row.id: row for row in locked_rows}
        locked_ambulance = next((locked_by_id.get(candidate.row.id) for candidate in ambulances if candidate.row.id in locked_by_id), None)
        if not locked_ambulance:
            raise AssignmentError("The nearby ambulances were assigned by another request; retry assignment")

        hospitals = find_suitable_hospitals(
            pickup_lat,
            pickup_lng,
            icu_required=icu_required,
            required_specialization=required_specialization,
        )
        if preferred_hospital_id:
            hospitals = [candidate for candidate in hospitals if candidate.row.id == int(preferred_hospital_id)]
        if not hospitals:
            raise AssignmentError("No nearby hospital has the required bed capacity and on-duty staff")

        locked_hospital_rows = list(
            Hospital.objects.select_for_update()
            .filter(id__in=[candidate.row.id for candidate in hospitals], is_active=True)
        )
        locked_hospital_by_id = {row.id: row for row in locked_hospital_rows}
        locked_hospital = next((locked_hospital_by_id.get(candidate.row.id) for candidate in hospitals if candidate.row.id in locked_hospital_by_id), None)
        if not locked_hospital:
            raise AssignmentError("The selected hospital is no longer available")

        # If a real bed inventory exists, re-check the exact type under lock.
        bed_type = "icu" if icu_required else "general"
        bed = (
            HospitalBed.objects.select_for_update()
            .filter(hospital=locked_hospital, bed_type=bed_type, status="available")
            .order_by("id")
            .first()
        )
        if HospitalBed.objects.filter(hospital=locked_hospital, bed_type=bed_type).exists() and not bed:
            raise AssignmentError("The selected hospital's required beds were just reserved")

        old_ambulance_id = locked_booking.ambulance_id
        locked_booking.ambulance_id = locked_ambulance.id
        locked_booking.ambulance_number = locked_ambulance.ambulance_number or ""
        locked_booking.driver = locked_ambulance.driver or ""
        locked_booking.driver_contact = locked_ambulance.driver_contact or ""
        locked_booking.assigned_hospital_id = locked_hospital.id
        locked_booking.assigned_hospital_name = locked_hospital.name or ""
        locked_booking.assigned_hospital_address = locked_hospital.address or ""
        locked_booking.assigned_hospital_contact = locked_hospital.contact_number or ""
        locked_booking.assigned_hospital_email = locked_hospital.email or ""
        locked_booking.hospital_assigned_at = timezone.now()
        locked_booking.hospital_response = "pending"
        locked_booking.icu_required = bool(icu_required)
        locked_booking.icu_requested_at = timezone.now() if icu_required else locked_booking.icu_requested_at
        metrics = _route_metrics(locked_ambulance, pickup_lat, pickup_lng, locked_hospital)
        if metrics:
            locked_booking.assignment_distance_km = metrics["distance_km"]
            locked_booking.assignment_eta_seconds = metrics["eta_seconds"]
            locked_booking.assignment_route_provider = metrics["provider"]
        locked_booking.assignment_updated_at = timezone.now()
        locked_booking.save(update_fields=[
            "ambulance_id", "ambulance_number", "driver", "driver_contact",
            "assigned_hospital_id", "assigned_hospital_name", "assigned_hospital_address",
            "assigned_hospital_contact", "assigned_hospital_email", "hospital_assigned_at",
            "hospital_response", "icu_required", "icu_requested_at", "assignment_distance_km",
            "assignment_eta_seconds", "assignment_route_provider", "assignment_updated_at",
        ])

        # Reserve the ambulance in the same transaction. It becomes en_route
        # only when the existing dispatch workflow sends it to the driver.
        locked_ambulance.status = "busy"
        locked_ambulance.save(update_fields=["status"])
        if old_ambulance_id and old_ambulance_id != locked_ambulance.id:
            Ambulance.objects.filter(id=old_ambulance_id, status__in=["busy", "en_route"]).update(status="available")

        if bed:
            bed.status = "reserved"
            bed.assigned_booking_id = locked_booking.id
            bed.patient_name = locked_booking.patient_name or locked_booking.booked_by or "Emergency Intake"
            bed.admission_time = timezone.now()
            bed.save(update_fields=["status", "assigned_booking_id", "patient_name", "admission_time", "updated_at"])
            if icu_required:
                locked_hospital.available_icu_beds = max(0, int(locked_hospital.available_icu_beds or 0) - 1)
            else:
                locked_hospital.available_beds = max(0, int(locked_hospital.available_beds or 0) - 1)
            locked_hospital.last_capacity_updated = timezone.now()
            locked_hospital.save(update_fields=["available_beds", "available_icu_beds", "last_capacity_updated", "updated_at"])

        invalidate_hospital_cache(locked_hospital.id)
        return locked_booking, {
            "ambulance_distance_km": locked_booking.assignment_distance_km,
            "eta_seconds": locked_booking.assignment_eta_seconds,
            "route_provider": locked_booking.assignment_route_provider,
            "bed_id": bed.id if bed else None,
        }
