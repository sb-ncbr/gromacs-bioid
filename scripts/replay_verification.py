"""Offline verification replay: refresh ONLY the verification block of stored
results using the CURRENT pipeline code (structure-anchored reranking).

Scope/discipline:
  - Results' own signatures + identifiers are read (never rewritten).
  - VerificationManager.verify_all() computes new verification per entry.
  - Results file atomically replaced only when output actually differs.
  - --dry-run: report what would change, write nothing.

Usage:
  replay_verification.py [--dry-run] [--since TS] [--sample N] [--entry ID]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import time

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager
from src_new.verification.manager import VerificationManager

ROOT = "/data/validation"


def _new_verification_for(payload: dict) -> dict:
    payload = json.loads(json.dumps(payload))
    rm = ResultsManager.__new__(ResultsManager)
    rm._payload = payload
    rm._save = lambda: None
    per = VerificationManager(RunConfig()).verify_all(rm)
    from src_new.signatures.skeletize import parse_signature  # noqa: F401
    out = {}
    for seg, hits in per.items():
        out[seg] = {"verified_hits": [dataclasses.asdict(h) for h in hits]}
    return out


def _catalog(root: str, since: float):
    out = []
    for d in os.scandir(root):
        if not d.is_dir() or not d.name.isdigit():
            continue
        p = os.path.join(d.path, "results.json")
        if os.path.exists(p) and os.path.getmtime(p) >= since:
            out.append(int(d.name))
    out.sort()
    return out


def _process_one(eid):
    path = os.path.join(ROOT, str(eid), "results.json")
    try:
        doc = json.load(open(path))
    except Exception:
        return None
    old_ver = (doc.get("data") or {}).get("verification") or {}
    try:
        new_ver = _new_verification_for(doc)
    except Exception as exc:
        return ("err", eid, exc)
    return (eid, doc, old_ver, new_ver)


def run(entries, dry_run: bool, threads: int = 8):
    changed = verified_new = verified_drop = 0
    examples = []
    from concurrent.futures import ThreadPoolExecutor, as_completed
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = {ex.submit(_process_one, eid): eid for eid in entries}
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if done % 5 == 0:
                print(f"[{done}/{len(entries)}] {time.time()-t0:.0f}s", flush=True)
            if r is None:
                continue
            if r and r[0] == "err":
                print(f"  {r[1]}: replay error {type(r[2]).__name__}", flush=True)
                continue
            eid, doc, old_ver, new_ver = r
            if new_ver != old_ver:
                changed += 1
                diff = 0
                for seg in set(old_ver) | set(new_ver):
                    o = set((h.get("identifier"), h.get("ident_type"),
                             h.get("is_verified"), h.get("skeleton_sim"))
                            for h in ((old_ver.get(seg) or {}).get("verified_hits") or []))
                    n = set((h.get("identifier"), h.get("ident_type"),
                             h.get("is_verified"), h.get("skeleton_sim"))
                            for h in ((new_ver.get(seg) or {}).get("verified_hits") or []))
                    diff += len(o ^ n)
                new_cnt = sum(1 for s in new_ver.values() for h in (s.get("verified_hits") or []) if h.get("is_verified"))
                old_cnt = sum(1 for s in old_ver.values() for h in (s.get("verified_hits") or []) if h.get("is_verified"))
                verified_new += max(0, new_cnt - old_cnt)
                verified_drop += max(0, old_cnt - new_cnt)
                if len(examples) < 10 and diff:
                    examples.append((eid, old_cnt, new_cnt, diff))
                if not dry_run:
                    data = dict(doc)
                    data.setdefault("data", {})["verification"] = new_ver
                    path = os.path.join(ROOT, str(eid), "results.json")
                    tmp = path + ".tmp"
                    with open(tmp, "w") as fh:
                        json.dump(data, fh)
                    os.replace(tmp, path)
                else:
                    pass
        if (len(examples) or len(entries) < 20) and False:
            pass
    print(f"processed={len(entries)} changed={changed} newVerified+={verified_new} verifiedDropped-={verified_drop} dry={dry_run}")
    for t in examples:
        print("   ", t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry", type=int, default=0)
    ap.add_argument("--since", type=float, default=0.0)
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max", type=int, default=0, dest="max_entries")
    ap.add_argument("--gt-inchikey", action="store_true",
                    help="Restrict to entries carrying inchikey ground truth (chemistry scope - skip protein-only)")
    ap.add_argument("--entries-file", type=str, default="",
                    help="File with entry ids (one per line) to replay (overrides other scopes)")
    ap.add_argument("--threads", type=int, default=8,
                    help="Concurrent verification threads (default 8; lower to avoid pod OOM)")
    a = ap.parse_args()
    if a.entries_file:
        with open(a.entries_file) as fh:
            entries = [int(x) for x in fh if x.strip()]
    elif a.entry:
        entries = [a.entry]
    else:
        entries = _catalog(ROOT, a.since)
        if a.gt_inchikey:
            import psycopg2
            DATABASE_URL = os.environ.get(
                "VALIDATION_DB_URL",
                "postgresql+psycopg://validation:bat3_validation@validation-postgres:5432/bat3_validation",
            )
            try:
                import campaign_stats as cs
                DATABASE_URL = cs.DATABASE_URL
            except Exception:
                pass
            url = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
            con = psycopg2.connect(url)
            cur = con.cursor()
            cur.execute("SELECT DISTINCT entry_id FROM ground_truth_signatures WHERE signature_type='inchikey'")
            ids = {int(r[0]) for r in cur.fetchall()}
            before = len(entries)
            entries = [e for e in entries if e in ids]
            print(f"scoped to inchikey-GT entries: {len(entries)}/{before}", flush=True)
        if a.sample:
            entries = entries[:: max(1, len(entries) // a.sample)][:a.sample]
        if a.max_entries:
            entries = entries[:a.max_entries]
    run(entries, a.dry_run, threads=a.threads)


if __name__ == "__main__":
    main()
