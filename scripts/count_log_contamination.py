#!/usr/bin/env python3
"""Count cross-run log contamination for a set of concurrently-run dirs.

W3 A4 (BH-007) log-isolation evidence: after N concurrent runs on ONE
worker, each run's results.log / results.json must contain only its own
run's lines. The four contamination counts, all of which must be 0:

  1. celery_framework_lines — celery framework logger lines in
     results.log ([celery., celery@host, Task ... received/succeeded)
  2. duplicate_lines        — CONSECUTIVE identical full lines in
     results.log (the b9/b10 double-handler signature: the same
     record written twice carries the same timestamp; legitimate
     per-segment business repeats are seconds apart and do not count)
  3. foreign_run_ids       — occurrences of any OTHER run's id in this
     run's results.log
  4. foreign_events         — occurrences of any OTHER run's id in this
     run's results.json (events or data)

Usage: count_log_contamination.py <run_dir> <run_dir> [...]
Exit status: 0 if all counts are 0, 1 otherwise.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CELERY_RE = re.compile(r"\[celery\.|celery@|Task .*(received|succeeded)")

def counts_for(run_dir: Path, all_ids: list[str]) -> dict[str, int]:
    run_id = run_dir.name
    foreign = [i for i in all_ids if i != run_id]

    log = run_dir / "results.log"
    celery_lines = dup = foreign_log = 0
    if log.exists():
        lines = log.read_text(errors="replace").splitlines()
        prev = None
        for line in lines:
            if CELERY_RE.search(line):
                celery_lines += 1
            if line.strip() and line == prev:
                dup += 1
            prev = line
            for fid in foreign:
                if fid in line:
                    foreign_log += 1

    foreign_json = 0
    rj = run_dir / "results.json"
    if rj.exists():
        text = rj.read_text(errors="replace")
        for fid in foreign:
            foreign_json += text.count(fid)

    return {"celery_framework_lines": celery_lines,
            "duplicate_lines": dup,
            "foreign_run_ids": foreign_log,
            "foreign_events": foreign_json}


def main() -> int:
    dirs = [Path(a) for a in sys.argv[1:]]
    if not dirs:
        print(__doc__)
        return 2
    ids = [d.name for d in dirs]
    print("run_id\tcelery_framework_lines\tduplicate_lines\t"
          "foreign_run_ids\tforeign_events")
    total = 0
    for d in dirs:
        c = counts_for(d, ids)
        row = [d.name] + [str(c[k]) for k in
                          ("celery_framework_lines", "duplicate_lines",
                           "foreign_run_ids", "foreign_events")]
        print("\t".join(row))
        total += sum(c.values())
    print(f"TOTAL\t{total}")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
