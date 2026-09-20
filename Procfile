web: python manage.py migrate --noinput && python manage.py repair_sequences && python manage.py ensure_admin && daphne -b 0.0.0.0 -p $PORT ambulance_tracker.asgi:application
