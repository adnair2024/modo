#!/bin/bash
set -e

# Ensure venv is active if not already
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo "Error: Virtual environment not found."
        exit 1
    fi
fi

echo "Running migrations..."
flask db upgrade

echo "Starting server..."
export PYTHONNOUSERSITE=1
unset PYTHONPATH
export FLASK_DEBUG=1
flask run
