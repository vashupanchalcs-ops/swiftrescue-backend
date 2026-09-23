import base64
import json
import threading

from django.core.mail import send_mail
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from ambulance.models import Ambulance
from hospitals.models import Hospital, HospitalStaff

from .models import Booking, BookingChatMessage, BookingChatThread, PatientConditionPhoto, VideoCallRequest, VoiceBookingCall


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


def _send_mail_background(subject, message, recipient_list, label="email"):
    recipients = [str(item).strip() for item in (recipient_list or []) if str(item or "").strip()]
    if not recipients:
        return

    def _worker():
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email="vashupanchal.cs@gmail.com",
                recipient_list=recipients,
                fail_silently=True,
            )
        except Exception as exc:
            print(f"{label} error:", exc)

    threading.Thread(target=_worker, daemon=True).start()


def _ensure_chat_thread(booking):
    ambulance = Ambulance.objects.filter(id=booking.ambulance_id).first()
    thread, _ = BookingChatThread.objects.get_or_create(
        booking=booking,
        defaults={
            "user_email": booking.booked_by_email or "",
            "user_name": booking.patient_name or booking.booked_by or "",
            "driver_email": (ambulance.driver_email or "") if ambulance else "",
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


_LOOKUP_NOT_PROVIDED = object()


def booking_to_dict(booking, *, ambulance=_LOOKUP_NOT_PROVIDED, chat_thread=_LOOKUP_NOT_PROVIDED):
    # List endpoints pass bulk-fetched related rows to avoid one database
    # query per booking. Detail endpoints keep the lazy lookup behaviour.
    if ambulance is _LOOKUP_NOT_PROVIDED:
        ambulance = Ambulance.objects.filter(id=booking.ambulance_id).first()
    if chat_thread is _LOOKUP_NOT_PROVIDED:
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
        "payment_status": getattr(booking, "payment_status", "due"),
        "payment_total": float(booking.payment_total) if getattr(booking, "payment_total", None) is not None else None,
        "payment_amount_due": float(booking.payment_amount_due) if getattr(booking, "payment_amount_due", None) is not None else None,
        "payment_note": getattr(booking, "payment_note", ""),
        "payment_updated_at": _iso(getattr(booking, "payment_updated_at", None)),
        "sent_to_driver": booking.sent_to_driver,
        "sent_to_driver_at": _iso(booking.sent_to_driver_at),
        "driver_task_completed": booking.driver_task_completed,
        "driver_task_completed_at": _iso(booking.driver_task_completed_at),
        "driver_rejected_once": booking.driver_rejected_once,
        "driver_rejected_at": _iso(booking.driver_rejected_at),
        "driver_rejection_reason": booking.driver_rejection_reason,
        "driver_accepted": getattr(booking, "driver_accepted", False),
        "driver_accepted_at": _iso(booking.driver_accepted_at),
        "driver_status": getattr(booking, "driver_status", "pending"),
        "patient_reached": getattr(booking, "patient_reached", False),
        "patient_reached_at": _iso(booking.patient_reached_at),
        "reassigned_due_to_unavailability": booking.reassigned_due_to_unavailability,
        "reassigned_at": _iso(booking.reassigned_at),
        "created_at": _iso(booking.created_at),
        "is_read": booking.is_read,
        "is_user_selected_hospital": getattr(booking, "is_user_selected_hospital", False),
        "transfer_requested": getattr(booking, "transfer_requested", False),
        "transfer_requested_at": _iso(getattr(booking, "transfer_requested_at", None)),
        "transfer_status": getattr(booking, "transfer_status", ""),
        "transfer_target_ambulance_id": getattr(booking, "transfer_target_ambulance_id", None),
        "transfer_target_ambulance_number": getattr(booking, "transfer_target_ambulance_number", ""),
        "transfer_from_ambulance_id": getattr(booking, "transfer_from_ambulance_id", None),
        "transfer_from_ambulance_number": getattr(booking, "transfer_from_ambulance_number", ""),
        "transfer_from_driver_email": getattr(booking, "transfer_from_driver_email", ""),
        "transfer_from_driver_name": getattr(booking, "transfer_from_driver_name", ""),
        "transferred_to_ambulance_id": getattr(booking, "transferred_to_ambulance_id", None),
        "transferred_to_ambulance_number": getattr(booking, "transferred_to_ambulance_number", ""),
        "transfer_approved_at": _iso(getattr(booking, "transfer_approved_at", None)),
        "transfer_rejected_at": _iso(getattr(booking, "transfer_rejected_at", None)),
        "assigned_doctors_json": getattr(booking, "assigned_doctors_json", "[]"),
        "assigned_doctor_names": getattr(booking, "assigned_doctor_names", ""),
        "assigned_doctor_specializations": getattr(booking, "assigned_doctor_specializations", ""),
        "assigned_doctor_contacts": getattr(booking, "assigned_doctor_contacts", ""),
        "doctors_assigned_at": _iso(getattr(booking, "doctors_assigned_at", None)),
        "assigned_bed_id": getattr(booking, "assigned_bed_id", None),
        "assigned_bed_number": getattr(booking, "assigned_bed_number", ""),
        "assigned_bed_type": getattr(booking, "assigned_bed_type", "general"),
        "icu_required": getattr(booking, "icu_required", False),
        "icu_requested_at": _iso(getattr(booking, "icu_requested_at", None)),
        "chat_thread_id": chat_thread.id if chat_thread else None,
    }


@csrf_exempt
def booking_list(request):
    if request.method == "GET":
        # Fast retrieval: latest 100 active cases for rapid JSON serialization & low payload
        bookings = Booking.objects.all().order_by("-created_at")[:100]
        booking_rows = list(bookings)
        ambulance_ids = {booking.ambulance_id for booking in booking_rows if booking.ambulance_id}
        booking_ids = {booking.id for booking in booking_rows}
        ambulance_map = {
            ambulance.id: ambulance
            for ambulance in Ambulance.objects.filter(id__in=ambulance_ids)
        }
        thread_map = {
            thread.booking_id: thread
            for thread in BookingChatThread.objects.filter(booking_id__in=booking_ids).only("id", "booking_id")
        }
        return JsonResponse([
            booking_to_dict(
                booking,
                ambulance=ambulance_map.get(booking.ambulance_id),
                chat_thread=thread_map.get(booking.id),
            )
            for booking in booking_rows
        ], safe=False)

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    ambulance_id = _to_int(data.get("ambulance_id"))
    ambulance = Ambulance.objects.filter(id=ambulance_id).first()

    user_hospital_id = _to_int(data.get("user_selected_hospital_id") or data.get("assigned_hospital_id"))
    user_hospital = Hospital.objects.filter(id=user_hospital_id, is_active=True).first() if user_hospital_id > 0 else None
    is_user_selected = _to_bool(data.get("is_user_selected_hospital")) or (user_hospital is not None)

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
        destination=str(data.get("destination", "")).strip() or (user_hospital.name if user_hospital else ""),
        is_user_selected_hospital=is_user_selected,
        assigned_hospital_id=user_hospital.id if user_hospital else None,
        assigned_hospital_name=user_hospital.name if user_hospital else "",
        assigned_hospital_address=user_hospital.address if user_hospital else "",
        assigned_hospital_contact=user_hospital.contact_number if user_hospital else "",
        assigned_hospital_email=user_hospital.email if user_hospital else "",
        hospital_assigned_at=timezone.now() if user_hospital else None,
        hospital_response="pending" if user_hospital else "",
        hospital_response_note="Awaiting hospital approval for user-selected booking." if user_hospital else "",
        hospital_alert_sent=_to_bool(data.get("send_hospital_alert"), False),
        hospital_alert_sent_at=timezone.now() if _to_bool(data.get("send_hospital_alert"), False) else None,
    )
    _ensure_chat_thread(booking)
    _push_system_message(booking, f"Booking #{booking.id} created and queued for dispatch.")
    return JsonResponse(booking_to_dict(booking), status=201)


