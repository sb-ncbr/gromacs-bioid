"""BLAST searches on a database service with a node-local NVMe copy (2026-11-19).

nr, nt, core_nt and UniRef50 are read from the shared NFS volume, which gives
about 50 MB/s to all pods together: one nr search reads 397 GB and takes
2.2 h or more. A BLAST service (src_new/blast_service.py, one per database)
keeps a copy on a node-local NVMe volume; the 2026-11-18 pilot searched nr in
5-13 min and returned the same hits as NFS.

A search goes to the service only when all of these hold, checked per search
(the answer is cached for 30 s per process):

- the [blast] <db>_service_url is set and the service answers;
- it has finished copying the database (state "ready");
- it serves the same database release as the NFS copy this worker would use
  (the directory the database symlink points to);
- it runs the same BLAST version.

Otherwise the search runs locally on NFS, as before. A service that fails
during a search (connection lost, error) also falls back to a local search;
a service search that runs out of time counts as a BLAST timeout, like a
local one. The route of each search is kept for run_health/blast_routes.
"""
from __future__ import annotations

import http.client
import json
import logging
import os
import socket
import subprocess
import threading
import time
from typing import Any, Optional
from urllib.parse import urlsplit

log = logging.getLogger(__name__)

HEALTH_TTL_S = 30.0
HEALTH_TIMEOUT_S = 3.0

_health: dict[str, tuple[float, Optional[dict[str, Any]]]] = {}
_versions: dict[str, str] = {}
#: resolver -> {"route": "service"|"local", "release", "reason"?, "seconds"?}
routes: dict[str, dict[str, Any]] = {}


class ServiceTimeout(Exception):
    """The service ran the search out of time."""


class ServiceUnavailable(Exception):
    """The service cannot run this search now; search locally."""


def _after_fork() -> None:
    _health.clear()
    routes.clear()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_after_fork)


def release_of(db_path: str) -> str:
    """Name of the database release a path resolves to, e.g. nr-20260729-070107
    for /app/databases/nr/nr (the directory is a symlink into .staging/)."""
    return os.path.basename(os.path.realpath(os.path.dirname(db_path)))


def blast_version(exec_path: str) -> str:
    if exec_path not in _versions:
        try:
            out = subprocess.run([exec_path, "-version"], capture_output=True, text=True, timeout=30)
            _versions[exec_path] = (out.stdout or "").strip().splitlines()[0]
        except Exception:
            _versions[exec_path] = ""
    return _versions[exec_path]


def health(url: str, now: Optional[float] = None) -> Optional[dict[str, Any]]:
    """The service's /health answer, or None when it does not answer."""
    now = time.time() if now is None else now
    cached = _health.get(url)
    if cached and now - cached[0] < HEALTH_TTL_S:
        return cached[1]
    try:
        import requests
        r = requests.get(f"{url.rstrip('/')}/health", timeout=HEALTH_TIMEOUT_S)
        body = r.json() if r.status_code == 200 else None
    except Exception:
        body = None
    _health[url] = (now, body)
    return body


def unusable_reason(url: str, db_path: str, exec_path: str) -> Optional[str]:
    """Why a search cannot go to the service now; None when it can."""
    h = health(url)
    if h is None:
        return "no answer"
    if h.get("state") != "ready":
        return f"state {h.get('state')}"
    if h.get("release") != release_of(db_path):
        return f"release {h.get('release')} != {release_of(db_path)}"
    if h.get("blast_version") != blast_version(exec_path):
        return "different BLAST version"
    return None


def search(url: str, *, release: str, query: str, task: Optional[str],
           max_target_seqs: int, timeout_s: float) -> dict[str, Any]:
    """Run one search on the service; returns the BLAST -outfmt 15 report.

    2026-11-23: the request runs in a helper thread while this one polls the
    run's cancellation every few seconds (cancellation.py). On a cancel the
    socket is shut down, so the service sees the client go away and stops the
    search, and RunCancelled is raised. (requests cannot be interrupted from
    another thread: a cancelled run used to wait up to ncbi_timeout_s.)"""
    from ... import cancellation
    body = json.dumps({"release": release, "query": query, "task": task,
                       "max_target_seqs": max_target_seqs, "timeout_s": timeout_s}).encode()
    call = _Post(f"{url.rstrip('/')}/search", body, connect_timeout=5, read_timeout=timeout_s + 60)
    worker = threading.Thread(target=call.run, daemon=True, name="blast-service-search")
    started = time.monotonic()
    worker.start()
    while not call.done.wait(cancellation.POLL_S):
        if cancellation.cancel_requested():
            call.abort()
            worker.join(5)
            raise cancellation.RunCancelled(f"BLAST service search on {url}")
    # counted like the requests calls it replaces (service_stats http hook)
    from ... import service_stats
    service_stats.record_http(url, call.status or None, time.monotonic() - started, call.error)
    if isinstance(call.error, TimeoutError) and call.connected:
        raise ServiceTimeout(str(call.error))
    if call.error is not None:
        raise ServiceUnavailable(f"{type(call.error).__name__}: {call.error}")
    status, text = call.status, call.text
    if status == 504:
        raise ServiceTimeout(text[:200])
    if status != 200:
        _health.pop(url, None)  # look again before the next search
        raise ServiceUnavailable(f"HTTP {status}: {text[:200]}")
    try:
        return json.loads(text)["output"]
    except Exception as exc:
        raise ServiceUnavailable(f"bad answer: {exc}")


class _Post:
    """One JSON POST over http.client, abortable from another thread
    (2026-11-23): abort() shuts the socket down, which ends the blocked read."""

    def __init__(self, url: str, body: bytes, *, connect_timeout: float, read_timeout: float) -> None:
        self.url, self.body = urlsplit(url), body
        self.connect_timeout, self.read_timeout = connect_timeout, read_timeout
        self.done = threading.Event()
        self.status: int = 0
        self.text = ""
        self.error: Optional[BaseException] = None
        self.connected = False
        self._conn: Optional[http.client.HTTPConnection] = None
        self._aborted = False

    def run(self) -> None:
        u = self.url
        cls = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
        try:
            conn = cls(u.hostname, u.port, timeout=self.connect_timeout)
            self._conn = conn
            conn.connect()
            self.connected = True
            if self._aborted:
                raise ConnectionAbortedError("cancelled")
            conn.sock.settimeout(self.read_timeout)
            conn.request("POST", u.path or "/", body=self.body,
                         headers={"Content-Type": "application/json"})
            r = conn.getresponse()
            self.status, self.text = r.status, r.read().decode("utf-8", "replace")
        except (OSError, http.client.HTTPException) as exc:
            self.error = exc
        finally:
            if self._conn is not None:
                self._conn.close()
            self.done.set()

    def abort(self) -> None:
        self._aborted = True
        conn = self._conn
        sock = getattr(conn, "sock", None) if conn is not None else None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
