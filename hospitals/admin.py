from django.contrib import admin
from .models import Hospital


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = (
        "name", "hospital_contract_id", "city", "contact_number", "available_beds",
        "available_icu_beds", "ventilators_available", "status", "is_active",
    )
    list_filter = ("hospital_type", "status", "is_active", "emergency_services", "is_24x7", "has_blood_bank")
    search_fields = ("name", "hospital_contract_id", "registration_number", "email", "contact_number", "city")
    list_editable = ("available_beds", "available_icu_beds", "ventilators_available", "status", "is_active")
    readonly_fields = ("created_at", "updated_at", "last_capacity_updated")
    fieldsets = (
        ("Identity & Contracts", {"fields": ("name", "hospital_type", "hospital_contract_id", "registration_number", "status", "is_active")} ),
        ("Address & Contact", {"fields": ("address", "city", "state", "pincode", "latitude", "longitude", "contact_number", "emergency_contact", "email", "website")} ),
        ("Primary Contact", {"fields": ("contact_person_name", "contact_person_role")} ),
        ("Beds & Emergency Capacity", {"fields": ("total_beds", "available_beds", "emergency_beds", "icu_beds", "available_icu_beds", "oxygen_beds", "ventilators_total", "ventilators_available", "ambulance_bays", "last_capacity_updated")} ),
        ("Clinical Services", {"fields": ("specializations", "facilities", "emergency_services", "is_24x7", "has_blood_bank", "insurance_partners")} ),
        ("Notes & Audit", {"fields": ("notes", "created_at", "updated_at")} ),
    )
