from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.contrib.auth.hashers import make_password, check_password
from django.core import signing
from decimal import Decimal, InvalidOperation
from ambulance.models import Ambulance
from hospitals.models import Hospital, HospitalStaff, HospitalBed
from bookings.models import Booking
from ambulance_tracker.pagination import parse_list_options
from .cache import cache_get, cache_set, dashboard_key, invalidate_hospital_cache
import json


def hospital_to_dict(h):
    staff_qs = h.staff.all() if hasattr(h, "staff") and h.id else HospitalStaff.objects.filter(hospital=h)
    doctors = staff_qs.filter(role="doctor")
    nurses = staff_qs.filter(role="nurse")

    t_beds = max(0, h.total_beds or 0)
    a_beds = max(0, h.available_beds or 0)
    b_beds = max(0, t_beds - a_beds)

    t_icu = max(0, h.icu_beds or 0)
    a_icu = max(0, h.available_icu_beds or 0)
    b_icu = max(0, t_icu - a_icu)

    s_total = staff_qs.count()
    s_active = staff_qs.filter(is_active=True).count()
    s_deactive = staff_qs.filter(is_active=False).count()

    doc_count = doctors.count()
    doc_active = doctors.filter(is_active=True).count()

    nurse_count = nurses.count()
    nurse_active = nurses.filter(is_active=True).count()



    return {
        "id":                 h.id,
        "name":               h.name,
        "hospital_contract_id": h.hospital_contract_id,
        "registration_number": h.registration_number,
        "address":            h.address,
        "city":               h.city,
        "state":              h.state,
        "pincode":            h.pincode,
        "latitude":           h.latitude,
        "longitude":          h.longitude,
        "contact_number":     h.contact_number,
        "emergency_contact":  h.emergency_contact,
        "email":              h.email,
        "website":            h.website,
        "contact_person_name": h.contact_person_name,
        "contact_person_role": h.contact_person_role,
        "hospital_type":      h.hospital_type,
        "total_beds":         t_beds,
        "available_beds":     a_beds,
        "booked_beds":        b_beds,
        "emergency_beds":     h.emergency_beds,
        "icu_beds":           t_icu,
        "available_icu_beds": a_icu,
        "booked_icu_beds":    b_icu,
        "oxygen_beds":        h.oxygen_beds,
        "ventilators_total":  h.ventilators_total,
        "ventilators_available": h.ventilators_available,
        "ambulance_bays":     h.ambulance_bays,
        "specializations":    h.specializations,
        "facilities":         h.facilities,
        "insurance_partners": h.insurance_partners,
        "notes":              h.notes,
        "emergency_services": h.emergency_services,
        "is_24x7":            h.is_24x7,
        "has_blood_bank":     h.has_blood_bank,
        "status":             h.status,
        "is_active":          h.is_active,
        "doctors_count":      doc_count,
        "doctors_active":     doc_active,
        "nurses_count":       nurse_count,
        "nurses_active":      nurse_active,
        "staff_total_count":  s_total,
        "staff_active_count": s_active,
        "staff_deactive_count": s_deactive,
        "last_capacity_updated": h.last_capacity_updated.isoformat() if h.last_capacity_updated else None,
        "created_at":         h.created_at.isoformat(),
        "updated_at":         h.updated_at.isoformat(),
    }


def staff_to_dict(member):
    return {
        "id": member.id,
        "full_name": member.full_name,
        "role": member.role,
        "staff_id": getattr(member, "staff_id", ""),
        "specialization": member.specialization,
        "registration_number": member.registration_number,
        "contact_number": member.contact_number,
        "email": member.email,
        "years_experience": member.years_experience,
        "photo_data": member.photo_data,
        "banner_data": member.banner_data,
        "shift": member.shift,
        "is_on_call": member.is_on_call,
        "is_active": member.is_active,
        "is_busy": getattr(member, "is_busy", False),
        "assigned_booking_id": getattr(member, "assigned_booking_id", None),
        "joined_on": member.joined_on.isoformat() if member.joined_on else None,
        "notes": member.notes,
    }




def bed_to_dict(bed):
    return {
        "id": bed.id,
        "hospital_id": bed.hospital_id,
        "bed_number": bed.bed_number,
        "bed_type": bed.bed_type,
        "status": bed.status,
        "wing": bed.wing,
        "assigned_booking_id": bed.assigned_booking_id,
        "patient_name": bed.patient_name,
        "patient_age": bed.patient_age,
        "patient_gender": bed.patient_gender,
        "blood_group": bed.blood_group,
        "patient_phone": bed.patient_phone,
        "emergency_contact": bed.emergency_contact,
        "medical_condition": bed.medical_condition,
        "vitals_summary": bed.vitals_summary,
        "attending_doctor": bed.attending_doctor,
        "assigned_staff_json": bed.assigned_staff_json,
        "admission_time": bed.admission_time.isoformat() if bed.admission_time else None,
        "last_status_update": bed.last_status_update.isoformat() if bed.last_status_update else None,
        "created_at": bed.created_at.isoformat() if bed.created_at else None,
    }


def sync_hospital_bed_counts(hospital_id):
    """Keep hospital summary counters derived from the persisted bed rows."""
    beds = HospitalBed.objects.filter(hospital_id=hospital_id)
    total = beds.count()
    available = beds.filter(status="available").count()
    icu_total = beds.filter(bed_type="icu").count()
    icu_available = beds.filter(bed_type="icu", status="available").count()
    Hospital.objects.filter(id=hospital_id).update(
        total_beds=total,
        available_beds=available,
        icu_beds=icu_total,
        available_icu_beds=icu_available,
        last_capacity_updated=timezone.now(),
    )


