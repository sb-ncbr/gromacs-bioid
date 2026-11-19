"""Admin API for the /admin page (one-page operations dashboard).

Auth: POST /api/v1/admin/login with the password in BAT3_ADMIN_PASSWORD
(unset = admin disabled, 503). It returns a signed session token (12 h) for
`Authorization: Bearer`. Failed logins are limited per address (10 per
15 min) and globally (100 per hour).

Kubernetes actions are limited to BioID's own deployments (DEPLOYMENTS);
the namespace also runs other teams' workloads and the validation stack,
which this API never touches. Deleting a run moves it to the retention
trash (restorable for BAT3_RETENTION_GRACE_DAYS); examples cannot be deleted.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from . import retention, run_index, security

router = APIRouter()

NAMESPACE = os.environ.get("BAT3_K8S_NAMESPACE", "ceitec-biodata-ns")
QUEUES = ("validation.ui.celery", os.environ.get("BAT3_REPO_QUEUE", "validation.repo.celery"),
          "celery", "bughunt")
SESSION_S = 12 * 3600

#: deployment -> (label, (min, max) replicas or None = not scalable, restartable)
DEPLOYMENTS: dict[str, tuple[str, Optional[tuple[int, int]], bool]] = {
    "bat3-ui-worker": ("UI workers — web, API and MCP runs", (0, 20), True),
    "bat3-repo-worker": ("Repository workers — campaign queue (token, automatic retries)", (0, 300), True),
    "bat3-ceitec-bat3-worker": ("Fleet workers — campaign runs", (0, 24), True),
    "bat3-ceitec-bat3-api": ("API", None, True),
    "bat3-ceitec-bat3-web": ("Web application", None, True),
    "bioid-mcp": ("MCP server", (0, 3), True),
    "validation-docs": ("Documentation", None, True),
    # BLAST services with an NVMe copy (deploy/bioid-blast-<db>.yaml): 0 = stopped,
    # the copy stays on the volume; workers search NFS meanwhile.
    "bioid-blast-nr": ("BLAST service — NCBI nr on NVMe", (0, 1), True),
    "bioid-blast-nt": ("BLAST service — NCBI nt on NVMe", (0, 1), True),
    "bioid-blast-core-nt": ("BLAST service — NCBI core_nt on NVMe", (0, 1), True),
    "bioid-blast-uniref50": ("BLAST service — UniRef50 on NVMe", (0, 1), True),
    "bat3-redis": ("Redis — queue broker (restart loses queued runs)", None, False),
}
PVCS = ("bat3-runs-data-ceitec", "bat3-databases-data-ceitec")


def _runs_dir() -> Path:
    from .routes.runs import get_runs_dir
    return get_runs_dir()


# -- auth ------------------------------------------------------------------------

def _password() -> str:
    pw = os.environ.get("BAT3_ADMIN_PASSWORD", "")
    if not pw:
        raise HTTPException(status_code=503, detail="Admin is not configured on this server.")
    return pw


def _signing_key() -> bytes:
    return hashlib.sha256(("bioid-admin|" + _password() + "|" +
                           os.environ.get("BAT3_IP_HASH_KEY", "")).encode()).digest()


def _sign(payload: dict[str, Any]) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    mac = hmac.new(_signing_key(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def require_admin(authorization: Optional[str] = Header(None)) -> None:
    token = (authorization or "").removeprefix("Bearer ").strip()
    body, _, mac = token.partition(".")
    if not body or not mac or not hmac.compare_digest(
            hmac.new(_signing_key(), body.encode(), hashlib.sha256).hexdigest(), mac):
        raise HTTPException(status_code=401, detail="Sign in to the admin page.")
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except ValueError:
        raise HTTPException(status_code=401, detail="Sign in to the admin page.")
    if payload.get("exp", 0) < time.time():
        raise HTTPException(status_code=401, detail="The admin session expired; sign in again.")


def _login_throttle(ip: Optional[str]) -> None:
    client = security._redis_client()
    if client is None:
        return
    keys = [(f"bioid:admin:fail:{security.ip_hash(ip)}", 10, 900),
            ("bioid:admin:fail:all", 100, 3600)]
    try:
        for key, limit, _ in keys:
            if int(client.get(key) or 0) >= limit:
                raise HTTPException(status_code=429, headers={"Retry-After": "900"},
                                    detail="Too many failed sign-ins; try again in 15 minutes.")
    except HTTPException:
        raise
    except Exception:
        pass


def _login_failed(ip: Optional[str]) -> None:
    client = security._redis_client()
    if client is None:
        return
    try:
        for key, ttl in ((f"bioid:admin:fail:{security.ip_hash(ip)}", 900), ("bioid:admin:fail:all", 3600)):
            if int(client.incr(key)) == 1:
                client.expire(key, ttl)
    except Exception:
        pass


@router.post("/login")
async def login(request: Request, body: dict = Body(...)) -> dict:
    from .routes.runs import _requester_ip
    ip = _requester_ip(request)
    _login_throttle(ip)
    given = str(body.get("password") or "")
    if not hmac.compare_digest(given.encode(), _password().encode()):
        _login_failed(ip)
        raise HTTPException(status_code=401, detail="Wrong password.")
    exp = int(time.time()) + SESSION_S
    return {"token": _sign({"exp": exp}), "expires_at": exp}


# -- helpers --------------------------------------------------------------------

_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()


def _cached(key: str, ttl: float, loader):
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    value = loader()
    with _cache_lock:
        _cache[key] = (now, value)
    return value


def _k8s():
    from kubernetes import client, config
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()
    return client.AppsV1Api(), client.CoreV1Api()


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _deployments() -> list[dict[str, Any]]:
    apps, core = _k8s()
    out = []
    for name, (label, scale, restartable) in DEPLOYMENTS.items():
        try:
            d = apps.read_namespaced_deployment(name, NAMESPACE)
        except Exception as exc:
            if name.startswith("bioid-blast-") and getattr(exc, "status", None) == 404:
                continue  # that BLAST service has not been set up
            out.append({"name": name, "label": label, "error": str(exc)[:200]})
            continue
        selector = ",".join(f"{k}={v}" for k, v in (d.spec.selector.match_labels or {}).items())
        pods = []
        for p in core.list_namespaced_pod(NAMESPACE, label_selector=selector).items:
            cs = (p.status.container_statuses or [])
            restarts = sum(c.restart_count for c in cs)
            last = next((c.last_state.terminated for c in cs
                         if c.last_state and c.last_state.terminated), None)
            waiting = next((c.state.waiting.reason for c in cs if c.state and c.state.waiting), None)
            pods.append({
                "name": p.metadata.name, "phase": p.status.phase,
                "ready": all(c.ready for c in cs) if cs else False,
                "restarts": restarts, "waiting": waiting,
                "last_exit": f"{last.reason} ({last.exit_code})" if last else None,
                "started": _iso(p.status.start_time), "node": p.spec.node_name,
                "deleting": p.metadata.deletion_timestamp is not None,
            })
        image = d.spec.template.spec.containers[0].image
        out.append({
            "name": name, "label": label,
            "replicas": d.spec.replicas, "ready": d.status.ready_replicas or 0,
            "updated": d.status.updated_replicas or 0,
            "image": image.split("/")[-1][:80],
            "scale": list(scale) if scale else None, "restartable": restartable,
            "pods": sorted(pods, key=lambda x: x["name"]),
        })
    return out


def _queues() -> dict[str, Any]:
    client = security._redis_client()
    out: dict[str, Any] = {"queues": [], "paused": []}
    if client is None:
        out["error"] = "Redis not configured"
        return out
    try:
        for q in QUEUES:
            out["queues"].append({"name": q, "waiting": int(client.llen(q))})
        out["paused"] = sorted(x.decode() for x in client.smembers("bioid:admin:paused"))
    except Exception as exc:
        out["error"] = str(exc)[:200]
    return out


def _workers() -> dict[str, Any]:
    from src_new.celery_app import celery
    insp = celery.control.inspect(timeout=2.0)
    try:
        active = insp.active() or {}
        reserved = insp.reserved() or {}
        queues = insp.active_queues() or {}
    except Exception as exc:
        return {"error": str(exc)[:200], "workers": []}
    workers = []
    for name in sorted(set(active) | set(queues)):
        workers.append({
            "name": name,
            "queues": sorted(q.get("name") for q in queues.get(name, []) if isinstance(q, dict)),
            "active": [{"run_id": t.get("id"), "started": t.get("time_start")}
                       for t in active.get(name, [])],
            "reserved": len(reserved.get(name, [])),
        })
    return {"workers": workers}


def _dir_size(path: Path) -> int:
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


_storage_state: dict[str, Any] = {"value": None, "at": 0.0, "running": False}


def _storage_async() -> dict[str, Any]:
    """Storage walks ~30 GB on NFS (tens of seconds): computed in the
    background at most every 10 minutes; the page shows the last result."""
    st = _storage_state
    if not st["running"] and time.time() - st["at"] > 600:
        st["running"] = True

        def work():
            try:
                st["value"] = _storage()
            except Exception as exc:
                st["value"] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            finally:
                st["at"], st["running"] = time.time(), False
        threading.Thread(target=work, daemon=True).start()
    if st["value"] is None:
        return {"error": "Measuring storage (first time after a restart, about a minute)…"}
    return {**st["value"], "measured_at": st["at"]}


def _storage() -> dict[str, Any]:
    runs = _runs_dir()
    top_files = []
    for e in os.scandir(runs):
        if e.is_file(follow_symlinks=False):
            top_files.append({"name": e.name, "bytes": e.stat(follow_symlinks=False).st_size})
    out: dict[str, Any] = {
        "runs_bytes": _dir_size(runs),
        "trash_bytes": _dir_size(runs / retention.EXPIRED_DIR) if (runs / retention.EXPIRED_DIR).is_dir() else 0,
        "adhoc_bytes": _dir_size(runs / "_adhoc") if (runs / "_adhoc").is_dir() else 0,
        "loose_files": sorted(top_files, key=lambda x: -x["bytes"])[:20],
        "pvcs": [],
    }
    try:
        _, core = _k8s()
        for name in PVCS:
            pvc = core.read_namespaced_persistent_volume_claim(name, NAMESPACE)
            out["pvcs"].append({"name": name, "capacity": (pvc.status.capacity or {}).get("storage")})
    except Exception as exc:
        out["pvc_error"] = str(exc)[:200]
    return out


def _by_queue(runs: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Run counts per queue and status."""
    out: dict[str, dict[str, int]] = {}
    for r in runs:
        lane = out.setdefault(r.get("queue") or "web", {})
        lane[r["status"]] = lane.get(r["status"], 0) + 1
    return out