@csrf_exempt
@transaction.atomic
def booking_detail(request, id):
    try:
        # Assignment actions can arrive together from the admin UI and the
        # polling clients. Serialize the booking row so the last request
        # cannot silently overwrite a partially applied assignment.
        booking = Booking.objects.select_for_update().get(id=id)
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
        ambulance = Ambulance.objects.select_for_update().filter(id=_to_int(ambulance_value, -1)).first()
        if not ambulance:
            return JsonResponse({"error": "Valid ambulance required for assignment"}, status=400)
        if ambulance.id != booking.ambulance_id and ambulance.status != "available":
            return JsonResponse({"error": "Selected ambulance is not available"}, status=400)
        old_ambulance_id = booking.ambulance_id
        booking.ambulance_id = ambulance.id
        booking.ambulance_number = ambulance.ambulance_number or ""
        booking.driver = ambulance.driver or ""
        booking.driver_contact = ambulance.driver_contact or ""
        is_reassign = bool(booking.transfer_requested or booking.driver_rejected_once or data.get("reassign_ambulance_id"))
        booking.sent_to_driver = _to_bool(data.get("send_to_driver"), True) if is_reassign else _to_bool(data.get("send_to_driver"), False)
        booking.sent_to_driver_at = timezone.now() if booking.sent_to_driver else None
        if booking.transfer_requested:
            booking.transferred_to_ambulance_id = ambulance.id
            booking.transferred_to_ambulance_number = ambulance.ambulance_number or ""
            booking.transfer_status = "completed"
            booking.transfer_approved_at = timezone.now()
        if is_reassign:
            booking.driver_accepted = False
            booking.driver_accepted_at = None
            booking.driver_status = "pending"
            booking.driver_rejected_once = False
            booking.patient_reached = False
            booking.patient_reached_at = None
        ambulance.status = "en_route"
        ambulance.save(update_fields=["status"])
        if old_ambulance_id and old_ambulance_id != ambulance.id:
            Ambulance.objects.filter(id=old_ambulance_id).update(status="available")
        changed_messages.append(f"Ambulance {booking.ambulance_number} assigned to Booking #{booking.id}.")

    if "is_user_selected_hospital" in data:
        booking.is_user_selected_hospital = _to_bool(data["is_user_selected_hospital"])

    if "assign_hospital_id" in data:
        hospital = Hospital.objects.select_for_update().filter(id=_to_int(data["assign_hospital_id"], -1), is_active=True).first()
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
    elif "send_hospital_alert" in data and booking.assigned_hospital_id:
        should_send = _to_bool(data["send_hospital_alert"])
        booking.hospital_alert_sent = should_send
        booking.hospital_alert_sent_at = timezone.now() if should_send else None
        if should_send:
            booking.hospital_response = "pending"
            booking.hospital_response_note = "Awaiting hospital readiness response."
            booking.hospital_responded_at = None
            changed_messages.append(f"Request alert sent to hospital {booking.assigned_hospital_name}.")

    if "send_to_driver" in data and ambulance_value is None:
        send_to_driver_val = _to_bool(data["send_to_driver"])
        if send_to_driver_val:
            if booking.status != "confirmed":
                return JsonResponse({"error": "Booking must be confirmed before sending to driver"}, status=400)
            if not booking.assigned_hospital_name:
                return JsonResponse({"error": "Assign hospital before sending booking to driver"}, status=400)
            if booking.hospital_response != "ready":
                return JsonResponse({"error": "Hospital must be ready before sending booking to driver"}, status=400)
            if not booking.ambulance_id:
                return JsonResponse({"error": "Assign ambulance before sending booking to driver"}, status=400)

            if not booking.sent_to_driver:
                booking.sent_to_driver = True
                booking.sent_to_driver_at = timezone.now()
                booking.driver_accepted = False
                booking.driver_accepted_at = None
                booking.driver_status = "pending"
                booking.driver_rejected_once = False
                booking.patient_reached = False
                booking.patient_reached_at = None
                Ambulance.objects.filter(id=booking.ambulance_id).update(status="en_route")
                changed_messages.append(
                    f"Booking dispatched to driver {booking.driver}. Live route and traffic updates are now active."
                )
        else:
            if booking.sent_to_driver:
                booking.sent_to_driver = False
                booking.sent_to_driver_at = None
                Ambulance.objects.filter(id=booking.ambulance_id).update(status="available")
                changed_messages.append("Booking recalled from driver.")

    if _to_bool(data.get("driver_accepted")) or data.get("driver_status") == "accepted":
        booking.driver_accepted = True
        booking.driver_status = "accepted"
        booking.driver_accepted_at = timezone.now()
        booking.driver_rejected_once = False
        changed_messages.append(f"Booking #{booking.id} accepted by driver {booking.driver}.")

    if _to_bool(data.get("cancel_driver_request")) or data.get("driver_status") == "rejected":
        booking.sent_to_driver = False
        booking.sent_to_driver_at = None
        booking.driver_rejected_once = True
        booking.driver_rejected_at = timezone.now()
        booking.driver_rejection_reason = str(data.get("driver_rejection_reason", "Driver cancelled request")).strip()
        booking.driver_status = "rejected"
        booking.driver_accepted = False
        booking.driver_accepted_at = None
        Ambulance.objects.filter(id=booking.ambulance_id).update(status="available")
        changed_messages.append(f"Driver {booking.driver} cancelled Booking #{booking.id}. Awaiting ambulance reassignment.")

    if "patient_reached" in data:
        booking.patient_reached = _to_bool(data["patient_reached"])
        booking.patient_reached_at = timezone.now() if booking.patient_reached else None
        if booking.patient_reached:
            changed_messages.append(f"Hospital {booking.assigned_hospital_name} confirmed patient reached for Booking #{booking.id}.")

    if _to_bool(data.get("request_ambulance_transfer")):
        target_id = _to_int(data.get("target_ambulance_id") or data.get("transfer_target_ambulance_id"))
        target_amb = Ambulance.objects.filter(id=target_id).first() if target_id else None
        target_num = str(data.get("target_ambulance_number") or (target_amb.ambulance_number if target_amb else "")).strip()

        booking.transfer_requested = True
        booking.transfer_requested_at = timezone.now()
        booking.transfer_status = "pending"
        booking.transfer_from_ambulance_id = booking.ambulance_id
        booking.transfer_from_ambulance_number = booking.ambulance_number
        booking.transfer_from_driver_email = str(data.get("driver_email") or "").strip()
        booking.transfer_from_driver_name = str(data.get("driver_name") or booking.driver).strip()
        booking.transfer_target_ambulance_id = target_amb.id if target_amb else (target_id if target_id else None)
        booking.transfer_target_ambulance_number = target_num
        changed_messages.append(
            f"Emergency transfer requested by driver {booking.driver}. Requesting switch to {target_num}."
        )

    if _to_bool(data.get("approve_ambulance_transfer")) or _to_bool(data.get("switch_ambulance_transfer")):
        target_id = _to_int(data.get("target_ambulance_id") or booking.transfer_target_ambulance_id)
        target_amb = Ambulance.objects.filter(id=target_id).first()
        if not target_amb:
            return JsonResponse({"error": "Target ambulance not found for transfer"}, status=400)

        old_ambulance_id = booking.ambulance_id
        booking.transfer_status = "approved"
        booking.transfer_approved_at = timezone.now()
        booking.transferred_to_ambulance_id = target_amb.id
        booking.transferred_to_ambulance_number = target_amb.ambulance_number or ""

        # Switch booking to the target ambulance
        booking.ambulance_id = target_amb.id
        booking.ambulance_number = target_amb.ambulance_number or ""
        booking.driver = target_amb.driver or ""
        booking.driver_contact = target_amb.driver_contact or ""

        # Dispatch to the new driver with normal workflow
        booking.sent_to_driver = True
        booking.sent_to_driver_at = timezone.now()
        booking.driver_accepted = False
        booking.driver_accepted_at = None
        booking.driver_status = "pending"
        booking.driver_rejected_once = False
        booking.patient_reached = False
        booking.patient_reached_at = None

        target_amb.status = "en_route"
        target_amb.save(update_fields=["status"])
        if old_ambulance_id and old_ambulance_id != target_amb.id:
            Ambulance.objects.filter(id=old_ambulance_id).update(status="available")

        changed_messages.append(
            f"Admin approved transfer! Booking #{booking.id} switched to {target_amb.ambulance_number} (Driver: {target_amb.driver}). Dispatched to new driver."
        )

    if _to_bool(data.get("reject_ambulance_transfer")):
        booking.transfer_status = "rejected"
        booking.transfer_rejected_at = timezone.now()
        changed_messages.append(
            f"Admin rejected transfer to {booking.transfer_target_ambulance_number}. Awaiting alternate ambulance assignment."
        )

    if "status" in data:
        new_status = str(data["status"]).lower().strip()
        valid_statuses = {choice[0] for choice in Booking.STATUS_CHOICES}
        if new_status not in valid_statuses:
            return JsonResponse({"error": f"Invalid status. Use: {sorted(valid_statuses)}"}, status=400)
        booking.status = new_status
        if new_status in {"completed", "cancelled"}:
            from hospitals.models import HospitalStaff
            HospitalStaff.objects.filter(assigned_booking_id=booking.id).update(is_active=True, is_busy=False, assigned_booking_id=None)
            Ambulance.objects.filter(id=booking.ambulance_id).update(status="available")
            if booking.hospital_response == "ready" and booking.assigned_hospital_id:
                h = Hospital.objects.filter(id=booking.assigned_hospital_id).first()
                if h:
                    if h.available_beds < h.total_beds:
                        h.available_beds += 1
                    if h.status == "full" and h.available_beds > 0:
                        h.status = "active"
                    h.last_capacity_updated = timezone.now()
                    h.save(update_fields=["available_beds", "status", "last_capacity_updated", "updated_at"])
        elif new_status == "confirmed":
            Ambulance.objects.filter(id=booking.ambulance_id).update(status="en_route")
        changed_messages.append(f"Booking status changed to {new_status}.")

    if _to_bool(data.get("driver_task_complete")):
        from hospitals.models import HospitalStaff
        HospitalStaff.objects.filter(assigned_booking_id=booking.id).update(is_active=True, is_busy=False, assigned_booking_id=None)
        booking.driver_task_completed = True
        booking.driver_task_completed_at = timezone.now()
        booking.status = "completed"
        Ambulance.objects.filter(id=booking.ambulance_id).update(status="available")
        changed_messages.append(f"Driver completed Booking #{booking.id}.")

    if "icu_required" in data:
        booking.icu_required = _to_bool(data["icu_required"])
        if booking.icu_required:
            booking.icu_requested_at = timezone.now()
            changed_messages.append(f"🚨 ICU bed urgently requested for Booking #{booking.id}.")
    if "assigned_bed_id" in data:
        booking.assigned_bed_id = _to_int(data["assigned_bed_id"]) or None
    if "assigned_bed_number" in data:
        booking.assigned_bed_number = str(data["assigned_bed_number"]).strip()
    if "assigned_bed_type" in data:
        booking.assigned_bed_type = str(data["assigned_bed_type"]).strip()

    if "assigned_doctors" in data or "assign_doctors" in data:
        from hospitals.models import HospitalStaff
        doctors_input = data.get("assigned_doctors") or data.get("assign_doctors") or []
        if isinstance(doctors_input, str):
            try:
                doctors_input = json.loads(doctors_input)
            except Exception:
                doctors_input = []
        if not isinstance(doctors_input, list):
            doctors_input = [doctors_input] if doctors_input else []
        
        doctors_input = doctors_input[:3]
        HospitalStaff.objects.filter(assigned_booking_id=booking.id).update(is_active=True, is_busy=False, assigned_booking_id=None)
        
        doctor_ids = []
        names = []
        specs = []
        contacts = []
        json_list = []
        
        for doc in doctors_input:
            if isinstance(doc, dict):
                d_id = _to_int(doc.get("id"))
                d_name = str(doc.get("full_name") or doc.get("name") or "").strip()
                d_spec = str(doc.get("specialization") or doc.get("spec") or "").strip()
                d_phone = str(doc.get("contact_number") or doc.get("contact") or doc.get("phone") or "").strip()
            else:
                d_id = _to_int(doc)
                d_name, d_spec, d_phone = "", "", ""
                
            staff_obj = HospitalStaff.objects.filter(id=d_id).first() if d_id > 0 else None
            if staff_obj:
                d_name = d_name or staff_obj.full_name
                d_spec = d_spec or staff_obj.specialization
                d_phone = d_phone or staff_obj.contact_number
                staff_obj.is_active = True
                staff_obj.is_busy = True
                staff_obj.assigned_booking_id = booking.id
                staff_obj.save()
            
            if d_name:
                doctor_ids.append(d_id)
                names.append(d_name)
                specs.append(d_spec)
                contacts.append(d_phone)
                json_list.append({
                    "id": d_id,
                    "full_name": d_name,
                    "specialization": d_spec,
                    "contact_number": d_phone,
                })
        
        booking.assigned_doctors_json = json.dumps(json_list)
        booking.assigned_doctor_names = ", ".join(names)
        booking.assigned_doctor_specializations = ", ".join(specs)
        booking.assigned_doctor_contacts = ", ".join(contacts)
        booking.doctors_assigned_at = timezone.now()
        changed_messages.append(f"{len(json_list)} doctor(s) assigned to Booking #{booking.id}: {booking.assigned_doctor_names}.")

    patient_report = data.get("patient_report")
    if isinstance(patient_report, dict):
        booking.patient_name = str(patient_report.get("patient_name", "")).strip()
        booking.patient_age = str(patient_report.get("patient_age", "")).strip()
        booking.patient_gender = str(patient_report.get("patient_gender", "")).strip()
        booking.attendant_name = str(patient_report.get("attendant_name", "")).strip()
        booking.attendant_contact = str(patient_report.get("attendant_contact", "")).strip()
        booking.patient_condition = str(patient_report.get("patient_condition", "")).strip()
        booking.vitals_summary = str(patient_report.get("vitals_summary", "")).strip()
        booking.report_submitted_by = str(patient_report.get("submitted_by", "")).strip() or booking.driver or "Driver Team"
        booking.report_submitted_at = timezone.now()
        booking.report_sent_to_hospital = True
        booking.report_sent_to_hospital_at = timezone.now()
        booking.driver_report_sent_at = timezone.now()

        # Send admin notification email (always)
        _send_mail_background(
            subject=f"Patient Condition Report - Booking #{booking.id}",
            message=f"""Patient report submitted by driver.

Booking ID: #{booking.id}
Patient: {booking.patient_name or booking.booked_by}
Age: {booking.patient_age or '-'}
Gender: {booking.patient_gender or '-'}
Attendant: {booking.attendant_name or '-'} ({booking.attendant_contact or '-'})
Condition: {booking.patient_condition or '-'}
Vitals: {booking.vitals_summary or '-'}

Pickup: {booking.pickup_location}
Hospital: {booking.assigned_hospital_name or booking.destination or '-'}
""",
            recipient_list=["vashupanchal.cs@gmail.com"],
            label="Admin patient report email",
        )
        # forward_patient_report: send_to_hospital flag from the driver (defaults True)
        forward_patient_report = _to_bool(patient_report.get("send_to_hospital"), True)
        if forward_patient_report and booking.assigned_hospital_email:
            _send_mail_background(
                subject=f"Patient Clinical Report - Booking #{booking.id}",
                message=f"""Incoming patient report.

Booking ID: #{booking.id}
Patient: {booking.patient_name or booking.booked_by}
Age: {booking.patient_age or '-'}
Gender: {booking.patient_gender or '-'}
Attendant: {booking.attendant_name or '-'} ({booking.attendant_contact or '-'})
Condition: {booking.patient_condition or '-'}
Vitals: {booking.vitals_summary or '-'}

Pickup: {booking.pickup_location}
Ambulance: {booking.ambulance_number}
Driver: {booking.driver} ({booking.driver_contact or '-'})
""",
                recipient_list=[booking.assigned_hospital_email],
                label="Driver patient report hospital email",
            )
        changed_messages.append(
            f"Driver submitted patient condition form for Booking #{booking.id}. "
            + ("Hospital intake received the report." if booking.report_sent_to_hospital else "Admin review pending.")
        )

    if _to_bool(data.get("send_report_to_hospital")):
        if not booking.assigned_hospital_email:
            return JsonResponse({"error": "Assigned hospital email missing"}, status=400)
        if not booking.report_submitted_at:
            return JsonResponse({"error": "Patient report not submitted yet"}, status=400)
        booking.report_sent_to_hospital = True
        booking.report_sent_to_hospital_at = timezone.now()
        booking.driver_report_sent_at = booking.driver_report_sent_at or timezone.now()
        _send_mail_background(
            subject=f"Patient Clinical Report - Booking #{booking.id}",
            message=f"""Incoming patient report.

Booking ID: #{booking.id}
Patient: {booking.patient_name or booking.booked_by}
Age: {booking.patient_age or '-'}
Gender: {booking.patient_gender or '-'}
Attendant: {booking.attendant_name or '-'} ({booking.attendant_contact or '-'})
Condition: {booking.patient_condition or '-'}
Vitals: {booking.vitals_summary or '-'}

Pickup: {booking.pickup_location}
Ambulance: {booking.ambulance_number}
Driver: {booking.driver} ({booking.driver_contact or '-'})
""",
            recipient_list=[booking.assigned_hospital_email],
            label="Hospital report email",
        )
        changed_messages.append("Patient clinical report forwarded to hospital intake desk.")

    insurance_details = data.get("insurance_details")
    if isinstance(insurance_details, dict):
        def _pick_text(keys, fallback=""):
            for key in keys:
                val = insurance_details.get(key, "")
                if val is None:
                    continue
                txt = str(val).strip()
                if txt:
                    return txt
            return fallback

        booking.insurance_full_name = _pick_text(["full_name", "patient_name", "fullName"], booking.insurance_full_name)
        booking.insurance_dob = _pick_text(["date_of_birth", "dob", "dateOfBirth"], booking.insurance_dob)
        booking.insurance_gender = _pick_text(["gender"], booking.insurance_gender)
        booking.insurance_provider = _pick_text(["insurance_provider", "provider", "insuranceProvider"], booking.insurance_provider)
        booking.insurance_policy_member_id = _pick_text(["policy_member_id", "member_id", "policyMemberId"], booking.insurance_policy_member_id)
        booking.insurance_policy_holder_name = _pick_text(["policy_holder_name", "holder_name", "policyHolderName"], booking.insurance_policy_holder_name)
        booking.insurance_government_id = _pick_text(["government_id", "govt_id", "governmentId"], booking.insurance_government_id)
        booking.insurance_sum_insured = _pick_text(["sum_insured", "sumInsured"], booking.insurance_sum_insured)
        booking.insurance_emergency_nature = _pick_text(["emergency_nature", "emergencyNature"], booking.insurance_emergency_nature)
        booking.insurance_exclusions_waiting = _pick_text(
            ["exclusions_waiting_period", "exclusions_waiting", "waiting_period", "exclusionsWaitingPeriod"],
            booking.insurance_exclusions_waiting,
        )
        booking.insurance_submitted_by = _pick_text(["submitted_by", "submittedBy"], booking.insurance_submitted_by) or booking.driver or "Ambulance Team"
        booking.insurance_submitted_at = timezone.now()
        booking.insurance_status = "pending"
        booking.insurance_reviewed_by = ""
        booking.insurance_reviewed_at = None
        booking.insurance_hospital_note = "Awaiting hospital insurance approval."
        changed_messages.append("Medical insurance details submitted to hospital.")

    booking.save()
    for message in changed_messages:
        # The booking state is authoritative. A temporary chat-timeline
        # failure must not turn a successful admin confirmation into HTTP 500.
        try:
            _push_system_message(booking, message)
        except Exception as exc:
            print("Booking system message error:", exc)
    return JsonResponse(booking_to_dict(booking))


