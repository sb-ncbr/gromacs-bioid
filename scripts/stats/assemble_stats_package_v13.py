"""Assemble the full statistics package for figure-building (v13 / audit-heal era).
Reads official campaign_stats versions + audit + coverability probe baselines,
emits /data/validation/stats_package_v13.json and .md.
Lineage: copied from assemble_stats_package_v12.py (frozen v12 official
package untouched). Includes v12 + new v13 (W10 OQ-9 full-family heal +
OQ-11 chembl revival + F-24 code default-off) views.
All numbers: absolute + percentage + denominator, never pct-only."""
import json, os, collections, datetime

D = "/data/validation"
def load(p):
    try:
        with open(p) as fh: return json.load(fh)
    except Exception: return None

VERS = ["v8", "v9", "v10", "v11", "v12", "v13"]
stats = {v: load(f"{D}/campaign_stats_{v}.json") for v in VERS}
audit = load(f"{D}/audit_chem_ion_postf14.json")
probe_now = load(f"{D}/coverability_probe.json")

def pct(part, whole):
    return round(100.0*part/whole, 2) if whole else None

def channel_block(fr_full, ch):
    s7 = (fr_full or {}).get("S7_similarity_hit_at_k", {})
    c = s7.get(ch) or {}
    ann = c.get("annotations"); att = c.get("attempted")
    out = {"annotations": ann, "attempted": att,
           "attempted_pct": c.get("attempted_pct"),
           "attempted_pct_of_ann": pct(att, ann)}
    for k in (1, 5, 10):
        p = c.get(f"pct_validated@{k}")
        est = round(p * ann / 100.0) if (p is not None and ann) else None
        out[f"validated@{k}"] = {"pct_of_ann": p,
                                  "pct_of_att": pct(est, att),
                                  "abs_est_from_pct": est}
        m = c.get(f"mean_sim@{k}")
        if m is not None: out[f"mean_sim@{k}"] = m
    return out

def rows(p):
    try:
        return [json.loads(l) for l in open(p) if l.strip()]
    except Exception: return []

# ---------- 1) channel tables per version ----------
channels = {}
for ch in ("inchikey", "ion", "pdb", "uniprot"):
    channels[ch] = {v: channel_block((stats[v] or {}).get("full"), ch)
                    if stats[v] else None for v in VERS}

entry_any = {}
for v in VERS:
    s7 = ((stats[v] or {}).get("full") or {}).get("S7_similarity_hit_at_k", {}) if stats[v] else {}
    ea = s7.get("entry_any_validated@%") or {}
    entry_any[v] = ea

# ---------- 2) stage funnel (v11) ----------
v11f = (stats["v11"] or {}).get("full") or {}
stages = {}
s3 = v11f.get("S3_per_stage", {})
tot_scanned = v11f.get("gt_covered_scanned") or v11f.get("scanned_entries")
for st, blk in s3.items():
    if isinstance(blk, dict):
        stages[st] = dict(blk)
        stot = blk.get("total")
        for key, val in list(stages[st].items()):
            if isinstance(val, int) and stot:
                stages[st][key + "_pct_of_stage_total"] = pct(val, stot)
funnel = {"denominator_scanned": v11f.get("scanned_entries"),
          "denominator_gt_covered": tot_scanned,
          "not_live_skipped": v11f.get("not_live_skipped"),
          "S3_deepest_stage_reached": v11f.get("S3_deepest_stage_reached"),
          "S6_runtime_s": v11f.get("S6_runtime_s"),
          "S6_pipeline_status": v11f.get("S6_pipeline_status"),
          "S6_top_warnings": v11f.get("S6_top_warnings"),
          "S6_critical_errors_total": v11f.get("S6_critical_errors_total")}

# ---------- 3) resolvers + signatures (S4, v11) ----------
def s4_table(section):
    out = {}
    for name, val in (v11f.get(section, {}) or {}).items():
        if isinstance(val, dict):
            out[name] = dict(val)
        elif isinstance(val, int):
            out[name] = {"attempts": val,
                         "pct_of_scanned": pct(val, v11f.get("scanned_entries"))}
    return out
resolvers = s4_table("S4_resolver_attempts")
signatures = s4_table("S4_signature_attempts")
molecules = v11f.get("S4_molecules")
gate_verified = {"entries": v11f.get("S7_gate_verified_chem_entries"),
                 "hits": v11f.get("S7_gate_verified_chem_hits")}
s5 = {ch: (v11f.get("S5_exact_hit_at_k", {}).get(ch)) for ch in ("overall","pdb","uniprot","inchikey")}
s5_entries_pct = v11f.get("S5_entries_with_verified_hit_pct")

# ---------- 4) audit outcomes ----------
audit_block = None
if audit:
    oo = audit.get("organic_outcomes", {}).get("ALL", {})
    io = (audit.get("ion_outcomes") or {}).get("ALL", {})
    tot_o = sum(oo.values()) if isinstance(oo, dict) else None
    audit_block = {
        "generated_at": audit.get("generated_at"),
        "entries_parsed": audit.get("entries_parsed"),
        "organic_annotations": audit.get("organic_annotations"),
        "ion_annotations": audit.get("ion_annotations"),
        "gt_classes": audit.get("gt_classes"),
        "organic_outcomes_abs": oo,
        "organic_outcomes_pct": {k: pct(v, tot_o) for k, v in oo.items()} if isinstance(oo, dict) else None,
        "organic_outcomes_denominator": tot_o,
        "ion_outcomes_abs": io,
        "excluded_annotations": audit.get("excluded_annotations"),
        "excluded_critical": audit.get("excluded_critical"),
    }

