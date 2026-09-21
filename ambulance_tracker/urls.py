from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from ambulance import views
from hospitals import views as hospital_views
from ambulance.route_views import get_route, get_route_by_booking
from ambulance.tracking_views import (
    driver_ping,
    all_live_locations,
    suggest_route,
    respond_route,
    driver_active_route,
    get_traffic_route,
    active_route_by_booking,
)

from django.http import JsonResponse

urlpatterns = [
    path("", views.home),
    path("favicon.ico", views.favicon),
    path("admin/", admin.site.urls),
    path("api/health/", lambda req: JsonResponse({"status": "ok", "service": "aarogya"})),

    # ── OTP & AUTH ──────────────────────────────────
    path("api/send-otp/",         views.send_otp),
    path("api/verify-otp/",       views.verify_otp),
    path("api/send-phone-otp/",   views.send_phone_otp),
    path("api/verify-phone-otp/", views.verify_phone_otp),
    path("api/auth/contract-validate/", views.validate_contract_access),
    path("api/auth/sync-user/",         views.sync_user),
    path("api/logout/",           views.logout_view),
    path("api/auth/staff-signup/", hospital_views.staff_signup),
    path("api/auth/staff-login/",  hospital_views.staff_login),
    path("api/staff/dashboard/",    hospital_views.staff_dashboard),
    path("api/staff/notifications/", hospital_views.staff_notifications),

    # ── AMBULANCE — static paths BEFORE <int:id> ────
    path("api/ambulances/",                       views.ambulance_list),
    path("api/ambulances/by-driver/",             views.ambulance_by_driver_email),
    path("api/ambulances/change-request/delete/", views.ambulance_change_request_delete),  # ✅ NEW
    path("api/ambulances/change-request/",        views.ambulance_change_request),
    path("api/ambulances/<int:id>/",              views.ambulance_detail),

    # ── DRIVER NOTIFICATIONS ─────────────────────────
    path("api/driver/notifications/",                views.get_driver_notifications),

    # ── REAL-TIME GPS TRACKING ───────────────────────
    path("api/driver/ping/",                         driver_ping),
    path("api/driver/active-route/",                 driver_active_route),
    path("api/driver/route/<int:route_id>/respond/", respond_route),

    path("api/admin/live-locations/",    all_live_locations),
    path("api/admin/suggest-route/",     suggest_route),
    path("api/admin/traffic-route/",     get_traffic_route),
    path("api/route/active/<int:booking_id>/", active_route_by_booking),

    # ── HOSPITALS & BOOKINGS ─────────────────────────
    path("api/hospitals/", include("hospitals.urls")),
    path("api/bookings/",  include("bookings.urls")),

    # ── GOOGLE ROUTE CALCULATION ─────────────────────
    path("api/route/",                          get_route),
    path("api/route/booking/<int:booking_id>/", get_route_by_booking),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