@csrf_exempt
@transaction.atomic
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
        booking = Booking.objects.select_for_update().get(id=id)
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)
    if not booking.assigned_hospital_id:
        return JsonResponse({"error": "Assign a hospital before responding"}, status=400)
    
    old_response = booking.hospital_response
    booking.hospital_response = response
    booking.hospital_response_note = str(data.get("hospital_response_note", "")).strip()
    booking.hospital_responded_at = timezone.now()
    booking.save(update_fields=["hospital_response", "hospital_response_note", "hospital_responded_at"])

    # Real-time update of hospital available beds & status
    hospital = Hospital.objects.select_for_update().filter(id=booking.assigned_hospital_id).first()
    if hospital:
        if old_response != "ready" and response == "ready":
            # Booking accepted: decrement available beds
            if hospital.available_beds > 0:
                hospital.available_beds -= 1
            if hospital.available_beds == 0:
                hospital.status = "full"
            hospital.last_capacity_updated = timezone.now()
            hospital.save(update_fields=["available_beds", "status", "last_capacity_updated", "updated_at"])
        elif old_response == "ready" and response == "not_ready":
            # Booking rejected after acceptance: restore available bed
            if hospital.available_beds < hospital.total_beds:
                hospital.available_beds += 1
            if hospital.status == "full" and hospital.available_beds > 0:
                hospital.status = "active"
            hospital.last_capacity_updated = timezone.now()
            hospital.save(update_fields=["available_beds", "status", "last_capacity_updated", "updated_at"])

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


