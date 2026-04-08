#!/bin/sh
set -eu

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

python manage.py migrate --noinput
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-60}"
