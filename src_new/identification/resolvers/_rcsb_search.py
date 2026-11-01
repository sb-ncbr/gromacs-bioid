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
"""

from __future__ import annotations

import logging
import time

import requests

from ..base import IdentifierResolutionError

logger = logging.getLogger("identifier")

RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"

# Settle before the single retry: the API pod's NFS negative-lookup cache
# holds a fresh-path 404 for up to tens of seconds; 10 s covered every
# observed race (P01 404 window was seconds, later fetches 200).
RETRY_SETTLE_S = 10.0


def _post_once(request: dict, timeout_s: float) -> dict:
    response = requests.post(
        RCSB_SEARCH_URL,
        json=request,
        headers={"Content-Type": "application/json"},
        timeout=timeout_s,
    )
    response.raise_for_status()
    return response.json()


def _unavailable(exc: requests.exceptions.RequestException) -> IdentifierResolutionError:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    detail = f"HTTP {status}" if status is not None else str(exc)
    return IdentifierResolutionError(f"structure_search_unavailable: {detail}")


def post_rcsb_query(request: dict, *, timeout_s: float = 30.0) -> dict:
    """POST a structure-search query to RCSB with one settle-retry.

    Args:
        request: RCSB Search API v2 request body.
        timeout_s: Per-attempt timeout.

    Returns:
        Parsed JSON response.

    Raises:
        IdentifierResolutionError: On timeout (no retry) or HTTP/request
            failure persisting through one settle-retry.
    """
    try:
        return _post_once(request, timeout_s)
    except requests.exceptions.Timeout:
        raise IdentifierResolutionError(
            "structure_search_unavailable: RCSB API request timed out")
    except requests.exceptions.RequestException as exc:
        if getattr(exc, "response", None) is None:
            # Connection-level failure (DNS/reset): retry is same-cost, same
            # benefit as the HTTP race — retry once as well.
            logger.info("RCSB POST failed (%s); retrying once after %.1fs",
                        exc, RETRY_SETTLE_S)
        else:
            logger.info(
                "RCSB POST failed (HTTP %s); retrying once after %.1fs",
                getattr(exc.response, "status_code", "?"), RETRY_SETTLE_S)
        time.sleep(RETRY_SETTLE_S)

    try:
        return _post_once(request, timeout_s)
    except requests.exceptions.Timeout:
        raise IdentifierResolutionError(
            "structure_search_unavailable: RCSB API request timed out")
    except requests.exceptions.RequestException as exc2:
        raise _unavailable(exc2)