PHOTO_REQUIREMENTS = {
    "ecg": "Send a clear ECG strip or ECG monitor photo.",
    "patient": "Send a clear photo showing the patient's current condition.",
    "patient_id": "Send the patient's ID/document only when it is safe and permitted.",
    "vitals": "Send the monitor/vitals display so the care team can read it.",
    "documents": "Send relevant medical documents or prescriptions.",
    "other": "Send another clinically relevant condition photo.",
}


def _photo_to_dict(photo, request=None):
    # New uploads are database-backed and remain available after a Render
    # deploy. Older rows may still reference the legacy media file, so keep a
    # safe fallback for them and never let a missing file turn the API into a
    # 500 response.
    url = str(getattr(photo, "image_data", "") or "")
    if not url and getattr(photo, "image", None):
        try:
            url = photo.image.url
        except (AttributeError, ValueError, OSError):
            url = ""
    # ``image_data`` is a complete data URL. Only legacy relative media paths
    # need Django's host prefix; prefixing a data URL would corrupt the image
    # source into an unusable API URL.
    if request and url and not url.startswith("data:") and not url.startswith(("http://", "https://")):
        url = request.build_absolute_uri(url)
    return {
        "id": photo.id,
        "booking_id": photo.booking_id,
        "photo_type": photo.photo_type,
        "label": photo.get_photo_type_display(),
        "instruction": photo.instruction or PHOTO_REQUIREMENTS.get(photo.photo_type, ""),
        "url": url,
        "original_name": photo.original_name,
        "content_type": photo.content_type,
        "uploader_role": photo.uploader_role,
        "uploader_name": photo.uploader_name,
        "uploader_email": photo.uploader_email,
        "created_at": _iso(photo.created_at),
    }


