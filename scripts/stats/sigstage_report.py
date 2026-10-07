#!/usr/bin/env python3
"""sigstage_report -- submission-ready report pack from S0/audit aggregates.

Reads (from --input-dir): sigstage_v1.json, audit_v1.json, campaign_stats_v13.json
Writes: {out}.md + {out}.json — tables T1-T4, absolute + pct + denominator
(publication-journal quoting convention; never pct-only).

T1  per-type S0 block vs S7@1/5/10 (side-by-side)
T2  decomposition per type: selection / oracle / pipeline-loss / both-fail
T3  S0 bucket census (global + per type)
T4  headline bullets (one-liners with denominators)

Pure stdlib aggregation; offline-fixture testable; deterministic output.
"""
import argparse
import json
import os
import sys

TYPE_ORDER = ("uniprot", "pdb", "inchikey", "ion")


def _load(input_dir, name):
    path = os.path.join(input_dir, name)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"required input missing: {path}")
    with open(path) as fh:
        return json.load(fh)


def _pct(part, whole):
    return round(100.0 * part / whole, 1) if whole else None


def build_t1(sig, s7_full):
    s7 = (s7_full or {}).get("S7_similarity_hit_at_k") or {}
    out = {}
    for t in TYPE_ORDER:
        blk = (sig.get("per_type") or {}).get(t)
        if not blk:
            continue
        s7blk = s7.get(t) or {}
        out[t] = {
            "s0": {
                "annotations": blk["annotations"],
                "attempted": blk["attempted"],
                "attempted_pct": blk["attempted_pct"],
                "validated": blk["validated"],
                "pct_validated": blk["pct_validated"],
                "mean_sim_attempted": blk.get("mean_sim_attempted"),
            },
            "s7": {f"pct_validated@{k}": s7blk.get(f"pct_validated@{k}")
                   for k in (1, 5, 10)},
            "s7_annotations": s7blk.get("annotations"),
        }
    return out


def build_t2(audit):
    out = {}
    for t in TYPE_ORDER:
        blk = (audit.get("types") or {}).get(t)
        if not blk:
            continue
        c1 = blk.get("crosstab@1") or {}
        c10 = blk.get("crosstab@10") or {}
        att = blk.get("s7_attempted") or 0
        out[t] = {
            "annotations": blk["annotations"],
            "s7_attempted": att,
            "selection": {
                "zero_hit_annotations": blk.get("zero_hit_entries_annotations"),
                "s0_pct_on_zero_hit": blk.get("s0_validated_pct_on_zero_hit"),
            },
            "oracle@1": {"n": c1.get("s0_0_s7_1", 0), "pct_of_att": _pct(c1.get("s0_0_s7_1", 0), att)},
            "pipeline_loss@1": {"n": c1.get("s0_1_s7_0", 0), "pct_of_att": _pct(c1.get("s0_1_s7_0", 0), att)},
            "pipeline_loss@10": {"n": c10.get("s0_1_s7_0", 0), "pct_of_att": _pct(c10.get("s0_1_s7_0", 0), att)},
            "oracle@10": {"n": c10.get("s0_0_s7_1", 0), "pct_of_att": _pct(c10.get("s0_0_s7_1", 0), att)},
            "both_fail@10": {"n": c10.get("s0_0_s7_0", 0), "pct_of_att": _pct(c10.get("s0_0_s7_0", 0), att)},
            "s0_pct": blk.get("s0_pct"),
            "s0_pct_on_s7_subset": blk.get("s0_validated_pct_on_s7_subset"),
            "s7_pct@1": blk.get("s7_validated@1_pct"),
            "s7_pct@10": blk.get("s7_validated@10_pct"),
        }
    return out


def build_t3(sig):
    per_type = {}
    for t in TYPE_ORDER:
        blk = (sig.get("per_type") or {}).get(t)
        if not blk:
            continue
        buckets = blk.get("buckets") or {}
        total = sum(buckets.values())
        per_type[t] = {b: {"n": n, "pct": _pct(n, total)}
                       for b, n in sorted(buckets.items())}
    gb = sig.get("buckets") or {}
    gtotal = sum(gb.values())
    return {"global": {b: {"n": n, "pct": _pct(n, gtotal)} for b, n in sorted(gb.items())},
            "per_type": per_type}