def _runs_overview() -> dict[str, Any]:
    from .routes.runs import example_ids  # never the full scan (2026-11-17)
    runs = run_index.summaries(_runs_dir())
    now = datetime.now(timezone.utc)
    by_status: dict[str, int] = {}
    for r in runs:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    def since(r, days):
        try:
            return datetime.fromisoformat(str(r["created_at"]).replace("Z", "+00:00")) >= now - timedelta(days=days)
        except ValueError:
            return False

    examples = example_ids(_runs_dir())
    public = [{k: v for k, v in r.items() if not k.startswith("_")} | {"example": r["run_id"] in examples}
              for r in runs]
    public.sort(key=lambda r: str(r["created_at"]), reverse=True)
    expiring = sorted((r for r in public if r["retention"]["expires_at"] and not r["example"]),
                      key=lambda r: r["retention"]["expires_at"])
    return {
        "total": len(runs), "by_status": by_status,
        "submitted_24h": sum(1 for r in runs if since(r, 1)),
        "submitted_7d": sum(1 for r in runs if since(r, 7)),
        "failed_24h": sum(1 for r in runs if r["status"] == "failed" and since(r, 1)),
        "active": [r for r in public if r["status"] in ("queued", "running", "pending", "created",
                                                        "retry_scheduled")],
        "by_queue": _by_queue(runs),
        "recent_failures": [r for r in public if r["status"] == "failed"][:15],
        "recent": public[:50],
        "expiring_soon": expiring[:15],
    }


