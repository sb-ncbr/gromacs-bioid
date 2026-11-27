#!/usr/bin/env python3
"""Re-run a validation campaign arm through the BioID repository queue.

One BioID run per campaign entry, reading the entry's downloaded input in
place (campaign_input=<entry>/input, repository queue + X-Queue-Token) with
the server's default configuration. When a run ends, its results.json is
copied next to the earlier arms as /data/validation/<entry>/results-<arm>.json,
so the scoring scripts work unchanged:

    campaign_stats.py --full --sim --pattern results-g2.json

Entries: every entry that has the reference arm's results file
(--reference results-g1.json), i.e. the same denominator as that arm.
Run ids are deterministic (<arm>-<entry>), so the runner is resumable: a run
that already exists (HTTP 409) is picked up and followed, and the state file
records every entry. The repository queue retries incomplete runs itself;
a run counts as finished only in a terminal status.

Runs in-cluster (it needs the campaign data and the runs volume):
    BIOID_QUEUE_TOKEN=... python3 scripts/campaign_rerun.py --arm g2 --limit 20
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

import requests

log = logging.getLogger("campaign_rerun")

#: pipeline statuses after which the run will not change any more
TERMINAL = {"success", "failed", "cancelled", "timeout", "error"}


def campaign_entries(data_root: Path, reference: str) -> list[str]:
    """Numeric entry directories that have the reference arm's results file."""
    out = []
    for d in data_root.iterdir():
        if d.name.isdigit() and (d / reference).is_file() and (d / "input").is_dir():
            out.append(d.name)
    return sorted(out, key=int)


