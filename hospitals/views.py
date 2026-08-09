from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from hospitals.models import Hospital, HospitalStaff
from bookings.models import Booking
import json


def hospital_to_dict(h):
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
        "total_beds":         h.total_beds,
        "available_beds":     h.available_beds,
        "emergency_beds":     h.emergency_beds,
        "icu_beds":           h.icu_beds,
        "available_icu_beds": h.available_icu_beds,
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
        "last_capacity_updated": h.last_capacity_updated.isoformat() if h.last_capacity_updated else None,
        "created_at":         h.created_at.isoformat(),
        "updated_at":         h.updated_at.isoformat(),
    }


def staff_to_dict(member):
    return {
        "id": member.id,
        "full_name": member.full_name,
        "role": member.role,
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
        "joined_on": member.joined_on.isoformat() if member.joined_on else None,
        "notes": member.notes,
    }


STAFF_MUTABLE_FIELDS = (
    "full_name", "role", "specialization", "registration_number", "contact_number",
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

    # New assignments use the immutable hospital id. The destination fallback keeps
    # historical bookings visible after the production schema upgrade.
    bookings = (
        Booking.objects.filter(
            Q(assigned_hospital_id=hospital.id)
            | Q(assigned_hospital_id__isnull=True, destination__iexact=hospital.name)
        )
        .exclude(status__in=["cancelled", "completed"])
        .order_by("-created_at")
    )
    staff = HospitalStaff.objects.filter(hospital=hospital, is_active=True)
    staff_data = [staff_to_dict(member) for member in staff]
    queue = [
        {
            "booking_id": booking.id,
            "patient_name": booking.patient_name or booking.booked_by,
            "patient_age": booking.patient_age,
            "patient_gender": booking.patient_gender,
            "patient_contact": booking.patient_contact_number or booking.booked_by_email,
            "pickup_location": booking.pickup_location,
            "pickup_landmark": booking.pickup_landmark,
            "status": booking.status,
            "ambulance_number": booking.ambulance_number,
            "driver_name": booking.driver,
            "driver_contact": booking.driver_contact,
            "created_at": booking.created_at.isoformat(),
            "hospital_assigned_at": booking.hospital_assigned_at.isoformat() if booking.hospital_assigned_at else None,
            "hospital_response": booking.hospital_response,
            "hospital_response_note": booking.hospital_response_note,
            "patient_condition": booking.patient_condition,
            "vitals_summary": booking.vitals_summary,
            "report_sent_to_hospital": booking.report_sent_to_hospital,
            "insurance_status": booking.insurance_status,
        }
        for booking in bookings
    ]

    return JsonResponse({
        "hospital": hospital_to_dict(hospital),
        "summary": {
            "active_cases": len(queue),
            "available_beds": hospital.available_beds,
            "available_icu_beds": hospital.available_icu_beds,
            "available_ventilators": hospital.ventilators_available,
            "active_staff": len(staff_data),
        },
        "queue": queue,
        "staff": staff_data,
        "on_call_specialists": [member for member in staff_data if member["is_on_call"]],
        "redirect_suggestion": None,
    })


@csrf_exempt
def hospital_list(request):

    if request.method == "GET":
        hospitals = Hospital.objects.all()
        return JsonResponse([hospital_to_dict(h) for h in hospitals], safe=False)

    if request.method == "POST":
        data = json.loads(request.body)
        h = Hospital()
        apply_hospital_payload(h, data)
        h.save()
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
        return JsonResponse(hospital_to_dict(h))

    if request.method == "PATCH":
        data = json.loads(request.body)
        apply_hospital_payload(h, data)
        h.save()
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
        apply_hospital_payload(hospital, data)
        hospital.save()
    return JsonResponse(hospital_to_dict(hospital))


@csrf_exempt
def hospital_staff_list(request, hospital_id):
    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except Hospital.DoesNotExist:
        return JsonResponse({"error": "Hospital not found"}, status=404)
    if request.method == "GET":
        return JsonResponse([staff_to_dict(s) for s in hospital.staff.all()], safe=False)
    if request.method == "POST":
        data = json.loads(request.body or b"{}")
        if not str(data.get("full_name", "")).strip():
            return JsonResponse({"error": "full_name is required"}, status=400)
        staff = HospitalStaff.objects.create(
            hospital=hospital,
            **{field: data[field] for field in STAFF_MUTABLE_FIELDS if field in data},
        )
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
        return JsonResponse({"status": "deleted"})
    if request.method == "PATCH":
        data = json.loads(request.body or b"{}")
        for field in STAFF_MUTABLE_FIELDS:
            if field in data:
                setattr(staff, field, data[field])
        staff.save()
        return JsonResponse(staff_to_dict(staff))
    return JsonResponse({"error": "Method not allowed"}, status=405)
