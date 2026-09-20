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
        if self.role not in {"driver", "staff"} or not await self._is_authorized():
            await self.close(code=4403)
            return
        self.group_name = f"consultation_{self.booking_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.channel_layer.group_send(self.group_name, {"type": "consultation.signal", "sender": self.channel_name, "payload": {"type": "peer-joined", "role": self.role}})

    async def disconnect(self, code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_send(self.group_name, {"type": "consultation.signal", "sender": self.channel_name, "payload": {"type": "peer-left", "role": getattr(self, "role", "")}})
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
            return bool(self.ambulance_id and str(booking.ambulance_id) == str(self.ambulance_id))
        staff = HospitalStaff.objects.filter(staff_id__iexact=self.staff_id, email__iexact=self.email, is_active=True).first()
        if not staff:
            return False
        try:
            team = json.loads(booking.assigned_doctors_json or "[]")
        except (TypeError, json.JSONDecodeError):
            team = []
        return any(isinstance(member, dict) and (str(member.get("id", "")) == str(staff.id) or str(member.get("staff_id", "")).lower() == staff.staff_id.lower() or str(member.get("full_name", member.get("name", ""))).strip().lower() == staff.full_name.strip().lower()) for member in team)
