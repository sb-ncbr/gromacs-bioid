"""Shared RCSB Search API POST helper (W3.3 item 1).

One POST to ``https://search.rcsb.org/rcsbsearch/v2/query`` with a single
settle-retry on HTTP *response* errors (4xx/5xx). Production evidence
2026-10-31 (P01): the worker stages the query structure to the shared
adhoc directory (atomic publish), hands the public URL to RCSB, and RCSB's
fetch can race the API pod's NFS negative-lookup cache by a few seconds —
RCSB then reports HTTP 404 for the query while the file is already
published and later fetches return 200. A bounded retry after a short
settle masks that whole race class (and transient RCSB 5xx) without
hiding persistent failures: the second failure stays a countable
``structure_search_unavailable`` error carrying the HTTP status.

Timeouts are NOT retried (the request already waited the full timeout).

c13 S5 (2026-11-04) supersedes the single retry for overload-class
failures: at 120 workers x 2 concurrent runs, mmcif_struct logged HTTP 500
in 345/397 runs of the pdb_struct-on arm (428 failures; c13 at ~80
concurrent runs: 19) and up to 51 timeouts per arm, while the same queries
answered normally at low load and the API pod served all 6,919 query-file
fetches with 200. 5xx, 429, timeouts and connection errors now get up to
three jittered backoff retries (~10/30/60 s); a 404 keeps its single settle
retry; any other 4xx is a deterministic rejection and is not retried.
Concurrent POSTs per worker process are capped (BAT3_RCSB_MAX_CONCURRENT,
default 1), so the fleet's load on RCSB scales with pods, not threads.
"""

from __future__ import annotations

import logging
import os
import random
import threading
import time

import requests

from ..base import IdentifierResolutionError

logger = logging.getLogger("identifier")

RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"

# Settle before the single retry: the API pod's NFS negative-lookup cache
# holds a fresh-path 404 for up to tens of seconds; 10 s covered every
# observed race (P01 404 window was seconds, later fetches 200).
RETRY_SETTLE_S = 10.0

# c13 S5: backoff schedule for overload-class failures (5xx/429/timeout/
# connection), jittered x0.75-1.25; and the per-process POST cap.
_BACKOFF_S = (RETRY_SETTLE_S, 30.0, 60.0)
_SLOTS = threading.BoundedSemaphore(
    max(1, int(os.environ.get("BAT3_RCSB_MAX_CONCURRENT", "1") or 1)))


def _post_once(request: dict, timeout_s: float) -> dict:
    response = requests.post(
        RCSB_SEARCH_URL,
        json=request,
        headers={"Content-Type": "application/json"},
        timeout=timeout_s,
    )
    response.raise_for_status()
    # c13 structure search (S2): RCSB answers a valid query with no matches
    # as HTTP 204 and an empty body. response.json() raised on it, so every
    # legitimate empty result burned the 10 s settle-retry and was counted
    # as structure_search_unavailable.
    if response.status_code == 204:
        return {"total_count": 0, "result_set": []}
    return response.json()


def _unavailable(exc: requests.exceptions.RequestException) -> IdentifierResolutionError:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    detail = f"HTTP {status}" if status is not None else str(exc)
    return IdentifierResolutionError(f"structure_search_unavailable: {detail}")


def _retries_for(exc: requests.exceptions.RequestException) -> int:
    """How many retries a failure class earns (c13 S5)."""
    if isinstance(exc, requests.exceptions.Timeout):
        return len(_BACKOFF_S)
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is None:  # connection-level (DNS/reset)
        return len(_BACKOFF_S)
    if status == 404:  # P01 adhoc publish race: one settle retry
        return 1
    if status == 429 or status >= 500:
        return len(_BACKOFF_S)
    return 0  # other 4xx: deterministic rejection


def post_rcsb_query(request: dict, *, timeout_s: float = 30.0) -> dict:
    """POST a structure-search query to RCSB with class-dependent retries.

    Args:
        request: RCSB Search API v2 request body.
        timeout_s: Per-attempt timeout.

    Returns:
        Parsed JSON response.

    Raises:
        IdentifierResolutionError: (structure_search_unavailable) when the
            failure persists through the retries its class earns.
    """
    attempt = 0
    while True:
        try:
            with _SLOTS:
                return _post_once(request, timeout_s)
        except requests.exceptions.RequestException as exc:
            allowed = _retries_for(exc)
            if attempt >= allowed:
                if isinstance(exc, requests.exceptions.Timeout):
                    raise IdentifierResolutionError(
                        "structure_search_unavailable: RCSB API request timed out")
                raise _unavailable(exc)
            status = getattr(getattr(exc, "response", None), "status_code", None)
            delay = _BACKOFF_S[attempt] * random.uniform(0.75, 1.25)
            logger.info("RCSB POST failed (%s); retry %d/%d after %.1fs",
                        f"HTTP {status}" if status is not None else exc,
                        attempt + 1, allowed, delay)
            attempt += 1
            time.sleep(delay)