def _booking_team(booking):
    try:
        parsed = json.loads(getattr(booking, "assigned_doctors_json", "[]") or "[]")
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def _driver_can_access_booking(request, booking):
    body = _json_body(request) or {}
    ambulance_id = _to_int(body.get("ambulance_id") or request.POST.get("ambulance_id") or request.GET.get("ambulance_id"), -1)
    email = str(body.get("driver_email") or request.POST.get("driver_email") or request.GET.get("driver_email") or "").strip().lower()
    name = str(body.get("driver_name") or request.POST.get("driver_name") or request.GET.get("driver_name") or "").strip().lower()

    # 1. Match by driver_email on booking when the deployed schema exposes it.
    # Older Booking rows/models do not have this field; use the linked
    # ambulance and driver-name fallbacks instead of raising AttributeError.
    booking_driver_email = getattr(booking, "driver_email", "")
    if email and booking_driver_email and str(booking_driver_email).strip().lower() == email:
        return True
    # 2. Match by driver name on booking
    if name and booking.driver and str(booking.driver).strip().lower() == name:
        return True
    # 3. Match by ambulance_id
    if ambulance_id > 0 and booking.ambulance_id == ambulance_id:
        ambulance = Ambulance.objects.filter(id=ambulance_id).first()
        if ambulance:
            if email and str(ambulance.driver_email or "").strip().lower() == email:
                return True
            if name and str(ambulance.driver or "").strip().lower() == name:
                return True
            if not email and not name:
                return True
        return True
    # 4. Fallback if booking has an assigned ambulance matching ambulance_id
    if booking.ambulance_id and ambulance_id == booking.ambulance_id:
        return True
    return False


