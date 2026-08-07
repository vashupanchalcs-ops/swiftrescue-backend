from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from hospitals.models import Hospital
from bookings.models import Booking
import json


def hospital_to_dict(h):
    return {
        "id":                 h.id,
        "name":               h.name,
        "address":            h.address,
        "latitude":           h.latitude,
        "longitude":          h.longitude,
        "contact_number":     h.contact_number,
        "email":              h.email,
        "hospital_type":      h.hospital_type,
        "total_beds":         h.total_beds,
        "available_beds":     h.available_beds,
        "icu_beds":           h.icu_beds,
        "specializations":    h.specializations,
        "emergency_services": h.emergency_services,
        "status":             h.status,
        "is_active":          h.is_active,
    }


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

    bookings = Booking.objects.filter(destination__iexact=hospital.name).exclude(status="cancelled").order_by("-created_at")
    queue = [
        {
            "booking_id": booking.id,
            "patient_name": booking.booked_by,
            "patient_contact": booking.booked_by_email,
            "pickup_location": booking.pickup_location,
            "status": booking.status,
            "ambulance_number": booking.ambulance_number,
            "driver_name": booking.driver,
            "driver_contact": booking.driver_contact,
            "created_at": booking.created_at.isoformat(),
            "hospital_response": "pending",
        }
        for booking in bookings
    ]

    return JsonResponse({
        "hospital": hospital_to_dict(hospital),
        "summary": {"active_cases": len(queue)},
        "queue": queue,
        "staff": [],
        "on_call_specialists": [],
        "redirect_suggestion": None,
    })


@csrf_exempt
def hospital_list(request):

    if request.method == "GET":
        hospitals = Hospital.objects.all()
        return JsonResponse([hospital_to_dict(h) for h in hospitals], safe=False)

    if request.method == "POST":
        data = json.loads(request.body)
        h = Hospital.objects.create(
            name               = data.get("name", ""),
            address            = data.get("address", ""),
            latitude           = data.get("latitude", ""),
            longitude          = data.get("longitude", ""),
            contact_number     = data.get("contact_number", ""),
            email              = data.get("email", ""),
            hospital_type      = data.get("hospital_type", "private"),
            total_beds         = data.get("total_beds", 0),
            available_beds     = data.get("available_beds", 0),
            icu_beds           = data.get("icu_beds", 0),
            specializations    = data.get("specializations", ""),
            emergency_services = data.get("emergency_services", False),
            status             = data.get("status", "closed"),
            is_active          = data.get("is_active", True),
        )
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
        h.name               = data.get("name",               h.name)
        h.address            = data.get("address",            h.address)
        h.latitude           = data.get("latitude",           h.latitude)
        h.longitude          = data.get("longitude",          h.longitude)
        h.contact_number     = data.get("contact_number",     h.contact_number)
        h.email              = data.get("email",              h.email)
        h.hospital_type      = data.get("hospital_type",      h.hospital_type)
        h.total_beds         = data.get("total_beds",         h.total_beds)
        h.available_beds     = data.get("available_beds",     h.available_beds)
        h.icu_beds           = data.get("icu_beds",           h.icu_beds)
        h.specializations    = data.get("specializations",    h.specializations)
        h.emergency_services = data.get("emergency_services", h.emergency_services)
        h.status             = data.get("status",             h.status)
        h.is_active          = data.get("is_active",          h.is_active)
        h.save()
        return JsonResponse(hospital_to_dict(h))

    if request.method == "PATCH":
        data = json.loads(request.body)
        if "available_beds" in data:
            h.available_beds = data["available_beds"]
        if "icu_beds" in data:
            h.icu_beds = data["icu_beds"]
        if "emergency_services" in data:
            h.emergency_services = data["emergency_services"]
        if "is_active" in data:
            h.is_active = data["is_active"]
        if "status" in data:
            h.status = data["status"]
        h.save()
        return JsonResponse(hospital_to_dict(h))

    if request.method == "DELETE":
        h.delete()
        return JsonResponse({"status": "deleted"})

    return JsonResponse({"error": "Method not allowed"}, status=405)