def ensure_hospital_beds(hospital):
    """Make the persisted bed inventory cover the hospital's configured capacity.

    Older production data can contain only the first batch of HospitalBed rows
    while the Hospital summary already has the full capacity.  Returning that
    partial batch makes the home dashboard and the bed console disagree. Add
    only missing rows and repair stale unassigned reservations; never rewrite a
    bed that is linked to a real booking. New beds start available so a fresh
    hospital inventory is usable immediately.
    """
    def as_non_negative_int(value):
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    with transaction.atomic():
        beds = list(HospitalBed.objects.select_for_update().filter(hospital_id=hospital.id))
        configured_total = as_non_negative_int(hospital.total_beds)
        configured_icu = as_non_negative_int(hospital.icu_beds)
        protected = [bed for bed in beds if bed.assigned_booking_id is not None]
        protected_icu = sum(bed.bed_type == "icu" for bed in protected)

        # The hospital's edited total is authoritative. Never delete a bed
        # linked to a booking, but remove excess free rows when the hospital
        # reduces capacity; the old max(current_total, configured_total)
        # logic was the reason edits reverted on the next fetch.
        target_total = max(1, configured_total, len(protected))
        target_icu = max(protected_icu, min(target_total, configured_icu))

        if len(beds) > target_total:
            removable = [bed for bed in beds if bed.assigned_booking_id is None]
            removable.sort(key=lambda bed: (bed.status != "available", -bed.id))
            for bed in removable[: len(beds) - target_total]:
                bed.delete()
            beds = list(HospitalBed.objects.select_for_update().filter(hospital_id=hospital.id))

        # If ICU capacity was reduced, reclassify only free ICU beds. Assigned
        # ICU beds remain protected and force the minimum ICU capacity above.
        free_icu = [bed for bed in beds if bed.bed_type == "icu" and bed.assigned_booking_id is None]
        current_icu = sum(bed.bed_type == "icu" for bed in beds)
        for bed in free_icu[: max(0, current_icu - target_icu)]:
            bed.bed_type = "general"
            bed.wing = "General Ward"
            bed.last_status_update = timezone.now()
            bed.save(update_fields=["bed_type", "wing", "last_status_update", "updated_at"])
        beds = list(HospitalBed.objects.select_for_update().filter(hospital_id=hospital.id))

        current_icu = sum(bed.bed_type == "icu" for bed in beds)
        total_to_add = max(0, target_total - len(beds))
        icu_to_add = min(total_to_add, max(0, target_icu - current_icu))
        general_to_add = total_to_add - icu_to_add
        used_numbers = {str(bed.bed_number or "").strip().upper() for bed in beds}

        def next_bed_number(prefix):
            index = 1
            while f"{prefix}-{index:03d}" in used_numbers:
                index += 1
            number = f"{prefix}-{index:03d}"
            used_numbers.add(number)
            return number

        # Newly created beds are always available. Reservation happens only
        # through an explicit booking/assignment action or capacity reconcile.
        for _ in range(icu_to_add):
            HospitalBed.objects.create(
                hospital_id=hospital.id,
                bed_number=next_bed_number("ICU"),
                bed_type="icu",
                status="available",
                wing="ICU",
            )
        for _ in range(general_to_add):
            HospitalBed.objects.create(
                hospital_id=hospital.id,
                bed_number=next_bed_number("G"),
                bed_type="general",
                status="available",
                wing="General Ward",
            )

        sync_hospital_bed_counts(hospital.id)

    hospital.refresh_from_db()
    return list(HospitalBed.objects.filter(hospital_id=hospital.id))


def reconcile_hospital_bed_availability(hospital):
    """Apply the hospital's edited capacity to unassigned persisted beds.

    Assigned/occupied beds are never touched. Only free rows can move between
    available and reserved, which keeps the summary counters and bed console
    consistent after a resource edit.
    """
    def as_non_negative_int(value):
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    with transaction.atomic():
        beds = list(HospitalBed.objects.select_for_update().filter(hospital_id=hospital.id))
        target_available = min(len(beds), as_non_negative_int(hospital.available_beds))
        target_icu = min(len(beds), as_non_negative_int(hospital.icu_beds))
        target_icu_available = min(target_icu, as_non_negative_int(hospital.available_icu_beds))
        target_general_available = max(0, target_available - target_icu_available)

        for bed_type, desired_available in (
            ("icu", target_icu_available),
            ("general", target_general_available),
        ):
            free_beds = [
                bed for bed in beds
                if bed.bed_type == bed_type
                and bed.assigned_booking_id is None
                and bed.status in {"available", "reserved"}
            ]
            for index, bed in enumerate(free_beds):
                next_status = "available" if index < desired_available else "reserved"
                if bed.status != next_status:
                    bed.status = next_status
                    bed.last_status_update = timezone.now()
                    bed.save(update_fields=["status", "last_status_update"])

        sync_hospital_bed_counts(hospital.id)


@csrf_exempt
def hospital_beds(request, hospital_id):
    """GET the complete persisted bed inventory. PATCH is handled separately."""
    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except Hospital.DoesNotExist:
        return JsonResponse({"error": "Hospital not found"}, status=404)

    if request.method == "GET":
        beds = ensure_hospital_beds(hospital)
        return JsonResponse([bed_to_dict(b) for b in beds], safe=False)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
@transaction.atomic
def hospital_bed_detail(request, bed_id):
    """PATCH a single bed's fields."""
    try:
        bed = HospitalBed.objects.select_for_update().get(id=bed_id)
    except HospitalBed.DoesNotExist:
        return JsonResponse({"error": "Bed not found"}, status=404)

    if request.method == "PATCH":
        import json as _json
        try:
            data = _json.loads(request.body)
        except Exception:
            data = {}
        allowed = [
            "status", "wing", "assigned_booking_id", "patient_name", "patient_age",
            "patient_gender", "blood_group", "patient_phone", "emergency_contact",
            "medical_condition", "vitals_summary", "attending_doctor",
            "assigned_staff_json", "admission_time"
        ]
        for field in allowed:
            if field in data:
                value = data[field]
                if field == "admission_time" and isinstance(value, str):
                    value = parse_datetime(value)
                    if value is None:
                        return JsonResponse({"error": "admission_time must be a valid ISO datetime"}, status=400)
                setattr(bed, field, value)
        bed.last_status_update = timezone.now()
        bed.save()
        sync_hospital_bed_counts(bed.hospital_id)
        return JsonResponse(bed_to_dict(bed))

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
@transaction.atomic
def assign_bed_to_booking(request, hospital_id):
    """POST: assign a specific or first available bed to a booking."""
    import json as _json
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = _json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    booking_id = data.get("booking_id")
    if not booking_id:
        return JsonResponse({"error": "booking_id required"}, status=400)

    try:
        booking = Booking.objects.select_for_update().get(id=booking_id)
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Booking not found"}, status=404)

    bed_id = data.get("bed_id")
    bed = None
    if bed_id:
        bed = HospitalBed.objects.select_for_update().filter(id=bed_id, hospital_id=hospital_id).first()
        if not bed:
            return JsonResponse({"error": "Selected bed does not belong to this hospital"}, status=400)
        if bed.assigned_booking_id not in (None, booking.id) and bed.status != "available":
            return JsonResponse({"error": "Selected bed is already assigned"}, status=409)
    if not bed:
        bed_type_pref = str(data.get("bed_type", "general")).lower()
        bed = HospitalBed.objects.select_for_update().filter(hospital_id=hospital_id, bed_type=bed_type_pref, status="available").first()
    if not bed:
        # Fallback to any available bed in hospital
        bed = HospitalBed.objects.select_for_update().filter(hospital_id=hospital_id, status="available").first()
    if not bed:
        return JsonResponse({"error": "No available bed found in this hospital"}, status=409)

    # If this booking already held another bed (e.g. switching to ICU or different bed), free it
    if booking.assigned_bed_id and booking.assigned_bed_id != bed.id:
        old_bed = HospitalBed.objects.select_for_update().filter(
            id=booking.assigned_bed_id,
            hospital_id=hospital_id,
        ).first()
        if old_bed:
            old_bed.status = "available"
            old_bed.assigned_booking_id = None
            old_bed.patient_name = ""
            old_bed.patient_age = ""
            old_bed.patient_gender = ""
            old_bed.blood_group = ""
            old_bed.patient_phone = ""
            old_bed.emergency_contact = ""
            old_bed.medical_condition = ""
            old_bed.vitals_summary = ""
            old_bed.attending_doctor = ""
            old_bed.assigned_staff_json = "[]"
            old_bed.admission_time = None
            old_bed.save()

    # Assign target bed
    bed.status = "reserved"
    bed.assigned_booking_id = booking.id
    bed.patient_name = booking.patient_name or booking.booked_by or "Emergency Intake"
    bed.patient_age = booking.patient_age
    bed.patient_gender = booking.patient_gender
    bed.patient_phone = booking.patient_contact_number
    bed.medical_condition = booking.patient_condition or ("Critical Care Required" if bed.bed_type == "icu" else "General Inpatient Care")
    bed.vitals_summary = booking.vitals_summary
    bed.attending_doctor = booking.assigned_doctor_names
    bed.assigned_staff_json = booking.assigned_doctors_json or "[]"
    bed.admission_time = timezone.now()
    bed.last_status_update = timezone.now()
    bed.save()
    sync_hospital_bed_counts(hospital_id)

    # Update booking
    booking.assigned_bed_id = bed.id
    booking.assigned_bed_number = bed.bed_number
    booking.assigned_bed_type = bed.bed_type
    booking.save()

    return JsonResponse({"bed": bed_to_dict(bed), "booking_id": booking_id})