def _staff_can_access_booking(request, booking):
    staff_id = str(request.GET.get("staff_id") or request.POST.get("staff_id") or "").strip()
    email = str(request.GET.get("email") or request.POST.get("email") or "").strip().lower()
    staff = HospitalStaff.objects.select_related("hospital").filter(staff_id__iexact=staff_id, email__iexact=email, is_active=True).first()
    if not staff:
        return False
    same_hospital = (
        (booking.assigned_hospital_id and booking.assigned_hospital_id == staff.hospital_id)
        or (staff.hospital and staff.hospital.name and str(booking.assigned_hospital_name or booking.destination).strip().lower() == staff.hospital.name.strip().lower())
    )
    if same_hospital:
        return True
    team = _booking_team(booking)
    return any(isinstance(member, dict) and (
        str(member.get("id", "")) == str(staff.id)
        or str(member.get("staff_id", "")).lower() == staff.staff_id.lower()
        or str(member.get("full_name", member.get("name", ""))).strip().lower() == staff.full_name.strip().lower()
    ) for member in team)


def _video_request_to_dict(item):
    return {
        "id": item.id,
        "booking_id": item.booking_id,
        "staff_id": item.staff.staff_id,
        "staff_profile_id": item.staff_id,
        "staff_contract_id": item.staff.staff_id,
        "staff_name": item.staff.full_name,
        "staff_role": item.staff.role,
        "staff_specialization": item.staff.specialization,
        "staff_email": item.staff.email,
        "staff_photo": item.staff.photo_data or "",
        "driver_name": item.driver_name,
        "driver_email": item.driver_email,
        "status": item.status,
        "requested_at": _iso(item.requested_at),
        "responded_at": _iso(item.responded_at),
        "joined_at": _iso(item.joined_at),
    }


