from django.urls import path

from . import views


urlpatterns = [
    path("", views.booking_list),
    path("unread/", views.unread_count),
    path("mark-read/", views.mark_all_read),
    path("voice/call-alert/", views.voice_call_alert),
    path("chat/threads/", views.chat_threads),
    path("chat/threads/<int:thread_id>/messages/", views.chat_messages),
    path("chat/threads/<int:thread_id>/presence/", views.chat_presence),
    path("chat/threads/<int:thread_id>/read/", views.chat_mark_read),
    path("chat/threads/<int:thread_id>/driver-request/", views.chat_driver_request),
    path("<int:booking_id>/chat/thread/", views.booking_chat_thread),
    path("<int:id>/hospital-response/", views.booking_hospital_response),
    path("<int:id>/", views.booking_detail),
]
