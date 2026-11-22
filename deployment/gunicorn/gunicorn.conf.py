# =============================================================================
# Gunicorn configuration - UMS Mart API
#
# Usage (from the project root on the server):
#   gunicorn config.wsgi:application \
#       --config /home/ums_mart/deployment/gunicorn/gunicorn.conf.py
#
# The systemd unit in deployment/scripts/ums-mart.service already passes this
# file, so in normal operation you never invoke gunicorn by hand.
# =============================================================================

import multiprocessing
import os

# ---------------------------------------------------------------------------
# Socket
# ---------------------------------------------------------------------------
# Bind to a UNIX socket: it is faster than TCP and cannot be reached from
# outside the host. Nginx is the only client. If you prefer TCP use
# "127.0.0.1:8001" - never "0.0.0.0" (that would bypass Nginx and TLS).
bind = os.environ.get("GUNICORN_BIND", "unix:/run/gunicorn/ums_mart.sock")

# Nginx redirects HTTP -> HTTPS, so the app always sits behind one hop.
forwarded_allow_ips = "127.0.0.1"

# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------
# Sync workers: the workload is short, I/O-bound request handling. Keep the
# worker count at (2 x cores) + 1, capped so a small VPS is not starved.
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
threads = int(os.environ.get("GUNICORN_THREADS", 2))

worker_tmp_dir = "/dev/shm"
max_requests = 1000
max_requests_jitter = 100
timeout = 60
graceful_timeout = 30
keepalive = 5

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Access logging lives in Nginx; Gunicorn only records errors so the log files
# stay small and readable.
accesslog = None
errorlog = os.environ.get("GUNICORN_ERROR_LOG", "-")
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
capture_output = True

# ---------------------------------------------------------------------------
# Process naming / files
# ---------------------------------------------------------------------------
proc_name = "ums_mart"
pidfile = os.environ.get("GUNICORN_PIDFILE", "/run/gunicorn/ums_mart.pid")

# Create the socket directory if it does not exist yet (systemd may start us
# before /run/gunicorn exists after a reboot).
def on_starting(server):  # noqa: D103
    directory = os.path.dirname(bind.split(":", 1)[1]) if bind.startswith("unix:") else None
    if directory:
        os.makedirs(directory, exist_ok=True)


def when_ready(server):  # noqa: D103
    server.log.info(
        "UMS Mart API ready - bind=%s workers=%s threads=%s",
        bind, workers, threads,
    )
