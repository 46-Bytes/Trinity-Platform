"""
Celery application configuration for Trinity Platform.

Uses Redis as both the message broker and result backend.
"""
from celery import Celery
from app.config import settings

celery_app = Celery("trinity")

celery_app.conf.update(
    # Broker and backend
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,

    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Task behavior
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Timeouts (30 min soft, 30.5 min hard kill)
    task_soft_time_limit=1800,
    task_time_limit=1860,

    # Results
    result_expires=86400,  # 24 hours

    # Worker
    worker_hijack_root_logger=False,
    worker_concurrency=4,

    # Task discovery
    include=["app.tasks.diagnostic_tasks"],
)
