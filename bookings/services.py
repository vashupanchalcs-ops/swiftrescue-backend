from django.core.exceptions import ValidationError


ALLOWED_STATUS_TRANSITIONS = {
    "pending": {"pending", "confirmed", "cancelled"},
    "confirmed": {"confirmed", "completed", "cancelled"},
    "completed": {"completed"},
    "cancelled": {"cancelled"},
}


def validate_status_transition(current, requested):
    """Validate and return a booking status transition."""
    current = str(current or "").strip().lower()
    requested = str(requested or "").strip().lower()
    allowed = ALLOWED_STATUS_TRANSITIONS.get(current, {current})
    if requested not in allowed:
        raise ValidationError(f"Invalid booking transition: {current} → {requested}.")
    return requested
