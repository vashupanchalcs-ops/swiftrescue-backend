from django.urls import path
from . import views

urlpatterns = [

    # ── Home ──────────────────────────────────────────────────────────────
    path("",                        views.home,                    name="home"),

    # ── Email OTP ─────────────────────────────────────────────────────────
    path("send-otp/",               views.send_otp,                name="send_otp"),
    path("verify-otp/",             views.verify_otp,              name="verify_otp"),
    path("logout/",                 views.logout_view,             name="logout"),

    # ── Phone OTP  (driver verification) ─────────────────────────────────
    path("send-phone-otp/",         views.send_phone_otp,          name="send_phone_otp"),
    path("verify-phone-otp/",       views.verify_phone_otp,        name="verify_phone_otp"),

    # ── Ambulances — STATIC paths MUST come before <int:id> ──────────────
    path("ambulances/by-driver/",             views.ambulance_by_driver_email,       name="ambulance_by_driver"),
    path("ambulances/change-request/delete/", views.ambulance_change_request_delete, name="change_request_delete"),
    path("ambulances/change-request/",        views.ambulance_change_request,        name="change_request"),
    path("ambulances/",                       views.ambulance_list,                  name="ambulance_list"),
    path("ambulances/<int:id>/",              views.ambulance_detail,                name="ambulance_detail"),

    # ── Driver Notifications (Server-side) ───────────────────────────────
    path("driver/notifications/",   views.get_driver_notifications,          name="driver_notifications"),

    # ── Driver GPS ────────────────────────────────────────────────────────
    path("driver/ping/",            views.driver_ping,                       name="driver_ping"),
    path("driver/location/",        views.get_driver_location_by_ambulance,  name="driver_location"),  # ✅ NEW — user live tracking
    path("driver/locations/",       views.get_driver_locations,              name="driver_locations"),
    path("driver/location/save/",   views.save_driver_location,              name="save_driver_location"),
    path("ambulance/<int:ambulance_id>/location-history/",
                                    views.get_location_history,              name="location_history"),

    # ── Suggested Routes ──────────────────────────────────────────────────
    path("routes/",                 views.save_suggested_route,    name="save_route"),
    path("driver/route/<int:route_id>/respond/",
                                    views.update_route_status,     name="update_route"),
    path("ambulance/<int:ambulance_id>/suggested-routes/",
                                    views.get_suggested_routes,    name="suggested_routes"),
    path("active-routes/",          views.get_active_routes,       name="active_routes"),
]