@csrf_exempt
@transaction.atomic
def switch_to_icu_bed(request, hospital_id):
    """POST: switch patient from general bed to available ICU bed."""
    import json as _json
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = _json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    booking_id = data.get("booking_id")
    try:
        booking = Booking.objects.select_for_update().get(id=booking_id)
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Booking not found"}, status=404)

    # Get current general bed
    current_bed = HospitalBed.objects.select_for_update().filter(
        id=booking.assigned_bed_id,
        hospital_id=hospital_id,
    ).first() if booking.assigned_bed_id else None

    # Find available ICU bed
    icu_bed = HospitalBed.objects.select_for_update().filter(hospital_id=hospital_id, bed_type="icu", status="available").first()
    if not icu_bed:
        return JsonResponse({"error": "No available ICU beds"}, status=409)

    # Copy patient info to ICU bed
    if current_bed:
        icu_bed.patient_name = current_bed.patient_name
        icu_bed.patient_age = current_bed.patient_age
        icu_bed.patient_gender = current_bed.patient_gender
        icu_bed.blood_group = current_bed.blood_group
        icu_bed.patient_phone = current_bed.patient_phone
        icu_bed.emergency_contact = current_bed.emergency_contact
        icu_bed.medical_condition = current_bed.medical_condition
        icu_bed.vitals_summary = current_bed.vitals_summary
        icu_bed.attending_doctor = current_bed.attending_doctor
        icu_bed.assigned_staff_json = current_bed.assigned_staff_json
        icu_bed.admission_time = current_bed.admission_time

        # Free the general bed
        current_bed.status = "available"
        current_bed.assigned_booking_id = None
        current_bed.patient_name = ""
        current_bed.patient_age = ""
        current_bed.patient_gender = ""
        current_bed.blood_group = ""
        current_bed.patient_phone = ""
        current_bed.emergency_contact = ""
        current_bed.medical_condition = ""
        current_bed.vitals_summary = ""
        current_bed.attending_doctor = ""
        current_bed.assigned_staff_json = "[]"
        current_bed.admission_time = None
        current_bed.save()

    icu_bed.status = "occupied"
    icu_bed.assigned_booking_id = booking_id
    icu_bed.save()

    # Update booking
    booking.assigned_bed_id = icu_bed.id
    booking.assigned_bed_number = icu_bed.bed_number
    booking.assigned_bed_type = icu_bed.bed_type
    booking.save()

    return JsonResponse({"icu_bed": bed_to_dict(icu_bed), "freed_bed": bed_to_dict(current_bed) if current_bed else None})


STAFF_MUTABLE_FIELDS = (
    "full_name", "role", "staff_id", "specialization", "registration_number", "contact_number",
    "email", "years_experience", "photo_data", "banner_data", "shift", "is_on_call",
    "is_active", "notes",
)


HOSPITAL_MUTABLE_FIELDS = (
    "name", "hospital_contract_id", "registration_number", "address", "city", "state", "pincode",
    "latitude", "longitude", "contact_number", "emergency_contact", "email", "website",
    "contact_person_name", "contact_person_role", "hospital_type", "total_beds", "available_beds",
    "emergency_beds", "icu_beds", "available_icu_beds", "oxygen_beds", "ventilators_total",
    "ventilators_available", "ambulance_bays", "specializations", "facilities", "insurance_partners",
    "notes", "emergency_services", "is_24x7", "has_blood_bank", "status", "is_active",
)
CAPACITY_FIELDS = {
    "total_beds", "available_beds", "emergency_beds", "icu_beds", "available_icu_beds",
    "oxygen_beds", "ventilators_total", "ventilators_available", "ambulance_bays",
}


def apply_hospital_payload(hospital, data):
    # Handle key aliases from frontend resource form cleanly without overwriting Total ICU beds
    if "available_ventilators" in data and "ventilators_available" not in data:
        data["ventilators_available"] = data["available_ventilators"]
    if "ventilators_available" in data and "available_ventilators" not in data:
        data["available_ventilators"] = data["ventilators_available"]

    # If booked_beds is explicitly updated by frontend:
    if "booked_beds" in data:
        try:
            b_beds = max(0, int(data["booked_beds"]))
            t_beds = int(data.get("total_beds", hospital.total_beds or 40))
            data["available_beds"] = max(0, t_beds - b_beds)
        except (ValueError, TypeError):
            pass

    for field in HOSPITAL_MUTABLE_FIELDS:
        if field in data:
            setattr(hospital, field, data[field])
    if CAPACITY_FIELDS.intersection(data):
        hospital.last_capacity_updated = timezone.now()


