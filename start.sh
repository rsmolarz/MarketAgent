#!/bin/bash
# Ultra-robust production startup script - zero undefined variables
set -e  # Exit on any error

# Set all variables explicitly with safe defaults
export DEPLOYMENT_ENV="production"
export PORT="${PORT:-5000}"
export WORKERS="${WORKERS:-1}"

# Validate critical variables
if [ -z "$PORT" ]; then
    export PORT="5000"
fi

echo "Market Inefficiency Platform starting..."
echo "Port: $PORT"
echo "Workers: $WORKERS" 
echo "Environment: $DEPLOYMENT_ENV"

# Start with robust configuration for deployment systems
exec gunicorn \
    --bind "0.0.0.0:$PORT" \
    --workers "$WORKERS" \
    --timeout 30 \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --preload \
    --access-logfile - \
    --error-logfile - \
    main:app