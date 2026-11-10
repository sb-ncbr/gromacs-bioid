"""Replace the plaintext submitter address in existing results.json files.

Runs submitted before 2026-11-10 stored pipeline.creator_ip, and /files
serves results.json publicly. This rewrites it as pipeline.creator_ip_hash
(src_new.api.security.ip_hash, so "Your annotations" keeps working: run it
where BAT3_IP_HASH_KEY is the API's, i.e. inside the API pod).

Only finished runs are touched (a running worker would write the old value
back from memory); run it again later for the rest. Writes are atomic
(temp file + rename). Idempotent.

    python scripts/migrate_creator_ip.py [--runs-dir /app/runs] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src_new.api.security import ip_hash  # noqa: E402

TERMINAL = {"success", "failed", "cancelled", "timeout", "error"}


def migrate(runs_dir: Path, dry_run: bool) -> dict[str, int]:
    counts = {"migrated": 0, "skipped_active": 0, "unchanged": 0, "unreadable": 0}
    for results in sorted(runs_dir.glob("*/results.json")):
        try:
            data = json.loads(results.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            counts["unreadable"] += 1
            continue
        pipeline = data.get("pipeline")
        if not isinstance(pipeline, dict) or "creator_ip" not in pipeline:
            counts["unchanged"] += 1
            continue
        if pipeline.get("status") not in TERMINAL:
            counts["skipped_active"] += 1
            continue
        ip = pipeline.pop("creator_ip")
        if ip and not pipeline.get("creator_ip_hash"):
            pipeline["creator_ip_hash"] = ip_hash(ip)
        counts["migrated"] += 1
        if dry_run:
            continue
        fd, tmp = tempfile.mkstemp(dir=results.parent, prefix=".results.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.chmod(tmp, results.stat().st_mode & 0o777)
        os.replace(tmp, results)
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs-dir", default=os.environ.get("BAT3_RUNS_DIR", "/app/runs"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    print(json.dumps(migrate(Path(args.runs_dir), args.dry_run)))


if __name__ == "__main__":
    main()