def _retention_status() -> dict[str, Any]:
    last = None
    client = security._redis_client()
    if client is not None:
        try:
            raw = client.get("bioid:retention:last")
            last = json.loads(raw) if raw else None
        except Exception:
            last = None
    return {"enforce": retention.enforcing(), "default_days": retention.default_days(),
            "grace_days": retention.grace_days(), "last_sweep": last,
            "expired": retention.expired_listing(_runs_dir())}


def _section(fn):
    try:
        return fn()
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}


@router.get("/overview", dependencies=[Depends(require_admin)])
async def overview() -> dict:
    """Everything the dashboard shows; cached a few seconds per section."""
    import asyncio
    def build():
        return {
            "time": time.time(),
            "code_version": os.environ.get("BAT3_CODE_VERSION", ""),
            "queues": _section(lambda: _cached("queues", 3, _queues)),
            "workers": _section(lambda: _cached("workers", 15, _workers)),
            "deployments": _section(lambda: _cached("deployments", 5, _deployments)),
            "runs": _section(lambda: _cached("runs", 30, _runs_overview)),
            "storage": _section(_storage_async),
            "retention": _section(lambda: _cached("retention", 30, _retention_status)),
            "limits": {**security.current_limits(), "max_files": security.MAX_FILES},
            "reports": _section(lambda: _cached("reports", 30, _reports_summary)),
            "checks": _section(lambda: _cached("checks", 30, _checks_summary)),
            "services": _section(lambda: _cached("services", 60, _services)),
            "blast_services": _section(lambda: _cached("blast_services", 10, _blast_services)),
            "lanes": _section(_lanes),
        }
    return await asyncio.to_thread(build)


