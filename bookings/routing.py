from django.urls import re_path
from bookings.consumers import ConsultationConsumer, BookingChatConsumer, TrackingConsumer, BookingTrackingConsumer

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<thread_id>\d+)/$", BookingChatConsumer.as_asgi()),
    re_path(r"ws/consultation/(?P<booking_id>\d+)/$", ConsultationConsumer.as_asgi()),
    re_path(r"ws/ambulances/(?P<ambulance_id>\d+)/$", TrackingConsumer.as_asgi()),
    re_path(r"ws/bookings/(?P<booking_id>\d+)/tracking/$", BookingTrackingConsumer.as_asgi()),
]
