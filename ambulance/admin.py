from django.contrib import admin
from .models import Ambulance, DriverLocation, SuggestedRoute


@admin.register(Ambulance)
class AmbulanceAdmin(admin.ModelAdmin):
    list_display  = ["ambulance_number", "driver", "driver_email", "status", "location"]
    search_fields = ["ambulance_number", "driver", "driver_email"]
    list_filter   = ["status"]


@admin.register(DriverLocation)
class DriverLocationAdmin(admin.ModelAdmin):
    list_display    = ["ambulance", "driver_email", "timestamp", "latitude", "longitude", "speed"]
    list_filter     = ["driver_email", "timestamp"]
    search_fields   = ["driver_email", "ambulance__ambulance_number"]
    date_hierarchy  = "timestamp"
    readonly_fields = ["timestamp"]


@admin.register(SuggestedRoute)
class SuggestedRouteAdmin(admin.ModelAdmin):
    list_display    = ["id", "ambulance", "pickup_location", "status", "distance_km", "created_at"]
    list_filter     = ["status", "created_at"]
    search_fields   = ["ambulance__ambulance_number", "pickup_location"]
    date_hierarchy  = "created_at"
    readonly_fields = ["created_at", "accepted_at", "completed_at"]