def _services() -> dict:
    """Calls per database / web service (service_stats.py) and the searches
    running now, with the NCBI concurrency check."""
    from src_new import service_stats as ss
    client = ss.reader()
    if client is None:
        return {"error": "BAT3_SHARED_CACHE_URL is not set on the API"}
    now = time.time()
    last_30m = ss.summarize(ss.window(client, 1800, now))
    running = ss.running_now(client)
    ncbi = [r for r in running if r.get("service") in ss.NCBI_SERVICES]
    return {"last_30m": last_30m,
            "last_24h": ss.summarize(ss.window(client, 86400, now)),
            "failing": ss.failing(last_30m),
            "running": running,
            "ncbi_running": len(ncbi), "ncbi_alarm_at": ss.ncbi_alarm_at()}


#: BLAST services with an NVMe copy (src_new/blast_service.py): database,
#: deployment, [blast] setting with the address
BLAST_SERVICES = (("nr", "bioid-blast-nr", "nr_service_url"), ("nt", "bioid-blast-nt", "nt_service_url"),
                  ("core_nt", "bioid-blast-core-nt", "core_nt_service_url"),
                  ("uniref50", "bioid-blast-uniref50", "uniref50_service_url"))


def _blast_services() -> list[dict]:
    """Each BLAST service's /health (2026-11-19): what it serves, what it is
    downloading or copying, and its searches. Workers search a database on
    its service only while it is ready with the release NFS points to."""
    import requests
    from src_new.config.loader import RunConfig
    from src_new.identification.resolvers.blast_service_client import release_of
    cfg = RunConfig.from_default_ini()
    db_paths = {"nr": cfg.blast.nr_aa_db, "nt": cfg.blast.nt_db, "core_nt": cfg.blast.core_nt_db,
                "uniref50": cfg.blast.uniref50_aa_db}
    out = []
    for db, deployment, setting in BLAST_SERVICES:
        url = getattr(cfg.blast, setting, "")
        row: dict[str, Any] = {"db": db, "deployment": deployment, "url": url}
        try:
            row["nfs_release"] = release_of(db_paths[db])
        except Exception:
            row["nfs_release"] = None
        try:
            h = requests.get(f"{url}/health", timeout=2).json()
            st = h.get("staging") or {}
            row.update(state=h.get("state"), release=h.get("release"), prefetch=h.get("prefetch"),
                       error=h.get("error") or "", blast_version=h.get("blast_version"),
                       threads=h.get("threads"),
                       counts={k: h.get(k, 0) for k in ("running", "waiting", "searches", "timeouts", "failures")},
                       staging={k: st.get(k) for k in ("release", "source", "done_bytes", "total_bytes",
                                                       "files_done", "files_total", "started", "finished")})
            row["used_by_workers"] = h.get("state") == "ready" and h.get("release") == row["nfs_release"]
        except Exception as exc:
            row.update(state="no answer", error=str(exc)[:200], used_by_workers=False)
        out.append(row)
    return out


#: The queues on the admin page: BioID's lanes (retries.py) first, then the
#: validation fleet's. "lane" = None: no submission token or retry policy.
LANE_CARDS = (
    {"lane": "web", "title": "Web", "deployment": "bat3-ui-worker",
     "about": "Runs submitted from the web page, the REST API and MCP."},
    {"lane": "repository", "title": "Repository", "deployment": "bat3-repo-worker",
     "about": "Campaigns (mdval): submitted with a token, automatic retries possible."},
    {"lane": None, "title": "Fleet", "queue": "celery", "deployment": "bat3-ceitec-bat3-worker",
     "about": "Validation fleet: Celery's default queue."},
    {"lane": None, "title": "Bughunt", "queue": "bughunt", "deployment": None,
     "about": "Bughunt campaign queue."},
)


