from django.urls import path
from . import views

urlpatterns = [
    path("",             views.booking_list),
    path("unread/",      views.unread_count),
    path("mark-read/",   views.mark_all_read),
    path("voice/call-alert/", views.voice_call_alert),
    path("<int:id>/",    views.booking_detail),
]
