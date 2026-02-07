from celery import Celery
import os
from app.core.logging_config import setup_logging

# Initialize logging for Celery
setup_logging()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "ncsaa_scheduler",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.scheduler_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],        
    result_serializer="json",
    timezone="America/Los_Angeles",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)
