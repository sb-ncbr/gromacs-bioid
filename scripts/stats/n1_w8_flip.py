"""W8 flip accounting: per-entry verified-hit pre/post for nucleic-fix-wave-1.
pre  = /data/validation/backups/n1_w8_prerequeue_results_20261003-180146.tgz (+9990 tgz)
post = /data/validation/<eid>/results.json for batch-nucleic-fix-wave-1 entries
       whose queue status == completed (settled only; 15 stuck excluded by design).
Outputs /data/validation/n1_w8_flip.json + prints summary.
"""
import json, os, tarfile, collections
import sqlalchemy as sa

ROOT = "/data/validation"
OUT = f"{ROOT}/n1_w8_flip.json"

eng = sa.create_engine("postgresql://validation:validation-password-change-me@validation-postgres:5432/bat3_validation")
with eng.connect() as c:
    done = [r[0] for r in c.execute(sa.text(
        "SELECT entry_id FROM validation_queue WHERE batch_id='nucleic-fix-wave-1' AND status='completed'"))]
print("wave-completed:", len(done), flush=True)

# --- load pre-wave results from snapshot tars ---
pre = {}
for tgz in (f"{ROOT}/backups/n1_w8_prerequeue_results_20261003-180146.tgz",
            f"{ROOT}/backups/n1_w8_prerequeue_results_9990_20261003.tgz"):
    tf = tarfile.open(tgz)
    for m in tf.getmembers():
        if m.name.endswith("results.json"):
            eid = int(m.name.split("/")[0])
            pre[eid] = json.load(tf.extractfile(m))

def verified_ids(doc):
    """entry -> {seg: set(identifier)} of is_verified hits (+ count)."""
    out = {}
    ver = ((doc or {}).get("data") or {}).get("verification") or {}
    for seg, blk in ver.items():
        ids = set()
        for h in (blk or {}).get("verified_hits") or []:
            if h.get("is_verified"):
                ids.add(str(h.get("identifier")))
        if ids:
            out[seg] = ids
    return out

rows = []
gain_entries = lost_entries = same_entries = 0
seg_gain = seg_lost = 0
for e in done:
    a = verified_ids(pre.get(e))
    b = None
    try:
        b = verified_ids(json.load(open(f"{ROOT}/{e}/results.json")))
    except Exception as ex:
        rows.append({"eid": e, "err": str(ex)})
        continue
    segs = set(a) | set(b)
    e_gain = e_lost = False
    for s in segs:
        g = (b.get(s) or set()) - (a.get(s) or set())
        l = (a.get(s) or set()) - (b.get(s) or set())
        seg_gain += 1 if g else 0
        seg_lost += 1 if l else 0
        e_gain |= bool(g)
        e_lost |= bool(l)
    gain_entries += e_gain
    lost_entries += e_lost
    same_entries += (not e_gain and not e_lost)
    if e_gain or e_lost:
        rows.append({"eid": e,
                     "gained": {s: sorted((b.get(s) or set()) - (a.get(s) or set())) for s in segs if (b.get(s) or set()) - (a.get(s) or set())},
                     "lost": {s: sorted((a.get(s) or set()) - (b.get(s) or set())) for s in segs if (a.get(s) or set()) - (b.get(s) or set())}})

summ = {"completed_compared": len(done),
        "entries_with_seg_gains": gain_entries,
        "entries_with_seg_losses": lost_entries,
        "entries_unchanged": same_entries,
        "segments_gaining_hits": seg_gain,
        "segments_losing_hits": seg_lost,
        "errors": sum(1 for r in rows if r.get("err"))}
json.dump({"summary": summ, "rows": rows}, open(OUT, "w"), indent=1)
print(json.dumps(summ, indent=1))
