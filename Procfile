web: sh -c 'set -e; python manage.py migrate --noinput; exec daphne -b 0.0.0.0 -p ${PORT} ambulance_tracker.asgi:application'
