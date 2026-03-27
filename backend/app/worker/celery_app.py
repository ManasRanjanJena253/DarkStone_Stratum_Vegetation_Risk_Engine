from celery import Celery
from ..core.config import settings

celery_app = Celery(
    "darkstone_worker",
    broker=settings.celery_url,
    backend=settings.celery_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
)