def hospital_by_email(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    email = str(request.GET.get("email", "")).strip().lower()
    if not email or "@" not in email:
        return JsonResponse({"error": "A valid email is required"}, status=400)

    hospital = Hospital.objects.filter(email__iexact=email, is_active=True).first()
    if not hospital:
        return JsonResponse({"exists": False, "error": "Hospital profile not found for this email"}, status=404)

    data = hospital_to_dict(hospital)
    data.update({"exists": True, "hospital_id": hospital.id})
    return JsonResponse(data)


def hospital_dashboard(request, id):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)

    try:
        hospital = Hospital.objects.get(id=id, is_active=True)
    except Hospital.DoesNotExist:
        return JsonResponse({"error": "Hospital not found"}, status=404)

    cached = cache_get(dashboard_key(hospital.id))
    if cached is not None:
        return JsonResponse(cached)

    # Keep the dashboard counters and the bed console on the same persisted
    # inventory even when an older deployment created only partial bed rows.
    ensure_hospital_beds(hospital)

    # Ensure hospital has valid real-world coordinates for accurate routing & ETA
    h_lat = str(hospital.latitude or "").strip()
    h_lng = str(hospital.longitude or "").strip()
    if not h_lat or not h_lng or h_lat in ["56", "0", "None"] or not ("28" in h_lat or "27" in h_lat or "29" in h_lat):
        hospital.latitude = "28.47314"
        hospital.longitude = "77.48308"
        if not hospital.address or hospital.address == "delhi":
            hospital.address = "Plot No. 32, 34, Knowledge Park III, Greater Noida, Uttar Pradesh 201306"
        hospital.save(update_fields=["latitude", "longitude", "address"])

    # New assignments use the immutable hospital id. Email/name fallbacks keep
    # historical bookings visible after profile or schema changes.
    hospital_filter = Q(assigned_hospital_id=hospital.id)
    if hospital.email:
        hospital_filter |= Q(assigned_hospital_email__iexact=hospital.email)
    if hospital.name:
        hospital_filter |= Q(assigned_hospital_name__iexact=hospital.name) | Q(destination__iexact=hospital.name)

    # New assignments use the immutable hospital id. The destination fallback keeps
    # historical bookings visible after the production schema upgrade.
    bookings = (
        Booking.objects.filter(hospital_filter)
        .filter(
            Q(status__in=["confirmed", "pending"])
            | Q(report_sent_to_hospital=True)
            | Q(report_submitted_at__isnull=False)
        )
        .order_by("-created_at")[:100]
    )
    all_staff = HospitalStaff.objects.filter(hospital=hospital)
    active_staff = all_staff.filter(is_active=True)
    staff_data = [staff_to_dict(member) for member in all_staff]
    ambulance_ids = [booking.ambulance_id for booking in bookings if booking.ambulance_id]
    ambulance_map = {amb.id: amb for amb in Ambulance.objects.filter(id__in=ambulance_ids)}
    queue = [
        {
            "booking_id": booking.id,
            "patient_name": booking.patient_name or booking.booked_by,
            "patient_age": booking.patient_age,
            "patient_gender": booking.patient_gender,
            "patient_contact": booking.patient_contact_number or booking.booked_by_email,
            "pickup_location": booking.pickup_location,
            "pickup_latitude": booking.pickup_latitude,
            "pickup_longitude": booking.pickup_longitude,
            "pickup_landmark": booking.pickup_landmark,
            "destination": booking.destination or booking.assigned_hospital_name or "",
            "assigned_hospital_id": booking.assigned_hospital_id,
            "assigned_hospital_name": booking.assigned_hospital_name,
            "assigned_hospital_address": booking.assigned_hospital_address,
            "assigned_hospital_contact": booking.assigned_hospital_contact,
            "assigned_hospital_email": booking.assigned_hospital_email,
            "status": booking.status,
            "payment_status": getattr(booking, "payment_status", "due"),
            "payment_total": float(booking.payment_total) if getattr(booking, "payment_total", None) is not None else None,
            "payment_amount_due": float(booking.payment_amount_due) if getattr(booking, "payment_amount_due", None) is not None else None,
            "payment_note": getattr(booking, "payment_note", ""),
            "payment_updated_at": booking.payment_updated_at.isoformat() if getattr(booking, "payment_updated_at", None) else None,
            "ambulance_number": booking.ambulance_number,
            "driver_name": booking.driver,
            "driver_contact": booking.driver_contact,
            "created_at": booking.created_at.isoformat(),
            "hospital_assigned_at": booking.hospital_assigned_at.isoformat() if booking.hospital_assigned_at else None,
            "hospital_response": booking.hospital_response,
            "hospital_response_note": booking.hospital_response_note,
            "patient_condition": booking.patient_condition,
            "vitals_summary": booking.vitals_summary,
            "live_vitals": {
                "heart_rate": getattr(booking, "heart_rate", "76 bpm") or "76 bpm",
                "spo2": getattr(booking, "spo2", "98%") or "98%",
                "bp": getattr(booking, "bp", "120/80") or "120/80",
            },
            "report_submitted_by": booking.report_submitted_by,
            "report_submitted_at": booking.report_submitted_at.isoformat() if booking.report_submitted_at else None,
            "report_sent_to_hospital": booking.report_sent_to_hospital,
            "report_sent_to_hospital_at": booking.report_sent_to_hospital_at.isoformat() if booking.report_sent_to_hospital_at else None,
            "driver_modified_report": booking.driver_modified_report,
            "insurance_status": booking.insurance_status,
            "patient_reached": getattr(booking, "patient_reached", False),
            "patient_reached_at": booking.patient_reached_at.isoformat() if getattr(booking, "patient_reached_at", None) else None,
            "driver_accepted": getattr(booking, "driver_accepted", False),
            "driver_status": getattr(booking, "driver_status", "pending"),
            "assigned_doctors_json": getattr(booking, "assigned_doctors_json", "[]"),
            "assigned_doctor_names": getattr(booking, "assigned_doctor_names", ""),
            "assigned_doctor_specializations": getattr(booking, "assigned_doctor_specializations", ""),
            "assigned_doctor_contacts": getattr(booking, "assigned_doctor_contacts", ""),
            "doctors_assigned_at": booking.doctors_assigned_at.isoformat() if getattr(booking, "doctors_assigned_at", None) else None,
            "assigned_bed_id": getattr(booking, "assigned_bed_id", None),
            "assigned_bed_number": getattr(booking, "assigned_bed_number", ""),
            "assigned_bed_type": getattr(booking, "assigned_bed_type", "general"),
            "icu_required": getattr(booking, "icu_required", False),
            "icu_requested_at": booking.icu_requested_at.isoformat() if getattr(booking, "icu_requested_at", None) else None,
            "digital_handover": {
                "patient_condition": booking.patient_condition,
                "vitals_summary": booking.vitals_summary,
                "report_submitted_by": booking.report_submitted_by,
                "report_submitted_at": booking.report_submitted_at.isoformat() if booking.report_submitted_at else None,
                "report_sent_to_hospital": booking.report_sent_to_hospital,
                "driver_voice_transcript": booking.driver_voice_transcript,
                "driver_modified_report": booking.driver_modified_report,
                "driver_report_sent_at": booking.driver_report_sent_at.isoformat() if booking.driver_report_sent_at else None,
            },
            "ambulance_live": (
                {
                    "ambulance_id": ambulance_map[booking.ambulance_id].id,
                    "ambulance_number": ambulance_map[booking.ambulance_id].ambulance_number,
                    "driver": ambulance_map[booking.ambulance_id].driver,
                    "driver_contact": ambulance_map[booking.ambulance_id].driver_contact,
                    "latitude": ambulance_map[booking.ambulance_id].latitude,
                    "longitude": ambulance_map[booking.ambulance_id].longitude,
                    "speed": ambulance_map[booking.ambulance_id].speed,
                    "status": ambulance_map[booking.ambulance_id].status,
                    "battery_percentage": getattr(ambulance_map[booking.ambulance_id], "battery_percentage", None),
                    "last_updated": ambulance_map[booking.ambulance_id].last_updated.isoformat()
                    if ambulance_map[booking.ambulance_id].last_updated
                    else None,
                }
                if booking.ambulance_id in ambulance_map
                else None
            ),
        }
        for booking in bookings
    ]

    payload = {
        "hospital": hospital_to_dict(hospital),
        "summary": {
            "active_cases": len(queue),
            "available_beds": hospital.available_beds,
            "available_icu_beds": hospital.available_icu_beds,
            "available_ventilators": hospital.ventilators_available,
            "active_staff": active_staff.count(),
        },
        "queue": queue,
        "staff": staff_data,
        "on_call_specialists": [member for member in staff_data if member["is_on_call"] and member["is_active"]],
        "redirect_suggestion": None,
    }
    cache_set(dashboard_key(hospital.id), payload)
    return JsonResponse(payload)