def _lanes() -> list[dict[str, Any]]:
    """One card per queue: waiting/running counts, its worker pool, the
    Celery workers consuming it, retry policy and submission token."""
    from src_new import retries
    from . import queue_tokens
    queues = _section(lambda: _cached("queues", 3, _queues))
    workers = _section(lambda: _cached("workers", 15, _workers))
    deployments = _section(lambda: _cached("deployments", 5, _deployments))
    runs = _section(lambda: _cached("runs", 30, _runs_overview))
    waiting = {q["name"]: q["waiting"] for q in queues.get("queues", [])} if "error" not in queues else {}
    paused = set(queues.get("paused", [])) if "error" not in queues else set()
    deps = {d["name"]: d for d in deployments} if isinstance(deployments, list) else {}
    policies = retries.policies(_runs_dir())
    out = []
    for card in LANE_CARDS:
        lane = card["lane"]
        queue = card.get("queue") or retries.celery_queue(lane) or "celery"
        consumers = [w for w in workers.get("workers", []) if queue in (w.get("queues") or [])]
        dep = deps.get(card["deployment"]) if card["deployment"] else None
        counts = (runs.get("by_queue") or {}).get(lane, {}) if lane and "error" not in runs else {}
        out.append({
            **{k: card[k] for k in ("lane", "title", "about", "deployment")},
            "queue": queue,
            "waiting": waiting.get(queue),
            "paused": queue in paused,
            "running": sum(len(w.get("active") or []) for w in consumers),
            "reserved": sum(w.get("reserved") or 0 for w in consumers),
            "consumers": [{"name": w["name"], "active": w.get("active") or [],
                           "reserved": w.get("reserved") or 0} for w in consumers],
            "pool": ({k: dep.get(k) for k in ("replicas", "ready", "updated", "image", "scale", "error")}
                     | {"crashing": sum(1 for p in dep.get("pods") or [] if p.get("waiting"))}
                     if dep else None),
            "runs": counts,
            "retry_waiting": counts.get(retries.STATUS, 0),
            "retry_policy": policies.get(lane) if lane else None,
            "token": queue_tokens.info(_runs_dir(), lane) if lane and lane != "web" else None,
            "errors": [x["error"] for x in (queues, workers, runs) if isinstance(x, dict) and "error" in x][:2],
        })
    return out


@router.put("/lanes/{lane}/retry", dependencies=[Depends(require_admin)])
async def put_retry_policy(lane: str, body: dict = Body(...)) -> dict:
    """Automatic retries of a queue: enabled, max_attempts, delay_minutes,
    incomplete, worker_lost (retries.py)."""
    from src_new import retries
    try:
        return {"lane": lane, "retry_policy": retries.set_policy(lane, body, _runs_dir())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/lanes/{lane}/token", dependencies=[Depends(require_admin)])
async def new_queue_token(lane: str) -> dict:
    """A new submission token for the queue (shown once; replaces the old one)."""
    from src_new import retries
    from . import queue_tokens
    if lane not in retries.LANES or lane == "web":
        raise HTTPException(status_code=404, detail="This queue takes no token.")
    token = queue_tokens.create(_runs_dir(), lane)
    return {"lane": lane, "token": token, "header": queue_tokens.HEADER,
            "info": queue_tokens.info(_runs_dir(), lane)}


@router.delete("/lanes/{lane}/token", dependencies=[Depends(require_admin)])
async def revoke_queue_token(lane: str) -> dict:
    from . import queue_tokens
    return {"lane": lane, "revoked": queue_tokens.revoke(_runs_dir(), lane)}


def _checks_summary() -> dict:
    from . import watchdog
    st = watchdog.state(_runs_dir())
    return {"cases": len(watchdog.cases(_runs_dir())), "status": st.get("status"),
            "started_at": st.get("started_at"), "finished_at": st.get("finished_at"),
            "last_completed": st.get("last_completed")}


def _reports_summary() -> dict:
    from . import reports
    items = reports.listing(_runs_dir())
    return {"open": sum(1 for r in items if r.get("status") == "open"), "total": len(items)}


@router.get("/traffic", dependencies=[Depends(require_admin)])
async def traffic_stats(window: str = Query("24h")) -> dict:
    """Traffic statistics for one window (1h, 24h, 7d, 30d, 90d, all)."""
    import asyncio
    from . import traffic
    if window not in traffic.WINDOWS:
        raise HTTPException(status_code=422, detail=f"window must be one of {', '.join(traffic.WINDOWS)}")
    ttl = 30 if window in ("1h", "24h") else 300
    return await asyncio.to_thread(lambda: _cached(f"traffic:{window}", ttl, lambda: traffic.summarize(window)))


@router.get("/settings/limits", dependencies=[Depends(require_admin)])
async def get_limits() -> dict:
    return security.current_limits()


def _limit_value(body: dict, key: str) -> Optional[int]:
    if key not in body or body[key] is None:
        return None
    try:
        value = int(body[key])
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"{key} must be a whole number")
    if not 0 <= value <= security.MAX_LIMIT:
        raise HTTPException(status_code=422, detail=f"{key} must be between 0 (no limit) and {security.MAX_LIMIT}")
    return value


