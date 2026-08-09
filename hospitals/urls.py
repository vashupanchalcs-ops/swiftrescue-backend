from django.urls import path
from . import views

urlpatterns = [
    path("",           views.hospital_list),
    path("by-email/",  views.hospital_by_email),
    path("<int:id>/dashboard/", views.hospital_dashboard),
    path("<int:id>/resources/", views.hospital_resources),
    path("<int:hospital_id>/staff/", views.hospital_staff_list),
    path("<int:hospital_id>/staff/<int:staff_id>/", views.hospital_staff_detail),
    path("<str:id>/",  views.hospital_detail),
]
