"""Traffic statistics for the admin page.

What is recorded, per page view (beacon from the web app and the
documentation) and per meaningful API request (submissions, results,
downloads, actions, every error or refusal; the routine polling of status,
queue and progress is not recorded): time, kind, route template,
status, duration, client (web / mcp / api / bot), the keyed hash of the
address (security.ip_hash, the same pseudonym the limits use), approximate
location looked up from the address at that moment (country, city,
coordinates rounded to 0.1 degree) and the referring site. The address
itself is never written anywhere.

Storage: <runs>/_traffic/events/YYYY-MM-DD/<host>-<pid>.jsonl (never
served, never touched by run retention), one writer per file, buffered and
appended every 10 s, deleted after RAW_DAYS (90). Statistics are computed
from these files for the requested window ("all" = everything kept).

Location: DB-IP "IP to City Lite" (CC BY 4.0, https://db-ip.com), kept at
<databases>/geoip/dbip-city-lite.mmdb and refreshed monthly in the
background; until it is there, locations are unknown.
"""
from __future__ import annotations

import gzip
import ipaddress
import json
import logging
import os
import shutil
import socket
import threading
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from . import security

log = logging.getLogger(__name__)

RAW_DAYS = int(os.environ.get("BAT3_TRAFFIC_RAW_DAYS", "90"))
FLUSH_S = 10.0
GEOIP_MAX_AGE_S = 35 * 86400
GEOIP_URL = "https://download.db-ip.com/free/dbip-city-lite-{month}.mmdb.gz"
GEOIP_ATTRIBUTION = "IP geolocation by DB-IP (db-ip.com), CC BY 4.0"
WINDOWS = {"1h": 1 / 24, "24h": 1, "7d": 7, "30d": 30, "90d": 90, "all": None}


def enabled() -> bool:
    return os.environ.get("BAT3_TRAFFIC", "1") != "0"


def traffic_dir() -> Path:
    from .routes.runs import get_runs_dir
    return get_runs_dir() / "_traffic"


# -- location ----------------------------------------------------------------------

def geoip_path() -> Path:
    return Path(os.environ.get("BAT3_GEOIP_DB", "/app/databases/geoip/dbip-city-lite.mmdb"))


_reader = None
_reader_mtime = 0.0
_reader_lock = threading.Lock()


def _geo_reader():
    global _reader, _reader_mtime
    path = geoip_path()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    with _reader_lock:
        if _reader is None or mtime != _reader_mtime:
            import maxminddb
            _reader, _reader_mtime = maxminddb.open_database(str(path)), mtime
        return _reader


def locate(ip: Optional[str]) -> dict[str, Any]:
    """Country / city / rounded coordinates for an address (no address kept)."""
    if not ip:
        return {}
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return {}
    if not addr.is_global:
        return {"country": "internal"}
    try:
        reader = _geo_reader()
        rec = reader.get(ip) if reader else None
    except Exception:
        rec = None
    if not rec:
        return {}
    loc = rec.get("location") or {}
    out = {"country": (rec.get("country") or {}).get("iso_code"),
           "country_name": ((rec.get("country") or {}).get("names") or {}).get("en"),
           "city": ((rec.get("city") or {}).get("names") or {}).get("en")}
    if "latitude" in loc and "longitude" in loc:
        out["lat"], out["lon"] = round(loc["latitude"], 1), round(loc["longitude"], 1)
    return {k: v for k, v in out.items() if v is not None}


def refresh_geoip(force: bool = False) -> Optional[str]:
    """Download this month's DB-IP city database if ours is missing or old
    (BAT3_GEOIP_REFRESH=0 disables). Never raises: runs in a background thread."""
    if os.environ.get("BAT3_GEOIP_REFRESH", "1") == "0":
        return None
    try:
        return _refresh_geoip(force)
    except Exception as exc:
        log.warning("traffic: GeoIP refresh failed: %s", exc)
        return None


