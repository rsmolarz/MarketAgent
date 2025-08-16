#!/bin/bash
# Production startup script for deployment - no undefined variables
export DEPLOYMENT_ENV=production
export PORT="${PORT:-5000}"
export WORKERS="${WORKERS:-1}"
echo "Starting application on port $PORT with $WORKERS workers"
exec gunicorn --bind 0.0.0.0:$PORT --workers $WORKERS --timeout 30 --keep-alive 2 --access-logfile - --error-logfile - main:app