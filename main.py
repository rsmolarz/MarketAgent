"""
Main entry point. Ultra-lightweight WSGI app that responds to health checks
instantly. The full Flask app loads lazily on the first real request.
"""

import os
import sys
import time
import logging
import threading

if ('gunicorn' in os.environ.get('SERVER_SOFTWARE', '') or
    os.environ.get('REPLIT_DEPLOYMENT') == '1' or
    'gunicorn' in ' '.join(os.environ.get('_', '').split('/'))):
    os.environ['DEPLOYMENT_ENV'] = 'production'

logging.basicConfig(
    level=logging.INFO if os.environ.get('DEPLOYMENT_ENV') == 'production' else logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

_HEALTH_PATHS = frozenset(('/', '/healthz', '/health', '/ready', '/live', '/status'))

_LOADING_BODY = (
    b"<!DOCTYPE html><html><head><title>Loading</title>"
    b"<meta http-equiv='refresh' content='3'></head>"
    b"<body style='background:#1a1a2e;color:#c9a84c;display:flex;"
    b"align-items:center;justify-content:center;height:100vh;"
    b"font-family:sans-serif'>"
    b"<div style='text-align:center'>"
    b"<h1>Market Inefficiency Agents</h1>"
    b"<p>Platform is starting up&hellip; please wait.</p>"
    b"</div></body></html>"
)

_flask_app = None
_flask_lock = threading.Lock()
_flask_loading = False
_flask_ready = threading.Event()


def _load_flask():
    """Load Flask app in background thread."""
    global _flask_app, _flask_loading
    try:
        logger.info("Background thread: importing Flask app...")
        from app import create_app
        real = create_app()
        if real is None:
            raise RuntimeError("create_app() returned None")
        with _flask_lock:
            _flask_app = real
        _flask_ready.set()
        logger.info("Background thread: Flask app ready")
    except Exception:
        logger.exception("Background thread: FAILED to load Flask app")
        _flask_ready.set()
    finally:
        with _flask_lock:
            _flask_loading = False


def _ensure_loading():
    """Start background loading if not already started."""
    global _flask_loading
    with _flask_lock:
        if _flask_app is not None or _flask_loading:
            return
        _flask_loading = True
    t = threading.Thread(target=_load_flask, daemon=True, name="flask-loader")
    t.start()


def app(environ, start_response):
    """WSGI entry point. Returns instant health-check responses while Flask
    loads in the background. Once loaded, delegates everything to Flask."""

    _ensure_loading()

    real = _flask_app
    if real is not None:
        return real(environ, start_response)

    path = environ.get('PATH_INFO', '/')
    if path in _HEALTH_PATHS:
        body = _LOADING_BODY
        start_response('200 OK', [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Content-Length', str(len(body))),
            ('Cache-Control', 'no-cache'),
        ])
        return [body]

    start_response('503 Service Unavailable', [
        ('Content-Type', 'text/plain'),
        ('Retry-After', '5'),
    ])
    return [b'Service is starting, please retry shortly.']


if __name__ == '__main__':
    _ensure_loading()
    _flask_ready.wait(timeout=60)
    if _flask_app:
        import socket
        desired_port = int(os.environ.get('PORT', 5000))
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', desired_port))
            port = desired_port
        except OSError:
            for p in range(desired_port + 1, desired_port + 100):
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('0.0.0.0', p))
                    port = p
                    break
                except OSError:
                    continue
            else:
                raise RuntimeError("No free ports")
        debug_mode = os.environ.get('DEPLOYMENT_ENV') != 'production'
        print(f"Starting on http://0.0.0.0:{port}")
        _flask_app.run(host='0.0.0.0', port=port, debug=debug_mode)
    else:
        print("ERROR: Flask application failed to load")
        sys.exit(1)
