#!/usr/bin/env python3
"""N1 leftover (D4): post-W4 mis-flag segment recount over the frozen frame.

Lineage: n1_nucleic_audit found "21 nucleic-frame molecules carry protein
signatures" (universe_facade frame-flag minority class, 1.2% of frame; n1
audit supporting_facts). W4 reworked NA segmentation/strand selection;
this recount re-applies the SAME frame conditions (entry range 1..14623;
load_simulation+analyze_universe success gate; data.universe.segments
properties.is_nucleic) and counts nucleic-prop segments whose generated
map contains protein-family generator keys.

PROTEIN_FAMILY = pdb_protein, pdb_not_sanitized_protein,
pdb_backbone_protein, pdb_backbone_not_sanitized_protein,
fasta_map_protein, fasta_resname_protein (canonical map: residue_sequence_protein).

Read-only across NFS. Runs in-pod (Pool). Output: /tmp/misflag_recount.json
Usage: python3 n1_misflag_recount_postw4.py [lo hi] (default 1 14623)
"""
import collections
import json
import os
import sys
from multiprocessing import Pool

ROOT = "/data/validation"
OUT = os.environ.get("MISFLAG_OUT", "/tmp/misflag_recount.json")
PROTEIN_FAMILY = {
    "pdb_protein", "pdb_not_sanitized_protein",
    "pdb_backbone_protein", "pdb_backbone_not_sanitized_protein",
    "fasta_map_protein", "fasta_resname_protein",
}
NUCLEIC_FAMILY = {
    "pdb_nucleic", "pdb_not_sanitized_nucleic",
    "pdb_backbone_nucleic", "pdb_backbone_not_sanitized_nucleic",
    "fasta_map_nucleic", "fasta_resname_nucleic", "mmcif",
}


def scan_one(eid):
    p = os.path.join(ROOT, str(eid), "results.json")
    try:
        with open(p) as fh:
            d = json.load(fh)
    except Exception:
        return {"excluded": "no_results_or_unparseable"}
    tasks = d.get("tasks") or {}
    if (tasks.get("load_smoke") or tasks.get("load_simulation") or {}).get("status") != "success":
        return {"excluded": "load_not_success"}
    if (tasks.get("analyze_universe") or {}).get("status") != "success":
        return {"excluded": "analyze_not_success"}
    data = d.get("data") or {}
    sigmap = data.get("signatures") or {}
    usegs = ((data.get("universe") or {}).get("segments")) or {}
    rows = []
    for s, blob in sigmap.items():
        gen = (blob or {}).get("generated") or {}
        if not gen:
            continue
        props = (usegs.get(s) or {}).get("properties") or {}
        rows.append({
            "eid": eid, "seg": s,
            "is_nucleic": bool(props.get("is_nucleic")),
            "protein_keys": sorted(PROTEIN_FAMILY & set(gen)),
            "nucleic_keys": sorted(NUCLEIC_FAMILY & set(gen)),
        })
    return {"rows": rows} if rows else {"excluded": "no_molecule_units"}


def main():
    lo, hi = (int(x) for x in (sys.argv[1:3] or ["1", "14623"]))
    nucleic_total = 0
    misflagged = []
    na_with_na_only = 0
    frame_entries = 0
    excluded = collections.Counter()
    with Pool(6) as pool:
        for i, res in enumerate(pool.imap_unordered(scan_one, range(lo, hi + 1), chunksize=16), 1):
            if "excluded" in res:
                excluded[res["excluded"]] += 1
                continue
            frame_entries += 1
            for row in res["rows"]:
                if not row["is_nucleic"]:
                    continue
                nucleic_total += 1
                if row["protein_keys"]:
                    misflagged.append(row)
                elif row["nucleic_keys"]:
                    na_with_na_only += 1
            if i % 1500 == 0:
                print(f"[{lo}-{hi}] {i}: nucleic={nucleic_total} misflag={len(misflagged)}", flush=True)
    out = {
        "frame": {"range": [lo, hi], "entries_in_frame": frame_entries,
                  "excluded": dict(excluded)},
        "nucleic_segments": nucleic_total,
        "misflagged_nucleic_with_protein_sigs": len(misflagged),
        "misflag_pct_of_nucleic_frame": round(100.0 * len(misflagged) / max(nucleic_total, 1), 2),
        "misflag_rows": misflagged[:200],
        "pre_w4_count_for_comparison": 21,
        "pre_w4_pct_of_nucleic_frame": 1.2,
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
    print("DONE", json.dumps({k: v for k, v in out.items() if k != "misflag_rows"}, indent=None))


if __name__ == "__main__":
    main()
