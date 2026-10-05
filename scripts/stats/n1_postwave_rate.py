"""N1 post-wave nucleic hit-rate recompute (audit-metric verbatim):
rescan ONLY the 797 wave entries live, splice into n1_nucleic_rows.jsonl rows,
recompute hit/verified rates total + length strata. Writes n1_nucleic_rows_postwave.jsonl + n1_postwave_rate.json.
"""
import json, collections
import importlib.util

ROOT = "/data/validation"
spec = importlib.util.spec_from_file_location("dump", f"{ROOT}/n1_nucleic_dump.py")
dump = importlib.util.module_from_spec(spec)
# module body runs argparse/main on import? guard: read source and exec only defs
src = open(f"{ROOT}/n1_nucleic_dump.py").read()
ns = {}
head = src.split("def main")[0]
exec(compile(head, "dump.py", "exec"), ns)
scan_one = ns["scan_one"]

wave = [int(x) for x in open(f"{ROOT}/n1_requeue_entries.txt") if x.strip()]
old_rows = [json.loads(l) for l in open(f"{ROOT}/n1_nucleic_rows.jsonl")]
old_idx = {(r["eid"], r["seg"]): r for r in old_rows}

new_rows = []
errs = 0
skipped_excl = collections.Counter()
for e in wave:
    try:
        rows = scan_one(e)
    except Exception:
        errs += 1
        continue
    if isinstance(rows, dict):
        if "excluded" in rows:
            skipped_excl[rows["excluded"]] += 1
            continue
        rows = rows.get("mol_rows") or []
    if rows:
        new_rows.extend(rows)

new_idx = {(r["eid"], r["seg"]): r for r in new_rows}
merged = dict(old_idx)
added = 0
for k, r in new_idx.items():
    if k not in merged:
        added += 1
    merged[k] = r

def rate(rows):
    n = len(rows)
    hit = sum(1 for r in rows if r["hit"])
    ver = sum(1 for r in rows if r["verified"])
    return {"n": n, "hit": hit, "hit_pct": round(100 * hit / n, 2),
            "verified": ver, "verified_pct": round(100 * ver / n, 2)}

def strata(rows):
    out = collections.defaultdict(lambda: [0, 0, 0])
    for r in rows:
        rc = r.get("residue_count") or 0
        lb = "<=12" if rc <= 12 else ("13-30" if rc <= 30 else (">30" if rc <= 100 else "big"))
        out[lb][0] += 1
        out[lb][1] += r["hit"]
        out[lb][2] += r["verified"]
    return {k: {"n": v[0], "hit": v[1], "verified": v[2],
                "hit_pct": round(100 * v[1] / v[0], 1) if v[0] else None} for k, v in sorted(out.items())}

all_now = list(merged.values())
pre = rate(old_rows)
post = rate(all_now)
out = {"pre": pre, "post": post,
       "pre_strata": strata(old_rows), "post_strata": strata(all_now),
       "wave_entries_rescanned": len(wave), "errors": errs, "skipped_excluded": dict(skipped_excl),
       "rows_old": len(old_rows), "rows_now": len(all_now), "rows_added_by_wave": added,
       "note": "metric verbatim from n1_nucleic_dump.scan_one: hit = any identifier-resolver hit list non-empty on the nucleic seg; verified = >=1 is_verified hit in verification block"}
json.dump(out, open(f"{ROOT}/n1_postwave_rate.json", "w"), indent=1)
print(json.dumps({"pre": pre, "post": post, "added_rows": added, "errs": errs}, indent=1))
