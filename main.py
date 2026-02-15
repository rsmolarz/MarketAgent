"""
Minimal WSGI entry for gunicorn. Zero non-stdlib imports at module level.
Health-check paths always return 200 instantly. Flask loads on first real request.
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

_HEALTH = frozenset(('/', '/healthz', '/health', '/ready', '/live', '/status'))
_flask_app = None


def app(environ, start_response):
    """WSGI entry. Health checks: instant 200. Everything else: lazy Flask."""
    global _flask_app

    path = environ.get('PATH_INFO', '/')

    if _flask_app is not None:
        return _flask_app(environ, start_response)

    if path in _HEALTH:
        body = b'OK'
        start_response('200 OK', [
            ('Content-Type', 'text/plain'),
            ('Content-Length', '2'),
        ])
        return [body]

    try:
        from app import create_app
        _flask_app = create_app()
        if _flask_app is not None:
            return _flask_app(environ, start_response)
    except Exception:
        logging.getLogger(__name__).exception("Failed to load Flask")

    body = b'Service starting, please retry.'
    start_response('503 Service Unavailable', [
        ('Content-Type', 'text/plain'),
        ('Content-Length', str(len(body))),
        ('Retry-After', '3'),
    ])
    return [body]
