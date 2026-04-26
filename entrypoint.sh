#!/bin/sh
set -e

PORT="${PORT:-8000}"

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting uvicorn on port ${PORT}..."
exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT}"
