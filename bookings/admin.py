from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display  = ["id", "ambulance_number", "booked_by", "pickup_location", "status", "created_at", "is_read"]
    list_filter   = ["status", "is_read"]
    search_fields = ["ambulance_number", "booked_by", "pickup_location"]
    ordering      = ["-created_at"]