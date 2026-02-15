"""Gunicorn config to speed up deployment cold starts."""
import os
import sys

timeout = 120
workers = 1
worker_class = "sync"

reload_engine = "poll"

_project = os.path.dirname(os.path.abspath(__file__))
reload_extra_files = []


def on_starting(server):
    """Restrict what the reloader watches – only project root .py files."""
    server.log.info("Gunicorn starting – project dir: %s", _project)


def post_fork(server, worker):
    """After worker forks, start background Flask loading."""
    import threading

    def _preload():
        import time
        time.sleep(1)
        try:
            import main
            if main._flask_app is None:
                main._get_flask()
                server.log.info("Flask pre-loaded in worker %s", worker.pid)
        except Exception as e:
            server.log.error("Flask pre-load failed: %s", e)

    t = threading.Thread(target=_preload, daemon=True, name="flask-preload")
    t.start()
