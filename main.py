"""
Ultra-minimal WSGI entry point for gunicorn.

Health-check paths (including /) ALWAYS return 200 instantly, no matter what.
The full Flask app is loaded lazily on the first non-health-check request.
No background threads, no imports beyond stdlib at module level.
"""

import os
import sys
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

_OK_BODY = b'OK'

_LOADING = (
    b'<!DOCTYPE html><html><head><title>Loading</title>'
    b'<meta http-equiv="refresh" content="3"></head>'
    b'<body style="background:#1a1a2e;color:#c9a84c;display:flex;'
    b'align-items:center;justify-content:center;height:100vh;'
    b'font-family:sans-serif"><div style="text-align:center">'
    b'<h1>Market Inefficiency Agents</h1>'
    b'<p>Platform is starting up, please wait...</p>'
    b'</div></body></html>'
)

_flask_app = None


def _get_flask():
    """Load and cache the Flask application (called once, on first real request)."""
    global _flask_app
    if _flask_app is not None:
        return _flask_app
    try:
        logging.getLogger(__name__).info("Loading Flask application...")
        from app import create_app
        _flask_app = create_app()
        logging.getLogger(__name__).info("Flask application loaded")
    except Exception:
        logging.getLogger(__name__).exception("Failed to load Flask")
    return _flask_app


def app(environ, start_response):
    """WSGI callable – health checks are always instant."""
    path = environ.get('PATH_INFO', '/')

    if path in _HEALTH:
        flask = _flask_app
        if flask is not None:
            return flask(environ, start_response)
        start_response('200 OK', [
            ('Content-Type', 'text/plain'),
            ('Content-Length', '2'),
        ])
        return [_OK_BODY]

    flask = _flask_app
    if flask is None:
        flask = _get_flask()

    if flask is not None:
        return flask(environ, start_response)

    start_response('503 Service Unavailable', [
        ('Content-Type', 'text/html; charset=utf-8'),
        ('Retry-After', '5'),
    ])
    return [_LOADING]


def _background_load():
    """Preload Flask in background so the first real request isn't slow."""
    import threading

    def _load():
        import time
        time.sleep(0.5)
        _get_flask()

    t = threading.Thread(target=_load, daemon=True, name='flask-preload')
    t.start()


_background_load()


if __name__ == '__main__':
    import time
    time.sleep(2)
    if _flask_app is None:
        _get_flask()
        time.sleep(3)
    if _flask_app:
        import socket
        port = int(os.environ.get('PORT', 5000))
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
        except OSError:
            for p in range(port + 1, port + 100):
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('0.0.0.0', p))
                    port = p
                    break
                except OSError:
                    continue
        debug = os.environ.get('DEPLOYMENT_ENV') != 'production'
        _flask_app.run(host='0.0.0.0', port=port, debug=debug)
    else:
        sys.exit(1)
