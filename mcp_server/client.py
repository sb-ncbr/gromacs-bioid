"""Thin async client of the BioID REST API (/api/v1/runs)."""
from __future__ import annotations

import json
import re
import time
from typing import Any, Optional
import httpx

from . import __version__
from .config import Settings

USER_AGENT = f"bioid-mcp/{__version__}"

# Run ids are UUIDs for runs made through the web UI / API; reruns and
# validation runs use other ASCII ids. Anything with a slash or "..", or
# longer than a sane id, never reaches the API.
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class BioIDError(Exception):
    """An API failure, phrased for the model reading the tool result."""


def check_run_id(run_id: str) -> str:
    run_id = (run_id or "").strip()
    if not _RUN_ID_RE.match(run_id) or ".." in run_id:
        raise BioIDError(
            f"'{run_id}' is not a valid BioID run id (expected something like "
            "'1c2a4d4b-94cb-48ec-81a9-d0c0924af8bd', as returned by a submit tool).")
    return run_id


def _detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError):
        return (resp.text or "").strip()[:300]
    if isinstance(body, dict) and "detail" in body:
        detail = body["detail"]
        if isinstance(detail, list):  # FastAPI validation errors
            return "; ".join(
                f"{'.'.join(str(p) for p in d.get('loc', []))}: {d.get('msg', '')}"
                if isinstance(d, dict) else str(d)
                for d in detail
            )[:300]
        return str(detail)[:300]
    return json.dumps(body)[:300]


