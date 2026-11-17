#!/usr/bin/env python3
"""W5 pre-measure, v14 frame: for short hitless nucleic sequences in the v14
nucleic anatomy, measure how many have a 100%-pident FULL-LENGTH match in the
campaign pdbnt db (and of those, how many are also both-directional exact:
subject_len == query_len).

Direct port of n1_short_premeasure.py from the v11 frame to the v14 anatomy
export; read-only, blastn-short exactly as the resolver invokes it.

Input:  /data/validation/nucleic_anatomy_v14.jsonl  (phase-1 export)
Output: /data/validation/n1_short_premeasure_v14.json
"""
import collections
import json
import os
import subprocess
import sys
import tempfile
from multiprocessing import Pool

ROWS = "/data/validation/nucleic_anatomy_v14.jsonl"
# DB path is pod-dependent: worker mounts /app/databases; validation-api uses
# the shared NFS copy at /data/validation/blastdb (no db mount there).
DB = os.environ.get("BLASTNT_DB", "/data/validation/blastdb/pdbnt/pdbnt")
OUT = "/data/validation/n1_short_premeasure_v14.json"
OUT_ROWS = "/data/validation/n1_short_premeasure_v14_rows.jsonl"
MAX_LEN = 25


def load_cases():
    cases = []
    for line in open(ROWS):
        r = json.loads(line)
        if r.get("id_distinct_hits"):
            continue
        seq = r.get("fasta_seq") or ""
        n = r.get("fasta_len") or 0
        if seq and n and n == len(seq) and n <= MAX_LEN:
            cases.append((str(r["entry_id"]), r["segment"], seq))
    return cases


def probe(case):
    eid, seg, seq = case
    with tempfile.NamedTemporaryFile("w", suffix=".fa", delete=False) as fh:
        fh.write(f">q\n{seq}\n")
        q = fh.name
    try:
        p = subprocess.run(
            ["blastn", "-task", "blastn-short", "-db", DB, "-query", q,
             "-outfmt", "15", "-max_target_seqs", "500", "-num_threads", "1"],
            capture_output=True, timeout=300)
        data = json.loads(p.stdout.decode() or "{}")
        out = {"eid": eid, "seg": seg, "q_len": len(seq), "n_hits": 0,
               "perfect_full": 0, "perfect_both_dir": 0,
               "best_evalue": None, "best_pident": 0.0, "best_cov": 0.0}
        bo = data.get("BlastOutput2")
        if isinstance(bo, list):
            bo = bo[0] if bo else {}
        hits = (bo.get("report", {}).get("results", {}).get("search", {}).get("hits")) or []
        out["n_hits"] = len(hits)
        for hit in hits:
            slen = hit.get("len")
            for hsp in (hit.get("hsps") or []):
                ident = hsp.get("identity") or 0
                alen = hsp.get("align_len") or 0
                gaps = hsp.get("gaps") or 0
                L = len(seq)
                cov = alen / L if L else 0.0
                pident = 100.0 * ident / alen if alen else 0.0
                ev = hsp.get("evalue")
                out["best_cov"] = max(out["best_cov"], cov)
                out["best_pident"] = max(out["best_pident"], pident)
                if ev is not None and (out["best_evalue"] is None or ev < out["best_evalue"]):
                    out["best_evalue"] = ev
                if gaps == 0 and ident == alen and alen == L:
                    out["perfect_full"] = 1
                    if slen == L:
                        out["perfect_both_dir"] = 1
        return out
    except Exception as e:
        return {"eid": eid, "seg": seg, "q_len": len(seq), "error": str(e)}
    finally:
        os.unlink(q)


def main():
    cases = load_cases()
    print(f"{len(cases)} short hitless nucleic cases (<= {MAX_LEN} nt, full seq) -> {OUT}", flush=True)
    rows = []
    with Pool(8) as pool:
        for i, out in enumerate(pool.imap_unordered(probe, cases, chunksize=16), 1):
            rows.append(out)
            if i % 200 == 0:
                print(f"  {i}/{len(cases)}", flush=True)
    ok = [r for r in rows if "error" not in r]
    perfect = [r for r in ok if r.get("perfect_full")]
    both = [r for r in ok if r.get("perfect_both_dir")]
    # full-length near-identical (gate-refused by evalue physics but human-visible)
    near_miss = [r for r in ok if not r.get("perfect_full")
                 and r.get("best_pident", 0) >= 90.0 and r.get("best_cov", 0) >= 0.99]
    any_hit = [r for r in ok if r.get("best_cov", 0) > 0 or r.get("best_pident", 0) > 0]
    with open(OUT_ROWS, "w") as fh:
        for r in ok:
            fh.write(json.dumps(r) + "\n")
    by_len = collections.defaultdict(lambda: {"n": 0, "with_perfect_full": 0, "with_perfect_both_dir": 0})
    for r in ok:
        b = by_len[r["q_len"]]
        b["n"] += 1
        b["with_perfect_full"] += r["perfect_full"]
        b["with_perfect_both_dir"] += r["perfect_both_dir"]
    summary = {
        "db": DB,
        "task": "blastn-short",
        "frame": "v14 anatomy: hitless nucleic segments with full fasta <= 25nt",
        "cases": len(cases),
        "errors": len(rows) - len(ok),
        "aggregate": {"molecules": len(ok),
                      "with_perfect_full": len(perfect),
                      "with_perfect_both_dir": len(both),
                      "near_miss_p90_cov99": len(near_miss),
                      "with_any_alignment": len(any_hit)},
        "per_query_len": {str(k): v for k, v in sorted(by_len.items())},
        "samples_both_dir": [r for r in both if True][:40],
    }
    with open(OUT, "w") as fh:
        json.dump(summary, fh, indent=1)
    print("DONE ->", OUT, json.dumps(summary["aggregate"]), flush=True)


if __name__ == "__main__":
    sys.exit(main())
