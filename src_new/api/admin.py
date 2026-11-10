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
QUEUES = ("validation.ui.celery", "celery", "bughunt")
SESSION_S = 12 * 3600

#: deployment -> (label, (min, max) replicas or None = not scalable, restartable)
DEPLOYMENTS: dict[str, tuple[str, Optional[tuple[int, int]], bool]] = {
    "bat3-ui-worker": ("UI workers — web, API and MCP runs", (0, 20), True),
    "bat3-ceitec-bat3-worker": ("Fleet workers — campaign runs", (0, 24), True),
    "bat3-ceitec-bat3-api": ("API", None, True),
    "bat3-ceitec-bat3-web": ("Web application", None, True),
    "bioid-mcp": ("MCP server", (0, 3), True),
    "validation-docs": ("Documentation", None, True),
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


def _runs_overview() -> dict[str, Any]:
    from .routes.runs import served_example_ids
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

    examples = served_example_ids(_runs_dir())
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
        "active": [r for r in public if r["status"] in ("queued", "running", "pending", "created")],
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
            "runs": _section(lambda: _cached("runs", 10, _runs_overview)),
            "storage": _section(lambda: _cached("storage", 600, _storage)),
            "retention": _section(lambda: _cached("retention", 30, _retention_status)),
            "limits": {"submit_per_hour": security.SUBMIT_LIMIT_PER_HOUR,
                       "queue_cap": security.QUEUE_CAP, "max_files": security.MAX_FILES},
        }
    return await asyncio.to_thread(build)


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
    celery.AsyncResult(run_id).revoke(terminate=True)
    ResultsManager(str(d / "results.json")).finish_run("cancelled")
    _drop_cache("runs")
    return {"run_id": run_id, "status": "cancelled"}


@router.post("/runs/{run_id}/delete", dependencies=[Depends(require_admin)])
async def admin_delete(run_id: security.RunId) -> dict:
    """Moves the run to the retention trash (restorable during the grace period)."""
    from .routes.runs import served_example_ids
    d = _run_dir(run_id)
    if run_id in served_example_ids(_runs_dir()):
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


@router.post("/expired/{run_id}/restore", dependencies=[Depends(require_admin)])
async def admin_restore(run_id: security.RunId) -> dict:
    try:
        retention.restore(_runs_dir(), run_id)
    except retention.RetentionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _drop_cache("runs", "retention")
    return {"run_id": run_id, "restored": True, "retention": {"policy": "preserve"}}
