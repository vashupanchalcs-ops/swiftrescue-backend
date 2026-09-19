from django.urls import path
from . import views

urlpatterns = [
    path("",           views.hospital_list),
    path("by-email/",  views.hospital_by_email),
    path("<int:id>/dashboard/", views.hospital_dashboard),
    path("<int:id>/resources/", views.hospital_resources),
    path("<int:hospital_id>/staff/", views.hospital_staff_list),
    path("<int:hospital_id>/staff/<int:staff_id>/", views.hospital_staff_detail),
    path("<int:hospital_id>/beds/",         views.hospital_beds),
    path("<int:hospital_id>/beds/assign/",  views.assign_bed_to_booking),
    path("<int:hospital_id>/beds/switch-icu/", views.switch_to_icu_bed),
    path("beds/<int:bed_id>/",              views.hospital_bed_detail),
    path("<str:id>/",  views.hospital_detail),
]