@csrf_exempt
def hospital_payment_detail(request, hospital_id, booking_id):
    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except Hospital.DoesNotExist:
        return JsonResponse({"error": "Hospital not found"}, status=404)

    authorization = str(request.headers.get("Authorization", ""))
    if request.method == "PATCH":
        if not authorization.startswith("Bearer "):
            return JsonResponse({"error": "Hospital session authorization is required"}, status=401)
        try:
            session = signing.loads(authorization[7:].strip(), max_age=86400)
        except signing.BadSignature:
            return JsonResponse({"error": "Hospital session authorization is invalid or expired"}, status=401)
        if (
            session.get("role") != "hospital"
            or int(session.get("hospital_id", 0)) != hospital.id
            or str(session.get("email", "")).strip().casefold() != str(hospital.email or "").strip().casefold()
        ):
            return JsonResponse({"error": "Hospital session is not authorized for this account"}, status=403)

    hospital_filter = Q(assigned_hospital_id=hospital.id)
    if hospital.email:
        hospital_filter |= Q(assigned_hospital_email__iexact=hospital.email)
    if hospital.name:
        hospital_filter |= Q(assigned_hospital_name__iexact=hospital.name) | Q(destination__iexact=hospital.name)
    booking = Booking.objects.filter(Q(id=booking_id) & hospital_filter).first()
    if not booking:
        return JsonResponse({"error": "Payment record not found for this hospital"}, status=404)

    if request.method == "GET":
        return JsonResponse({
            "booking_id": booking.id,
            "payment_status": getattr(booking, "payment_status", "due"),
            "payment_total": float(booking.payment_total) if booking.payment_total is not None else None,
            "payment_amount_due": float(booking.payment_amount_due) if booking.payment_amount_due is not None else None,
            "payment_note": getattr(booking, "payment_note", ""),
            "payment_updated_at": booking.payment_updated_at.isoformat() if booking.payment_updated_at else None,
        })
    if request.method != "PATCH":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    payment_status = str(data.get("payment_status", getattr(booking, "payment_status", "due"))).strip().lower()
    if payment_status not in {"draft", "due", "paid", "overdue", "cancelled"}:
        return JsonResponse({"error": "Invalid payment status"}, status=400)
    try:
        total = Decimal(str(data.get("payment_total", booking.payment_total or "0")))
        amount_due = Decimal(str(data.get("payment_amount_due", booking.payment_amount_due or "0")))
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({"error": "Payment amounts must be valid numbers"}, status=400)
    if total < 0 or amount_due < 0 or amount_due > total:
        return JsonResponse({"error": "Amount due cannot be greater than total"}, status=400)

    booking.payment_status = payment_status
    booking.payment_total = total
    booking.payment_amount_due = amount_due
    booking.payment_note = str(data.get("payment_note", ""))[:500]
    booking.payment_updated_at = timezone.now()
    booking.save(update_fields=["payment_status", "payment_total", "payment_amount_due", "payment_note", "payment_updated_at"])
    return JsonResponse({
        "booking_id": booking.id,
        "payment_status": booking.payment_status,
        "payment_total": float(booking.payment_total),
        "payment_amount_due": float(booking.payment_amount_due),
        "payment_note": booking.payment_note,
        "payment_updated_at": booking.payment_updated_at.isoformat(),
    })


def hospital_list(request):

    if request.method == "GET":
        params = request.GET
        hospitals = Hospital.objects.all().order_by("name")
        if str(params.get("active", "")).strip().lower() in {"1", "true", "yes"}:
            hospitals = hospitals.filter(is_active=True)
        status = str(params.get("status", "")).strip().lower()
        if status:
            hospitals = hospitals.filter(status=status)
        city = str(params.get("city", "")).strip()
        if city:
            hospitals = hospitals.filter(city__icontains=city)
        if str(params.get("emergency_services", "")).strip().lower() in {"1", "true", "yes"}:
            hospitals = hospitals.filter(emergency_services=True)
        search = str(params.get("search", "")).strip()
        if search:
            hospitals = hospitals.filter(Q(name__icontains=search) | Q(city__icontains=search) | Q(address__icontains=search))
        page, page_size, paginate = parse_list_options(request, default_page_size=50, max_page_size=200)
        if not paginate:
            return JsonResponse([hospital_to_dict(h) for h in hospitals], safe=False)
        total = hospitals.count()
        start = (page - 1) * page_size
        rows = list(hospitals[start : start + page_size])
        return JsonResponse({
            "results": [hospital_to_dict(h) for h in rows],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if total else 0,
                "has_next": start + page_size < total,
                "has_previous": page > 1,
            },
        })

    if request.method == "POST":
        data = json.loads(request.body)
        h = Hospital()
        apply_hospital_payload(h, data)
        h.save()
        invalidate_hospital_cache(h.id)
        return JsonResponse(hospital_to_dict(h), status=201)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def hospital_detail(request, id):

    try:
        h = Hospital.objects.get(id=id)
    except Hospital.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(hospital_to_dict(h))

    if request.method == "PUT":
        data = json.loads(request.body)
        apply_hospital_payload(h, data)
        h.save()
        if CAPACITY_FIELDS.intersection(data):
            ensure_hospital_beds(h)
            h.refresh_from_db()
            for field in CAPACITY_FIELDS.intersection(data):
                setattr(h, field, data[field])
            h.save(update_fields=[*CAPACITY_FIELDS.intersection(data), "last_capacity_updated", "updated_at"])
            reconcile_hospital_bed_availability(h)
            h.refresh_from_db()
        invalidate_hospital_cache(h.id)
        return JsonResponse(hospital_to_dict(h))

    if request.method == "PATCH":
        data = json.loads(request.body)
        apply_hospital_payload(h, data)
        h.save()
        if CAPACITY_FIELDS.intersection(data):
            ensure_hospital_beds(h)
            h.refresh_from_db()
            for field in CAPACITY_FIELDS.intersection(data):
                setattr(h, field, data[field])
            h.save(update_fields=[*CAPACITY_FIELDS.intersection(data), "last_capacity_updated", "updated_at"])
            reconcile_hospital_bed_availability(h)
            h.refresh_from_db()
        invalidate_hospital_cache(h.id)
        return JsonResponse(hospital_to_dict(h))

    if request.method == "DELETE":
        h.delete()
        return JsonResponse({"status": "deleted"})

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def hospital_resources(request, id):
    try:
        hospital = Hospital.objects.get(id=id)
    except Hospital.DoesNotExist:
        return JsonResponse({"error": "Hospital not found"}, status=404)
    if request.method not in ("GET", "PATCH"):
        return JsonResponse({"error": "Method not allowed"}, status=405)
    if request.method == "PATCH":
        data = json.loads(request.body or b"{}")
        requested_capacity = {
            field: data[field]
            for field in CAPACITY_FIELDS
            if field in data
        }
        apply_hospital_payload(hospital, data)
        hospital.save()
        if requested_capacity:
            # Ensure missing rows exist, then reconcile free-bed statuses with
            # the capacity the hospital just saved. Without this step the next
            # bed refresh recalculated the old count from stale bed rows.
            ensure_hospital_beds(hospital)
            hospital.refresh_from_db()
            for field, value in requested_capacity.items():
                setattr(hospital, field, value)
            hospital.save(update_fields=[*requested_capacity.keys(), "last_capacity_updated", "updated_at"])
            reconcile_hospital_bed_availability(hospital)
            hospital.refresh_from_db()
    else:
        hospital.refresh_from_db()
    invalidate_hospital_cache(hospital.id)
    return JsonResponse(hospital_to_dict(hospital))