@router.put("/settings/limits", dependencies=[Depends(require_admin)])
async def put_limits(body: dict = Body(...)) -> dict:
    """{submit_per_hour?, queue_cap?}: 0 = no limit; takes effect within 10 s."""
    out = security.save_limits(submit_per_hour=_limit_value(body, "submit_per_hour"),
                               queue_cap=_limit_value(body, "queue_cap"))
    _drop_cache()
    return out


@router.put("/settings/limits/exceptions", dependencies=[Depends(require_admin)])
async def put_limit_exception(body: dict = Body(...)) -> dict:
    """{address (IP or CIDR), label, per_hour}: an address's own hourly limit."""
    import ipaddress
    address = str(body.get("address") or "").strip()
    try:
        address = str(ipaddress.ip_network(address, strict=False))
    except ValueError:
        raise HTTPException(status_code=422, detail="address must be an IP address or a CIDR range")
    per_hour = _limit_value(body, "per_hour")
    if per_hour is None:
        raise HTTPException(status_code=422, detail="per_hour is required")
    exceptions = dict(security.current_limits()["exceptions"])
    exceptions[address] = {"label": str(body.get("label") or "")[:80], "per_hour": per_hour}
    out = security.save_limits(exceptions=exceptions)
    _drop_cache()
    return out


@router.delete("/settings/limits/exceptions", dependencies=[Depends(require_admin)])
async def delete_limit_exception(address: str = Query(...)) -> dict:
    exceptions = dict(security.current_limits()["exceptions"])
    if exceptions.pop(address, None) is None:
        raise HTTPException(status_code=404, detail="No exception for this address.")
    out = security.save_limits(exceptions=exceptions)
    _drop_cache()
    return out


# -- actions ----------------------------------------------------------------------

def _drop_cache(*keys: str) -> None:
    with _cache_lock:
        for k in keys:
            _cache.pop(k, None)


def _deployment(name: str) -> tuple[str, Optional[tuple[int, int]], bool]:
    if name not in DEPLOYMENTS:
        raise HTTPException(status_code=404, detail="Not a BioID deployment.")
    return DEPLOYMENTS[name]


