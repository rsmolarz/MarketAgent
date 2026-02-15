"""
WSGI entry point for gunicorn.
Reserved VM deployment - no lazy loading needed.
"""

import os
import logging

if ('gunicorn' in os.environ.get('SERVER_SOFTWARE', '') or
    os.environ.get('REPLIT_DEPLOYMENT') == '1' or
    'gunicorn' in ' '.join(os.environ.get('_', '').split('/'))):
    os.environ['DEPLOYMENT_ENV'] = 'production'

logging.basicConfig(
    level=logging.INFO if os.environ.get('DEPLOYMENT_ENV') == 'production' else logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler()]
)

import app as app_module
from app import create_app

app = create_app()
app_module.app = app
