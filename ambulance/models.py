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
    ambulance_contract_id = models.CharField(max_length=80, blank=True, default="")
    registration_number = models.CharField(max_length=80, blank=True, default="")
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

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["driver_email"]),
        ]

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
    booking_id      = models.IntegerField(null=True, blank=True, db_index=True)
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


class UserProfile(models.Model):
    """
    Stores every user who logs in — all roles (user, driver, hospital, staff, admin).
    Synced from frontend via /api/auth/sync-user/ on every login.
    """
    ROLE_CHOICES = [
        ("user",     "User"),
        ("driver",   "Driver"),
        ("hospital", "Hospital"),
        ("staff",    "Staff"),
        ("admin",    "Admin"),
    ]

    email            = models.EmailField(unique=True, db_index=True)
    name             = models.CharField(max_length=200, blank=True, default="")
    phone            = models.CharField(max_length=30, blank=True, default="")
    role             = models.CharField(max_length=20, choices=ROLE_CHOICES, default="user", db_index=True)

    # Driver-specific
    ambulance_id     = models.IntegerField(null=True, blank=True)
    ambulance_number = models.CharField(max_length=80, blank=True, default="")
    contract_id      = models.CharField(max_length=80, blank=True, default="")
    registration_number = models.CharField(max_length=80, blank=True, default="")

    # Hospital/Staff-specific
    hospital_id      = models.IntegerField(null=True, blank=True)
    hospital_name    = models.CharField(max_length=200, blank=True, default="")
    staff_id         = models.CharField(max_length=80, blank=True, default="")
    staff_role       = models.CharField(max_length=80, blank=True, default="")

    # Login metadata
    login_count      = models.IntegerField(default=0)
    first_login_at   = models.DateTimeField(auto_now_add=True)
    last_login_at    = models.DateTimeField(auto_now=True)
    last_login_ip    = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-last_login_at"]
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["email"]),
            models.Index(fields=["-last_login_at"]),
        ]

    def __str__(self):
        return f"{self.email} ({self.role})"