"""Cancelling a running run (2026-11-23).

Workers run Celery with --pool=threads, which cannot terminate a task, so
`revoke(terminate=True)` only ever removed queued messages: a cancelled (and
then deleted) run kept its worker slot for hours, mostly waiting on a BLAST
service. Cancellation is cooperative instead:

- the API calls request_cancel(run_id, run_dir) on cancel and delete. It sets
  a key in the broker Redis (bioid:cancel:<run_id>, 2 days) and writes a
  `.cancel_requested` file into the run directory, so a Redis outage still
  cancels;
- is_cancelled(run_id, run_dir) answers True when the key or the file
  exists, the run directory or its results.json is gone, or results.json says
  "cancelled". The answer is cached for a few seconds per run and the call
  never raises;
- the executor binds the run (bind) for the duration of the run; the pipeline
  checks before every step and before every resolver (check), and the long
  waits poll while they wait: a BLAST service search
  (blast_service_client.search) and local BLAST / Foldseek runs
  (run_subprocess). They raise RunCancelled, which ends the run as
  "cancelled" and is never retried;
- the Celery task polls too and stops the pipeline process (and its BLAST
  children) when the pipeline does not stop by itself (api/tasks.py).
"""
from __future__ import annotations

import contextvars
import logging
import os
import re
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Union

log = logging.getLogger(__name__)

KEY_PREFIX = "bioid:cancel:"
KEY_TTL_S = 2 * 24 * 3600
MARKER = ".cancel_requested"
#: how long an answer of is_cancelled is reused (per run, per process)
CACHE_S = 5.0
#: how often a long wait looks again
POLL_S = 5.0
#: pipeline.status is read from this many bytes at the start of results.json
_HEAD_BYTES = 65536
_STATUS_RE = re.compile(r'"pipeline"\s*:\s*\{[^{}]*?"status"\s*:\s*"([a-z_]+)"')


class RunCancelled(BaseException):
    """The run was cancelled or deleted. A BaseException on purpose: resolvers
    and stages turn every Exception into a recorded failure (and the shared
    cache would remember it); this must pass through all of them."""


_current: contextvars.ContextVar[Optional[tuple[str, Optional[Path]]]] = \
    contextvars.ContextVar("bioid_run", default=None)
_cache: dict[str, tuple[float, bool]] = {}
_cache_lock = threading.Lock()
_redis = None
_redis_pid = 0


def _client():
    """Broker Redis (CELERY_BROKER_URL, shared by the API and every worker);
    None without the URL. Short timeouts: a wedged broker must not wedge a run."""
    global _redis, _redis_pid
    url = os.environ.get("CELERY_BROKER_URL")
    if not url:
        return None
    if _redis is None or _redis_pid != os.getpid():
        import redis
        _redis = redis.Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)
        _redis_pid = os.getpid()
    return _redis


def request_cancel(run_id: str, run_dir: Union[str, Path, None] = None) -> bool:
    """Ask the run's worker to stop. True when at least one of the Redis key
    and the marker file was written. Never raises."""
    done = False
    try:
        client = _client()
        if client is not None:
            client.set(KEY_PREFIX + run_id, str(time.time()), ex=KEY_TTL_S)
            done = True
    except Exception as exc:
        log.warning("cancel %s: Redis unavailable (%s); using the marker file", run_id, exc)
    if run_dir is not None:
        try:
            if Path(run_dir).is_dir():
                (Path(run_dir) / MARKER).write_text(f"{time.time()}\n")
                done = True
        except OSError as exc:
            log.warning("cancel %s: cannot write %s (%s)", run_id, MARKER, exc)
    with _cache_lock:
        _cache[run_id] = (time.monotonic(), True)
    return done


def _status_head(results_path: Path) -> Optional[str]:
    """pipeline.status from the start of results.json (cheap: the file can be
    10 MB). None when it is not near the start or the file is unreadable."""
    try:
        with open(results_path, "rb") as f:
            head = f.read(_HEAD_BYTES).decode("utf-8", "replace")
    except OSError:
        return None
    m = _STATUS_RE.search(head)
    return m.group(1) if m else None


def _check_now(run_id: str, run_dir: Optional[Path]) -> bool:
    if run_dir is not None:
        try:
            results = run_dir / "results.json"
            if (run_dir / MARKER).exists() or not results.exists():
                return True
            if _status_head(results) == "cancelled":
                return True
        except OSError:
            pass
    try:
        client = _client()
        if client is not None and client.exists(KEY_PREFIX + run_id):
            return True
    except Exception as exc:
        log.debug("is_cancelled %s: Redis unavailable (%s)", run_id, exc)
    return False


def is_cancelled(run_id: Optional[str], run_dir: Union[str, Path, None] = None,
                 fresh: bool = False) -> bool:
    """True when the run was cancelled or deleted. Cached for CACHE_S per run
    (True for good; `fresh` looks again now); never raises."""
    if not run_id:
        return False
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(run_id)
    if cached and (cached[1] or (not fresh and now - cached[0] < CACHE_S)):
        return cached[1]
    try:
        answer = _check_now(run_id, Path(run_dir) if run_dir is not None else None)
    except Exception:
        answer = False
    with _cache_lock:
        _cache[run_id] = (now, answer)
    return answer


def forget(run_id: str) -> None:
    """Drop the cached answer (tests; a run id used again)."""
    with _cache_lock:
        _cache.pop(run_id, None)


# -- the run being executed ---------------------------------------------------

@contextmanager
def bind(run_id: Optional[str], run_dir: Union[str, Path, None] = None) -> Iterator[None]:
    """Make `run_id` the current run for this context (the executor wraps the
    whole run; executor.parallel copies it into its worker threads)."""
    token = _current.set((run_id, Path(run_dir) if run_dir is not None else None) if run_id else None)
    try:
        yield
    finally:
        _current.reset(token)


def current() -> Optional[tuple[str, Optional[Path]]]:
    return _current.get()


def cancel_requested() -> bool:
    """True when the current run (if any) was cancelled."""
    cur = _current.get()
    return bool(cur) and is_cancelled(cur[0], cur[1])


def check() -> None:
    """Raise RunCancelled when the current run was cancelled."""
    if cancel_requested():
        raise RunCancelled(_current.get()[0])


def run_subprocess(cmd, *, timeout: Optional[float] = None, input: Optional[str] = None,
                   poll_s: Optional[float] = None, **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run(cmd, capture_output=True, ...) that also stops when the
    current run is cancelled: the process is killed and RunCancelled raised.
    Without a current run it is subprocess.run."""
    if _current.get() is None:
        return subprocess.run(cmd, input=input, timeout=timeout, capture_output=True, **kwargs)
    check()
    poll_s = POLL_S if poll_s is None else poll_s
    deadline = None if timeout is None else time.monotonic() + timeout
    with subprocess.Popen(cmd, stdin=subprocess.PIPE if input is not None else None,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs) as proc:
        pending = input
        while True:
            wait = poll_s if deadline is None else max(0.0, min(poll_s, deadline - time.monotonic()))
            try:
                out, err = proc.communicate(pending, timeout=wait)
                break
            except subprocess.TimeoutExpired:
                pending = None  # communicate() keeps sending the rest itself
                if cancel_requested():
                    proc.kill()
                    proc.communicate()
                    raise RunCancelled(_current.get()[0])
                if deadline is not None and time.monotonic() >= deadline:
                    proc.kill()
                    out, err = proc.communicate()
                    raise subprocess.TimeoutExpired(cmd, timeout, output=out, stderr=err)
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)
