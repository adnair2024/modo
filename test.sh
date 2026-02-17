#!/bin/bash
set -e

if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo "Error: Virtual environment not found."
        exit 1
    fi
fi

pip install pytest pytest-cov coverage

echo "Running tests with coverage..."
pytest --cov=app --cov=routes --cov=models --cov=utils --cov-report=term-missing tests/
