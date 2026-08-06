from django.db import models


class Hospital(models.Model):

    TYPE_CHOICES = [
        ("government", "Government"),
        ("private",    "Private"),
        ("semi_govt",  "Semi-Government"),
    ]

    STATUS_CHOICES = [
        ("active",   "Active"),
        ("critical", "Critical"),
        ("full",     "Full"),
        ("closed",   "Closed"),
    ]

    name               = models.CharField(max_length=200)
    hospital_contract_id = models.CharField(max_length=80, blank=True, default="")
    registration_number = models.CharField(max_length=80, blank=True, default="")
    address            = models.CharField(max_length=300, blank=True, default="")
    latitude           = models.CharField(max_length=50, blank=True, default="")
    longitude          = models.CharField(max_length=50, blank=True, default="")
    contact_number     = models.CharField(max_length=20, blank=True, default="")
    email              = models.EmailField(blank=True, default="")
    hospital_type      = models.CharField(max_length=20, choices=TYPE_CHOICES, default="private")
    total_beds         = models.IntegerField(default=0)
    available_beds     = models.IntegerField(default=0)
    icu_beds           = models.IntegerField(default=0)
    total_ventilators  = models.IntegerField(default=0)
    available_ventilators = models.IntegerField(default=0)
    specializations    = models.TextField(blank=True, default="")
    emergency_services = models.BooleanField(default=False)
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES, default="closed")
    is_active          = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class HospitalStaff(models.Model):
    ROLE_CHOICES = [
        ("doctor", "Doctor"),
        ("nurse", "Nurse"),
        ("technician", "Technician"),
        ("support", "Support"),
    ]

    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="staff")
    full_name = models.CharField(max_length=120)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="doctor")
    specialization = models.CharField(max_length=120, blank=True, default="")
    contact_number = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    is_on_call = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    years_experience = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} ({self.role})"
