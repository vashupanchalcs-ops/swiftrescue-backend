from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Hospital, HospitalStaff

admin.site.register(Hospital)


@admin.register(HospitalStaff)
class HospitalStaffAdmin(admin.ModelAdmin):
    list_display = ["id", "hospital", "full_name", "role", "is_on_call", "is_active"]
    search_fields = ["full_name", "email", "contact_number", "specialization", "hospital__name"]
    list_filter = ["role", "is_on_call", "is_active"]