def _assigned_team_member(booking, staff):
    # Allow if staff belongs to the hospital assigned to this emergency booking
    if booking.assigned_hospital_id and staff.hospital_id == booking.assigned_hospital_id:
        return True
    if staff.hospital and staff.hospital.name and str(booking.assigned_hospital_name or booking.destination).strip().lower() == staff.hospital.name.strip().lower():
        return True
    return any(isinstance(member, dict) and (
        str(member.get("id", "")) == str(staff.id)
        or str(member.get("staff_id", "")).lower() == staff.staff_id.lower()
        or str(member.get("full_name", member.get("name", ""))).strip().lower() == staff.full_name.strip().lower()
    ) for member in _booking_team(booking))


@csrf_exempt
def video_call_requests(request):
    """Persist driver-to-allocated-staff video requests and accepted members."""
    if request.method == "GET":
        booking_id = _to_int(request.GET.get("booking_id"), -1)
        if booking_id < 0:
            return JsonResponse({"error": "booking_id is required"}, status=400)
        booking = Booking.objects.filter(id=booking_id).first()
        if not booking:
            return JsonResponse({"error": "Booking not found"}, status=404)
        role = str(request.GET.get("role", "")).strip().lower()
        if role == "driver":
            if not _driver_can_access_booking(request, booking):
                return JsonResponse({"error": "Only the assigned driver can view these requests"}, status=403)
            try:
                qs = VideoCallRequest.objects.filter(booking=booking).select_related("staff")
            except (OperationalError, ProgrammingError):
                # A rolling Render deployment can briefly serve a worker before
                # the migration transaction is visible. Return an empty,
                # usable state instead of breaking the driver portal.
                return JsonResponse({"booking_id": booking.id, "requests": []})
        elif role == "staff":
            if not _staff_can_access_booking(request, booking):
                return JsonResponse({"error": "Only allocated staff can view these requests"}, status=403)
            staff_id = str(request.GET.get("staff_id", "")).strip()
            email = str(request.GET.get("email", "")).strip().lower()
            staff = HospitalStaff.objects.filter(staff_id__iexact=staff_id, email__iexact=email, is_active=True).first()
            if not staff:
                return JsonResponse({"error": "Staff account not found or inactive"}, status=404)
            try:
                qs = VideoCallRequest.objects.filter(booking=booking, staff=staff).select_related("staff")
            except (OperationalError, ProgrammingError):
                return JsonResponse({"booking_id": booking.id, "requests": []})
        else:
            return JsonResponse({"error": "role must be driver or staff"}, status=400)
        try:
            rows = [_video_request_to_dict(item) for item in qs[:20]]
        except (OperationalError, ProgrammingError):
            rows = []
        return JsonResponse({"booking_id": booking.id, "requests": rows})

    if request.method != "POST":
        return JsonResponse({"error": "GET or POST only"}, status=405)
    data = _json_body(request) or {}
    booking_id = _to_int(data.get("booking_id"), -1)
    booking = Booking.objects.filter(id=booking_id).first()
    if not booking or not _driver_can_access_booking(request, booking):
        return JsonResponse({"error": "Only the assigned driver can request a booking call"}, status=403)
    staff_profile_id = _to_int(data.get("staff_id"), -1)
    staff = HospitalStaff.objects.filter(id=staff_profile_id, is_active=True).first()
    if not staff or not _assigned_team_member(booking, staff):
        return JsonResponse({"error": "Video requests can only be sent to staff allocated to this booking"}, status=403)
    try:
        accepted_count = VideoCallRequest.objects.filter(booking=booking, status="accepted").count()
        existing = VideoCallRequest.objects.filter(booking=booking, staff=staff, status__in=["pending", "accepted"]).order_by("-id").first()
    except (OperationalError, ProgrammingError):
        return JsonResponse({"error": "Video call service is still initializing. Please try again."}, status=503)
    if existing:
        return JsonResponse(_video_request_to_dict(existing), status=200)
    if accepted_count >= 3:
        return JsonResponse({"error": "Maximum 4 participants added (driver + 3 staff)", "code": "MAX_PARTICIPANTS"}, status=409)
    driver_email = str(data.get("driver_email") or request.POST.get("driver_email") or "").strip().lower()
    driver_name = str(data.get("driver_name") or booking.driver or "Driver").strip()
    try:
        item = VideoCallRequest.objects.create(booking=booking, staff=staff, driver_email=driver_email, driver_name=driver_name)
    except (OperationalError, ProgrammingError):
        return JsonResponse({"error": "Video call service is still initializing. Please try again."}, status=503)
    return JsonResponse(_video_request_to_dict(item), status=201)


