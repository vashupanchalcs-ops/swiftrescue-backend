"""Best-effort booking events for Channels clients."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def publish_booking_update(booking, event="booking_update"):
    payload = {
        "type": event,
        "booking_id": booking.id,
        "status": booking.status,
        "ambulance_id": booking.ambulance_id,
        "ambulance_number": booking.ambulance_number,
        "assigned_hospital_id": booking.assigned_hospital_id,
        "assigned_hospital_name": booking.assigned_hospital_name,
        "hospital_response": booking.hospital_response,
        "assignment_eta_seconds": getattr(booking, "assignment_eta_seconds", None),
        "assignment_route_provider": getattr(booking, "assignment_route_provider", ""),
    }
    try:
        layer = get_channel_layer()
        async_to_sync(layer.group_send)(
            f"booking_{booking.id}",
            {"type": "tracking.booking", "payload": payload},
        )
        if booking.ambulance_id:
            async_to_sync(layer.group_send)(
                f"ambulance_{booking.ambulance_id}",
                {"type": "tracking.booking", "payload": payload},
            )
    except Exception:
        # A broker outage must not roll back a successful database mutation.
        pass
