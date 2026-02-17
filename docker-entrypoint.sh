#!/bin/sh
set -e

# Default to port 8000 if PORT is not set (e.g., local Docker)
PORT="${PORT:-8000}"

echo "--- Starting MODO Deployment Entrypoint ---"
echo "Target Port: $PORT"

# Run database migrations - This is the CRITICAL part
echo "Running database migrations (flask db upgrade)..."
flask db upgrade || echo "Migration failed, but attempting to start anyway..."

# Run repair and sync in the background so they don't block the web server
echo "Starting background tasks (repair & sync)..."
(python repair_migrations.py && python sync_achievements.py && echo "Background tasks complete.") &

# Start the application with verbose logging and bind to $PORT
echo "Starting Gunicorn on port $PORT..."
exec gunicorn --bind 0.0.0.0:$PORT --access-logfile - --error-logfile - --log-level debug --workers 2 --timeout 120 app:app
