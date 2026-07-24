import multiprocessing
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
worker_class = "uvicorn.workers.UvicornWorker"

# Container Apps CPU allocation is fractional; fall back to a safe default
# rather than sizing off the host's full core count.
workers = int(os.environ.get("WEB_CONCURRENCY", min(multiprocessing.cpu_count(), 4)))

# Some endpoints call Claude synchronously in-request (ANTHROPIC_TIMEOUT is
# 1800s) rather than via a background task — the worker timeout has to be
# comfortably above that or gunicorn kills the request mid-generation.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "1800"))
graceful_timeout = 30
keepalive = 5

# Container Apps ingress terminates TLS and forwards plain HTTP, setting
# X-Forwarded-Proto. Trust it so request.url_for() (used to build the Auth0
# redirect_uri) produces https:// instead of http:// — only the platform's
# internal ingress can reach this container, so trusting all peers is safe.
forwarded_allow_ips = "*"

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