@csrf_exempt
def video_call_request_respond(request, request_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    item = VideoCallRequest.objects.select_related("booking", "staff").filter(id=request_id).first()
    if not item:
        return JsonResponse({"error": "Video request not found"}, status=404)
    data = _json_body(request) or {}
    staff_id = str(data.get("staff_id", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    if staff_id.lower() != item.staff.staff_id.lower() or email != item.staff.email.lower():
        return JsonResponse({"error": "Only the requested staff member can respond"}, status=403)
    action = str(data.get("action", "")).strip().lower()
    if action not in {"accept", "reject"}:
        return JsonResponse({"error": "action must be accept or reject"}, status=400)
    if item.status not in {"pending", "accepted"}:
        return JsonResponse(_video_request_to_dict(item))
    if action == "accept":
        accepted_count = VideoCallRequest.objects.filter(booking=item.booking, status="accepted").exclude(id=item.id).count()
        if accepted_count >= 3:
            return JsonResponse({"error": "Maximum 4 participants added (driver + 3 staff)", "code": "MAX_PARTICIPANTS"}, status=409)
        item.status = "accepted"
        item.joined_at = timezone.now()
    else:
        item.status = "rejected"
    item.responded_at = timezone.now()
    item.save(update_fields=["status", "joined_at", "responded_at"])
    return JsonResponse(_video_request_to_dict(item))


@csrf_exempt
def driver_assigned_bookings(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    ambulance_id = _to_int(request.GET.get("ambulance_id"), -1)
    email = str(request.GET.get("driver_email", "")).strip().lower()

    ambulance = None
    if ambulance_id > 0:
        ambulance = Ambulance.objects.filter(id=ambulance_id).first()
    if not ambulance and email:
        ambulance = Ambulance.objects.filter(driver_email__iexact=email).first()
        if ambulance:
            ambulance_id = ambulance.id

    if ambulance_id > 0 and ambulance and email:
        if str(ambulance.driver_email or "").strip().lower() != email:
            return JsonResponse({"error": "Driver is not assigned to this ambulance"}, status=403)

    if ambulance_id > 0:
        bookings = list(
            Booking.objects.filter(ambulance_id=ambulance_id)
            .exclude(status__in=["completed", "cancelled"])
            .order_by("-created_at")[:100]
        )
    elif email:
        # Booking stores the assignment through ambulance_id in the deployed
        # schema; it does not expose a driver_email column. If no matching
        # ambulance was found above, return an empty result instead of issuing
        # an invalid ORM lookup.
        bookings = []
    else:
        return JsonResponse({"error": "ambulance_id or driver_email is required"}, status=400)

    # The driver portal opens this endpoint on every tab change. Build all
    # related data in bulk so a booking card does not wait for N+1 queries.
    booking_ids = {booking.id for booking in bookings}
    ambulance_ids = {booking.ambulance_id for booking in bookings if booking.ambulance_id}
    ambulance_map = {
        item.id: item
        for item in Ambulance.objects.filter(id__in=ambulance_ids).only("id", "driver_email")
    }
    thread_map = {
        item.booking_id: item
        for item in BookingChatThread.objects.filter(booking_id__in=booking_ids).only("id", "booking_id")
    }
    photos_by_booking = {booking_id: [] for booking_id in booking_ids}
    if booking_ids:
        for photo in PatientConditionPhoto.objects.filter(booking_id__in=booking_ids).order_by("-created_at", "-id"):
            photos_by_booking.setdefault(photo.booking_id, []).append(_photo_to_dict(photo, request))
    rows = []
    for booking in bookings:
        row = booking_to_dict(
            booking,
            ambulance=ambulance_map.get(booking.ambulance_id),
            chat_thread=thread_map.get(booking.id),
        )
        row["photo_requirements"] = [{"type": key, "label": label, "instruction": PHOTO_REQUIREMENTS[key]} for key, label in PatientConditionPhoto.PHOTO_TYPES]
        row["condition_photos"] = photos_by_booking.get(booking.id, [])
        rows.append(row)
    return JsonResponse(rows, safe=False)


@csrf_exempt
def booking_photos(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Booking not found"}, status=404)
    role = str(request.GET.get("role") or request.POST.get("role") or "").strip().lower()
    if request.method == "GET":
        hospital_id = _to_int(request.GET.get("hospital_id"), -1)
        allowed = role == "admin" or (role == "driver" and _driver_can_access_booking(request, booking)) or (role == "staff" and _staff_can_access_booking(request, booking)) or (hospital_id >= 0 and booking.assigned_hospital_id == hospital_id)
        if not allowed:
            return JsonResponse({"error": "You are not authorised to view these photos"}, status=403)
        try:
            photos = [_photo_to_dict(photo, request) for photo in booking.condition_photos.all()]
        except (OperationalError, ProgrammingError, ValueError, OSError):
            photos = []
        return JsonResponse({"booking_id": booking.id, "photos": photos})
    if request.method != "POST":
        return JsonResponse({"error": "GET or POST only"}, status=405)
    if role != "driver" or not _driver_can_access_booking(request, booking):
        return JsonResponse({"error": "Only the assigned driver can upload photos"}, status=403)
    if booking.status in {"completed", "cancelled"}:
        return JsonResponse({"error": "Photos cannot be added to a closed booking"}, status=409)
    files = request.FILES.getlist("photos")
    if not files:
        return JsonResponse({"error": "At least one photo is required"}, status=400)
    photo_type = str(request.POST.get("photo_type", "patient")).strip().lower()
    raw_types = [str(value).strip().lower() for value in request.POST.getlist("photo_types")]
    raw_instructions = [str(value).strip() for value in request.POST.getlist("instructions")]
    valid_types = {key for key, _ in PatientConditionPhoto.PHOTO_TYPES}
    if photo_type not in valid_types:
        return JsonResponse({"error": "Unknown photo type"}, status=400)
    for item_type in raw_types:
        if item_type not in valid_types:
            return JsonResponse({"error": "Unknown photo type"}, status=400)
    default_instruction = str(request.POST.get("instruction", "")).strip()
    uploader_name = str(request.POST.get("driver_name", "")).strip() or booking.driver or "Ambulance driver"
    uploader_email = str(request.POST.get("driver_email", "")).strip().lower()
    created = []
    for index, uploaded in enumerate(files):
        if not str(uploaded.content_type or "").lower().startswith("image/"):
            return JsonResponse({"error": "Only image files are accepted"}, status=400)
        if uploaded.size > 10 * 1024 * 1024:
            return JsonResponse({"error": "Each image must be 10 MB or smaller"}, status=413)
        item_type = raw_types[index] if index < len(raw_types) else photo_type
        item_instruction = raw_instructions[index] if index < len(raw_instructions) else (default_instruction or PHOTO_REQUIREMENTS[item_type])
        content_type = uploaded.content_type or "image/*"
        encoded = base64.b64encode(uploaded.read()).decode("ascii")
        created.append(PatientConditionPhoto.objects.create(
            booking=booking,
            photo_type=item_type,
            instruction=item_instruction,
            image="",
            image_data=f"data:{content_type};base64,{encoded}",
            original_name=uploaded.name[:255],
            content_type=content_type,
            uploader_role="driver",
            uploader_name=uploader_name,
            uploader_email=uploader_email,
        ))
    return JsonResponse({"status": "uploaded", "photos": [_photo_to_dict(photo, request) for photo in created]}, status=201)