class State:
    """{entry: {run_id, status, ...}} persisted atomically after each change."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.entries: dict[str, dict] = json.loads(path.read_text())
        except (OSError, ValueError):
            self.entries = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".{self.path.name}.tmp")
        tmp.write_text(json.dumps(self.entries, indent=1, sort_keys=True))
        os.replace(tmp, self.path)

    def counts(self) -> dict[str, int]:
        c: dict[str, int] = {}
        for e in self.entries.values():
            c[e["status"]] = c.get(e["status"], 0) + 1
        return c


class Runner:
    def __init__(self, args):
        self.args = args
        self.api = args.api.rstrip("/")
        self.token = os.environ.get(args.token_env, "")
        self.data_root = Path(args.data_root)
        self.runs_dir = Path(args.runs_dir)
        self.state = State(Path(args.state or self.data_root / f"rerun-{args.arm}" / "state.json"))
        self.session = requests.Session()

    # -- one entry ----------------------------------------------------------
    def run_id(self, entry: str) -> str:
        return f"{self.args.arm}-{entry}"

    def submit(self, entry: str) -> str:
        """'submitted' | 'rejected' | 'busy' (retry later)."""
        rid = self.run_id(entry)
        data = {"queue": "repository", "campaign_input": f"{entry}/input",
                "run_name": f"{self.args.arm} entry {entry}",
                "retention": self.args.retention}
        if self.args.preset:
            data["preset"] = self.args.preset
        r = self.session.post(f"{self.api}/api/v1/runs", params={"run_id": rid}, data=data,
                              headers={"X-Queue-Token": self.token}, timeout=120)
        rec = self.state.entries.setdefault(entry, {"run_id": rid})
        if r.status_code in (200, 409):  # 409: submitted by an earlier pass
            rec.update(status="submitted", submitted_at=time.time())
            return "submitted"
        if r.status_code == 429:
            return "busy"
        if r.status_code in (401, 403):
            sys.exit(f"repository queue refused the token: HTTP {r.status_code} {r.text[:200]}")
        rec.update(status="rejected", detail=f"HTTP {r.status_code}: {r.text[:300]}")
        return "rejected"

    def poll(self, entry: str) -> None:
        rec = self.state.entries[entry]
        r = self.session.get(f"{self.api}/api/v1/runs/{rec['run_id']}/status", timeout=60)
        if r.status_code == 404:
            rec.update(status="lost")
            return
        r.raise_for_status()
        status = ((r.json().get("pipeline") or {}).get("status") or "").lower()
        if status in TERMINAL:
            self.collect(entry, status)

    def collect(self, entry: str, status: str) -> None:
        """Copy the run's results.json into the campaign tree (atomic)."""
        rec = self.state.entries[entry]
        src = self.runs_dir / rec["run_id"] / "results.json"
        dst = self.data_root / entry / f"results-{self.args.arm}.json"
        tmp = dst.with_name(f".{dst.name}.tmp")
        try:
            shutil.copyfile(src, tmp)
            os.replace(tmp, dst)
        except OSError as exc:
            rec.update(status="collect_failed", detail=str(exc))
            return
        rec.update(status=f"done:{status}", finished_at=time.time())

    # -- the loop -----------------------------------------------------------
    def run(self) -> None:
        a = self.args
        todo = campaign_entries(self.data_root, a.reference)
        if a.entries:
            wanted = {e.strip() for e in Path(a.entries).read_text().split() if e.strip()}
            todo = [e for e in todo if e in wanted]
        if a.limit:
            todo = todo[:a.limit]
        log.info("%d entries (reference %s), arm %s", len(todo), a.reference, a.arm)
        if a.dry_run:
            print(json.dumps({"entries": len(todo), "first": todo[:5],
                              "example_run_id": self.run_id(todo[0]) if todo else None}))
            return
        if not self.token:
            sys.exit(f"set {a.token_env} to the repository queue token")
        pending = [e for e in todo
                   if self.state.entries.get(e, {}).get("status") in (None, "busy")]
        last_report = 0.0
        while True:
            active = [e for e, r in self.state.entries.items() if r["status"] == "submitted"]
            for entry in active:
                try:
                    self.poll(entry)
                except requests.RequestException as exc:
                    log.warning("poll %s: %s", entry, exc)
            active = [e for e, r in self.state.entries.items() if r["status"] == "submitted"]
            while pending and len(active) < a.max_in_flight:
                entry = pending[0]
                try:
                    outcome = self.submit(entry)
                except requests.RequestException as exc:
                    log.warning("submit %s: %s", entry, exc)
                    break
                if outcome == "busy":
                    break
                pending.pop(0)
                if outcome == "submitted":
                    active.append(entry)
            self.state.save()
            if time.time() - last_report > a.report_s:
                log.info("pending %d, in flight %d, %s", len(pending), len(active),
                         self.state.counts())
                last_report = time.time()
            if not pending and not active:
                break
            time.sleep(a.poll_s)
        log.info("finished: %s", self.state.counts())


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arm", required=True, help="arm name, e.g. g2 (results-<arm>.json)")
    p.add_argument("--reference", default="results-g1.json",
                   help="entries = those with this results file")
    p.add_argument("--api", default=os.environ.get("BIOID_API", "http://bat3-ceitec-bat3-api:8000"))
    p.add_argument("--token-env", default="BIOID_QUEUE_TOKEN")
    p.add_argument("--data-root", default=os.environ.get("VALIDATION_DATA_ROOT", "/data/validation"))
    p.add_argument("--runs-dir", default=os.environ.get("BAT3_RUNS_DIR", "/app/runs"))
    p.add_argument("--state", help="state file (default <data-root>/rerun-<arm>/state.json)")
    p.add_argument("--preset", help="run preset (default: the server defaults)")
    p.add_argument("--retention", default="default")
    p.add_argument("--entries", help="file with entry ids to restrict to")
    p.add_argument("--limit", type=int, default=0, help="first N entries only (smoke runs)")
    p.add_argument("--max-in-flight", type=int, default=32, help="runs queued or running at once")
    p.add_argument("--poll-s", type=float, default=30.0)
    p.add_argument("--report-s", type=float, default=300.0)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    Runner(args).run()


if __name__ == "__main__":
    main()