def _refresh_geoip(force: bool) -> Optional[str]:
    path = geoip_path()
    try:
        if not force and time.time() - path.stat().st_mtime < GEOIP_MAX_AGE_S:
            return None
    except OSError:
        pass
    client = security._redis_client()
    if client is not None:
        try:
            if not client.set("bioid:geoip:refresh", "1", nx=True, ex=3600):
                return None  # another process is on it
        except Exception:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    months = [now.strftime("%Y-%m"), (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")]
    for month in months:
        url = GEOIP_URL.format(month=month)
        tmp = path.with_suffix(".download")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (BioID geoip refresh)"})
            with urllib.request.urlopen(req, timeout=300) as resp, gzip.open(resp) as gz, open(tmp, "wb") as out:
                shutil.copyfileobj(gz, out, 1024 * 1024)
            import maxminddb
            maxminddb.open_database(str(tmp)).close()  # valid before it replaces ours
            os.replace(tmp, path)
            log.warning("traffic: GeoIP database %s installed", month)
            return month
        except Exception as exc:
            log.warning("traffic: GeoIP download %s failed: %s", month, exc)
            tmp.unlink(missing_ok=True)
    return None


# -- recording -----------------------------------------------------------------------

#: GET routes polled by the web app every few seconds: not recorded unless
#: they fail (they would drown everything else).
POLLING_ROUTES = {
    "/api/v1/runs/{run_id}/status", "/api/v1/runs/{run_id}/queue", "/api/v1/runs/{run_id}/loading",
    "/api/v1/runs/{run_id}/logs", "/api/v1/runs/{run_id}/render", "/api/v1/runs",
    "/api/v1/runs/config/options", "/api/v1/runs/examples", "/api/v1/capabilities",
    "/api/v1/health", "/api/v1/runs/{run_id}", "/api/v1/runs/{run_id}/files",
}


def page_route(path: str) -> Optional[str]:
    """A page path as a template: /runs/<id> -> /runs/:id; admin pages and
    anything that is not a page of the app or the documentation -> None."""
    import re
    path = path.split("?")[0].split("#")[0][:200] or "/"
    if path.startswith("/admin"):
        return None
    if re.fullmatch(r"/runs/[^/]+/?", path):
        return "/runs/:id"
    if path == "/" or path.startswith("/documentation"):
        return path
    return "(other)"


def worth_recording(method: str, route: str, status: int, client: str) -> bool:
    if route.startswith("/api/v1/admin") or route.startswith("/api/v1/events"):
        return False
    if status >= 400 or method != "GET" or client == "mcp":
        return True
    return route not in POLLING_ROUTES

BOT_WORDS = ("bot", "crawler", "spider", "slurp", "scrapy", "preview", "monitor", "uptime",
             "headless", "lighthouse", "facebookexternalhit")


def client_kind(user_agent: str, client_header: str) -> str:
    """web / mcp / docs / bot / script / api."""
    ua = (user_agent or "").lower()
    if client_header in ("web", "mcp", "docs"):
        return client_header
    if any(w in ua for w in BOT_WORDS):
        return "bot"
    if any(w in ua for w in ("curl", "wget", "python", "httpx", "requests", "go-http", "java/", "okhttp", "node")):
        return "script"
    return "api"


def browser(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    for name, needle in (("Edge", "edg/"), ("Opera", "opr/"), ("Chrome", "chrome/"), ("Firefox", "firefox/"),
                         ("Safari", "safari/"), ("curl", "curl"), ("Python", "python")):
        if needle in ua:
            return name
    return "other"


def referrer_site(referrer: Optional[str]) -> Optional[str]:
    if not referrer:
        return None
    from urllib.parse import urlparse
    host = (urlparse(referrer).hostname or "").lower()
    own = os.environ.get("BAT3_PUBLIC_HOST", "bioid-ceitec.dyn.cloud.e-infra.cz")
    return None if not host or host == own else host


_buffer: list[tuple[str, str]] = []  # (day, json line)
_buffer_lock = threading.Lock()
_flusher: Optional[threading.Thread] = None


def _ensure_flusher() -> None:
    global _flusher
    if _flusher is None or not _flusher.is_alive():
        _flusher = threading.Thread(target=_flush_loop, daemon=True, name="traffic-flush")
        _flusher.start()


def _flush_loop() -> None:
    while True:
        time.sleep(FLUSH_S)
        try:
            flush()
        except Exception as exc:
            log.warning("traffic: flush failed: %s", exc)


def flush() -> int:
    with _buffer_lock:
        lines, _buffer[:] = list(_buffer), []
    if not lines:
        return 0
    by_day: dict[str, list[str]] = defaultdict(list)
    for day, line in lines:
        by_day[day].append(line)
    for day, chunk in by_day.items():
        d = traffic_dir() / "events" / day
        d.mkdir(parents=True, exist_ok=True)
        with open(d / f"{socket.gethostname()}-{os.getpid()}.jsonl", "a", encoding="utf-8") as f:
            f.write("\n".join(chunk) + "\n")
    return len(lines)


def record(kind: str, *, ip: Optional[str], route: str, status: int = 200, ms: float = 0.0,
           user_agent: str = "", client: str = "", referrer: Optional[str] = None,
           method: str = "GET", now: Optional[datetime] = None) -> None:
    if not enabled():
        return
    ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%S")
    event = {"ts": ts, "kind": kind, "method": method, "route": route, "status": status,
             "ms": round(ms, 1), "visitor": security.ip_hash(ip), "client": client_kind(user_agent, client),
             "browser": browser(user_agent), **locate(ip)}
    site = referrer_site(referrer)
    if site:
        event["ref"] = site
    with _buffer_lock:
        _buffer.append((ts[:10], json.dumps(event, separators=(",", ":"))))
    _ensure_flusher()


# -- aggregation ---------------------------------------------------------------------

def _events(day: str) -> Iterable[dict[str, Any]]:
    d = traffic_dir() / "events" / day
    if not d.is_dir():
        return
    for f in sorted(d.glob("*.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def _empty() -> dict[str, Any]:
    return {"requests": 0, "pageviews": 0, "errors": 0, "rate_limited": 0, "runs": Counter(),
            "visitors": set(), "series": defaultdict(lambda: [0, 0, set()]),
            "pages": Counter(), "endpoints": Counter(), "status": Counter(), "clients": Counter(),
            "browsers": Counter(), "referrers": Counter(), "ms": [],
            "countries": defaultdict(lambda: {"name": None, "requests": 0, "pageviews": 0, "visitors": set()}),
            "places": defaultdict(lambda: {"requests": 0, "pageviews": 0, "visitors": set()})}


def _add(agg: dict[str, Any], e: dict[str, Any], bucket: str) -> None:
    v = e.get("visitor")
    pv = e.get("kind") == "pageview"
    s = agg["series"][bucket]
    if pv:
        agg["pageviews"] += 1
        agg["pages"][e.get("route", "")] += 1
        s[1] += 1
        if e.get("ref"):
            agg["referrers"][e["ref"]] += 1
    else:
        agg["requests"] += 1
        agg["endpoints"][f'{e.get("method", "GET")} {e.get("route", "")}'] += 1
        agg["status"][str(e.get("status"))] += 1
        s[0] += 1
        st = int(e.get("status") or 0)
        agg["errors"] += st >= 500
        agg["rate_limited"] += st == 429
        if e.get("method") == "POST" and st == 200 and e.get("route") in ("/api/v1/runs", "/api/v1/runs/{run_id}/rerun"):
            agg["runs"][e.get("client", "api")] += 1
        if isinstance(e.get("ms"), (int, float)):
            agg["ms"].append(e["ms"])
    agg["clients"][e.get("client", "api")] += 1
    agg["browsers"][e.get("browser", "other")] += 1
    if v and e.get("client") != "bot":
        agg["visitors"].add(v)
        s[2].add(v)
    c = e.get("country")
    if c and c != "internal":
        cc = agg["countries"][c]
        cc["name"] = e.get("country_name") or c
        cc["requests" if not pv else "pageviews"] += 1
        if v:
            cc["visitors"].add(v)
        if "lat" in e:
            p = agg["places"][(e["lat"], e["lon"], e.get("city") or "", c)]
            p["requests" if not pv else "pageviews"] += 1
            if v:
                p["visitors"].add(v)


def summarize(window: str = "24h", now: Optional[datetime] = None) -> dict[str, Any]:
    """Statistics for one window (1h, 24h, 7d, 30d, 90d, all)."""
    if window not in WINDOWS:
        window = "24h"
    now = now or datetime.now(timezone.utc)
    days = WINDOWS[window]
    start = now - timedelta(days=days) if days else None
    hourly = days is not None and days <= 7
    agg = _empty()
    root = traffic_dir() / "events"
    day_names = sorted(p.name for p in root.iterdir()) if root.is_dir() else []
    for day in day_names:
        if start and day < start.strftime("%Y-%m-%d"):
            continue
        for e in _events(day):
            ts = e.get("ts", "")
            if start and ts < start.strftime("%Y-%m-%dT%H:%M:%S"):
                continue
            _add(agg, e, ts[:13] if hourly else ts[:10])
    ms = sorted(agg["ms"])
    pct = lambda q: ms[min(len(ms) - 1, int(q * len(ms)))] if ms else None
    top = lambda c, n=15: [{"name": k, "count": v} for k, v in c.most_common(n)]
    return {
        "window": window, "from": start.isoformat() if start else (day_names[0] if day_names else None),
        "to": now.isoformat(), "bucket": "hour" if hourly else "day",
        "totals": {"visitors": len(agg["visitors"]), "pageviews": agg["pageviews"],
                   "requests": agg["requests"], "runs": sum(agg["runs"].values()),
                   "errors": agg["errors"], "rate_limited": agg["rate_limited"],
                   "countries": len(agg["countries"]), "p50_ms": pct(0.5), "p95_ms": pct(0.95)},
        "runs_by_client": dict(agg["runs"]),
        "series": [{"t": k, "requests": v[0], "pageviews": v[1], "visitors": len(v[2])}
                   for k, v in sorted(agg["series"].items())],
        "countries": sorted(({"code": k, "name": v["name"], "visitors": len(v["visitors"]),
                              "pageviews": v["pageviews"], "requests": v["requests"]}
                             for k, v in agg["countries"].items()), key=lambda x: -x["visitors"]),
        "places": sorted(({"lat": k[0], "lon": k[1], "city": k[2], "country": k[3],
                           "visitors": len(v["visitors"]), "pageviews": v["pageviews"], "requests": v["requests"]}
                          for k, v in agg["places"].items()), key=lambda x: -x["visitors"])[:500],
        "pages": top(agg["pages"]), "endpoints": top(agg["endpoints"]), "status": dict(agg["status"]),
        "clients": dict(agg["clients"]), "browsers": dict(agg["browsers"]), "referrers": top(agg["referrers"]),
        "geoip": {"available": geoip_path().is_file(), "attribution": GEOIP_ATTRIBUTION},
        "raw_days": RAW_DAYS,
    }


def prune(now: Optional[datetime] = None) -> list[str]:
    """Delete raw event days older than RAW_DAYS."""
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=RAW_DAYS)).strftime("%Y-%m-%d")
    root = traffic_dir() / "events"
    removed = []
    if root.is_dir():
        for d in root.iterdir():
            if d.is_dir() and not d.is_symlink() and len(d.name) == 10 and d.name < cutoff:
                shutil.rmtree(d)
                removed.append(d.name)
    return removed
