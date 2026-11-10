"""Safety rails for the public runs API.

- Run ids: one path segment of a safe alphabet, so a run id can never name
  the runs directory itself ("." / "..") or anything outside it.
- Owner tokens: a submission returns a secret token; deleting or cancelling
  the run needs it (X-Owner-Token header). Only its SHA-256 is stored, in
  results.json (pipeline.owner_token_sha256). Runs without one (submitted
  before 2026-11-10, the examples) cannot be deleted or cancelled through the
  API.
- Submitter address: stored only as a keyed hash (pipeline.creator_ip_hash,
  HMAC-SHA256 with BAT3_IP_HASH_KEY), enough for "your runs" and rate limits.
- Limits: run submissions per address per hour, and a cap on runs waiting in
  the UI queue, both answered with 429 + Retry-After. Counters live in the
  Celery Redis; when it is unreachable the limits are not enforced (logged).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from pathlib import Path
from typing import Annotated, Any, Optional

from fastapi import HTTPException
from fastapi import Path as PathParam

log = logging.getLogger(__name__)

RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
#: Path parameter type for every {run_id} route.
RunId = Annotated[str, PathParam(pattern=RUN_ID_RE.pattern + "$",
                                 description="Run id returned by POST /runs")]

OWNER_HEADER = "X-Owner-Token"

#: File types a run may upload (the web form's list, plus CHARMM/GROMACS
#: auxiliaries). Anything else, e.g. .html or .svg, is refused: /files serves
#: the uploads back from the BioID origin.
ALLOWED_SUFFIXES = (
    ".tpr", ".gro", ".top", ".itp", ".trr", ".xtc", ".ndx", ".mdp",
    ".prmtop", ".parm7", ".nc", ".rst7", ".inpcrd", ".restrt", ".mdcrd",
    ".psf", ".pdb", ".ent", ".crd", ".dcd", ".prm", ".rtf", ".str", ".inp",
    ".data", ".lmp", ".cif", ".mmcif", ".xyz",
    ".json", ".yaml", ".yml", ".ini",
    ".zip", ".tar", ".tar.gz", ".tgz",
)
MAX_FILES = int(os.environ.get("BAT3_MAX_UPLOAD_FILES", "50"))


def valid_run_id(run_id: str) -> bool:
    return bool(RUN_ID_RE.fullmatch(run_id)) and ".." not in run_id


def run_dir(runs_dir: Path, run_id: str) -> Path:
    """The run's directory, guaranteed to be a direct child of runs_dir."""
    if not valid_run_id(run_id):
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    path = runs_dir / run_id
    if path.resolve().parent != runs_dir.resolve():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return path


def allowed_upload(name: str) -> bool:
    return name.lower().endswith(ALLOWED_SUFFIXES)


# -- owner tokens -------------------------------------------------------------

def new_owner_token() -> tuple[str, str]:
    """(token for the submitter, hash to store)."""
    token = secrets.token_urlsafe(24)
    return token, token_hash(token)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def require_owner(pipeline: dict[str, Any], token: Optional[str], action: str) -> None:
    """403 unless `token` is the run's owner token."""
    stored = pipeline.get("owner_token_sha256") if isinstance(pipeline, dict) else None
    if not stored:
        raise HTTPException(status_code=403, detail=(
            f"This run cannot be {action} through the API: it has no owner token "
            "(it was submitted before owner tokens existed, or it is an example)."))
    if not token or not hmac.compare_digest(token_hash(token), stored):
        raise HTTPException(status_code=403, detail=(
            f"Only the submitter of this run can have it {action}. Send the owner token "
            f"returned at submission in the {OWNER_HEADER} header."))


# -- submitter address --------------------------------------------------------

def _ip_key() -> bytes:
    return os.environ.get("BAT3_IP_HASH_KEY", "bioid-default-ip-key").encode()


def ip_hash(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    return hmac.new(_ip_key(), ip.encode(), hashlib.sha256).hexdigest()[:32]


def same_submitter(pipeline: dict[str, Any], ip: Optional[str]) -> bool:
    """Was the run submitted from `ip`? (hash; plain creator_ip of older runs)"""
    if not ip or not isinstance(pipeline, dict):
        return False
    if pipeline.get("creator_ip_hash"):
        return hmac.compare_digest(pipeline["creator_ip_hash"], ip_hash(ip) or "")
    return pipeline.get("creator_ip") == ip


# -- limits --------------------------------------------------------------------

SUBMIT_LIMIT_PER_HOUR = int(os.environ.get("BAT3_SUBMIT_LIMIT_PER_HOUR", "30"))
QUEUE_CAP = int(os.environ.get("BAT3_QUEUE_CAP", "40"))

_redis = None


def _redis_client():
    global _redis
    if _redis is None:
        url = os.environ.get("CELERY_BROKER_URL")
        if not url:
            return None
        import redis
        _redis = redis.Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)
    return _redis


def check_submit_limits(ip: Optional[str]) -> None:
    """429 when this address submitted too many runs this hour, or when too
    many runs are already waiting. Counts this submission."""
    client = _redis_client()
    if client is None:
        return
    try:
        queue = os.environ.get("VALIDATION_UI_QUEUE") or "celery"
        waiting = int(client.llen(queue))
        if QUEUE_CAP > 0 and waiting >= QUEUE_CAP:
            raise HTTPException(status_code=429, headers={"Retry-After": "600"}, detail=(
                f"BioID is busy: {waiting} runs are waiting to start. "
                "Please try again in about 10 minutes."))
        if SUBMIT_LIMIT_PER_HOUR > 0 and ip:
            hour = int(time.time() // 3600)
            key = f"bioid:submits:{ip_hash(ip)}:{hour}"
            count = int(client.incr(key))
            if count == 1:
                client.expire(key, 3700)
            if count > SUBMIT_LIMIT_PER_HOUR:
                retry = 3600 - int(time.time()) % 3600
                raise HTTPException(status_code=429, headers={"Retry-After": str(retry)}, detail=(
                    f"Too many runs from your network address: at most "
                    f"{SUBMIT_LIMIT_PER_HOUR} per hour. Please try again in "
                    f"{max(1, retry // 60)} minutes."))
    except HTTPException:
        raise
    except Exception as exc:  # Redis down: do not block submissions
        log.warning("submit limits not checked: %s", exc)
