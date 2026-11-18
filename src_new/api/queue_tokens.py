"""Tokens for submitting to a non-web queue (2026-11-18).

The repository queue (retries.py) is for campaigns, with its own workers and
automatic retries; submitting to it needs a token, created and revoked on the
admin page. Only a SHA-256 of each token is stored, in
_settings/queue_tokens.json; the token itself is shown once, when created.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Optional

FILE = "_settings/queue_tokens.json"
HEADER = "X-Queue-Token"


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _load(runs_dir: Path) -> dict[str, Any]:
    try:
        return json.loads((runs_dir / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _store(runs_dir: Path, data: dict[str, Any]) -> None:
    path = runs_dir / FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def create(runs_dir: Path, lane: str) -> str:
    """A new token for `lane`, replacing any previous one. Returned once."""
    token = secrets.token_urlsafe(32)
    data = _load(runs_dir)
    data[lane] = {"sha256": _sha(token), "created_at": time.time(), "hint": token[-4:]}
    _store(runs_dir, data)
    return token


def revoke(runs_dir: Path, lane: str) -> bool:
    data = _load(runs_dir)
    if data.pop(lane, None) is None:
        return False
    _store(runs_dir, data)
    return True


def check(runs_dir: Path, lane: str, token: Optional[str]) -> bool:
    entry = _load(runs_dir).get(lane) or {}
    expected = entry.get("sha256")
    return bool(token and expected and hmac.compare_digest(_sha(token), expected))


def info(runs_dir: Path, lane: str) -> Optional[dict[str, Any]]:
    """{created_at, hint} of the lane's token, or None."""
    entry = _load(runs_dir).get(lane)
    return {"created_at": entry.get("created_at"), "hint": entry.get("hint")} if entry else None
