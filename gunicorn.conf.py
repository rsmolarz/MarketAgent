"""Gunicorn config – keep workers minimal for fast cold starts in Cloud Run."""

timeout = 120
graceful_timeout = 30
workers = 1
worker_class = "sync"
preload_app = False
reload_engine = "poll"
reload_extra_files = []
