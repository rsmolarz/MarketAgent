#!/bin/bash
# Simple deployment script with explicit variables only
export PORT=5000
export WORKERS=1
export DEPLOYMENT_ENV=production

echo "Deploying Market Inefficiency Platform..."
echo "All variables explicitly set - no undefined references"
echo "PORT=$PORT WORKERS=$WORKERS ENV=$DEPLOYMENT_ENV"

# Simple gunicorn command with no variable references
gunicorn --bind 0.0.0.0:5000 --workers 1 --timeout 30 main:app