@router.post("/deployments/{name}/scale", dependencies=[Depends(require_admin)])
async def scale(name: str, body: dict = Body(...)) -> dict:
    _, bounds, _ = _deployment(name)
    if not bounds:
        raise HTTPException(status_code=400, detail=f"{name} is not scalable here.")
    try:
        replicas = int(body.get("replicas"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="replicas must be a number")
    if not bounds[0] <= replicas <= bounds[1]:
        raise HTTPException(status_code=422, detail=f"replicas must be between {bounds[0]} and {bounds[1]}")
    apps, _ = _k8s()
    apps.patch_namespaced_deployment_scale(name, NAMESPACE, {"spec": {"replicas": replicas}})
    _drop_cache("deployments")
    return {"name": name, "replicas": replicas}


@router.post("/deployments/{name}/restart", dependencies=[Depends(require_admin)])
async def restart(name: str) -> dict:
    _, _, restartable = _deployment(name)
    if not restartable:
        raise HTTPException(status_code=400, detail=f"{name} cannot be restarted from here.")
    apps, _ = _k8s()
    stamp = datetime.now(timezone.utc).isoformat()
    apps.patch_namespaced_deployment(name, NAMESPACE, {"spec": {"template": {"metadata": {
        "annotations": {"kubectl.kubernetes.io/restartedAt": stamp}}}}})
    _drop_cache("deployments")
    return {"name": name, "restarted_at": stamp}


def _bioid_pod(name: str) -> None:
    deps = {d for d, (_, _, restartable) in DEPLOYMENTS.items()}
    if not any(name.startswith(d + "-") for d in deps):
        raise HTTPException(status_code=404, detail="Not a BioID pod.")


@router.post("/pods/{name}/delete", dependencies=[Depends(require_admin)])
async def delete_pod(name: str) -> dict:
    _bioid_pod(name)
    if name.startswith("bat3-redis-"):
        raise HTTPException(status_code=400, detail="Redis cannot be restarted from here.")
    _, core = _k8s()
    core.delete_namespaced_pod(name, NAMESPACE)
    _drop_cache("deployments")
    return {"pod": name, "deleted": True}


@router.get("/pods/{name}/logs", dependencies=[Depends(require_admin)])
async def pod_logs(name: str, tail: int = Query(300, ge=10, le=5000)) -> PlainTextResponse:
    _bioid_pod(name)
    _, core = _k8s()
    text = core.read_namespaced_pod_log(name, NAMESPACE, tail_lines=tail, timestamps=True)
    return PlainTextResponse(text or "")


@router.post("/queues/{name}/{action}", dependencies=[Depends(require_admin)])
async def queue_action(name: str, action: str) -> dict:
    if name not in QUEUES:
        raise HTTPException(status_code=404, detail="Unknown queue.")
    client = security._redis_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Redis not configured")
    from src_new.celery_app import celery
    if action == "purge":
        # The queued runs' results.json still say "queued": mark them
        # cancelled, or they would show as waiting forever.
        messages = client.lrange(name, 0, -1)
        client.delete(name)
        cancelled = _cancel_purged(messages)
        result: dict[str, Any] = {"queue": name, "removed": len(messages), "cancelled": cancelled}
    elif action == "pause":
        celery.control.cancel_consumer(name)
        client.sadd("bioid:admin:paused", name)
        result = {"queue": name, "paused": True}
    elif action == "resume":
        celery.control.add_consumer(name)
        client.srem("bioid:admin:paused", name)
        result = {"queue": name, "paused": False}
    else:
        raise HTTPException(status_code=404, detail="Unknown action.")
    _drop_cache("queues", "workers")
    return result


def _cancel_purged(messages: list) -> list[str]:
    """Mark the runs of purged Celery messages cancelled (if still queued)."""
    from src_new.results.results_manager import ResultsManager
    done = []
    for raw in messages:
        try:
            run_id = json.loads(raw).get("headers", {}).get("id")
            d = security.run_dir(_runs_dir(), str(run_id))
            results = d / "results.json"
            status = json.loads(results.read_text()).get("pipeline", {}).get("status")
        except Exception:
            continue
        if status in ("queued", "pending", "created"):
            ResultsManager(str(results)).finish_run("cancelled")
            done.append(run_id)
    _drop_cache("runs")
    return done


def _run_dir(run_id: str) -> Path:
    d = security.run_dir(_runs_dir(), run_id)
    if not (d / "results.json").is_file():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return d


@router.post("/runs/{run_id}/cancel", dependencies=[Depends(require_admin)])
async def admin_cancel(run_id: security.RunId) -> dict:
    from src_new.celery_app import celery
    from src_new.results.results_manager import ResultsManager
    d = _run_dir(run_id)
    status = json.loads((d / "results.json").read_text()).get("pipeline", {}).get("status")
    if status in retention.TERMINAL:
        raise HTTPException(status_code=400, detail=f"The run already finished ({status}).")
    if status == "retry_scheduled":  # stop retrying; keep the last attempt's results
        rm = ResultsManager(str(d / "results.json"))
        rm._payload["pipeline"].setdefault("retry", {})["cancelled"] = True
        rm.finish_run("success")
        _drop_cache("runs")
        return {"run_id": run_id, "status": "success"}
    celery.AsyncResult(run_id).revoke(terminate=True)
    ResultsManager(str(d / "results.json")).finish_run("cancelled")
    _drop_cache("runs")
    return {"run_id": run_id, "status": "cancelled"}


@router.post("/runs/{run_id}/delete", dependencies=[Depends(require_admin)])
async def admin_delete(run_id: security.RunId) -> dict:
    """Moves the run to the retention trash (restorable during the grace period)."""
    from .routes.runs import example_ids
    d = _run_dir(run_id)
    if run_id in example_ids(_runs_dir()):
        raise HTTPException(status_code=403, detail="Example runs cannot be deleted.")
    status = json.loads((d / "results.json").read_text()).get("pipeline", {}).get("status")
    if status not in retention.TERMINAL:
        raise HTTPException(status_code=400, detail="Cancel the run before deleting it.")
    trash = _runs_dir() / retention.EXPIRED_DIR
    trash.mkdir(exist_ok=True)
    if (trash / run_id).exists():
        raise HTTPException(status_code=409, detail="Already in the trash.")
    (d / ".expired_at").write_text(datetime.now(timezone.utc).isoformat())
    os.rename(d, trash / run_id)
    _drop_cache("runs", "retention")
    return {"run_id": run_id, "trashed": True, "grace_days": retention.grace_days()}


@router.post("/runs/{run_id}/retention", dependencies=[Depends(require_admin)])
async def admin_retention(run_id: security.RunId, body: dict = Body(...)) -> dict:
    d = _run_dir(run_id)
    try:
        policy = retention.parse_retention(str(body.get("retention") or ""))
    except retention.RetentionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    retention.set_policy(d, policy)
    _drop_cache("runs")
    return {"run_id": run_id, "retention": policy}


@router.get("/reports", dependencies=[Depends(require_admin)])
async def admin_reports() -> dict:
    from . import reports
    items = reports.listing(_runs_dir())
    for r in items:
        r.pop("reporter_hash", None)
    return {"reports": items, "open": sum(1 for r in items if r.get("status") == "open")}


@router.put("/reports/{report_id}", dependencies=[Depends(require_admin)])
async def admin_report_update(report_id: str, body: dict = Body(...)) -> dict:
    from . import reports
    try:
        report = reports.update(_runs_dir(), report_id, body.get("status"), body.get("admin_note"))
    except reports.ReportError as e:
        raise HTTPException(status_code=404 if "unknown" in str(e) else 422, detail=str(e))
    report.pop("reporter_hash", None)
    _drop_cache("reports")
    return report


@router.get("/checks", dependencies=[Depends(require_admin)])
async def admin_checks() -> dict:
    """Known-answers cases, the last/current nightly check, crash loops, recent alarms."""
    import asyncio
    from . import alerts, watchdog

    def build():
        try:
            loops = watchdog.crash_loops()
        except Exception as exc:
            loops = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
        return {"cases": watchdog.cases(_runs_dir()), "check": watchdog.state(_runs_dir()),
                "crash_loops": loops, "alerts": alerts.recent(),
                "alert_email": alerts.recipient()}
    return await asyncio.to_thread(build)


@router.post("/checks/cases", dependencies=[Depends(require_admin)])
async def admin_add_case(body: dict = Body(...)) -> dict:
    from . import watchdog
    run_id = str(body.get("run_id") or "")
    _run_dir(run_id)
    try:
        case = watchdog.add_case(_runs_dir(), run_id, str(body.get("label") or ""))
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    _drop_cache("checks")
    return case


@router.delete("/checks/cases/{run_id}", dependencies=[Depends(require_admin)])
async def admin_remove_case(run_id: security.RunId) -> dict:
    from . import watchdog
    watchdog.remove_case(_runs_dir(), run_id)
    _drop_cache("checks")
    return {"removed": run_id}


@router.post("/checks/cases/{run_id}/accept", dependencies=[Depends(require_admin)])
async def admin_accept_case(run_id: security.RunId) -> dict:
    from . import watchdog
    try:
        case = watchdog.accept(_runs_dir(), run_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    _drop_cache("checks")
    return case


@router.post("/checks/run", dependencies=[Depends(require_admin)])
async def admin_run_check() -> dict:
    """Start the known-answers check now (409 while one is running)."""
    import asyncio
    from . import watchdog
    if watchdog.state(_runs_dir()).get("status") == "running":
        raise HTTPException(status_code=409, detail="A check is already running.")
    if not watchdog.cases(_runs_dir()):
        raise HTTPException(status_code=409, detail="No known-answers cases yet.")
    st = await asyncio.to_thread(watchdog.start_check, _runs_dir())
    _drop_cache("checks")
    return st


@router.post("/alerts/test", dependencies=[Depends(require_admin)])
async def admin_test_alert() -> dict:
    """Send a test alarm email (bypasses the once-per-6-hours limit)."""
    import asyncio
    from . import alerts
    if not alerts.recipient():
        raise HTTPException(status_code=409, detail="BAT3_ALERT_EMAIL is not set.")
    sent = await asyncio.to_thread(alerts.alarm, f"test:{time.time()}", "Test alarm",
                                   "A test alarm from the BioID admin page. No action needed.", 60)
    return {"sent": sent, "to": alerts.recipient()}


@router.post("/expired/{run_id}/restore", dependencies=[Depends(require_admin)])
async def admin_restore(run_id: security.RunId) -> dict:
    try:
        retention.restore(_runs_dir(), run_id)
    except retention.RetentionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _drop_cache("runs", "retention")
    return {"run_id": run_id, "restored": True, "retention": {"policy": "preserve"}}
