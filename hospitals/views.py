from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from hospitals.models import Hospital
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