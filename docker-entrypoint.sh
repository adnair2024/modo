#!/bin/sh
set -e

echo "--- Starting MODO Deployment Entrypoint ---"

# Run database migrations - This is the CRITICAL part
echo "Running database migrations (flask db upgrade)..."
flask db upgrade || echo "Migration failed, but attempting to start anyway..."

# Run repair and sync in the background so they don't block the web server
echo "Starting background tasks (repair & sync)..."
(python repair_migrations.py && python sync_achievements.py && echo "Background tasks complete.") &

# Start the application with verbose logging
echo "Starting Gunicorn on port 8000..."
exec gunicorn --bind 0.0.0.0:8000 --access-logfile - --error-logfile - --log-level debug app:app
