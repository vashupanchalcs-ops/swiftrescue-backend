from django.db import models


class Booking(models.Model):
    STATUS_CHOICES = [
        ("pending",   "Pending"),
        ("confirmed", "Confirmed"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    ambulance_id     = models.IntegerField()
    ambulance_number = models.CharField(max_length=50, blank=True, default="")
    driver           = models.CharField(max_length=100, blank=True, default="")
    driver_contact   = models.CharField(max_length=20, blank=True, default="")
    booked_by        = models.CharField(max_length=100)
    booked_by_email  = models.CharField(max_length=100, blank=True, default="")
    pickup_location  = models.CharField(max_length=300)
    destination      = models.CharField(max_length=300, blank=True, default="")
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at       = models.DateTimeField(auto_now_add=True)
    is_read          = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.ambulance_number} — {self.booked_by}"


class BookingChatThread(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="chat_thread")
    user_email = models.CharField(max_length=120, blank=True, default="")
    user_name = models.CharField(max_length=120, blank=True, default="")
    driver_email = models.CharField(max_length=120, blank=True, default="")
    driver_name = models.CharField(max_length=120, blank=True, default="")
    admin_email = models.CharField(max_length=120, blank=True, default="")
    is_active = models.BooleanField(default=True)
    user_online = models.BooleanField(default=False)
    driver_online = models.BooleanField(default=False)
    admin_online = models.BooleanField(default=False)
    user_typing = models.BooleanField(default=False)
    driver_typing = models.BooleanField(default=False)
    admin_typing = models.BooleanField(default=False)
    user_last_seen_at = models.DateTimeField(null=True, blank=True)
    driver_last_seen_at = models.DateTimeField(null=True, blank=True)
    admin_last_seen_at = models.DateTimeField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class BookingChatMessage(models.Model):
    thread = models.ForeignKey(BookingChatThread, on_delete=models.CASCADE, related_name="messages")
    sender_role = models.CharField(max_length=20, default="system")
    sender_name = models.CharField(max_length=120, blank=True, default="")
    message_type = models.CharField(max_length=20, default="text")
    message = models.TextField(default="", blank=True)
    metadata = models.TextField(default="", blank=True)
    seen_by_user = models.BooleanField(default=False)
    seen_by_driver = models.BooleanField(default=False)
    seen_by_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class VoiceBookingCall(models.Model):
    call_sid = models.CharField(max_length=120, unique=True, db_index=True)
    from_number = models.CharField(max_length=30, blank=True, default="")
    call_status = models.CharField(max_length=20, default="ringing")
    current_step = models.CharField(max_length=30, blank=True, default="name")
    caller_name = models.CharField(max_length=120, blank=True, default="")
    city = models.CharField(max_length=120, blank=True, default="")
    district = models.CharField(max_length=120, blank=True, default="")
    landmark = models.CharField(max_length=180, blank=True, default="")
    attempts = models.IntegerField(default=0)
    is_confirmed = models.BooleanField(default=False)
    booking = models.ForeignKey(Booking, null=True, blank=True, on_delete=models.SET_NULL, related_name="voice_calls")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)
