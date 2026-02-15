"""Gunicorn configuration for deployment stability."""

import os
import multiprocessing

timeout = 120
graceful_timeout = 30
keep_alive = 5
workers = 2
worker_class = "sync"
preload_app = False

reload_exclude = [
    "*.json",
    "*.log",
    "*.csv",
    "telemetry/*",
    "meta_supervisor/*",
    "__pycache__/*",
    "*.pyc",
]

accesslog = "-"
errorlog = "-"
loglevel = "info" if os.environ.get("DEPLOYMENT_ENV") == "production" else "debug"
