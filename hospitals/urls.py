from django.urls import path
from . import views

urlpatterns = [
    path("",           views.hospital_list),
    path("by-email/",  views.hospital_by_email),
    path("<int:id>/dashboard/", views.hospital_dashboard),
    path("<str:id>/",  views.hospital_detail),
]
