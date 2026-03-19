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
    address            = models.CharField(max_length=300, blank=True, default="")
    latitude           = models.CharField(max_length=50, blank=True, default="")
    longitude          = models.CharField(max_length=50, blank=True, default="")
    contact_number     = models.CharField(max_length=20, blank=True, default="")
    email              = models.EmailField(blank=True, default="")
    hospital_type      = models.CharField(max_length=20, choices=TYPE_CHOICES, default="private")
    total_beds         = models.IntegerField(default=0)
    available_beds     = models.IntegerField(default=0)
    icu_beds           = models.IntegerField(default=0)
    specializations    = models.TextField(blank=True, default="")
    emergency_services = models.BooleanField(default=False)
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES, default="closed")
    is_active          = models.BooleanField(default=True)

    def __str__(self):
        return self.name