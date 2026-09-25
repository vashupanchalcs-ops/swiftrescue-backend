from django.db import models


class Booking(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    PAYMENT_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("due", "Due"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]

    ambulance_id = models.IntegerField()
    ambulance_number = models.CharField(max_length=50, blank=True, default="")
    driver = models.CharField(max_length=100, blank=True, default="")
    driver_contact = models.CharField(max_length=20, blank=True, default="")
    booked_by = models.CharField(max_length=100)
    booked_by_email = models.CharField(max_length=100, blank=True, default="")
    pickup_location = models.CharField(max_length=300)
    pickup_latitude = models.FloatField(null=True, blank=True)
    pickup_longitude = models.FloatField(null=True, blank=True)
    pickup_landmark = models.CharField(max_length=200, blank=True, default="")
    pickup_city = models.CharField(max_length=120, blank=True, default="")
    pickup_district = models.CharField(max_length=120, blank=True, default="")
    patient_contact_number = models.CharField(max_length=30, blank=True, default="")
    destination = models.CharField(max_length=300, blank=True, default="")

    # A booking stores a snapshot of the selected hospital so historical cases remain readable.
    assigned_hospital_id = models.IntegerField(null=True, blank=True)
    assigned_hospital_name = models.CharField(max_length=200, blank=True, default="")
    assigned_hospital_address = models.CharField(max_length=300, blank=True, default="")
    assigned_hospital_contact = models.CharField(max_length=20, blank=True, default="")
    assigned_hospital_email = models.EmailField(blank=True, default="")
    hospital_assigned_at = models.DateTimeField(null=True, blank=True)
    hospital_alert_sent = models.BooleanField(default=False)
    hospital_alert_sent_at = models.DateTimeField(null=True, blank=True)
    hospital_response = models.CharField(max_length=20, blank=True, default="pending")
    hospital_response_note = models.CharField(max_length=300, blank=True, default="")
    hospital_responded_at = models.DateTimeField(null=True, blank=True)

    patient_name = models.CharField(max_length=120, blank=True, default="")
    patient_age = models.CharField(max_length=20, blank=True, default="")
    patient_gender = models.CharField(max_length=20, blank=True, default="")
    attendant_name = models.CharField(max_length=120, blank=True, default="")
    attendant_contact = models.CharField(max_length=30, blank=True, default="")
    patient_condition = models.TextField(blank=True, default="")
    vitals_summary = models.TextField(blank=True, default="")
    driver_voice_transcript = models.TextField(blank=True, default="")
    driver_modified_report = models.TextField(blank=True, default="")
    driver_report_sent_at = models.DateTimeField(null=True, blank=True)
    report_submitted_by = models.CharField(max_length=120, blank=True, default="")
    report_submitted_at = models.DateTimeField(null=True, blank=True)
    report_sent_to_hospital = models.BooleanField(default=False)
    report_sent_to_hospital_at = models.DateTimeField(null=True, blank=True)

    insurance_full_name = models.CharField(max_length=160, blank=True, default="")
    insurance_dob = models.CharField(max_length=40, blank=True, default="")
    insurance_gender = models.CharField(max_length=30, blank=True, default="")
    insurance_provider = models.CharField(max_length=160, blank=True, default="")
    insurance_policy_member_id = models.CharField(max_length=120, blank=True, default="")
    insurance_policy_holder_name = models.CharField(max_length=160, blank=True, default="")
    insurance_government_id = models.CharField(max_length=120, blank=True, default="")
    insurance_sum_insured = models.CharField(max_length=80, blank=True, default="")
    insurance_emergency_nature = models.TextField(blank=True, default="")
    insurance_exclusions_waiting = models.TextField(blank=True, default="")
    insurance_status = models.CharField(max_length=20, blank=True, default="pending")
    insurance_hospital_note = models.CharField(max_length=300, blank=True, default="")
    insurance_submitted_by = models.CharField(max_length=120, blank=True, default="")
    insurance_submitted_at = models.DateTimeField(null=True, blank=True)
    insurance_reviewed_by = models.CharField(max_length=120, blank=True, default="")
    insurance_reviewed_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="due")
    payment_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    payment_amount_due = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    payment_note = models.CharField(max_length=500, blank=True, default="")
    payment_updated_at = models.DateTimeField(null=True, blank=True)
    sent_to_driver = models.BooleanField(default=False)
    sent_to_driver_at = models.DateTimeField(null=True, blank=True)
    driver_task_completed = models.BooleanField(default=False)
    driver_task_completed_at = models.DateTimeField(null=True, blank=True)
    driver_accepted = models.BooleanField(default=False)
    driver_accepted_at = models.DateTimeField(null=True, blank=True)
    driver_status = models.CharField(max_length=20, blank=True, default="pending")
    patient_reached = models.BooleanField(default=False)
    patient_reached_at = models.DateTimeField(null=True, blank=True)
    driver_rejected_once = models.BooleanField(default=False)
    driver_rejected_at = models.DateTimeField(null=True, blank=True)
    driver_rejection_reason = models.CharField(max_length=200, blank=True, default="")
    reassigned_due_to_unavailability = models.BooleanField(default=False)
    reassigned_at = models.DateTimeField(null=True, blank=True)
    transfer_requested = models.BooleanField(default=False)
    transfer_requested_at = models.DateTimeField(null=True, blank=True)
    transfer_status = models.CharField(max_length=30, blank=True, default="")
    transfer_target_ambulance_id = models.IntegerField(null=True, blank=True)
    transfer_target_ambulance_number = models.CharField(max_length=50, blank=True, default="")
    transfer_from_ambulance_id = models.IntegerField(null=True, blank=True)
    transfer_from_ambulance_number = models.CharField(max_length=50, blank=True, default="")
    transfer_from_driver_email = models.CharField(max_length=120, blank=True, default="")
    transfer_from_driver_name = models.CharField(max_length=120, blank=True, default="")
    transferred_to_ambulance_id = models.IntegerField(null=True, blank=True)
    transferred_to_ambulance_number = models.CharField(max_length=50, blank=True, default="")
    transfer_approved_at = models.DateTimeField(null=True, blank=True)
    transfer_rejected_at = models.DateTimeField(null=True, blank=True)
    assigned_doctors_json = models.TextField(blank=True, default="[]")
    assigned_doctor_names = models.CharField(max_length=500, blank=True, default="")
    assigned_doctor_specializations = models.CharField(max_length=500, blank=True, default="")
    assigned_doctor_contacts = models.CharField(max_length=300, blank=True, default="")
    doctors_assigned_at = models.DateTimeField(null=True, blank=True)
    assigned_bed_id      = models.IntegerField(null=True, blank=True)
    assigned_bed_number  = models.CharField(max_length=50, blank=True, default="")
    assigned_bed_type    = models.CharField(max_length=20, blank=True, default="general")
    icu_required         = models.BooleanField(default=False)
    icu_requested_at     = models.DateTimeField(null=True, blank=True)
    assignment_distance_km = models.FloatField(null=True, blank=True)
    assignment_eta_seconds = models.PositiveIntegerField(null=True, blank=True)
    assignment_route_provider = models.CharField(max_length=40, blank=True, default="")
    assignment_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    is_user_selected_hospital = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["ambulance_id"]),
            models.Index(fields=["booked_by_email"]),
        ]
    def __str__(self):
        return f"{self.ambulance_number} - {self.booked_by}"


