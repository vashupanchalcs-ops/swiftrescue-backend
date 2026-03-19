from django.db import models


class Ambulance(models.Model):
    STATUS_CHOICES = [
        ("available", "Available"),
        ("en_route",  "En Route"),
        ("busy",      "Busy"),
        ("offline",   "Offline"),
    ]

    ambulance_number  = models.CharField(max_length=50)
    driver            = models.CharField(max_length=100)
    driver_contact    = models.CharField(max_length=20, blank=True)
    driver_email      = models.EmailField(blank=True, null=True)
    model             = models.CharField(max_length=100, blank=True)
    speed             = models.CharField(max_length=20, default="0")
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default="offline")
    location          = models.CharField(max_length=200, blank=True)
    nearest_hospital  = models.CharField(max_length=200, blank=True)
    hospital_distance = models.CharField(max_length=50, blank=True)
    eta_to_patient    = models.CharField(max_length=50, blank=True)
    eta_to_hospital   = models.CharField(max_length=50, blank=True)
    latitude          = models.FloatField(null=True, blank=True)
    longitude         = models.FloatField(null=True, blank=True)
    last_updated      = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.ambulance_number


class DriverLocation(models.Model):
    ambulance    = models.ForeignKey(Ambulance, on_delete=models.CASCADE, related_name="locations")
    driver_email = models.EmailField()
    latitude     = models.FloatField()
    longitude    = models.FloatField()
    speed        = models.FloatField(default=0)
    timestamp    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.driver_email} @ {self.timestamp}"

    class Meta:
        ordering = ["-timestamp"]


class SuggestedRoute(models.Model):
    STATUS_CHOICES = [
        ("pending",   "Pending"),
        ("accepted",  "Accepted"),
        ("rejected",  "Rejected"),
        ("completed", "Completed"),
    ]

    ambulance       = models.ForeignKey(Ambulance, on_delete=models.CASCADE, related_name="suggested_routes")
    pickup_location = models.CharField(max_length=300)
    destination     = models.CharField(max_length=300, blank=True)
    polyline        = models.TextField(blank=True)
    distance_km     = models.CharField(max_length=50, blank=True)
    duration        = models.CharField(max_length=50, blank=True)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    # Coordinates for driver map (set by admin when suggesting route)
    pickup_lat      = models.FloatField(null=True, blank=True)
    pickup_lng      = models.FloatField(null=True, blank=True)
    dest_lat        = models.FloatField(null=True, blank=True)
    dest_lng        = models.FloatField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    accepted_at     = models.DateTimeField(null=True, blank=True)
    completed_at    = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Route #{self.id} — {self.ambulance.ambulance_number}"

    class Meta:
        ordering = ["-created_at"]