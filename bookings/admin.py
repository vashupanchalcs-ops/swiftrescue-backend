from django.contrib import admin
from django.utils import timezone

from .models import Booking, BookingChatMessage, BookingChatThread, VoiceBookingCall


class BookingChatThreadInline(admin.StackedInline):
    model = BookingChatThread
    extra = 0
    max_num = 1
    show_change_link = True
    fields = (
        "user_name",
        "user_email",
        "driver_name",
        "driver_email",
        "admin_email",
        "is_active",
        "last_message_at",
        "updated_at",
    )
    readonly_fields = ("last_message_at", "updated_at")


class BookingChatMessageInline(admin.TabularInline):
    model = BookingChatMessage
    extra = 0
    can_delete = False
    fields = (
        "sender_role",
        "sender_name",
        "message_type",
        "message",
        "seen_by_user",
        "seen_by_driver",
        "seen_by_admin",
        "created_at",
    )
    readonly_fields = ("sender_role", "sender_name", "message_type", "message", "created_at")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient_name",
        "ambulance_number",
        "assigned_hospital_name",
        "hospital_response",
        "status",
        "created_at",
        "is_read",
    )
    list_filter = ("status", "hospital_response", "insurance_status", "report_sent_to_hospital", "is_read")
    search_fields = (
        "ambulance_number",
        "booked_by",
        "patient_name",
        "patient_contact_number",
        "pickup_location",
        "assigned_hospital_name",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    inlines = [BookingChatThreadInline]
    actions = ("mark_as_read", "mark_as_unread")
    readonly_fields = (
        "created_at",
        "hospital_assigned_at",
        "hospital_alert_sent_at",
        "hospital_responded_at",
        "driver_report_sent_at",
        "report_submitted_at",
        "report_sent_to_hospital_at",
        "insurance_submitted_at",
        "insurance_reviewed_at",
        "sent_to_driver_at",
        "driver_task_completed_at",
        "driver_rejected_at",
        "reassigned_at",
    )
    fieldsets = (
        (
            "Dispatch",
            {
                "fields": (
                    "ambulance_id",
                    "ambulance_number",
                    "driver",
                    "driver_contact",
                    "status",
                    "is_read",
                    "created_at",
                )
            },
        ),
        (
            "Patient & Pickup",
            {
                "fields": (
                    "booked_by",
                    "booked_by_email",
                    "patient_name",
                    "patient_age",
                    "patient_gender",
                    "patient_contact_number",
                    "attendant_name",
                    "attendant_contact",
                    "pickup_location",
                    "pickup_landmark",
                    "pickup_city",
                    "pickup_district",
                    "pickup_latitude",
                    "pickup_longitude",
                    "destination",
                )
            },
        ),
        (
            "Hospital Assignment",
            {
                "fields": (
                    "assigned_hospital_id",
                    "assigned_hospital_name",
                    "assigned_hospital_address",
                    "assigned_hospital_contact",
                    "assigned_hospital_email",
                    "hospital_assigned_at",
                    "hospital_alert_sent",
                    "hospital_alert_sent_at",
                    "hospital_response",
                    "hospital_response_note",
                    "hospital_responded_at",
                )
            },
        ),
        (
            "Clinical Handover",
            {
                "fields": (
                    "patient_condition",
                    "vitals_summary",
                    "driver_voice_transcript",
                    "driver_modified_report",
                    "report_submitted_by",
                    "report_submitted_at",
                    "report_sent_to_hospital",
                    "report_sent_to_hospital_at",
                    "driver_report_sent_at",
                )
            },
        ),
        (
            "Insurance",
            {
                "fields": (
                    "insurance_full_name",
                    "insurance_dob",
                    "insurance_gender",
                    "insurance_provider",
                    "insurance_policy_member_id",
                    "insurance_policy_holder_name",
                    "insurance_government_id",
                    "insurance_sum_insured",
                    "insurance_emergency_nature",
                    "insurance_exclusions_waiting",
                    "insurance_status",
                    "insurance_hospital_note",
                    "insurance_submitted_by",
                    "insurance_submitted_at",
                    "insurance_reviewed_by",
                    "insurance_reviewed_at",
                )
            },
        ),
        (
            "Driver Workflow",
            {
                "fields": (
                    "sent_to_driver",
                    "sent_to_driver_at",
                    "driver_task_completed",
                    "driver_task_completed_at",
                    "driver_rejected_once",
                    "driver_rejected_at",
                    "driver_rejection_reason",
                    "reassigned_due_to_unavailability",
                    "reassigned_at",
                )
            },
        ),
    )

    @admin.action(description="Mark selected bookings as read")
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description="Mark selected bookings as unread")
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)


