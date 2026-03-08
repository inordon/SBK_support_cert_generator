#!/bin/sh
set -e

echo "Running collectstatic..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate --noinput

echo "Setting up Celery Beat schedule..."
python manage.py setup_celery_schedule

exec "$@"
