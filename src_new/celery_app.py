from celery import Celery
import os

celery = Celery(
    "bat3",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    include=["src_new.api.tasks"],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Prague",
    enable_utc=True,
    result_expires=86400 * 7,
    # 2026-09-22 OOM-storm fix: threads pool already runs N tasks in parallel
    # per pod; prefetching a deep buffer on top stacks heavy multi-GB pipeline
    # tasks and OOMs the 10Gi container (poison entry class ~76.5k bonds).
    # Cap the buffer at one message per worker slot. Durable config; the
    # bat3-worker deployment command also pins --prefetch-multiplier=1 and
    # --concurrency=2 explicitly.
    worker_prefetch_multiplier=1,
)
