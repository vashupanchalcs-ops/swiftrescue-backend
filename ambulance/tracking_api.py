import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ambulance.models import TrackingRoute
from ambulance.tracking_service import is_authorized, route_dict, snapshot_for_booking, broadcast, EVENT_TYPES
from bookings.models import Booking
from ambulance.route_service import calculate_booking_route


def _identity(request):
    return (
        request.headers.get("X-Tracking-Role", request.GET.get("role", "")),
        request.headers.get("X-Tracking-Email", request.GET.get("email", "")),
        request.headers.get("X-Ambulance-Id", request.GET.get("ambulance_id", "")),
        request.headers.get("X-Hospital-Id", request.GET.get("hospital_id", "")),
        request.headers.get("X-Staff-Id", request.GET.get("staff_id", "")),
    )


def _authorize(request, booking):
    return is_authorized(booking, *_identity(request))


@csrf_exempt
def tracking_snapshot(request, booking_id):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    booking = Booking.objects.filter(id=booking_id).first()
    if not booking or not _authorize(request, booking):
        return JsonResponse({"error": "Not authorized"}, status=403)
    snapshot = snapshot_for_booking(booking_id) or {}
    if not snapshot.get("route") and booking.status not in {"completed", "cancelled"}:
        try:
            from ambulance.route_service import calculate_booking_route
            calculate_booking_route(booking, force=False, reason="tracking_opened")
            snapshot = snapshot_for_booking(booking_id) or snapshot
        except Exception:
            # The map can still open with markers while showing the explicit
            # traffic/route unavailable state in Flutter.
            pass
    return JsonResponse(snapshot, status=200)


@csrf_exempt
def tracking_route(request, booking_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    booking = Booking.objects.filter(id=booking_id).first()
    if not booking or not _authorize(request, booking):
        return JsonResponse({"error": "Not authorized"}, status=403)
    try:
        data = json.loads(request.body or "{}")
        route = calculate_booking_route(booking, force=True, reason=data.get("reason", "manual"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc), "traffic_available": False}, status=422)
    except Exception as exc:
        return JsonResponse({"error": str(exc), "traffic_available": False}, status=502)
    normalized = route_dict(route)
    broadcast(booking_id, EVENT_TYPES["route"], normalized)
    broadcast(booking_id, EVENT_TYPES["eta"], {"distance_m": normalized["distance_m"], "duration_s": normalized["duration_s"], "traffic_duration_s": normalized["traffic_duration_s"], "traffic_available": normalized["traffic_available"]})
    return JsonResponse(normalized, status=201)
