from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from ambulance_tracker.pagination import parse_list_options

from .assignment import haversine_km
from .services import validate_status_transition


class BookingStatusTransitionTests(SimpleTestCase):
    def test_supported_transitions_are_accepted(self):
        for previous, current in (
            ("pending", "pending"),
            ("pending", "confirmed"),
            ("confirmed", "completed"),
            ("confirmed", "cancelled"),
        ):
            with self.subTest(previous=previous, current=current):
                self.assertEqual(validate_status_transition(previous, current), current)

    def test_closed_booking_cannot_be_reopened(self):
        with self.assertRaises(ValidationError):
            validate_status_transition("completed", "confirmed")

        with self.assertRaises(ValidationError):
            validate_status_transition("cancelled", "pending")


class DispatchHelperTests(SimpleTestCase):
    def test_haversine_distance_is_reasonable(self):
        self.assertAlmostEqual(haversine_km(28.6139, 77.2090, 28.6139, 78.2090), 97.5, delta=1.5)

    def test_pagination_is_bounded_and_opt_in(self):
        request = type("Request", (), {"GET": {"page": "2", "page_size": "999"}})()
        page, page_size, paginate = parse_list_options(request)
        self.assertEqual(page, 2)
        self.assertEqual(page_size, 200)
        self.assertTrue(paginate)