def build_t4(t1, t2):
    bullets = []
    if "inchikey" in t2:
        d = t2["inchikey"]
        bullets.append(
            f"Chemistry reranking pain: {d['pipeline_loss@1']['n']} organic "
            f"annotations ({d['pipeline_loss@1']['pct_of_att']}% of "
            f"{d['s7_attempted']} attempted) are input-correct (S0-validated) "
            f"but lost at verified rank 1; {d['pipeline_loss@10']['n']} remain "
            f"lost @10.")
    if "uniprot" in t2:
        d = t2["uniprot"]
        bullets.append(
            f"UniProt S0-vs-S7 gap decomposition: S0 {d['s0_pct']}% overall; "
            f"{d['s0_pct_on_s7_subset']}% on S7 subset (selection: "
            f"{d['selection']['zero_hit_annotations']} zero-hit annotations); "
            f"oracle {d['oracle@1']['n']} rows ({d['oracle@1']['pct_of_att']}% "
            f"of attempted) recovered by database reference; pipeline loss "
            f"@10 {d['pipeline_loss@10']['n']}.")
    if "ion" in t2:
        d = t2["ion"]
        bullets.append(
            f"Ion channel: S0 {d['s0_pct']}% (zero-hit-subset resilience "
            f"{d['selection']['s0_pct_on_zero_hit']}%).")
    return bullets


def build_report(sig, audit, s7_full):
    t1 = build_t1(sig, s7_full)
    t2 = build_t2(audit)
    t3 = build_t3(sig)
    t4 = build_t4(t1, t2)
    entries = sig.get("entries") or {}
    return {"generated_by": "sigstage_report.py v1",
            "entries": entries, "t1": t1, "t2": t2, "t3": t3, "t4": t4}


def _t1_md(t1):
    lines = ["| type | S0 ann | S0 attempted | S0 validated | mean sim | "
             "S7@1 | S7@5 | S7@10 |",
             "|---|---|---|---|---|---|---|---|"]
    for t in TYPE_ORDER:
        if t not in t1:
            continue
        s0, s7 = t1[t]["s0"], t1[t]["s7"]
        lines.append(
            f"| {t} | {s0['annotations']} | {s0['attempted']} "
            f"({s0['attempted_pct']}%) | {s0['validated']} "
            f"({s0['pct_validated']}%) | {s0['mean_sim_attempted']} | "
            f"{s7['pct_validated@1']} | {s7['pct_validated@5']} | "
            f"{s7['pct_validated@10']} |")
    return lines


def _t2_md(t2):
    lines = ["| type | attempted | selection zero-hit | oracle@1 | "
             "pipeline@1 | pipeline@10 | both-fail@10 |",
             "|---|---|---|---|---|---|---|"]
    for t in TYPE_ORDER:
        if t not in t2:
            continue
        d = t2[t]
        lines.append(
            f"| {t} | {d['s7_attempted']} | "
            f"{d['selection']['zero_hit_annotations']} "
            f"(S0 {d['selection']['s0_pct_on_zero_hit']}%) | "
            f"{d['oracle@1']['n']} ({d['oracle@1']['pct_of_att']}%) | "
            f"{d['pipeline_loss@1']['n']} ({d['pipeline_loss@1']['pct_of_att']}%) | "
            f"{d['pipeline_loss@10']['n']} ({d['pipeline_loss@10']['pct_of_att']}%) | "
            f"{d['both_fail@10']['n']} ({d['both_fail@10']['pct_of_att']}%) |")
    return lines


def _t3_md(t3):
    lines = ["| bucket | n | pct |", "|---|---|---|"]
    for b, d in t3["global"].items():
        lines.append(f"| {b} | {d['n']} | {d['pct']}% |")
    return lines


def render_md(rep):
    lines = ["# S0 signature-stage validation - report pack", "",
             f"entries: {rep['entries'].get('seen')} with GT rows; any-validated "
             f"{rep['entries'].get('any_validated')} "
             f"({rep['entries'].get('any_validated_pct')}%)", "",
             "## T1 S0 vs S7 (per type)", ""]
    lines += _t1_md(rep["t1"])
    lines += ["", "## T2 decomposition (S0 x S7, per type)", ""]
    lines += _t2_md(rep["t2"])
    lines += ["", "## T3 S0 bucket census (global)", ""]
    lines += _t3_md(rep["t3"])
    lines += ["", "## T4 headline bullets", ""]
    lines += [f"- {b}" for b in rep["t4"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input-dir", default=os.path.join(
        os.environ.get("VALIDATION_DATA_ROOT", "/data/validation"),
        "sigstage", "report_inputs"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    out = args.out or os.path.join(args.input_dir, "sigstage_report_v1")

    sig = _load(args.input_dir, "sigstage_v1.json")
    audit = _load(args.input_dir, "audit_v1.json")
    s7 = _load(args.input_dir, "campaign_stats_v13.json")
    rep = build_report(sig, audit, s7.get("full") or {})
    with open(out + ".json", "w") as fh:
        json.dump(rep, fh, indent=1, sort_keys=True)
    with open(out + ".md", "w") as fh:
        fh.write(render_md(rep))
    print(f"wrote {out}.json / {out}.md", file=sys.stderr)


if __name__ == "__main__":
    main()
