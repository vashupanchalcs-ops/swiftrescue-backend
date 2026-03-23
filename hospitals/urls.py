from django.urls import path
from . import views

urlpatterns = [
    path("",           views.hospital_list),
    path("<str:id>/",  views.hospital_detail),
]