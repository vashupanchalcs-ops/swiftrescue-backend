import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from ambulance.models import Ambulance
from hospitals.models import Hospital

from .models import Booking, BookingChatMessage, BookingChatThread, VoiceBookingCall


def _json_body(request):
    try:
        return json.loads(request.body or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _iso(value):
    return value.isoformat() if value else None


def _ensure_chat_thread(booking):
    ambulance = Ambulance.objects.filter(id=booking.ambulance_id).first()
    thread, _ = BookingChatThread.objects.get_or_create(
        booking=booking,
        defaults={
            "user_email": booking.booked_by_email or "",
            "user_name": booking.patient_name or booking.booked_by or "",
            "driver_email": ambulance.driver_email if ambulance else "",
            "driver_name": booking.driver or "",
        },
    )
    return thread


def _push_system_message(booking, message, message_type="update"):
    thread = _ensure_chat_thread(booking)
    chat_message = BookingChatMessage.objects.create(
        thread=thread,
        sender_role="system",
        sender_name="SwiftRescue",
        message_type=message_type,
        message=message,
    )
    thread.last_message_at = chat_message.created_at
    thread.save(update_fields=["last_message_at", "updated_at"])
    return chat_message


def _message_to_dict(message):
    return {
        "id": message.id,
        "thread_id": message.thread_id,
        "sender_role": message.sender_role,
        "sender_name": message.sender_name,
        "message_type": message.message_type,
        "message": message.message,
        "metadata": message.metadata,
        "seen_by_user": message.seen_by_user,
        "seen_by_driver": message.seen_by_driver,
        "seen_by_admin": message.seen_by_admin,
        "created_at": _iso(message.created_at),
    }


def _thread_to_dict(thread):
    return {
        "id": thread.id,
        "booking_id": thread.booking_id,
        "user_email": thread.user_email,
        "user_name": thread.user_name,
        "driver_email": thread.driver_email,
        "driver_name": thread.driver_name,
        "admin_email": thread.admin_email,
        "is_active": thread.is_active,
        "presence": {
            "user_online": thread.user_online,
            "driver_online": thread.driver_online,
            "admin_online": thread.admin_online,
            "user_typing": thread.user_typing,
            "driver_typing": thread.driver_typing,
            "admin_typing": thread.admin_typing,
        },
        "last_message_at": _iso(thread.last_message_at),
        "updated_at": _iso(thread.updated_at),
    }


def booking_to_dict(booking):
    ambulance = Ambulance.objects.filter(id=booking.ambulance_id).first()
    chat_thread = BookingChatThread.objects.filter(booking=booking).only("id").first()
    return {
        "id": booking.id,
        "ambulance_id": booking.ambulance_id,
        "ambulance_number": booking.ambulance_number,
        "driver": booking.driver,
        "driver_email": ambulance.driver_email if ambulance else "",
        "driver_contact": booking.driver_contact,
        "booked_by": booking.booked_by,
        "booked_by_email": booking.booked_by_email,
        "patient_name": booking.patient_name,
        "patient_age": booking.patient_age,
        "patient_gender": booking.patient_gender,
        "patient_contact_number": booking.patient_contact_number,
        "attendant_name": booking.attendant_name,
        "attendant_contact": booking.attendant_contact,
        "pickup_location": booking.pickup_location,
        "pickup_latitude": booking.pickup_latitude,
        "pickup_longitude": booking.pickup_longitude,
        "pickup_landmark": booking.pickup_landmark,
        "pickup_city": booking.pickup_city,
        "pickup_district": booking.pickup_district,
        "destination": booking.destination,
        "assigned_hospital_id": booking.assigned_hospital_id,
        "assigned_hospital_name": booking.assigned_hospital_name,
        "assigned_hospital_address": booking.assigned_hospital_address,
        "assigned_hospital_contact": booking.assigned_hospital_contact,
        "assigned_hospital_email": booking.assigned_hospital_email,
        "hospital_assigned_at": _iso(booking.hospital_assigned_at),
        "hospital_alert_sent": booking.hospital_alert_sent,
        "hospital_alert_sent_at": _iso(booking.hospital_alert_sent_at),
        "hospital_response": booking.hospital_response,
        "hospital_response_note": booking.hospital_response_note,
        "hospital_responded_at": _iso(booking.hospital_responded_at),
        "patient_condition": booking.patient_condition,
        "vitals_summary": booking.vitals_summary,
        "driver_voice_transcript": booking.driver_voice_transcript,
        "driver_modified_report": booking.driver_modified_report,
        "driver_report_sent_at": _iso(booking.driver_report_sent_at),
        "report_submitted_by": booking.report_submitted_by,
        "report_submitted_at": _iso(booking.report_submitted_at),
        "report_sent_to_hospital": booking.report_sent_to_hospital,
        "report_sent_to_hospital_at": _iso(booking.report_sent_to_hospital_at),
        "insurance_full_name": booking.insurance_full_name,
        "insurance_dob": booking.insurance_dob,
        "insurance_gender": booking.insurance_gender,
        "insurance_provider": booking.insurance_provider,
        "insurance_policy_member_id": booking.insurance_policy_member_id,
        "insurance_policy_holder_name": booking.insurance_policy_holder_name,
        "insurance_government_id": booking.insurance_government_id,
        "insurance_sum_insured": booking.insurance_sum_insured,
        "insurance_emergency_nature": booking.insurance_emergency_nature,
        "insurance_exclusions_waiting": booking.insurance_exclusions_waiting,
        "insurance_status": booking.insurance_status,
        "insurance_hospital_note": booking.insurance_hospital_note,
        "insurance_submitted_by": booking.insurance_submitted_by,
        "insurance_submitted_at": _iso(booking.insurance_submitted_at),
        "insurance_reviewed_by": booking.insurance_reviewed_by,
        "insurance_reviewed_at": _iso(booking.insurance_reviewed_at),
        "status": booking.status,
        "sent_to_driver": booking.sent_to_driver,
        "sent_to_driver_at": _iso(booking.sent_to_driver_at),
        "driver_task_completed": booking.driver_task_completed,
        "driver_task_completed_at": _iso(booking.driver_task_completed_at),
        "driver_rejected_once": booking.driver_rejected_once,
        "driver_rejected_at": _iso(booking.driver_rejected_at),
        "driver_rejection_reason": booking.driver_rejection_reason,
        "reassigned_due_to_unavailability": booking.reassigned_due_to_unavailability,
        "reassigned_at": _iso(booking.reassigned_at),
        "created_at": _iso(booking.created_at),
        "is_read": booking.is_read,
        "chat_thread_id": chat_thread.id if chat_thread else None,
    }


@csrf_exempt
def booking_list(request):
    if request.method == "GET":
        bookings = Booking.objects.all().order_by("-created_at")
        return JsonResponse([booking_to_dict(booking) for booking in bookings], safe=False)

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    ambulance_id = _to_int(data.get("ambulance_id"))
    ambulance = Ambulance.objects.filter(id=ambulance_id).first()
    booking = Booking.objects.create(
        ambulance_id=ambulance_id,
        ambulance_number=data.get("ambulance_number") or (ambulance.ambulance_number if ambulance else ""),
        driver=data.get("driver") or (ambulance.driver if ambulance else ""),
        driver_contact=data.get("driver_contact") or (ambulance.driver_contact if ambulance else ""),
        booked_by=str(data.get("booked_by", "")).strip(),
        booked_by_email=str(data.get("booked_by_email", "")).strip(),
        patient_name=str(data.get("patient_name", "")).strip(),
        patient_age=str(data.get("patient_age", "")).strip(),
        patient_gender=str(data.get("patient_gender", "")).strip(),
        patient_contact_number=str(data.get("patient_contact_number", "")).strip(),
        attendant_name=str(data.get("attendant_name", "")).strip(),
        attendant_contact=str(data.get("attendant_contact", "")).strip(),
        pickup_location=str(data.get("pickup_location", "")).strip(),
        pickup_latitude=_to_float(data.get("pickup_latitude")),
        pickup_longitude=_to_float(data.get("pickup_longitude")),
        pickup_landmark=str(data.get("pickup_landmark", "")).strip(),
        pickup_city=str(data.get("pickup_city", "")).strip(),
        pickup_district=str(data.get("pickup_district", "")).strip(),
        destination=str(data.get("destination", "")).strip(),
    )
    _ensure_chat_thread(booking)
    _push_system_message(booking, f"Booking #{booking.id} created and queued for dispatch.")
    return JsonResponse(booking_to_dict(booking), status=201)


@csrf_exempt
def booking_detail(request, id):
    try:
        booking = Booking.objects.get(id=id)
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(booking_to_dict(booking))
    if request.method == "DELETE":
        booking.delete()
        return JsonResponse({"status": "deleted"})
    if request.method != "PATCH":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    changed_messages = []
    editable_fields = (
        "patient_name", "patient_age", "patient_gender", "patient_contact_number", "attendant_name",
        "attendant_contact", "pickup_location", "pickup_landmark", "pickup_city", "pickup_district",
        "destination", "patient_condition", "vitals_summary", "driver_voice_transcript", "driver_modified_report",
        "report_submitted_by", "insurance_full_name", "insurance_dob", "insurance_gender", "insurance_provider",
        "insurance_policy_member_id", "insurance_policy_holder_name", "insurance_government_id", "insurance_sum_insured",
        "insurance_emergency_nature", "insurance_exclusions_waiting", "insurance_status", "insurance_hospital_note",
        "insurance_submitted_by", "insurance_reviewed_by",
    )
    for field in editable_fields:
        if field in data:
            setattr(booking, field, data[field])

    for field in ("pickup_latitude", "pickup_longitude"):
        if field in data:
            setattr(booking, field, _to_float(data[field]))
    if "is_read" in data:
        booking.is_read = _to_bool(data["is_read"])

    ambulance_value = data.get("assign_ambulance_id", data.get("reassign_ambulance_id"))
    if ambulance_value is not None:
        ambulance = Ambulance.objects.filter(id=_to_int(ambulance_value, -1)).first()
        if not ambulance:
            return JsonResponse({"error": "Valid ambulance required for assignment"}, status=400)
        if ambulance.id != booking.ambulance_id and ambulance.status != "available":
            return JsonResponse({"error": "Selected ambulance is not available"}, status=400)
        old_ambulance_id = booking.ambulance_id
        booking.ambulance_id = ambulance.id
        booking.ambulance_number = ambulance.ambulance_number or ""
        booking.driver = ambulance.driver or ""
        booking.driver_contact = ambulance.driver_contact or ""
        booking.sent_to_driver = _to_bool(data.get("send_to_driver"), True)
        booking.sent_to_driver_at = timezone.now() if booking.sent_to_driver else None
        ambulance.status = "en_route"
        ambulance.save(update_fields=["status"])
        if old_ambulance_id and old_ambulance_id != ambulance.id:
            Ambulance.objects.filter(id=old_ambulance_id, status="en_route").update(status="available")
        changed_messages.append(f"Ambulance {booking.ambulance_number} assigned to Booking #{booking.id}.")

    if "assign_hospital_id" in data:
        hospital = Hospital.objects.filter(id=_to_int(data["assign_hospital_id"], -1), is_active=True).first()
        if not hospital:
            return JsonResponse({"error": "Valid active hospital required"}, status=400)
        booking.assigned_hospital_id = hospital.id
        booking.assigned_hospital_name = hospital.name or ""
        booking.assigned_hospital_address = hospital.address or ""
        booking.assigned_hospital_contact = hospital.contact_number or ""
        booking.assigned_hospital_email = hospital.email or ""
        booking.hospital_assigned_at = timezone.now()
        booking.destination = hospital.name or booking.destination
        booking.hospital_response = "pending"
        booking.hospital_response_note = "Awaiting hospital readiness response."
        booking.hospital_responded_at = None
        booking.hospital_alert_sent = _to_bool(data.get("send_hospital_alert"), True)
        booking.hospital_alert_sent_at = timezone.now() if booking.hospital_alert_sent else None
        changed_messages.append(f"Hospital {hospital.name} assigned to Booking #{booking.id}.")

    if "status" in data:
        new_status = str(data["status"]).lower().strip()
        valid_statuses = {choice[0] for choice in Booking.STATUS_CHOICES}
        if new_status not in valid_statuses:
            return JsonResponse({"error": f"Invalid status. Use: {sorted(valid_statuses)}"}, status=400)
        booking.status = new_status
        if new_status in {"completed", "cancelled"}:
            Ambulance.objects.filter(id=booking.ambulance_id).update(status="available")
        elif new_status == "confirmed":
            Ambulance.objects.filter(id=booking.ambulance_id).update(status="en_route")
        changed_messages.append(f"Booking status changed to {new_status}.")

    if _to_bool(data.get("driver_task_complete")):
        booking.driver_task_completed = True
        booking.driver_task_completed_at = timezone.now()
        booking.status = "completed"
        Ambulance.objects.filter(id=booking.ambulance_id).update(status="available")
        changed_messages.append(f"Driver completed Booking #{booking.id}.")

    booking.save()
    for message in changed_messages:
        _push_system_message(booking, message)
    return JsonResponse(booking_to_dict(booking))


@csrf_exempt
def booking_hospital_response(request, id):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    response = str(data.get("hospital_response", "")).strip().lower()
    if response not in {"ready", "not_ready"}:
        return JsonResponse({"error": "hospital_response must be ready or not_ready"}, status=400)
    try:
        booking = Booking.objects.get(id=id)
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)
    if not booking.assigned_hospital_id:
        return JsonResponse({"error": "Assign a hospital before responding"}, status=400)
    booking.hospital_response = response
    booking.hospital_response_note = str(data.get("hospital_response_note", "")).strip()
    booking.hospital_responded_at = timezone.now()
    booking.save(update_fields=["hospital_response", "hospital_response_note", "hospital_responded_at"])
    _push_system_message(booking, f"Hospital response: {response.replace('_', ' ')}.")
    return JsonResponse(booking_to_dict(booking))


