web: sh -c 'set -e; python manage.py migrate --noinput; python manage.py createcachetable --verbosity 0 || true; exec daphne -b 0.0.0.0 -p ${PORT} ambulance_tracker.asgi:application'
