from django.contrib import admin
from .models import Booking, BookingChatThread, BookingChatMessage, VoiceBookingCall


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display  = ["id", "ambulance_number", "booked_by", "pickup_location", "status", "created_at", "is_read"]
    list_filter   = ["status", "is_read"]
    search_fields = ["ambulance_number", "booked_by", "pickup_location"]
    ordering      = ["-created_at"]


@admin.register(BookingChatThread)
class BookingChatThreadAdmin(admin.ModelAdmin):
    list_display = ["id", "booking", "user_name", "driver_name", "is_active", "last_message_at", "updated_at"]
    search_fields = ["booking__id", "user_name", "user_email", "driver_name", "driver_email"]
    list_filter = ["is_active", "user_online", "driver_online", "admin_online"]
    ordering = ["-updated_at"]


@admin.register(BookingChatMessage)
class BookingChatMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "thread", "sender_role", "message_type", "created_at"]
    search_fields = ["thread__booking__id", "sender_name", "message"]
    list_filter = ["sender_role", "message_type", "seen_by_admin", "seen_by_driver", "seen_by_user"]
    ordering = ["-created_at"]


@admin.register(VoiceBookingCall)
class VoiceBookingCallAdmin(admin.ModelAdmin):
    list_display = ["id", "call_sid", "from_number", "call_status", "current_step", "caller_name", "city", "district", "is_confirmed", "booking", "updated_at"]
    search_fields = ["call_sid", "from_number", "caller_name", "city", "district", "landmark"]
    list_filter = ["call_status", "current_step", "is_confirmed"]
    ordering = ["-updated_at"]
