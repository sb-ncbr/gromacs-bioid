from celery import Celery
import os
import socket


def redis_broker_transport_opts() -> dict:
    """Redis broker/result-backend transport hardening (shared by ALL Celery apps:
    src_new.celery_app, root tasks.py validation app, queue_dispatcher producer).

    2026-09-24/25 wedge class: cluster (CERIT) network resets half-kill long-lived
    broker TCP sockets: the middlebox keeps flows ESTABLISHED and even answers TCP
    keepalive probes, while no data ever flows again. kombu then blocks *forever*
    inside BRPOP; pods look healthy (0 restarts), celery list grows, throughput
    collapses. Server-side `CONFIG SET timeout 60` cannot help either: clients
    blocked in blocking commands are never "idle" for the server.

    Hardening below bounds every blocking broker interaction so dead flows surface
    as ConnectionError and kombu reconnects on its normal cycle:

      * socket_timeout=180       finite upper bound on ANY single blocking read
                                 (BRPOP). Generous on purpose: a healthy broker
                                 answers instantly (messages are almost always
                                 queued in this system), so this only ever fires
                                 on dead/stalled flows. It bounds broker READS
                                 ONLY — task execution time is never limited;
                                 a 6h simulation never touches the broker read
                                 socket while running.
      * socket_connect_timeout   fail fast on connect stalls.
      * retry_on_timeout         absorb one transient timeout inside redis-py;
                                 on a truly dead flow the retry WRITE hits
                                 EPIPE/RST and the consumer reconnects.
      * keepalive + health_check_interval  (2026-09-24 fix, kept) defeat
                                 NAT/conntrack idle reaping and PING before reuse.
      * visibility_timeout=6h    redelivery horizon for *reserved but not yet
                                 started* messages. Must exceed the longest
                                 plausible single-entry pipeline duration:
                                 otherwise a heavy simulation holding the worker
                                 slot makes its prefetched neighbour redeliver
                                 mid-flight and the same entry runs TWICE
                                 concurrently. 6h > max observed pipeline.

    Supported by kombu>=5.3 / redis-py>=4.4 (deployed: kombu 5.6.2 / redis 5.0).
    """
    return {
        "socket_keepalive": True,
        "socket_keepalive_options": {
            socket.TCP_KEEPIDLE: 60,
            socket.TCP_KEEPINTVL: 20,
            socket.TCP_KEEPCNT: 3,
        },
        "socket_timeout": 180,
        "socket_connect_timeout": 15,
        "retry_on_timeout": True,
        "health_check_interval": 30,
        # Celery redis-transport option (kombu transport_options key).
        "visibility_timeout": 6 * 60 * 60,
    }


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
    # Reconnect on broker loss instead of dying (and silence the 5.3+
    # deprecation warning); pairs with retry_on_timeout in transport opts.
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_transport_options=redis_broker_transport_opts(),
    result_backend_transport_options=redis_broker_transport_opts(),
)
