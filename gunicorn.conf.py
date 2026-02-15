"""Gunicorn config for Reserved VM deployment."""
import os

timeout = 120
workers = 1
worker_class = "sync"

reload_engine = "poll"

_project = os.path.dirname(os.path.abspath(__file__))
reload_extra_files = []


def on_starting(server):
    server.log.info("Gunicorn starting – project dir: %s", _project)
