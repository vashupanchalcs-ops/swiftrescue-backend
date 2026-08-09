from django.db import models
from django.utils import timezone


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
    hospital_contract_id = models.CharField(max_length=80, blank=True, default="", db_index=True)
    registration_number = models.CharField(max_length=100, blank=True, default="", db_index=True)
    address            = models.CharField(max_length=300, blank=True, default="")
    city               = models.CharField(max_length=100, blank=True, default="")
    state              = models.CharField(max_length=100, blank=True, default="")
    pincode            = models.CharField(max_length=12, blank=True, default="")
    latitude           = models.CharField(max_length=50, blank=True, default="")
    longitude          = models.CharField(max_length=50, blank=True, default="")
    contact_number     = models.CharField(max_length=20, blank=True, default="")
    emergency_contact  = models.CharField(max_length=20, blank=True, default="")
    email              = models.EmailField(blank=True, default="")
    website            = models.URLField(blank=True, default="")
    contact_person_name = models.CharField(max_length=120, blank=True, default="")
    contact_person_role = models.CharField(max_length=120, blank=True, default="")
    hospital_type      = models.CharField(max_length=20, choices=TYPE_CHOICES, default="private")
    total_beds         = models.IntegerField(default=0)
    available_beds     = models.IntegerField(default=0)
    emergency_beds     = models.IntegerField(default=0)
    icu_beds           = models.IntegerField(default=0)
    available_icu_beds = models.IntegerField(default=0)
    oxygen_beds        = models.IntegerField(default=0)
    ventilators_total  = models.IntegerField(default=0)
    ventilators_available = models.IntegerField(default=0)
    ambulance_bays     = models.IntegerField(default=0)
    specializations    = models.TextField(blank=True, default="")
    facilities         = models.TextField(blank=True, default="")
    insurance_partners = models.TextField(blank=True, default="")
    notes              = models.TextField(blank=True, default="")
    emergency_services = models.BooleanField(default=False)
    is_24x7            = models.BooleanField(default=True)
    has_blood_bank     = models.BooleanField(default=False)
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES, default="closed")
    is_active          = models.BooleanField(default=True)
    last_capacity_updated = models.DateTimeField(null=True, blank=True)
    created_at         = models.DateTimeField(default=timezone.now, editable=False)
    updated_at         = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class HospitalStaff(models.Model):
    ROLE_CHOICES = [
        ("doctor", "Doctor"),
        ("nurse", "Nurse"),
        ("technician", "Technician"),
        ("support", "Support Staff"),
        ("coordinator", "Emergency Coordinator"),
        ("administrator", "Administrator"),
        ("other", "Other"),
    ]

    SHIFT_CHOICES = [
        ("day", "Day"),
        ("night", "Night"),
        ("rotational", "Rotational"),
        ("on_call", "On call"),
    ]

    hospital            = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="staff")
    full_name           = models.CharField(max_length=150)
    role                = models.CharField(max_length=20, choices=ROLE_CHOICES, default="doctor")
    specialization      = models.CharField(max_length=150, blank=True, default="")
    registration_number = models.CharField(max_length=100, blank=True, default="")
    contact_number      = models.CharField(max_length=20, blank=True, default="")
    email               = models.EmailField(blank=True, default="")
    years_experience    = models.PositiveSmallIntegerField(default=0)
    photo_data          = models.TextField(blank=True, default="")
    banner_data         = models.TextField(blank=True, default="")
    shift               = models.CharField(max_length=20, choices=SHIFT_CHOICES, default="day")
    is_on_call          = models.BooleanField(default=False)
    is_active           = models.BooleanField(default=True)
    joined_on           = models.DateField(null=True, blank=True)
    notes               = models.TextField(blank=True, default="")
    created_at          = models.DateTimeField(default=timezone.now, editable=False)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["hospital__name", "role", "full_name"]
        verbose_name = "Hospital Staff"
        verbose_name_plural = "Hospital Staff"

    def __str__(self):
        return f"{self.full_name} - {self.hospital.name}"
