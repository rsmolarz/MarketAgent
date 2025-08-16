#!/bin/bash
# BULLETPROOF Deployment Startup Script 
# Eliminates ALL undefined variable issues for deployment systems

# Exit on any error
set -e

# Explicitly set ALL variables to prevent undefined errors
export PORT="${PORT:-5000}"
export WORKERS="${WORKERS:-1}"
export TIMEOUT="${TIMEOUT:-30}"
export KEEP_ALIVE="${KEEP_ALIVE:-2}"
export MAX_REQUESTS="${MAX_REQUESTS:-1000}"
export MAX_REQUESTS_JITTER="${MAX_REQUESTS_JITTER:-100}"
export DEPLOYMENT_ENV="production"

# Validate critical variables exist
if [ -z "$PORT" ]; then
    echo "ERROR: PORT not set, defaulting to 5000"
    export PORT="5000"
fi

echo "🚀 Market Inefficiency Platform - Production Startup"
echo "=================================================="
echo "Port: $PORT"
echo "Workers: $WORKERS"
echo "Timeout: $TIMEOUT seconds"
echo "Keep-Alive: $KEEP_ALIVE seconds"
echo "Max Requests: $MAX_REQUESTS"
echo "Environment: $DEPLOYMENT_ENV"
echo "=================================================="

# Start with bulletproof gunicorn configuration for deployment systems
exec gunicorn \
    --bind "0.0.0.0:$PORT" \
    --workers "$WORKERS" \
    --timeout "$TIMEOUT" \
    --keep-alive "$KEEP_ALIVE" \
    --max-requests "$MAX_REQUESTS" \
    --max-requests-jitter "$MAX_REQUESTS_JITTER" \
    --preload \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    main:app