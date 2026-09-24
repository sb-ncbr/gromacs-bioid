from celery import Celery
import os
import socket

celery = Celery(
    "bat3",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    include=["src_new.api.tasks"],
)

# 2026-09-24 zombie-consumer fix: cluster network resets half-kill long-lived
# broker TCP sockets; kombu then waits forever on a dead connection while pods
# look healthy (0 unacked, growing celery list, all client connections idle
# for hours). Detect and re-establish them:
#  * socket keepalive defeats NAT/conntrack idle reaping and surfaces dead
#    peers within ~100s (60s idle + 3 probes * 20s),
#  * health_check_interval makes kombu PING connections before reuse.
# Supported by kombu>=5.3 / redis-py>=4.4 (verified: kombu 5.6.2 / redis 5.0).
_REDIS_TRANSPORT_HEALTH_OPTS = {
    "socket_keepalive": True,
    "socket_keepalive_options": {
        socket.TCP_KEEPIDLE: 60,
        socket.TCP_KEEPINTVL: 20,
        socket.TCP_KEEPCNT: 3,
    },
    "health_check_interval": 30,
}

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
    broker_transport_options=_REDIS_TRANSPORT_HEALTH_OPTS,
    result_backend_transport_options=_REDIS_TRANSPORT_HEALTH_OPTS,
)
