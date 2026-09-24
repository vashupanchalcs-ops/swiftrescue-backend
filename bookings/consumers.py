import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from bookings.models import Booking
from hospitals.models import HospitalStaff


class ConsultationConsumer(AsyncWebsocketConsumer):
    """Booking-scoped WebRTC signaling for driver <-> assigned medical staff."""

    async def connect(self):
        self.booking_id = int(self.scope["url_route"]["kwargs"]["booking_id"])
        query = parse_qs(self.scope.get("query_string", b"").decode("utf-8"))
        self.role = (query.get("role", [""])[0] or "").lower()
        self.staff_id = query.get("staff_id", [""])[0]
        self.email = query.get("email", [""])[0]
        self.ambulance_id = query.get("ambulance_id", [""])[0]
        self.client_id = query.get("client_id", [""])[0] or self.channel_name
        self.participant_id = query.get("participant_id", [""])[0]
        if self.role not in {"driver", "staff"} or not await self._is_authorized():
            await self.close(code=4403)
            return
        self.group_name = f"consultation_{self.booking_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.channel_layer.group_send(self.group_name, {"type": "consultation.signal", "sender": self.channel_name, "payload": {"type": "peer-joined", "role": self.role, "sender_id": self.client_id, "participant_id": self.participant_id}})

    async def disconnect(self, code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_send(self.group_name, {"type": "consultation.signal", "sender": self.channel_name, "payload": {"type": "peer-left", "role": getattr(self, "role", ""), "sender_id": getattr(self, "client_id", "")}})
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data or not getattr(self, "group_name", None):
            return
        try:
            payload = json.loads(text_data)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict) or payload.get("type") not in {"join", "offer", "answer", "ice-candidate", "leave"}:
            return
        payload = {
            **payload,
            "sender_id": self.client_id,
            "role": getattr(self, "role", ""),
            "participant_id": getattr(self, "participant_id", ""),
        }
        await self.channel_layer.group_send(self.group_name, {"type": "consultation.signal", "sender": self.channel_name, "payload": payload})

    async def consultation_signal(self, event):
        if event.get("sender") == self.channel_name:
            return
        await self.send(text_data=json.dumps(event.get("payload") or {}))

    @database_sync_to_async
    def _is_authorized(self):
        booking = Booking.objects.filter(id=self.booking_id).first()
        if not booking:
            return False
        if self.role == "driver":
            # Accept if ambulance_id matches OR if driver email matches booking.driver_email
            ambulance_match = bool(self.ambulance_id and str(booking.ambulance_id) == str(self.ambulance_id))
            # Older Booking rows use the ambulance id/name as the driver
            # identity and do not have a driver_email column.  Accessing the
            # optional field directly made every otherwise-valid driver
            # WebSocket handshake crash with HTTP 500.
            booking_driver_email = getattr(booking, "driver_email", "") or ""
            email_match = bool(self.email and booking_driver_email and str(booking_driver_email).lower() == str(self.email).lower())
            return ambulance_match or email_match
        # Staff: look up by staff_id + email
        staff = HospitalStaff.objects.filter(staff_id__iexact=self.staff_id, email__iexact=self.email, is_active=True).first()
        if not staff:
            return False
        # Accept if staff belongs to the assigned hospital for this booking
        if booking.assigned_hospital_id and staff.hospital_id == booking.assigned_hospital_id:
            return True
        # Also accept if staff is explicitly listed in assigned_doctors_json
        try:
            team = json.loads(booking.assigned_doctors_json or "[]")
        except (TypeError, json.JSONDecodeError):
            team = []
        return any(
            isinstance(member, dict) and (
                str(member.get("id", "")) == str(staff.id)
                or str(member.get("staff_id", "")).lower() == staff.staff_id.lower()
                or str(member.get("full_name", member.get("name", ""))).strip().lower() == staff.full_name.strip().lower()
            )
            for member in team
        )


class BookingChatConsumer(AsyncWebsocketConsumer):
    """Realtime chat consumer between patient, driver, and hospital admin."""

    async def connect(self):
        self.thread_id = int(self.scope["url_route"]["kwargs"].get("thread_id", 0))
        self.group_name = f"chat_{self.thread_id}"
        query = parse_qs(self.scope.get("query_string", b"").decode("utf-8"))
        self.role = (query.get("role", ["user"])[0] or "user").lower()
        self.name = query.get("name", ["User"])[0] or "User"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send initial presence acknowledgement
        await self.send(text_data=json.dumps({
            "type": "presence",
            "presence": {
                f"{self.role}_online": True,
                f"{self.role}_typing": False,
            }
        }))

    async def disconnect(self, code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data or not getattr(self, "group_name", None):
            return
        try:
            payload = json.loads(text_data)
        except (TypeError, json.JSONDecodeError):
            return

        msg_type = payload.get("type", "message")
        if msg_type == "read":
            return

        if msg_type == "typing":
            await self.channel_layer.group_send(self.group_name, {
                "type": "chat.presence",
                "presence": {f"{self.role}_typing": bool(payload.get("typing", False))}
            })
            return

        # Broadcast chat message to group
        await self.channel_layer.group_send(self.group_name, {
            "type": "chat.message",
            "payload": payload
        })

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event.get("payload") or {}))

    async def chat_presence(self, event):
        await self.send(text_data=json.dumps({
            "type": "presence",
            "presence": event.get("presence", {})
        }))
