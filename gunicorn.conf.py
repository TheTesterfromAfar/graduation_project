"""Gunicorn settings. Everything can be overridden with environment variables."""
import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")

# A small survey site does not need many processes; cap the default at 4.
workers = int(os.environ.get("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 4)))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
worker_class = "gthread"

timeout = 30
graceful_timeout = 30
keepalive = 5

# Recycle workers periodically to contain slow memory growth.
max_requests = 1000
max_requests_jitter = 100

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info").lower()

# Add this line to your gunicorn.conf.py
control_socket_disable = True