def _ensure_bed_inventory(hospital):
    """Keep the legacy allocation endpoints on the reconciled inventory."""
    return ensure_hospital_beds(hospital)


@csrf_exempt
def hospital_beds(request, hospital_id):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    with transaction.atomic():
        hospital = Hospital.objects.select_for_update().filter(id=hospital_id, is_active=True).first()
        if not hospital:
            return JsonResponse({"error": "Hospital not found"}, status=404)
        _ensure_bed_inventory(hospital)
        beds = HospitalBed.objects.filter(hospital=hospital).order_by("bed_type", "bed_number")
        page, page_size, paginate = parse_list_options(request, default_page_size=100, max_page_size=300)
        if not paginate:
            return JsonResponse([bed_to_dict(bed) for bed in beds], safe=False)
        total = beds.count()
        start = (page - 1) * page_size
        rows = list(beds[start : start + page_size])
        return JsonResponse({
            "results": [bed_to_dict(bed) for bed in rows],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if total else 0,
                "has_next": start + page_size < total,
                "has_previous": page > 1,
            },
        })


@csrf_exempt
@transaction.atomic
def hospital_bed_assign(request, hospital_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        data = json.loads(request.body or b"{}")
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    hospital = Hospital.objects.select_for_update().filter(id=hospital_id, is_active=True).first()
    if not hospital:
        return JsonResponse({"error": "Hospital not found"}, status=404)
    try:
        booking = Booking.objects.select_for_update().get(id=int(data.get("booking_id")), assigned_hospital_id=hospital.id)
    except (Booking.DoesNotExist, TypeError, ValueError):
        return JsonResponse({"error": "Booking is not assigned to this hospital"}, status=403)
    _ensure_bed_inventory(hospital)
    bed_type = "icu" if str(data.get("bed_type", "general")).lower() == "icu" else "general"
    try:
        bed = HospitalBed.objects.select_for_update().get(id=int(data.get("bed_id")), hospital=hospital)
    except (HospitalBed.DoesNotExist, TypeError, ValueError):
        return JsonResponse({"error": "Bed not found"}, status=404)
    if bed.bed_type != bed_type:
        return JsonResponse({"error": "Bed type does not match the requested allocation"}, status=409)
    if bed.status != "available" and bed.assigned_booking_id != booking.id:
        return JsonResponse({"error": "Bed is no longer available"}, status=409)
    previous = HospitalBed.objects.select_for_update().filter(hospital=hospital, assigned_booking_id=booking.id).exclude(id=bed.id).first()
    if previous:
        previous.status, previous.assigned_booking_id, previous.patient_name, previous.assigned_staff_json = "available", None, "", "[]"
        previous.save(update_fields=["status", "assigned_booking_id", "patient_name", "assigned_staff_json", "updated_at"])
        if previous.bed_type == "icu":
            hospital.available_icu_beds = min(int(hospital.icu_beds or 0), int(hospital.available_icu_beds or 0) + 1)
        else:
            hospital.available_beds = min(int(hospital.total_beds or 0), int(hospital.available_beds or 0) + 1)
    if bed.status == "available":
        if bed_type == "icu":
            if int(hospital.available_icu_beds or 0) <= 0:
                return JsonResponse({"error": "No ICU beds are available"}, status=409)
            hospital.available_icu_beds -= 1
        else:
            if int(hospital.available_beds or 0) <= 0:
                return JsonResponse({"error": "No general beds are available"}, status=409)
            hospital.available_beds -= 1
    bed.status = "reserved"
    bed.assigned_booking_id = booking.id
    bed.patient_name = booking.patient_name or booking.booked_by or "Emergency Intake"
    bed.patient_age = booking.patient_age or ""
    bed.patient_gender = booking.patient_gender or ""
    bed.patient_phone = booking.patient_contact_number or booking.booked_by_email or ""
    bed.medical_condition = booking.patient_condition or ("Critical Care Required" if bed_type == "icu" else "General Inpatient Care")
    bed.vitals_summary = booking.vitals_summary or ""
    bed.attending_doctor = booking.assigned_doctor_names or ""
    bed.assigned_staff_json = booking.assigned_doctors_json or "[]"
    bed.admission_time = timezone.now()
    bed.save()
    booking.assigned_bed_id, booking.assigned_bed_number, booking.assigned_bed_type = bed.id, bed.bed_number, bed.bed_type
    booking.icu_required = bed.bed_type == "icu"
    if booking.icu_required and not booking.icu_requested_at:
        booking.icu_requested_at = timezone.now()
    booking.save(update_fields=["assigned_bed_id", "assigned_bed_number", "assigned_bed_type", "icu_required", "icu_requested_at"])
    hospital.last_capacity_updated = timezone.now()
    hospital.save(update_fields=["available_beds", "available_icu_beds", "last_capacity_updated", "updated_at"])
    invalidate_hospital_cache(hospital.id)
    return JsonResponse({"status": "assigned", "bed": bed_to_dict(bed)})


@csrf_exempt
@transaction.atomic
def hospital_bed_detail(request, bed_id):
    if request.method not in {"GET", "PATCH"}:
        return JsonResponse({"error": "GET or PATCH only"}, status=405)
    bed = HospitalBed.objects.select_for_update().select_related("hospital").filter(id=bed_id).first()
    if not bed:
        return JsonResponse({"error": "Bed not found"}, status=404)
    if request.method == "GET":
        return JsonResponse(bed_to_dict(bed))
    try:
        data = json.loads(request.body or b"{}")
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    next_status = str(data.get("status", bed.status)).lower()
    if next_status not in {"available", "reserved", "occupied"}:
        return JsonResponse({"error": "Invalid bed status"}, status=400)
    if next_status == "available" and bed.status != "available":
        if bed.bed_type == "icu":
            bed.hospital.available_icu_beds = min(int(bed.hospital.icu_beds or 0), int(bed.hospital.available_icu_beds or 0) + 1)
        else:
            bed.hospital.available_beds = min(int(bed.hospital.total_beds or 0), int(bed.hospital.available_beds or 0) + 1)
        bed.hospital.last_capacity_updated = timezone.now()
        bed.hospital.save(update_fields=["available_beds", "available_icu_beds", "last_capacity_updated", "updated_at"])
    for field in ("status", "assigned_booking_id", "patient_name", "patient_age", "patient_gender", "blood_group", "patient_phone", "emergency_contact", "medical_condition", "vitals_summary", "attending_doctor", "assigned_staff_json", "admission_time"):
        if field in data:
            setattr(bed, field, data[field])
    if next_status == "available":
        bed.assigned_booking_id = None
    bed.save()
    invalidate_hospital_cache(bed.hospital_id)
    return JsonResponse(bed_to_dict(bed))


@csrf_exempt
def hospital_staff_list(request, hospital_id):
    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except Hospital.DoesNotExist:
        return JsonResponse({"error": "Hospital not found"}, status=404)
    if request.method == "GET":
        staff = hospital.staff.all().order_by("role", "full_name")
        page, page_size, paginate = parse_list_options(request, default_page_size=50, max_page_size=200)
        if not paginate:
            return JsonResponse([staff_to_dict(s) for s in staff], safe=False)
        total = staff.count()
        start = (page - 1) * page_size
        rows = list(staff[start : start + page_size])
        return JsonResponse({
            "results": [staff_to_dict(s) for s in rows],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if total else 0,
                "has_next": start + page_size < total,
                "has_previous": page > 1,
            },
        })
    if request.method == "POST":
        data = json.loads(request.body or b"{}")
        full_name = str(data.get("full_name", "")).strip()
        staff_id_value = str(data.get("staff_id", "")).strip()
        registration_number = str(data.get("registration_number", "")).strip()
        if not full_name or not staff_id_value or not registration_number:
            return JsonResponse({"error": "Full name, Staff ID and Registration No. are required"}, status=400)
        duplicate = HospitalStaff.objects.filter(
            Q(staff_id__iexact=staff_id_value) | Q(registration_number__iexact=registration_number)
        ).exists()
        if duplicate:
            return JsonResponse({"error": "Staff ID or Registration No. is already assigned"}, status=409)
        staff = HospitalStaff.objects.create(
            hospital=hospital,
            **{
                field: data[field]
                for field in STAFF_MUTABLE_FIELDS
                if field in data and field not in {"full_name", "staff_id", "registration_number"}
            },
            full_name=full_name,
            staff_id=staff_id_value,
            registration_number=registration_number,
        )
        invalidate_hospital_cache(hospital.id)
        return JsonResponse(staff_to_dict(staff), status=201)
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def hospital_staff_detail(request, hospital_id, staff_id):
    try:
        staff = HospitalStaff.objects.get(id=staff_id, hospital_id=hospital_id)
    except HospitalStaff.DoesNotExist:
        return JsonResponse({"error": "Staff not found"}, status=404)
    if request.method == "DELETE":
        staff.delete()
        invalidate_hospital_cache(hospital_id)
        return JsonResponse({"status": "deleted"})
    if request.method == "PATCH":
        data = json.loads(request.body or b"{}")
        if "staff_id" in data or "registration_number" in data:
            next_staff_id = str(data.get("staff_id", staff.staff_id)).strip()
            next_registration_number = str(data.get("registration_number", staff.registration_number)).strip()
            if not next_staff_id or not next_registration_number:
                return JsonResponse({"error": "Staff ID and Registration No. cannot be empty"}, status=400)
            duplicate = HospitalStaff.objects.filter(
                Q(staff_id__iexact=next_staff_id) | Q(registration_number__iexact=next_registration_number)
            ).exclude(id=staff.id).exists()
            if duplicate:
                return JsonResponse({"error": "Staff ID or Registration No. is already assigned"}, status=409)
            staff.staff_id = next_staff_id
            staff.registration_number = next_registration_number
        for field in STAFF_MUTABLE_FIELDS:
            if field in data and field not in {"staff_id", "registration_number"}:
                setattr(staff, field, data[field])
        staff.save()
        invalidate_hospital_cache(hospital_id)
        return JsonResponse(staff_to_dict(staff))
    return JsonResponse({"error": "Method not allowed"}, status=405)