class PatientConditionPhoto(models.Model):
    PHOTO_TYPES = [
        ("ecg", "ECG"),
        ("patient", "Patient condition"),
        ("patient_id", "Patient ID"),
        ("vitals", "Vitals / monitor"),
        ("documents", "Medical document"),
        ("other", "Other"),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="condition_photos")
    photo_type = models.CharField(max_length=30, choices=PHOTO_TYPES, default="patient")
    instruction = models.CharField(max_length=300, blank=True, default="")
    # Keep the actual image in PostgreSQL so Render's ephemeral filesystem
    # cannot make a successful transfer disappear after a restart/deploy.
    # ``image`` remains for backwards compatibility with older rows.
    image = models.FileField(upload_to="condition_photos/%Y/%m/%d/", blank=True, default="")
    image_data = models.TextField(blank=True, default="")
    original_name = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=100, blank=True, default="")
    uploader_role = models.CharField(max_length=30, default="driver")
    uploader_name = models.CharField(max_length=120, blank=True, default="")
    uploader_email = models.EmailField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.get_photo_type_display()} for Booking #{self.booking_id}"


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

    def __str__(self):
        return f"Chat thread for booking #{self.booking_id}"


class BookingChatMessage(models.Model):
    SENDER_CHOICES = [
        ("system", "System"),
        ("admin", "Admin"),
        ("driver", "Driver"),
        ("user", "User"),
    ]
    TYPE_CHOICES = [
        ("text", "Text"),
        ("update", "Update"),
        ("request", "Request"),
        ("alert", "Alert"),
    ]

    thread = models.ForeignKey(BookingChatThread, on_delete=models.CASCADE, related_name="messages")
    sender_role = models.CharField(max_length=20, choices=SENDER_CHOICES, default="system")
    sender_name = models.CharField(max_length=120, blank=True, default="")
    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="text")
    message = models.TextField(blank=True, default="")
    metadata = models.TextField(blank=True, default="")
    seen_by_user = models.BooleanField(default=False)
    seen_by_driver = models.BooleanField(default=False)
    seen_by_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Chat message #{self.id} ({self.sender_role})"


class VoiceBookingCall(models.Model):
    STATUS_CHOICES = [
        ("ringing", "Ringing"),
        ("in_progress", "In Progress"),
        ("confirmed", "Confirmed"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("ended", "Ended"),
    ]

    call_sid = models.CharField(max_length=120, unique=True, db_index=True)
    from_number = models.CharField(max_length=30, blank=True, default="")
    call_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ringing")
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

    def __str__(self):
        return f"{self.call_sid} ({self.call_status})"


class VideoCallRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="video_call_requests")
    staff = models.ForeignKey("hospitals.HospitalStaff", on_delete=models.CASCADE, related_name="video_call_requests")
    driver_email = models.EmailField(blank=True, default="")
    driver_name = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at", "-id"]
        indexes = [
            models.Index(fields=["booking", "status"]),
            models.Index(fields=["staff", "status"]),
        ]

    def __str__(self):
        return f"Video request #{self.id} · Booking #{self.booking_id} · {self.staff.full_name} ({self.status})"
