from django.urls import path
from . import views

urlpatterns = [
    path("",           views.hospital_list),
    path("by-email/",  views.hospital_by_email),
    path("<str:id>/",  views.hospital_detail),
]
