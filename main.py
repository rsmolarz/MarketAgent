"""
Main application entry point for the Market Inefficiency Detection Platform.
Uses a lazy-loading WSGI wrapper so gunicorn can respond to health checks
immediately while the full Flask app loads in the background.
"""

import os
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


class LazyApp:
    """WSGI wrapper that responds to health checks instantly while the real
    Flask app loads in a background thread. Once loaded, all requests are
    forwarded to Flask."""

    _LOADING_HTML = (
        b"<!DOCTYPE html><html><head><title>Loading...</title>"
        b"<meta http-equiv='refresh' content='3'></head>"
        b"<body style='background:#1a1a2e;color:#c9a84c;display:flex;"
        b"align-items:center;justify-content:center;height:100vh;"
        b"font-family:sans-serif'>"
        b"<div style='text-align:center'>"
        b"<h1>Market Inefficiency Agents</h1>"
        b"<p>Platform is starting up... please wait.</p>"
        b"</div></body></html>"
    )

    def __init__(self):
        self._real_app = None
        self._lock = threading.Lock()
        self._loading = True
        self._load_thread = threading.Thread(target=self._load_app, daemon=True)
        self._load_thread.start()

    def _load_app(self):
        try:
            logger.info("Background: loading Flask application...")
            from app import create_app
            real_app = create_app()
            if not real_app:
                raise RuntimeError("create_app() returned None")
            with self._lock:
                self._real_app = real_app
                self._loading = False
            logger.info("Background: Flask application loaded successfully")
        except Exception as e:
            logger.error(f"Background: Failed to load Flask app: {e}")
            raise

    def __call__(self, environ, start_response):
        with self._lock:
            loading = self._loading
            real_app = self._real_app

        if not loading and real_app is not None:
            return real_app(environ, start_response)

        path = environ.get('PATH_INFO', '/')
        if path in ('/', '/healthz', '/health', '/ready', '/live', '/status'):
            start_response('200 OK', [
                ('Content-Type', 'text/html; charset=utf-8'),
                ('Cache-Control', 'no-cache'),
            ])
            return [self._LOADING_HTML]

        start_response('503 Service Unavailable', [
            ('Content-Type', 'text/plain'),
            ('Retry-After', '5'),
        ])
        return [b'Service starting up, please retry shortly.']


app = LazyApp()

if __name__ == '__main__':
    import time
    time.sleep(3)
    if app._real_app:
        import socket

        def find_free_port(start_port=5000):
            for port in range(start_port, start_port + 100):
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('0.0.0.0', port))
                        return port
                except OSError:
                    continue
            raise RuntimeError("No free ports available")

        desired_port = int(os.environ.get('PORT', 5000))
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', desired_port))
            port = desired_port
        except OSError:
            port = find_free_port(desired_port + 1)
            print(f"Port {desired_port} is in use. Using port {port} instead.")

        debug_mode = os.environ.get('DEPLOYMENT_ENV') != 'production'
        print(f"Starting Market Inefficiency Detection Platform on http://0.0.0.0:{port}")
        app._real_app.run(host='0.0.0.0', port=port, debug=debug_mode)
    else:
        print("ERROR: Flask application failed to load")