@admin.register(BookingChatThread)
class BookingChatThreadAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "booking",
        "user_name",
        "driver_name",
        "is_active",
        "user_online",
        "driver_online",
        "admin_online",
        "last_message_at",
        "updated_at",
    )
    search_fields = (
        "booking__id",
        "booking__patient_name",
        "user_name",
        "user_email",
        "driver_name",
        "driver_email",
    )
    list_filter = ("is_active", "user_online", "driver_online", "admin_online")
    ordering = ("-updated_at",)
    date_hierarchy = "updated_at"
    list_select_related = ("booking",)
    inlines = [BookingChatMessageInline]
    actions = ("close_threads", "reopen_threads")
    readonly_fields = (
        "created_at",
        "updated_at",
        "last_message_at",
        "user_last_seen_at",
        "driver_last_seen_at",
        "admin_last_seen_at",
    )
    fieldsets = (
        ("Linked Booking", {"fields": ("booking", "is_active")}),
        ("Participants", {"fields": ("user_name", "user_email", "driver_name", "driver_email", "admin_email")} ),
        (
            "Live Presence",
            {
                "fields": (
                    "user_online",
                    "user_typing",
                    "user_last_seen_at",
                    "driver_online",
                    "driver_typing",
                    "driver_last_seen_at",
                    "admin_online",
                    "admin_typing",
                    "admin_last_seen_at",
                )
            },
        ),
        ("Activity", {"fields": ("last_message_at", "created_at", "updated_at")}),
    )

    @admin.action(description="Close selected chat threads")
    def close_threads(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description="Reopen selected chat threads")
    def reopen_threads(self, request, queryset):
        queryset.update(is_active=True)


@admin.register(BookingChatMessage)
class BookingChatMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "booking_reference",
        "sender_role",
        "sender_name",
        "message_type",
        "message_preview",
        "seen_by_admin",
        "created_at",
    )
    search_fields = ("thread__booking__id", "thread__booking__patient_name", "sender_name", "message")
    list_filter = ("sender_role", "message_type", "seen_by_admin", "seen_by_driver", "seen_by_user")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_select_related = ("thread", "thread__booking")
    actions = ("mark_seen_by_admin", "mark_unseen_by_admin")
    readonly_fields = ("created_at",)
    fieldsets = (
        ("Conversation", {"fields": ("thread", "sender_role", "sender_name", "message_type", "message", "metadata")} ),
        ("Read Receipts", {"fields": ("seen_by_user", "seen_by_driver", "seen_by_admin")} ),
        ("Audit", {"fields": ("created_at",)}),
    )

    @admin.display(description="Booking", ordering="thread__booking__id")
    def booking_reference(self, obj):
        return f"#{obj.thread.booking_id}"

    @admin.display(description="Message")
    def message_preview(self, obj):
        return obj.message[:90] + ("..." if len(obj.message) > 90 else "")

    @admin.action(description="Mark selected messages as seen by admin")
    def mark_seen_by_admin(self, request, queryset):
        queryset.update(seen_by_admin=True)

    @admin.action(description="Mark selected messages as unseen by admin")
    def mark_unseen_by_admin(self, request, queryset):
        queryset.update(seen_by_admin=False)


@admin.register(VoiceBookingCall)
class VoiceBookingCallAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "call_sid",
        "from_number",
        "call_status",
        "current_step",
        "caller_name",
        "city",
        "district",
        "is_confirmed",
        "booking",
        "updated_at",
    )
    search_fields = ("call_sid", "from_number", "caller_name", "city", "district", "landmark")
    list_filter = ("call_status", "current_step", "is_confirmed")
    ordering = ("-updated_at",)
    date_hierarchy = "created_at"
    list_select_related = ("booking",)
    actions = ("mark_calls_ended",)
    readonly_fields = ("created_at", "updated_at", "ended_at")
    fieldsets = (
        ("Call", {"fields": ("call_sid", "from_number", "call_status", "current_step", "attempts", "is_confirmed")} ),
        ("Caller Location", {"fields": ("caller_name", "city", "district", "landmark")} ),
        ("Booking Outcome", {"fields": ("booking",)}),
        ("Audit", {"fields": ("created_at", "updated_at", "ended_at")} ),
    )

    @admin.action(description="Mark selected calls as ended")
    def mark_calls_ended(self, request, queryset):
        queryset.exclude(call_status="ended").update(call_status="ended", ended_at=timezone.now())