def _staff_auth_payload(staff):
    return {
        "valid": True,
        "role": "staff",
        "staff_role": staff.role,
        "staff": staff_to_dict(staff),
        "hospital": hospital_to_dict(staff.hospital),
        "hospital_id": staff.hospital_id,
        "hospital_name": staff.hospital.name,
        "staff_id": staff.staff_id,
        "registration_number": staff.registration_number,
        "name": staff.full_name,
        "email": staff.email,
    }


@csrf_exempt
def staff_signup(request):
    """Create a staff password after hospital ID and registration validation."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        data = json.loads(request.body or b"{}")
    except (TypeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    email = str(data.get("email", "")).strip().lower()
    staff_id = str(data.get("staff_id", "")).strip()
    registration_number = str(data.get("registration_number", "")).strip()
    password = str(data.get("password", ""))
    if not email or not staff_id or not registration_number:
        return JsonResponse({"error": "Email, Staff ID and Registration No. are required"}, status=400)
    if len(password) < 6:
        return JsonResponse({"error": "Password must be at least 6 characters"}, status=400)

    staff = HospitalStaff.objects.select_related("hospital").filter(
        email__iexact=email,
        staff_id__iexact=staff_id,
        registration_number__iexact=registration_number,
        is_active=True,
    ).first()
    if not staff:
        return JsonResponse({"error": "Staff ID, Registration No. or email do not match hospital records"}, status=401)
    if not staff.hospital.is_active:
        return JsonResponse({"error": "This hospital account is currently inactive"}, status=403)
    if staff.password_hash:
        return JsonResponse({"error": "Staff account is already set up. Please use Sign In."}, status=409)
    if data.get("verify_only"):
        return JsonResponse({"valid": True, "otp_required": True})

    staff.password_hash = make_password(password)
    staff.save(update_fields=["password_hash", "updated_at"])
    return JsonResponse(_staff_auth_payload(staff))


@csrf_exempt
def staff_login(request):
    """Authenticate staff using hospital-issued Staff ID and Registration No."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        data = json.loads(request.body or b"{}")
    except (TypeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    email = str(data.get("email", "")).strip().lower()
    staff_id = str(data.get("staff_id", "")).strip()
    registration_number = str(data.get("registration_number", "")).strip()
    password = str(data.get("password", ""))
    if not all((email, staff_id, registration_number, password)):
        return JsonResponse({"error": "Email, Staff ID, Registration No. and password are required"}, status=400)

    staff = HospitalStaff.objects.select_related("hospital").filter(
        email__iexact=email,
        staff_id__iexact=staff_id,
        registration_number__iexact=registration_number,
        is_active=True,
    ).first()
    if not staff or not staff.password_hash or not check_password(password, staff.password_hash):
        return JsonResponse({"error": "Staff ID, Registration No. or password do not match hospital records"}, status=401)
    if not staff.hospital.is_active:
        return JsonResponse({"error": "This hospital account is currently inactive"}, status=403)
    return JsonResponse(_staff_auth_payload(staff))


@csrf_exempt
def staff_dashboard(request):
    """Return the signed-in staff profile and the cases assigned to that member."""
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    staff_id = str(request.GET.get("staff_id", "")).strip()
    email = str(request.GET.get("email", "")).strip().lower()
    if not staff_id or not email:
        return JsonResponse({"error": "staff_id and email are required"}, status=400)
    staff = HospitalStaff.objects.select_related("hospital").filter(
        staff_id__iexact=staff_id, email__iexact=email, is_active=True
    ).first()
    if not staff:
        return JsonResponse({"error": "Staff account not found or inactive"}, status=404)

    from bookings.views import booking_to_dict

    hospital_filter = Q(assigned_hospital_id=staff.hospital_id)
    if staff.hospital.email:
        hospital_filter |= Q(assigned_hospital_email__iexact=staff.hospital.email)
    if staff.hospital.name:
        hospital_filter |= Q(assigned_hospital_name__iexact=staff.hospital.name) | Q(destination__iexact=staff.hospital.name)

    cases = []
    for booking in Booking.objects.filter(hospital_filter).order_by("-id")[:200]:
        team = []
        try:
            parsed = json.loads(getattr(booking, "assigned_doctors_json", "[]") or "[]")
            team = parsed if isinstance(parsed, list) else []
        except (TypeError, ValueError):
            pass
        assigned = any(
            isinstance(member, dict) and (
                str(member.get("id", "")) == str(staff.id)
                or str(member.get("staff_id", "")).lower() == staff.staff_id.lower()
                or str(member.get("full_name", member.get("name", ""))).strip().lower() == staff.full_name.strip().lower()
            ) for member in team
        )
        assigned = assigned or getattr(staff, "assigned_booking_id", None) == booking.id
        if not assigned and staff.full_name:
            assigned = staff.full_name.strip().lower() in str(getattr(booking, "assigned_doctor_names", "")).lower()
        if team and not assigned:
            continue
        row = booking_to_dict(booking)
        row["assigned_team"] = team
        row["staff_role"] = staff.role
        cases.append(row)

    active_cases = [item for item in cases if item.get("status") not in {"completed", "cancelled"}]
    urgent_cases = [item for item in active_cases if any(
        token in f"{item.get('patient_condition', '')} {item.get('vitals_summary', '')}".lower()
        for token in ("critical", "cardiac", "stroke", "trauma", "icu", "emergency")
    )]
    completed_cases = [item for item in cases if item.get("status") == "completed"]
    team_members = sum(len(item.get("assigned_team") or []) for item in cases)
    return JsonResponse({
        "staff": staff_to_dict(staff),
        "hospital": hospital_to_dict(staff.hospital),
        "summary": {
            "assigned_cases": len(cases),
            "active_cases": len(active_cases),
            "urgent_cases": len(urgent_cases),
            "bed_allocated_cases": sum(1 for item in cases if item.get("assigned_bed_number")),
            "completed_cases": len(completed_cases),
            "team_members": team_members,
            "new_allocations": sum(1 for item in active_cases if item.get("doctors_assigned_at")),
        },
        "cases": cases,
    })


@csrf_exempt
def staff_notifications(request):
    """Return allocation alerts for every staff member on a booking team."""
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    staff_id = str(request.GET.get("staff_id", "")).strip()
    email = str(request.GET.get("email", "")).strip().lower()
    staff = HospitalStaff.objects.select_related("hospital").filter(staff_id__iexact=staff_id, email__iexact=email, is_active=True).first()
    if not staff:
        return JsonResponse({"error": "Staff account not found or inactive"}, status=404)
    hospital_filter = Q(assigned_hospital_id=staff.hospital_id)
    if staff.hospital.email:
        hospital_filter |= Q(assigned_hospital_email__iexact=staff.hospital.email)
    if staff.hospital.name:
        hospital_filter |= Q(assigned_hospital_name__iexact=staff.hospital.name) | Q(destination__iexact=staff.hospital.name)
    notifications = []
    from bookings.models import VideoCallRequest
    for booking in Booking.objects.filter(hospital_filter).order_by("-doctors_assigned_at", "-id")[:100]:
        try:
            team = json.loads(getattr(booking, "assigned_doctors_json", "[]") or "[]")
        except (TypeError, ValueError):
            team = []
        assigned = any(isinstance(member, dict) and (str(member.get("id", "")) == str(staff.id) or str(member.get("staff_id", "")).lower() == staff.staff_id.lower() or str(member.get("full_name", member.get("name", ""))).strip().lower() == staff.full_name.strip().lower()) for member in team)
        if not assigned and getattr(staff, "assigned_booking_id", None) == booking.id:
            assigned = True
        if not assigned and staff.full_name:
            assigned = staff.full_name.strip().lower() in str(getattr(booking, "assigned_doctor_names", "")).lower()
        if not assigned:
            continue
        notifications.append({
            "id": f"staff-{staff.id}-booking-{booking.id}",
            "booking_id": booking.id,
            "title": f"Booking #{booking.id} is allocated to you",
            "message": f"{booking.patient_name or booking.booked_by or 'Patient'} · Start the care workflow at {booking.assigned_hospital_name or staff.hospital.name}.",
            "status": booking.status,
            "timestamp": getattr(booking, "doctors_assigned_at", None).isoformat() if getattr(booking, "doctors_assigned_at", None) else booking.created_at.isoformat(),
        })
    video_requests = VideoCallRequest.objects.filter(
        staff=staff, status="pending"
    ).select_related("booking", "staff").order_by("-requested_at")[:20]
    notifications.extend({
        "id": f"video-call-{item.id}",
        "booking_id": item.booking_id,
        "video_request_id": item.id,
        "type": "video_call_request",
        "title": f"Video call request from {item.driver_name or 'ambulance driver'}",
        "message": f"Join the live consultation for Booking #{item.booking_id}.",
        "status": item.status,
        "timestamp": item.requested_at.isoformat(),
    } for item in video_requests)
    return JsonResponse({"notifications": notifications})
