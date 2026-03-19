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