@csrf_exempt
def unread_count(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    return JsonResponse({"unread": Booking.objects.filter(is_read=False).count()})


@csrf_exempt
def mark_all_read(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    Booking.objects.filter(is_read=False).update(is_read=True)
    return JsonResponse({"status": "ok"})


@csrf_exempt
def chat_threads(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    role = str(request.GET.get("role", "admin")).strip().lower()
    email = str(request.GET.get("email", "")).strip()
    if role == "admin":
        for booking in Booking.objects.all().iterator():
            _ensure_chat_thread(booking)
        threads = BookingChatThread.objects.select_related("booking").all()
    elif role == "user" and email:
        threads = BookingChatThread.objects.select_related("booking").filter(user_email__iexact=email)
    elif role == "driver" and email:
        threads = BookingChatThread.objects.select_related("booking").filter(driver_email__iexact=email)
    else:
        return JsonResponse({"error": "A valid role and email are required"}, status=400)
    return JsonResponse([_thread_to_dict(thread) for thread in threads.order_by("-updated_at")], safe=False)


@csrf_exempt
def booking_chat_thread(request, booking_id):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    try:
        booking = Booking.objects.get(id=booking_id)
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Booking not found"}, status=404)
    return JsonResponse(_thread_to_dict(_ensure_chat_thread(booking)))


@csrf_exempt
def chat_messages(request, thread_id):
    try:
        thread = BookingChatThread.objects.select_related("booking").get(id=thread_id)
    except BookingChatThread.DoesNotExist:
        return JsonResponse({"error": "Thread not found"}, status=404)
    if request.method == "GET":
        return JsonResponse({"thread": _thread_to_dict(thread), "messages": [_message_to_dict(message) for message in thread.messages.all()]})
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    sender_role = str(data.get("sender_role", "")).strip().lower()
    if sender_role not in {"admin", "driver", "user"}:
        return JsonResponse({"error": "sender_role must be admin, driver, or user"}, status=400)
    message_text = str(data.get("message", "")).strip()
    if not message_text:
        return JsonResponse({"error": "message is required"}, status=400)
    message = BookingChatMessage.objects.create(
        thread=thread,
        sender_role=sender_role,
        sender_name=str(data.get("sender_name", "")).strip() or sender_role.title(),
        message_type=str(data.get("message_type", "text")).strip().lower(),
        message=message_text,
        metadata=json.dumps(data.get("metadata", {})) if isinstance(data.get("metadata"), dict) else str(data.get("metadata", "")),
    )
    thread.last_message_at = message.created_at
    thread.save(update_fields=["last_message_at", "updated_at"])
    return JsonResponse(_message_to_dict(message), status=201)


@csrf_exempt
def chat_presence(request, thread_id):
    if request.method != "PATCH":
        return JsonResponse({"error": "PATCH only"}, status=405)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    try:
        thread = BookingChatThread.objects.get(id=thread_id)
    except BookingChatThread.DoesNotExist:
        return JsonResponse({"error": "Thread not found"}, status=404)
    role = str(data.get("role", "")).strip().lower()
    if role not in {"admin", "driver", "user"}:
        return JsonResponse({"error": "role must be admin, driver, or user"}, status=400)
    if "online" in data:
        setattr(thread, f"{role}_online", _to_bool(data["online"]))
        setattr(thread, f"{role}_last_seen_at", timezone.now())
    if "typing" in data:
        setattr(thread, f"{role}_typing", _to_bool(data["typing"]))
    thread.save()
    return JsonResponse(_thread_to_dict(thread))


@csrf_exempt
def chat_mark_read(request, thread_id):
    if request.method != "PATCH":
        return JsonResponse({"error": "PATCH only"}, status=405)
    data = _json_body(request)
    role = str((data or {}).get("role", "")).strip().lower()
    if role not in {"admin", "driver", "user"}:
        return JsonResponse({"error": "role must be admin, driver, or user"}, status=400)
    try:
        thread = BookingChatThread.objects.get(id=thread_id)
    except BookingChatThread.DoesNotExist:
        return JsonResponse({"error": "Thread not found"}, status=404)
    thread.messages.exclude(sender_role=role).update(**{f"seen_by_{role}": True})
    return JsonResponse({"status": "ok"})


@csrf_exempt
def chat_driver_request(request, thread_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    try:
        thread = BookingChatThread.objects.get(id=thread_id)
    except BookingChatThread.DoesNotExist:
        return JsonResponse({"error": "Thread not found"}, status=404)
    message_text = str(data.get("message", "")).strip()
    if not message_text:
        return JsonResponse({"error": "message is required"}, status=400)
    message = BookingChatMessage.objects.create(
        thread=thread,
        sender_role="driver",
        sender_name=thread.driver_name or "Driver",
        message_type="request",
        message=message_text,
        metadata=json.dumps({"target_role": "admin", "issue_type": data.get("issue_type", "route_issue")}),
    )
    thread.last_message_at = message.created_at
    thread.save(update_fields=["last_message_at", "updated_at"])
    return JsonResponse(_message_to_dict(message), status=201)


@csrf_exempt
def voice_call_alert(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    active_calls = VoiceBookingCall.objects.filter(call_status__in=["ringing", "in_progress"]).order_by("-updated_at")
    latest = active_calls.first()
    return JsonResponse(
        {
            "is_active_call": latest is not None,
            "active_count": active_calls.count(),
            "latest_call": {
                "call_sid": latest.call_sid if latest else "",
                "from_number": latest.from_number if latest else "",
                "step": latest.current_step if latest else "",
                "updated_at": _iso(latest.updated_at) if latest else None,
            },
        }
    )
