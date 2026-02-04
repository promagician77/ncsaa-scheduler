"""
Celery configuration for async task processing.
"""

from celery import Celery
import os

# Redis connection URL (default to localhost)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "ncsaa_scheduler",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.scheduler_tasks"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Los_Angeles",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max
    task_soft_time_limit=540,  # 9 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)
