from django.urls import path
from . import views

urlpatterns = [
    path("",             views.booking_list),
    path("unread/",      views.unread_count),
    path("mark-read/",   views.mark_all_read),
    path("<int:id>/",    views.booking_detail),
]