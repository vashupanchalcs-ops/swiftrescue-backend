from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from ambulance.models import Ambulance, DriverLocation, SuggestedRoute
import json
import random
import logging
import os
import urllib.request
import urllib.error
import base64

logger = logging.getLogger(__name__)


def send_otp_email(recipient, otp):
    brevo_key = os.getenv("BREVO_API_KEY", "").strip()
    if brevo_key:
        print("[OTP] Provider: Brevo", flush=True)
        payload = json.dumps({
            "sender": {
                "email": os.getenv("BREVO_FROM_EMAIL", "").strip() or settings.EMAIL_HOST_USER,
                "name": os.getenv("BREVO_FROM_NAME", "SwiftRescue").strip() or "SwiftRescue",
            },
            "to": [{"email": recipient}],
            "subject": "SwiftRescue OTP",
            "textContent": f"Your SwiftRescue OTP is {otp}. It is valid for 5 minutes.",
            "htmlContent": (
                "<html><body>"
                "<p>Your SwiftRescue OTP is:</p>"
                f"<h2>{otp}</h2>"
                "<p>This OTP is valid for 5 minutes.</p>"
                "</body></html>"
            ),
        }).encode()
        request = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=payload,
            headers={
                "accept": "application/json",
                "api-key": brevo_key,
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status >= 300:
                    raise RuntimeError(f"Brevo returned HTTP {response.status}")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Brevo HTTP {error.code}: {detail}") from error
        return

    mailjet_key = os.getenv("MAILJET_API_KEY", "").strip()
    mailjet_secret = os.getenv("MAILJET_SECRET_KEY", "").strip()
    if mailjet_key and mailjet_secret:
        print("[OTP] Provider: Mailjet", flush=True)
        payload = json.dumps({
            "Messages": [{
                "From": {
                    "Email": os.getenv("MAILJET_FROM_EMAIL", "").strip() or settings.EMAIL_HOST_USER,
                    "Name": "YiCare",
                },
                "To": [{"Email": recipient}],
                "Subject": "YiCare OTP",
                "TextPart": f"Your YiCare OTP is {otp}",
            }]
        }).encode()
        credentials = base64.b64encode(f"{mailjet_key}:{mailjet_secret}".encode()).decode()
        request = urllib.request.Request(
            "https://api.mailjet.com/v3.1/send",
            data=payload,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status >= 300:
                    raise RuntimeError(f"Mailjet returned HTTP {response.status}")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Mailjet HTTP {error.code}: {detail}") from error
        return

    resend_key = os.getenv("RESEND_API_KEY", "").strip()
    if resend_key:
        print("[OTP] Provider: Resend", flush=True)
        payload = json.dumps({
            "from": os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev"),
            "to": [recipient],
            "subject": "YiCare OTP",
            "text": f"Your YiCare OTP is {otp}",
        }).encode()
        request = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status >= 300:
                    raise RuntimeError(f"Resend returned HTTP {response.status}")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Resend HTTP {error.code}: {detail}") from error
        return

    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        raise RuntimeError("No email provider configured. Set BREVO_API_KEY on Render.")

    print("[OTP] Provider: SMTP", flush=True)
    send_mail(
        "YiCare OTP",
        f"Your OTP is {otp}",
        getattr(settings, "DEFAULT_FROM_EMAIL", "") or settings.EMAIL_HOST_USER,
        [recipient],
        fail_silently=False,
    )


def home(request):
    return JsonResponse({"message": "SwiftRescue Backend Running"})


def favicon(request):
    """Return a tiny inline icon so browser probes do not create 404 log noise."""
    return HttpResponse(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="14" fill="#126f1e"/>'
        '<path d="M13 34h10l5-15 8 28 5-13h10" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>',
        content_type="image/svg+xml",
    )


@csrf_exempt
def send_otp(request):
    if request.method == "POST":
        data  = json.loads(request.body)
        email = data.get("email")
        otp   = str(random.randint(100000, 999999))
        cache.set(f"otp_{email}", otp, timeout=300)

        print(f"\n{'='*40}", flush=True)
        print(f"[OTP] Email : {email}", flush=True)
        print(f"[OTP] Code  : {otp}", flush=True)
        print(f"{'='*40}\n", flush=True)

        try:
            send_otp_email(email, otp)
            print(f"[OTP] Email sent to {email}", flush=True)
        except Exception as e:
            print(f"[OTP] Email failed: {e}", flush=True)
            if settings.DEBUG:
                return JsonResponse({
                    "status": "otp_sent",
                    "delivery": "console",
                    "dev_otp": otp,
                    "message": "Gmail SMTP failed locally; use the development OTP shown on screen.",
                })
            return JsonResponse({"status": "error", "message": "Email service unavailable"}, status=503)

        return JsonResponse({"status": "otp_sent"})
    return JsonResponse({"status": "error"})


@csrf_exempt
def verify_otp(request):
    if request.method == "POST":
        data      = json.loads(request.body)
        user_otp  = data.get("otp")
        email     = data.get("email")
        saved_otp = cache.get(f"otp_{email}")
        if saved_otp and user_otp == saved_otp:
            cache.delete(f"otp_{email}")
            return JsonResponse({"status": "success", "email": email})
        else:
            return JsonResponse({"status": "invalid", "message": "Invalid OTP"})
    return JsonResponse({"status": "error"})


@csrf_exempt
def send_phone_otp(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST only"}, status=405)

    data  = json.loads(request.body)
    phone = data.get("phone", "").strip().replace(" ", "").replace("+91", "").replace("+", "")

    if not phone or len(phone) != 10:
        return JsonResponse({"status": "error", "message": "Enter a valid 10-digit phone number"}, status=400)

    otp = str(random.randint(100000, 999999))
    cache.set(f"phone_otp_{phone}", otp, timeout=300)

    print(f"\n{'='*40}", flush=True)
    print(f"[PHONE OTP] Number : +91{phone}", flush=True)
    print(f"[PHONE OTP] Code   : {otp}", flush=True)
    print(f"{'='*40}\n", flush=True)

    return JsonResponse({"status": "otp_sent", "message": f"OTP sent to +91{phone}"})


@csrf_exempt
def verify_phone_otp(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST only"}, status=405)

    data      = json.loads(request.body)
    phone     = data.get("phone", "").strip().replace(" ", "").replace("+91", "")
    user_otp  = data.get("otp", "").strip()
    saved_otp = cache.get(f"phone_otp_{phone}")

    if saved_otp and user_otp == saved_otp:
        cache.delete(f"phone_otp_{phone}")
        return JsonResponse({"status": "success", "phone": phone})
    else:
        return JsonResponse({"status": "invalid", "message": "Invalid or expired OTP"})


def logout_view(request):
    request.session.flush()
    return JsonResponse({"status": "logout"})


@csrf_exempt
def validate_contract_access(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        data = json.loads(request.body or b"{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    role = str(data.get("role", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower()
    contract_id = str(
        data.get("hospital_id")
        or data.get("hospitalId")
        or data.get("hospital_contract_id")
        or data.get("hospitalContractId")
        or data.get("contract_id")
        or data.get("contractId")
        or ""
    ).strip()
    registration = str(
        data.get("registration_number")
        or data.get("registrationNumber")
        or data.get("hospital_registration_number")
        or data.get("hospitalRegistrationNumber")
        or ""
    ).strip().replace(" ", "").lower()
    if role not in {"driver", "hospital"} or not email or not contract_id or not registration:
        return JsonResponse({"valid": False, "error": "Contract ID, registration number and email are required"}, status=400)
    if role == "driver":
        item = Ambulance.objects.filter(ambulance_contract_id__iexact=contract_id, driver_email__iexact=email).first()
        if not item:
            return JsonResponse({"valid": False, "error": "Ambulance contract details do not match"}, status=403)
        if (item.registration_number or "").replace(" ", "").lower() != registration:
            return JsonResponse({"valid": False, "error": "Ambulance registration number does not match"}, status=403)
        return JsonResponse({"valid": True, "role": "driver", "ambulance_id": item.id, "contract_id": item.ambulance_contract_id, "registration_number": item.registration_number, "ambulance_number": item.ambulance_number, "driver_name": item.driver})
    from hospitals.models import Hospital

    # Admin-entered contract values may contain accidental spaces or casing
    # differences. Compare normalized values so the same visible credentials
    # work reliably in production as well as in the admin form.
    normalize = lambda value: "".join(str(value or "").split()).casefold()
    item = next(
        (
            hospital for hospital in Hospital.objects.filter(is_active=True)
            if normalize(hospital.hospital_contract_id) == normalize(contract_id)
            and normalize(hospital.email) == normalize(email)
        ),
        None,
    )
    if not item:
        print(
            "[CONTRACT] Hospital mismatch "
            f"email={email} contract={contract_id} registration={registration}",
            flush=True,
        )
        return JsonResponse({"valid": False, "error": "Hospital contract details do not match"}, status=403)
    if (item.registration_number or "").replace(" ", "").lower() != registration:
        return JsonResponse({"valid": False, "error": "Hospital registration number does not match"}, status=403)
    return JsonResponse({"valid": True, "role": "hospital", "hospital_id": item.id, "contract_id": item.hospital_contract_id, "hospital_contract_id": item.hospital_contract_id, "registration_number": item.registration_number, "hospital_name": item.name})


def ambulance_to_dict(a):
    return {
        "id":                    a.id,
        "ambulance_number":      a.ambulance_number,
        "driver":                a.driver,
        "driver_contact":        a.driver_contact,
        "driver_email":          a.driver_email or "",
        "model":                 a.model,
        "ambulance_contract_id": a.ambulance_contract_id,
        "registration_number":   a.registration_number,
        "speed":                 a.speed,
        "status":                a.status,
        "location":              a.location,
        "nearest_hospital":      a.nearest_hospital,
        "hospital_distance":     a.hospital_distance,
        "eta_to_patient":        a.eta_to_patient,
        "eta_to_hospital":       a.eta_to_hospital,
        "latitude":              a.latitude,
        "longitude":             a.longitude,
        "last_updated":          a.last_updated.strftime("%d %b %Y, %I:%M %p"),
    }


@csrf_exempt
def ambulance_list(request):
    if request.method == "GET":
        ambulances = Ambulance.objects.all()
        return JsonResponse([ambulance_to_dict(a) for a in ambulances], safe=False)

    if request.method == "POST":
        data = json.loads(request.body)
        a = Ambulance.objects.create(
            ambulance_number  = data.get("ambulance_number", ""),
            driver            = data.get("driver", ""),
            driver_contact    = data.get("driver_contact", ""),
            driver_email      = data.get("driver_email", ""),
            model             = data.get("model", ""),
            ambulance_contract_id = data.get("ambulance_contract_id", ""),
            registration_number   = data.get("registration_number", ""),
            speed             = data.get("speed", "0"),
            status            = data.get("status", "available"),
            location          = data.get("location", ""),
            nearest_hospital  = data.get("nearest_hospital", ""),
            hospital_distance = data.get("hospital_distance", ""),
            eta_to_patient    = data.get("eta_to_patient", ""),
            eta_to_hospital   = data.get("eta_to_hospital", ""),
            latitude          = data.get("latitude"),
            longitude         = data.get("longitude"),
        )
        return JsonResponse(ambulance_to_dict(a), status=201)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def ambulance_by_driver_email(request):
    email = request.GET.get("email", "")
    if not email:
        return JsonResponse({"error": "email parameter required"}, status=400)
    a = Ambulance.objects.filter(driver_email__iexact=email).first()
    if not a:
        return JsonResponse({"error": "Ambulance not found"}, status=404)
    return JsonResponse(ambulance_to_dict(a))


@csrf_exempt
def ambulance_detail(request, id):
    try:
        a = Ambulance.objects.get(id=id)
    except Ambulance.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(ambulance_to_dict(a))

    if request.method == "PUT":
        data = json.loads(request.body)
        a.ambulance_number  = data.get("ambulance_number",  a.ambulance_number)
        a.driver            = data.get("driver",            a.driver)
        a.driver_contact    = data.get("driver_contact",    a.driver_contact)
        a.driver_email      = data.get("driver_email",      a.driver_email)
        a.model             = data.get("model",             a.model)
        a.ambulance_contract_id = data.get("ambulance_contract_id", a.ambulance_contract_id)
        a.registration_number   = data.get("registration_number",   a.registration_number)
        a.speed             = data.get("speed",             a.speed)
        a.status            = data.get("status",            a.status)
        a.location          = data.get("location",          a.location)
        a.nearest_hospital  = data.get("nearest_hospital",  a.nearest_hospital)
        a.hospital_distance = data.get("hospital_distance", a.hospital_distance)
        a.eta_to_patient    = data.get("eta_to_patient",    a.eta_to_patient)
        a.eta_to_hospital   = data.get("eta_to_hospital",   a.eta_to_hospital)
        a.latitude          = data.get("latitude",          a.latitude)
        a.longitude         = data.get("longitude",         a.longitude)
        a.save()
        return JsonResponse(ambulance_to_dict(a))

    if request.method == "PATCH":
        data = json.loads(request.body)
        if "driver"                in data: a.driver                = data["driver"]
        if "driver_contact"        in data: a.driver_contact        = data["driver_contact"]
        if "driver_email"          in data: a.driver_email          = data["driver_email"]
        if "ambulance_contract_id" in data: a.ambulance_contract_id = data["ambulance_contract_id"]
        if "registration_number"   in data: a.registration_number   = data["registration_number"]

        new_status = data.get("status")
        if new_status:
            valid = {"available", "en_route", "busy", "offline"}
            if new_status not in valid:
                return JsonResponse({"error": f"Invalid status. Use: {valid}"}, status=400)
            a.status = new_status

        if "latitude"          in data: a.latitude          = data["latitude"]
        if "longitude"         in data: a.longitude         = data["longitude"]
        if "location"          in data: a.location          = data["location"]
        if "speed"             in data: a.speed             = data["speed"]
        if "nearest_hospital"  in data: a.nearest_hospital  = data["nearest_hospital"]
        if "hospital_distance" in data: a.hospital_distance = data["hospital_distance"]
        if "eta_to_patient"    in data: a.eta_to_patient    = data["eta_to_patient"]
        if "eta_to_hospital"   in data: a.eta_to_hospital   = data["eta_to_hospital"]

        a.save()
        return JsonResponse(ambulance_to_dict(a))

    if request.method == "DELETE":
        a.delete()
        return JsonResponse({"status": "deleted"})

    return JsonResponse({"error": "Method not allowed"}, status=405)


CHANGE_REQ_CACHE_KEY = "swiftrescue_change_requests"
CHANGE_REQ_TIMEOUT   = 86400 * 7


@csrf_exempt
def ambulance_change_request(request):
    if request.method == "GET":
        all_reqs = cache.get(CHANGE_REQ_CACHE_KEY) or []
        return JsonResponse(all_reqs, safe=False)

    if request.method == "POST":
        data = json.loads(request.body)
        data["status"] = "pending"
        all_reqs = cache.get(CHANGE_REQ_CACHE_KEY) or []
        already = any(
            r.get("driverEmail") == data.get("driverEmail") and
            r.get("newAmbId")    == data.get("newAmbId")    and
            r.get("status")      == "pending"
            for r in all_reqs
        )
        if already:
            return JsonResponse({"status": "already_pending", "message": "Your request is already pending"})
        all_reqs.insert(0, data)
        cache.set(CHANGE_REQ_CACHE_KEY, all_reqs, timeout=CHANGE_REQ_TIMEOUT)
        return JsonResponse({"status": "saved", "message": "Request sent to admin"})

    if request.method == "PATCH":
        data      = json.loads(request.body)
        timestamp = data.get("timestamp")
        action    = data.get("status")
        if action not in ("approved", "rejected"):
            return JsonResponse({"error": "status must be 'approved' or 'rejected'"}, status=400)
        all_reqs    = cache.get(CHANGE_REQ_CACHE_KEY) or []
        updated_req = None
        for r in all_reqs:
            if r.get("timestamp") == timestamp:
                r["status"] = action
                updated_req = r
                break
        if not updated_req:
            return JsonResponse({"error": "Request not found"}, status=404)
        cache.set(CHANGE_REQ_CACHE_KEY, all_reqs, timeout=CHANGE_REQ_TIMEOUT)
        if action == "approved":
            try:
                amb = Ambulance.objects.get(id=updated_req.get("newAmbId"))
                amb.driver         = updated_req.get("driverName", amb.driver)
                amb.driver_contact = updated_req.get("driverPhone", amb.driver_contact)
                amb.driver_email   = updated_req.get("driverEmail", amb.driver_email)
                amb.save()
            except Ambulance.DoesNotExist:
                pass
        driver_email  = updated_req.get("driverEmail", "")
        notif_key     = f"dr_server_notif_{driver_email}"
        driver_notifs = cache.get(notif_key) or []
        driver_notifs.insert(0, {
            "id":        f"req_{timestamp}",
            "type":      action,
            "title":     "✅ Request Approved!" if action == "approved" else "❌ Request Rejected",
            "message":   (
                f"Admin ne aapki {updated_req.get('newAmbNumber')} ambulance change request approve kar di!"
                if action == "approved"
                else f"Admin ne aapki {updated_req.get('newAmbNumber')} ambulance change request reject kar di."
            ),
            "ambNumber": updated_req.get("newAmbNumber"),
            "timestamp": timezone.now().isoformat(),
            "read":      False,
        })
        cache.set(notif_key, driver_notifs, timeout=CHANGE_REQ_TIMEOUT)
        return JsonResponse({"status": "updated", "action": action})

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def ambulance_change_request_delete(request):
    if request.method != "DELETE":
        return JsonResponse({"error": "DELETE only"}, status=405)
    data     = json.loads(request.body)
    all_reqs = cache.get(CHANGE_REQ_CACHE_KEY) or []
    if data.get("clear_all"):
        new_reqs = [r for r in all_reqs if r.get("status") == "pending"]
        cache.set(CHANGE_REQ_CACHE_KEY, new_reqs, timeout=CHANGE_REQ_TIMEOUT)
        removed = len(all_reqs) - len(new_reqs)
        return JsonResponse({"status": "deleted", "removed": removed})
    timestamp = data.get("timestamp")
    new_reqs  = [r for r in all_reqs if r.get("timestamp") != timestamp]
    if len(new_reqs) == len(all_reqs):
        return JsonResponse({"error": "Request not found"}, status=404)
    cache.set(CHANGE_REQ_CACHE_KEY, new_reqs, timeout=CHANGE_REQ_TIMEOUT)
    return JsonResponse({"status": "deleted"})


@csrf_exempt
def get_driver_notifications(request):
    if request.method == "GET":
        email     = request.GET.get("email", "")
        notif_key = f"dr_server_notif_{email}"
        notifs    = cache.get(notif_key) or []
        return JsonResponse(notifs, safe=False)
    if request.method == "POST":
        data      = json.loads(request.body)
        email     = data.get("email", "")
        notif_key = f"dr_server_notif_{email}"
        notifs    = cache.get(notif_key) or []
        updated   = [{ **n, "read": True } for n in notifs]
        cache.set(notif_key, updated, timeout=CHANGE_REQ_TIMEOUT)
        return JsonResponse({"status": "marked_read"})
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def driver_ping(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    data = json.loads(request.body)
    try:
        ambulance = Ambulance.objects.get(id=data.get("ambulance_id"))
    except Ambulance.DoesNotExist:
        return JsonResponse({"error": "Ambulance not found"}, status=404)
    DriverLocation.objects.create(
        ambulance    = ambulance,
        driver_email = data.get("driver_email", ambulance.driver_email or ""),
        latitude     = data.get("latitude"),
        longitude    = data.get("longitude"),
        speed        = data.get("speed", 0),
    )
    ambulance.latitude  = data.get("latitude")
    ambulance.longitude = data.get("longitude")
    ambulance.speed     = str(data.get("speed", 0))
    ambulance.save()
    pending_route = SuggestedRoute.objects.filter(
        ambulance=ambulance, status="pending"
    ).order_by("-created_at").first()
    response_data = {"status": "ok"}
    if pending_route:
        response_data["pending_route"] = route_to_dict(pending_route)
    return JsonResponse(response_data)


def driver_location_to_dict(dl):
    return {
        "id":           dl.id,
        "ambulance_id": dl.ambulance_id,
        "driver_email": dl.driver_email,
        "latitude":     dl.latitude,
        "longitude":    dl.longitude,
        "speed":        dl.speed,
        "timestamp":    dl.timestamp.strftime("%d %b %Y, %I:%M %p"),
    }


@csrf_exempt
def save_driver_location(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    data = json.loads(request.body)
    try:
        ambulance = Ambulance.objects.get(id=data.get("ambulance_id"))
    except Ambulance.DoesNotExist:
        return JsonResponse({"error": "Ambulance not found"}, status=404)
    dl = DriverLocation.objects.create(
        ambulance    = ambulance,
        driver_email = data.get("driver_email", ambulance.driver_email or ""),
        latitude     = data.get("latitude"),
        longitude    = data.get("longitude"),
        speed        = data.get("speed", 0),
    )
    ambulance.latitude  = data.get("latitude")
    ambulance.longitude = data.get("longitude")
    ambulance.speed     = str(data.get("speed", 0))
    ambulance.save()
    return JsonResponse(driver_location_to_dict(dl), status=201)


@csrf_exempt
def get_driver_locations(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    email = request.GET.get("email", "")
    if email:
        qs = DriverLocation.objects.filter(driver_email=email).order_by("-timestamp")[:1]
    else:
        seen = {}
        for dl in DriverLocation.objects.select_related("ambulance").order_by("-timestamp"):
            if dl.ambulance_id not in seen:
                seen[dl.ambulance_id] = dl
        qs = seen.values()
    return JsonResponse([driver_location_to_dict(dl) for dl in qs], safe=False)


@csrf_exempt
def get_location_history(request, ambulance_id):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    limit   = int(request.GET.get("limit", 50))
    history = DriverLocation.objects.filter(ambulance_id=ambulance_id).order_by("-timestamp")[:limit]
    return JsonResponse([driver_location_to_dict(dl) for dl in history], safe=False)


# Latest driver location for user live tracking.
@csrf_exempt
def get_driver_location_by_ambulance(request):
    """
    GET /api/driver/location/?ambulance_id=<id>
    Returns the driver's latest location.
    UserBookingMap.jsx uses this API for live tracking.
    """
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)

    ambulance_id = request.GET.get("ambulance_id")
    if not ambulance_id:
        return JsonResponse({"error": "ambulance_id parameter required"}, status=400)

    try:
        # Latest record from DriverLocation.
        dl = DriverLocation.objects.filter(
            ambulance_id=ambulance_id
        ).order_by("-timestamp").first()

        if not dl:
            # Fallback: check latitude/longitude directly on the Ambulance table.
            try:
                amb = Ambulance.objects.get(id=ambulance_id)
                if amb.latitude and amb.longitude:
                    return JsonResponse({
                        "ambulance_id":     amb.id,
                        "latitude":         float(amb.latitude),
                        "longitude":        float(amb.longitude),
                        "speed":            amb.speed or 0,
                        "driver_email":     amb.driver_email or "",
                        "driver_name":      amb.driver or "",
                        "ambulance_number": amb.ambulance_number or "",
                        "timestamp":        amb.last_updated.isoformat(),
                        "source":           "ambulance_table",
                    })
            except Ambulance.DoesNotExist:
                pass
            return JsonResponse({"error": "No location found for this ambulance"}, status=404)

        # Fetch driver details from the Ambulance record.
        try:
            amb              = Ambulance.objects.get(id=ambulance_id)
            driver_name      = amb.driver or ""
            ambulance_number = amb.ambulance_number or ""
            driver_contact   = amb.driver_contact or ""
        except Ambulance.DoesNotExist:
            driver_name      = ""
            ambulance_number = ""
            driver_contact   = ""

        return JsonResponse({
            "ambulance_id":     dl.ambulance_id,
            "latitude":         float(dl.latitude)  if dl.latitude  else None,
            "longitude":        float(dl.longitude) if dl.longitude else None,
            "speed":            dl.speed or 0,
            "driver_email":     dl.driver_email or "",
            "driver_name":      driver_name,
            "driver_contact":   driver_contact,
            "ambulance_number": ambulance_number,
            "timestamp":        dl.timestamp.isoformat(),
            "source":           "driver_location_table",
        })

    except Exception as e:
        logger.error(f"get_driver_location_by_ambulance error: {e}")
        return JsonResponse({"error": str(e)}, status=500)


def route_to_dict(r):
    return {
        "id":               r.id,
        "ambulance_id":     r.ambulance_id,
        "pickup_location":  r.pickup_location,
        "destination":      r.destination,
        "polyline":         r.polyline,
        "distance_km":      r.distance_km,
        "duration":         r.duration,
        "status":           r.status,
        "created_at":       r.created_at.strftime("%d %b %Y, %I:%M %p"),
        "accepted_at":      r.accepted_at.strftime("%d %b %Y, %I:%M %p") if r.accepted_at else None,
        "completed_at":     r.completed_at.strftime("%d %b %Y, %I:%M %p") if r.completed_at else None,
    }


@csrf_exempt
def save_suggested_route(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    data = json.loads(request.body)
    try:
        ambulance = Ambulance.objects.get(id=data.get("ambulance_id"))
    except Ambulance.DoesNotExist:
        return JsonResponse({"error": "Ambulance not found"}, status=404)
    route = SuggestedRoute.objects.create(
        ambulance       = ambulance,
        pickup_location = data.get("pickup_location", ""),
        destination     = data.get("destination", ""),
        polyline        = data.get("polyline", ""),
        distance_km     = data.get("distance_km", ""),
        duration        = data.get("duration", ""),
        status          = "pending",
    )
    return JsonResponse(route_to_dict(route), status=201)


@csrf_exempt
def update_route_status(request, route_id):
    if request.method != "PATCH":
        return JsonResponse({"error": "PATCH only"}, status=405)
    try:
        route = SuggestedRoute.objects.get(id=route_id)
    except SuggestedRoute.DoesNotExist:
        return JsonResponse({"error": "Route not found"}, status=404)
    data       = json.loads(request.body)
    new_status = data.get("status")
    valid      = {"pending", "accepted", "rejected", "completed"}
    if new_status not in valid:
        return JsonResponse({"error": f"Invalid status. Use: {valid}"}, status=400)
    route.status = new_status
    if new_status == "accepted":
        route.accepted_at = timezone.now()
    elif new_status == "completed":
        route.completed_at = timezone.now()
    route.save()
    return JsonResponse(route_to_dict(route))



@csrf_exempt
def get_suggested_routes(request, ambulance_id):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    status = request.GET.get("status", "")
    qs = SuggestedRoute.objects.filter(ambulance_id=ambulance_id)
    if status:
        qs = qs.filter(status=status)
    return JsonResponse([route_to_dict(r) for r in qs], safe=False)


@csrf_exempt
def get_active_routes(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    routes = SuggestedRoute.objects.filter(
        status__in=["pending", "accepted"]
    ).select_related("ambulance")
    return JsonResponse([route_to_dict(r) for r in routes], safe=False)


@csrf_exempt
def sync_user(request):
    """
    POST: Store logged-in user details — ALL roles (user, driver, hospital, staff, admin).
    Creates/updates Django auth.User + UserProfile with all columns.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    email = str(data.get("email", "")).strip().lower()
    if not email:
        return JsonResponse({"error": "Email is required"}, status=400)

    name                = str(data.get("name", "")).strip()
    role                = str(data.get("role", "user")).strip().lower()
    phone               = str(data.get("phone", "")).strip()
    ambulance_id        = data.get("ambulance_id")
    ambulance_number    = str(data.get("ambulance_number", "")).strip()
    contract_id         = str(data.get("contract_id", "")).strip()
    registration_number = str(data.get("registration_number", "")).strip()
    hospital_id         = data.get("hospital_id")
    hospital_name       = str(data.get("hospital_name", "")).strip()
    staff_id            = str(data.get("staff_id", "")).strip()
    staff_role          = str(data.get("staff_role", "")).strip()
    ip = (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
          or request.META.get("REMOTE_ADDR") or None)

    from django.contrib.auth.models import User
    from django.utils import timezone
    from ambulance.models import UserProfile

    # 1. Sync Django auth.User
    auth_user, _ = User.objects.get_or_create(username=email, defaults={"email": email, "first_name": name})
    if name: auth_user.first_name = name
    if email: auth_user.email = email
    auth_user.last_login = timezone.now()
    auth_user.save()

    # 2. Upsert UserProfile — all columns
    profile, created = UserProfile.objects.get_or_create(
        email=email,
        defaults={
            "name": name, "phone": phone, "role": role,
            "ambulance_id": ambulance_id, "ambulance_number": ambulance_number,
            "contract_id": contract_id, "registration_number": registration_number,
            "hospital_id": hospital_id, "hospital_name": hospital_name,
            "staff_id": staff_id, "staff_role": staff_role,
            "last_login_ip": ip, "login_count": 1,
        }
    )
    if not created:
        update_fields = {"last_login_ip": ip, "login_count": profile.login_count + 1}
        if name:  update_fields["name"] = name
        if phone: update_fields["phone"] = phone
        if role:  update_fields["role"] = role
        if ambulance_id:     update_fields["ambulance_id"] = ambulance_id
        if ambulance_number: update_fields["ambulance_number"] = ambulance_number
        if contract_id:      update_fields["contract_id"] = contract_id
        if registration_number: update_fields["registration_number"] = registration_number
        if hospital_id:   update_fields["hospital_id"] = hospital_id
        if hospital_name: update_fields["hospital_name"] = hospital_name
        if staff_id:   update_fields["staff_id"] = staff_id
        if staff_role: update_fields["staff_role"] = staff_role
        UserProfile.objects.filter(email=email).update(**update_fields)
        profile.refresh_from_db()

    return JsonResponse({
        "success": True,
        "created": created,
        "profile": {
            "id": profile.id,
            "email": email,
            "name": profile.name,
            "role": role,
            "login_count": profile.login_count,
        }
    })