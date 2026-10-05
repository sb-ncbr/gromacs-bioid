#!/usr/bin/env python3
"""Force re-run of identify/verify/export stages for entries: flips
tasks.<stage>.status to 'failed' so executor resume re-executes only these.
Upstream stages (loading, signatures...) stay 'success' -> skipped on resume."""
import json, os, sys

STAGES = ("identify_molecules", "verify_results", "export_results")

def main(path):
    for eid in [int(x) for x in open(path).read().split()]:
        f = f'/data/validation/{eid}/results.json'
        try:
            d = json.load(open(f))
        except Exception:
            continue
        tasks = d.get('tasks') or {}
        flipped = []
        for st in STAGES:
            if st in tasks and tasks[st].get('status') in ('success', 'skipped'):
                tasks[st]['status'] = 'failed'
                flipped.append(st)
        if flipped:
            tmp = f + '.tmp'
            with open(tmp, 'w') as fh:
                json.dump(d, fh)
            os.replace(tmp, f)
        print(eid, 'flipped:', ','.join(flipped) or 'none')

if __name__ == '__main__':
    main(sys.argv[1])
