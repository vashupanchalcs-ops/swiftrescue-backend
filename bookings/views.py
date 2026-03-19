from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.mail import send_mail
from bookings.models import Booking
from ambulance.models import Ambulance
import json


def booking_to_dict(b):
    return {
        "id":               b.id,
        "ambulance_id":     b.ambulance_id,
        "ambulance_number": b.ambulance_number,
        "driver":           b.driver,
        "driver_contact":   b.driver_contact,
        "booked_by":        b.booked_by,
        "booked_by_email":  b.booked_by_email,
        "pickup_location":  b.pickup_location,
        "destination":      b.destination,
        "status":           b.status,
        "created_at":       b.created_at.strftime("%d %b %Y, %I:%M %p"),
        "is_read":          b.is_read,
    }


@csrf_exempt
def booking_list(request):

    if request.method == "GET":
        bookings = Booking.objects.all().order_by("-created_at")
        return JsonResponse([booking_to_dict(b) for b in bookings], safe=False)

    if request.method == "POST":
        data = json.loads(request.body)

        # Driver email ambulance se fetch karo
        driver_email = ""
        try:
            amb          = Ambulance.objects.get(id=data.get("ambulance_id"))
            driver_email = amb.driver_email or ""
        except Ambulance.DoesNotExist:
            pass

        b = Booking.objects.create(
            ambulance_id     = data.get("ambulance_id"),
            ambulance_number = data.get("ambulance_number", ""),
            driver           = data.get("driver", ""),
            driver_contact   = data.get("driver_contact", ""),
            booked_by        = data.get("booked_by", ""),
            booked_by_email  = data.get("booked_by_email", ""),
            pickup_location  = data.get("pickup_location", ""),
            destination      = data.get("destination", ""),
            status           = "pending",
        )

        # Driver ko email bhejo
        if driver_email:
            try:
                send_mail(
                    subject        = f"🚨 New Booking — {b.ambulance_number}",
                    message        = f"""Namaskar {b.driver},

Aapko ek naya emergency booking request mila hai:

━━━━━━━━━━━━━━━━━━━━━━
📋 Booking ID    : #{b.id}
👤 Patient       : {b.booked_by}
📧 Patient Email : {b.booked_by_email}
📍 Pickup        : {b.pickup_location}
🏥 Destination   : {b.destination or 'Nearest hospital'}
━━━━━━━━━━━━━━━━━━━━━━

Kripya turant patient ke paas pahunchen.

— SwiftRescue Dispatch Team
""",
                    from_email     = "vashupanchal.cs@gmail.com",
                    recipient_list = [driver_email],
                    fail_silently  = True,
                )
            except Exception as e:
                print("Driver email error:", e)

        # Ambulance status en_route karo
        try:
            amb        = Ambulance.objects.get(id=data.get("ambulance_id"))
            amb.status = "en_route"
            amb.save()
        except Ambulance.DoesNotExist:
            pass

        return JsonResponse(booking_to_dict(b), status=201)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def booking_detail(request, id):

    try:
        b = Booking.objects.get(id=id)
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(booking_to_dict(b))

    if request.method == "PATCH":
        data       = json.loads(request.body)
        new_status = data.get("status")

        if "is_read" in data:
            b.is_read = data["is_read"]

        if new_status:
            valid = {"pending", "confirmed", "completed", "cancelled"}
            if new_status not in valid:
                return JsonResponse({"error": f"Invalid status. Use: {valid}"}, status=400)
            b.status = new_status
            b.save()

            # Ambulance status update karo
            try:
                amb = Ambulance.objects.get(id=b.ambulance_id)
                if new_status in ("completed", "cancelled"):
                    amb.status = "available"
                elif new_status == "confirmed":
                    amb.status = "en_route"
                amb.save()
            except Ambulance.DoesNotExist:
                pass

            # Driver email fetch karo
            try:
                amb          = Ambulance.objects.get(id=b.ambulance_id)
                driver_email = amb.driver_email or ""
            except Ambulance.DoesNotExist:
                driver_email = ""

            # Confirmed hone par driver ko email
            if new_status == "confirmed" and driver_email:
                try:
                    send_mail(
                        subject        = f"✅ Booking Confirmed — {b.ambulance_number}",
                        message        = f"""Namaskar {b.driver},

Aapki booking admin ne confirm kar di hai. Turant jaiye!

━━━━━━━━━━━━━━━━━━━━━━
📋 Booking ID : #{b.id}
👤 Patient    : {b.booked_by}
📍 Pickup     : {b.pickup_location}
🏥 Hospital   : {b.destination or 'Nearest available'}
━━━━━━━━━━━━━━━━━━━━━━

— SwiftRescue Dispatch Team
""",
                        from_email     = "vashupanchal.cs@gmail.com",
                        recipient_list = [driver_email],
                        fail_silently  = True,
                    )
                except Exception as e:
                    print("Confirm email error:", e)

        else:
            b.save()

        return JsonResponse(booking_to_dict(b))

    if request.method == "DELETE":
        b.delete()
        return JsonResponse({"status": "deleted"})

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def unread_count(request):
    count = Booking.objects.filter(is_read=False).count()
    return JsonResponse({"unread": count})


@csrf_exempt
def mark_all_read(request):
    if request.method == "POST":
        Booking.objects.filter(is_read=False).update(is_read=True)
        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "Method not allowed"}, status=405)