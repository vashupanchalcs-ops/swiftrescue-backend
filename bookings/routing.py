from django.urls import re_path

from bookings.consumers import ConsultationConsumer


websocket_urlpatterns = [
    re_path(r"ws/consultation/(?P<booking_id>\d+)/$", ConsultationConsumer.as_asgi()),
]
