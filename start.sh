#!/bin/bash
# Production startup script for deployment
export DEPLOYMENT_ENV=production
exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers ${WORKERS:-1} --timeout 30 --keep-alive 2 main:app