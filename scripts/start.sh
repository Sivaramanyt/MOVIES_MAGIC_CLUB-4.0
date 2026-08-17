#!/bin/sh
set -eu

echo "Running database migrations..."
alembic upgrade head
echo "Database migrations completed."

echo "Starting MOVIES MAGIC CLUB 4.0..."
exec uvicorn app.main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8000}"
