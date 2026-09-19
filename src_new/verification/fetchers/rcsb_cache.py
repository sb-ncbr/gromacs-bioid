"""RCSB API cache for verification fetchers."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time

import requests
from ...utils.net import prefer_ipv4 as _prefer_ipv4
_prefer_ipv4()

logger = logging.getLogger(__name__)

_SIM_CACHE = "/data/validation/sim_cache/rcsb"
_MIN_INTERVAL_S = 0.34         # keep the whole pipeline under ~3 rps
_last_request_ts = 0.0


class _CachedResponse:
    """Shim object mimicking requests.Response for cache hits."""

    def __init__(self, text: str, data):
        self._text = text
        self._data = data
        self.status_code = 200

    @property
    def text(self) -> str:
        return self._text

    def json(self):
        return self._data

    def raise_for_status(self):
        pass  # no-op for cached hits


def _cache_path(url: str) -> str:
    return os.path.join(_SIM_CACHE, hashlib.sha1(url.encode()).hexdigest()[:24] + ".json")


def _cache_read(url: str):
    try:
        with open(_cache_path(url)) as fh:
            return json.load(fh)
    except Exception:
        return None


def _cache_write(url: str, text: str) -> None:
    try:
        os.makedirs(_SIM_CACHE, exist_ok=True)
        with open(_cache_path(url), "w") as fh:
            json.dump({"_text": text}, fh)
    except OSError:
        pass


def _polite_get(url: str, timeout: int = 30, tries: int = 4) -> requests.Response | None:
    """GET with rate-limit etiquette: min interval + 429/503 backoff."""
    global _last_request_ts
    delay = 1.5
    for attempt in range(tries):
        gap = time.time() - _last_request_ts
        if gap < _MIN_INTERVAL_S:
            time.sleep(_MIN_INTERVAL_S - gap)
        try:
            r = requests.get(url, timeout=timeout)
            _last_request_ts = time.time()
        except Exception as exc:
            if attempt < tries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            logger.warning(f"GET failed {url}: {exc}")
            return None
        status = r.status_code if isinstance(getattr(r, "status_code", None), int) else 200
        if status in (429, 500, 502, 503) and attempt < tries - 1:
            time.sleep(delay)
            delay *= 2
            continue
        if status >= 400:
            return None
        r.raise_for_status()
        return r
    return None


def get_cached(url: str, timeout: int = 30) -> requests.Response | _CachedResponse | None:
    """GET with NFS cache for RCSB URLs.

    On cache HIT: return a shim object with .text/.json()/.status_code=200/.raise_for_status() no-op.
    On cache MISS: do a polite requests.get, cache response.text on HTTP 200, return the real response.
    On failure: return None.

    Does NOT cache non-200 responses.
    """
    cached = _cache_read(url)
    if cached is not None:
        text = cached.get("_text", "")
        try:
            data = json.loads(text)
        except Exception:
            data = None
        logger.debug(f"RCSB cache HIT: {url}")
        return _CachedResponse(text, data)

    r = _polite_get(url, timeout=timeout)
    if r is None:
        return None

    status = r.status_code if isinstance(getattr(r, "status_code", None), int) else 200
    if status == 200:
        _cache_write(url, r.text)
        logger.debug(f"RCSB cache MISS -> cached: {url}")
    return r