class BioIDClient:
    """One shared httpx client; every method raises BioIDError on failure."""

    def __init__(self, settings: Settings, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.settings = settings
        self._http = httpx.AsyncClient(
            base_url=settings.api_url,
            timeout=httpx.Timeout(settings.api_timeout_s, connect=10.0),
            # X-BioID-Client: the API's traffic statistics count MCP use separately
            headers={"User-Agent": USER_AGENT, "Accept": "application/json", "X-BioID-Client": "mcp"},
            transport=transport,
            follow_redirects=False,
        )
        self._cache: dict[str, tuple[float, Any]] = {}

    async def aclose(self) -> None:
        await self._http.aclose()

    # -- plumbing -------------------------------------------------------

    async def _request(self, method: str, path: str, *, not_found: Optional[str] = None,
                       headers: Optional[dict[str, str]] = None,
                       timeout: Optional[float] = None, **kwargs: Any) -> httpx.Response:
        try:
            resp = await self._http.request(
                method, path, headers=headers,
                timeout=timeout if timeout is not None else httpx.USE_CLIENT_DEFAULT,
                **kwargs)
        except httpx.TimeoutException as e:
            raise BioIDError(
                f"The BioID API did not answer in time ({type(e).__name__} on {method} {path}). "
                "The service may be busy; try again in a minute.") from e
        except httpx.HTTPError as e:
            raise BioIDError(
                f"Could not reach the BioID API ({type(e).__name__}: {e}). Try again later.") from e
        if resp.status_code == 404 and not_found:
            raise BioIDError(not_found)
        if resp.status_code >= 400:
            detail = _detail(resp)
            if resp.status_code >= 500:
                raise BioIDError(
                    f"The BioID API failed with HTTP {resp.status_code}"
                    f"{': ' + detail if detail else ''}. Try again later.")
            raise BioIDError(f"The BioID API rejected the request (HTTP {resp.status_code})"
                             f"{': ' + detail if detail else ''}.")
        return resp

    async def _json(self, path: str, *, not_found: Optional[str] = None,
                    params: Optional[dict[str, Any]] = None) -> Any:
        resp = await self._request("GET", path, not_found=not_found, params=params)
        try:
            return resp.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise BioIDError(f"The BioID API returned a non-JSON answer for {path}.") from e

    async def _cached(self, key: str, ttl: float, loader) -> Any:
        hit = self._cache.get(key)
        now = time.monotonic()
        if hit and now - hit[0] < ttl:
            return hit[1]
        value = await loader()
        self._cache[key] = (now, value)
        return value

    @staticmethod
    def _run_missing(run_id: str) -> str:
        return (f"Run '{run_id}' was not found on BioID. Check the id; runs are "
                "addressed by the run_id a submit tool returned.")

    # -- endpoints -------------------------------------------------------

    async def config_options(self) -> Optional[dict[str, Any]]:
        """GET /runs/config/options; None when the server predates presets."""
        async def load():
            try:
                resp = await self._http.get("/api/v1/runs/config/options")
            except httpx.HTTPError as e:
                raise BioIDError(f"Could not reach the BioID API ({type(e).__name__}).") from e
            # Older servers: the path falls through to GET /runs/{run_id}
            # (404 "Run 'config' not found") or 405.
            if resp.status_code in (404, 405):
                return None
            if resp.status_code >= 400:
                raise BioIDError(f"The BioID API failed with HTTP {resp.status_code}: {_detail(resp)}")
            data = resp.json()
            if not isinstance(data, dict) or not isinstance(data.get("presets"), list):
                return None
            return data
        return await self._cached("config_options", 300.0, load)

    async def capabilities(self) -> dict[str, Any]:
        async def load():
            try:
                return await self._json("/api/v1/capabilities")
            except BioIDError:
                return {}
        return await self._cached("capabilities", 600.0, load)

    async def create_run(self, files: list[tuple[str, bytes]], *, run_name: Optional[str],
                         preset: Optional[str], client_ip: Optional[str] = None,
                         retention: Optional[str] = None) -> dict[str, Any]:
        data: dict[str, str] = {}
        if run_name:
            data["run_name"] = run_name
        if preset:
            data["preset"] = preset
        if retention:
            data["retention"] = retention
        headers = {}
        if client_ip:
            headers["X-Forwarded-For"] = client_ip
        resp = await self._request(
            "POST", "/api/v1/runs",
            files=[("files", (name, content, "application/octet-stream")) for name, content in files],
            data=data, headers=headers, timeout=self.settings.submit_timeout_s)
        return resp.json()

    async def summary(self, run_id: str) -> dict[str, Any]:
        return await self._json(f"/api/v1/runs/{run_id}", not_found=self._run_missing(run_id))

    async def status(self, run_id: str) -> dict[str, Any]:
        return await self._json(f"/api/v1/runs/{run_id}/status", not_found=self._run_missing(run_id))

    async def queue(self, run_id: str) -> dict[str, Any]:
        return await self._json(f"/api/v1/runs/{run_id}/queue", not_found=self._run_missing(run_id))

    async def loading(self, run_id: str) -> dict[str, Any]:
        return await self._json(f"/api/v1/runs/{run_id}/loading", not_found=self._run_missing(run_id))

    async def molecules(self, run_id: str) -> dict[str, Any]:
        return await self._json(f"/api/v1/runs/{run_id}/molecules", not_found=self._run_missing(run_id))

    async def verification(self, run_id: str, segment: Optional[str] = None) -> dict[str, Any]:
        params = {"segment": segment} if segment is not None else None
        return await self._json(f"/api/v1/runs/{run_id}/verification",
                                not_found=self._run_missing(run_id), params=params)

    async def signatures(self, run_id: str, segment: str) -> dict[str, Any]:
        return await self._json(f"/api/v1/runs/{run_id}/signatures",
                                not_found=self._run_missing(run_id), params={"segment": segment})

    async def results_json(self, run_id: str) -> dict[str, Any]:
        """The whole results.json (MBs; the caller extracts what it needs)."""
        resp = await self._request("GET", f"/api/v1/runs/{run_id}/download/results.json",
                                   not_found=self._run_missing(run_id),
                                   timeout=max(self.settings.api_timeout_s, 60.0))
        try:
            return resp.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise BioIDError("The BioID API returned a non-JSON results.json.") from e

    async def examples(self, limit: int) -> dict[str, Any]:
        return await self._json("/api/v1/runs/examples", params={"limit": limit})

    async def cancel(self, run_id: str, owner_token: str) -> dict[str, Any]:
        resp = await self._request("POST", f"/api/v1/runs/{run_id}/cancel",
                                   not_found=self._run_missing(run_id),
                                   headers={"X-Owner-Token": owner_token})
        return resp.json()