# ---------- 5) flip accounting ----------
b10 = {(r["eid"], r["ik"]): r["bucket"] for r in rows(f"{D}/coverability_rows.jsonl.v10-baseline")}
now = {(r["eid"], r["ik"]): r["bucket"] for r in rows(f"{D}/coverability_rows.jsonl")} if os.path.exists(f"{D}/coverability_rows.jsonl") else {}
fixed = {k: b for k, b in b10.items() if k not in now}
buckets_now = collections.Counter(now.values())
b11 = {(r["eid"], r["ik"]): r["bucket"] for r in rows(f"{D}/coverability_rows.jsonl.v11-baseline")}
fixed11 = {k: b for k, b in b11.items() if k not in now}
flip = {"v10_baseline_rows": len(b10), "v11_rows": len(now),
        "fixed": len(fixed), "regressions": len([k for k in now if k not in b10]),
        "fixed_by_bucket": dict(collections.Counter(fixed.values())),
        "residual_buckets_now": dict(buckets_now),
        "v12_vs_v11": {"v11_baseline_rows": len(b11),
                       "fixed": len(fixed11),
                       "fixed_by_bucket": dict(collections.Counter(fixed11.values())),
                       "regressions": len([k for k in now if k not in b11])}}
r8 = rows(f"{D}/residual_failing_rows_v8.jsonl.taskB-baseline")
r10 = rows(f"{D}/residual_failing_rows_v8.jsonl.v10-baseline")
r11 = rows(f"{D}/residual_failing_rows_v8.jsonl.v11-baseline")
rnow = rows(f"{D}/residual_failing_rows_v8.jsonl")
flip["failing_set_sizes"] = {"taskB_v8": len(r8), "v10": len(r10), "v11": len(r11), "v12_now": len(rnow)}

frames = {v: ((stats[v] or {}).get("full", {}).get("S7_similarity_hit_at_k", {}) or {})
          for v in VERS}

pkg = {
    "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    "wave": "nucleic-fix-wave-1 (N1) -> S7 v12 ; w10-heal (OQ-9 family requeue, 4324) + OQ-11 chembl -> v13 (produced during tail-drain)",
    "channels": channels,
    "entry_any_validated": entry_any,
    "stage_funnel": funnel,
    "per_stage": stages,
    "resolver_attempts": resolvers,
    "signature_attempts": signatures,
    "molecules": molecules,
    "s5_exact_hit_at_k": s5,
    "s5_entries_with_verified_hit_pct": s5_entries_pct,
    "s7_gate_verified": gate_verified,
    "audit": audit_block,
    "flip_accounting": flip,
}
with open(f"{D}/stats_package_v13.json", "w") as fh:
    json.dump(pkg, fh, indent=1)

# ---------- markdown ----------
L = []
ap = L.append
ap(f"# BAT3 validation — full statistics package (v11, boxchem wave)")
ap(f"generated {pkg['generated_at']}\n")
ap("## 1. S7 hit@10 per channel (abs / %of-annotations / %of-attempted)")
ap("| channel | version | annotations | attempted | att% | @1 est | @5 est | @10 est | @10 %ann | @10 %att |")
ap("|---|---|---|---|---|---|---|---|---|---|")
for ch in ("inchikey", "ion", "pdb", "uniprot"):
    for v in VERS:
        b = channels[ch].get(v)
        if not b or b.get("annotations") is None:
            ap(f"| {ch} | {v} | — | | | | | | | |"); continue
        ap(f"| {ch} | {v} | {b['annotations']} | {b['attempted']} | {b['attempted_pct_of_ann']} | "
           f"{b['validated@1']['abs_est_from_pct']} ({b['validated@1']['pct_of_ann']}%) | {b['validated@5']['abs_est_from_pct']} ({b['validated@5']['pct_of_ann']}%) | "
           f"{b['validated@10']['abs_est_from_pct']} | {b['validated@10']['pct_of_ann']} | {b['validated@10']['pct_of_att']} |")
ap("")
ap("Note: campaign_stats stores percentages; @k absolutes are est = round(pct·ann/100) (±1). "
   "Exact regen counts from coverability-probe gate logs: v8 @10=5241, v10 @10=5374, v11 @10=5374 (inchikey).")
ap("\n## 2. Stage funnel (v11; denominators: scanned=%(denominator_scanned)s, gt_covered=%(denominator_gt_covered)s)" % funnel)
ap("| stage | counters (abs + pct where int) |")
ap("|---|---|")
for st, blk in stages.items():
    ap(f"| {st} | {blk} |")
ap("\n## 3. Resolver attempts (v11)")
ap("| resolver | counters |")
ap("|---|---|")
for n, b in sorted(resolvers.items(), key=lambda t: str(t[0])):
    ap(f"| {n} | {b} |")
ap("\n## 4. Signature attempts (v11)")
for n, b in sorted(signatures.items(), key=lambda t: str(t[0])):
    ap(f"| {n} | {b} |")
ap("\n## 5. S5 exact hit@k (v11)")
ap(f"```json\n{json.dumps(s5, indent=1)}\n```")
ap(f"entries_with_verified_hit: {s5_entries_pct}%\n")
ap("## 6. Audit outcomes (v11-era)")
if audit_block:
    ap(f"organic denominator: {audit_block['organic_outcomes_denominator']} | ion annotations: {audit_block['ion_annotations']}")
    ap("| outcome | abs | pct |")
    ap("|---|---|---|")
    for k, v in (audit_block.get("organic_outcomes_abs") or {}).items():
        ap(f"| {k} | {v} | {audit_block['organic_outcomes_pct'][k]} |")
ap("\n## 7. Flip accounting")
ap(f"```json\n{json.dumps(flip, indent=1)}\n```")
with open(f"{D}/stats_package_v13.md", "w") as fh:
    fh.write("\n".join(L))
print("written stats_package_v13.json/.md")
