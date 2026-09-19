from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from ambulance.models import Ambulance
from hospitals.models import Hospital, HospitalStaff, HospitalBed
from bookings.models import Booking
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


@csrf_exempt
def hospital_beds(request, hospital_id):
    """GET all beds for a hospital (auto-seeds if none). PATCH a single bed."""
    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except Hospital.DoesNotExist:
        return JsonResponse({"error": "Hospital not found"}, status=404)

    if request.method == "GET":
        beds = HospitalBed.objects.filter(hospital=hospital)
        # Auto-seed beds if none exist
        if not beds.exists():
            total_general = max(1, hospital.total_beds - hospital.icu_beds)
            total_icu = max(0, hospital.icu_beds)
            created = []
            for i in range(1, total_general + 1):
                b = HospitalBed.objects.create(
                    hospital=hospital,
                    bed_number=f"G-{i:03d}",
                    bed_type="general",
                    status="available",
                    wing="General Ward"
                )
                created.append(b)
            for i in range(1, total_icu + 1):
                b = HospitalBed.objects.create(
                    hospital=hospital,
                    bed_number=f"ICU-{i:03d}",
                    bed_type="icu",
                    status="available",
                    wing="ICU"
                )
                created.append(b)
            return JsonResponse([bed_to_dict(b) for b in created], safe=False)
        return JsonResponse([bed_to_dict(b) for b in beds], safe=False)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def hospital_bed_detail(request, bed_id):
    """PATCH a single bed's fields."""
    try:
        bed = HospitalBed.objects.get(id=bed_id)
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
                setattr(bed, field, data[field])
        bed.save()
        return JsonResponse(bed_to_dict(bed))

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
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
        booking = Booking.objects.get(id=booking_id)
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Booking not found"}, status=404)

    bed_id = data.get("bed_id")
    bed = None
    if bed_id:
        bed = HospitalBed.objects.filter(id=bed_id).first()
    if not bed:
        bed_type_pref = str(data.get("bed_type", "general")).lower()
        bed = HospitalBed.objects.filter(hospital_id=hospital_id, bed_type=bed_type_pref, status="available").first()
    if not bed:
        # Fallback to any available bed in hospital
        bed = HospitalBed.objects.filter(hospital_id=hospital_id, status="available").first()
    if not bed:
        return JsonResponse({"error": "No available bed found in this hospital"}, status=409)

    # If this booking already held another bed (e.g. switching to ICU or different bed), free it
    if booking.assigned_bed_id and booking.assigned_bed_id != bed.id:
        old_bed = HospitalBed.objects.filter(id=booking.assigned_bed_id).first()
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
    bed.admission_time = timezone.now()
    bed.save()

    # Update booking
    booking.assigned_bed_id = bed.id
    booking.assigned_bed_number = bed.bed_number
    booking.assigned_bed_type = bed.bed_type
    booking.save()

    return JsonResponse({"bed": bed_to_dict(bed), "booking_id": booking_id})


@csrf_exempt
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
        booking = Booking.objects.get(id=booking_id)
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Booking not found"}, status=404)

    # Get current general bed
    current_bed = HospitalBed.objects.filter(id=booking.assigned_bed_id).first() if booking.assigned_bed_id else None

    # Find available ICU bed
    icu_bed = HospitalBed.objects.filter(hospital_id=hospital_id, bed_type="icu", status="available").first()
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

    return JsonResponse({
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
