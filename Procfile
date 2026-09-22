web: python manage.py migrate --noinput && python manage.py createcachetable 2>/dev/null || true; export ASGI_THREADS=${ASGI_THREADS:-4}; daphne -b 0.0.0.0 -p $PORT ambulance_tracker.asgi:application
