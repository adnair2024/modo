#!/bin/sh
set -e

# Run database migrations
echo "Running database migrations..."
python repair_migrations.py
python sync_achievements.py
flask db upgrade

# Start the application
echo "Starting application..."
exec gunicorn --bind 0.0.0.0:8000 app:app