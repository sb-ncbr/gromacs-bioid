#!/usr/bin/env python3
"""failure_mode_audit -- mutually exclusive decomposition of every residual
failure fraction in the frozen S0/v2 numbers into audited failure modes.

Deliverable of the final S0 wave (2026-10-08): the article's "why aren't we
at 100% (and why that's still excellent)" section. Every mode carries n, pct
and explicit denominator (numbers-only rule); every per-metric mode table is
reconciled against the frozen audit_v2 types block and the sum of exclusive
modes equals the failed count per metric (self-audit pattern).

INPUTS (all frozen artifacts, read-only):
  audit_v2 shards   per-annotation joined rows (36,159)
  audit_v2.json     frozen types block = reconciliation reference
  casefiles         S0-OQ-1_nmg.jsonl (624), S0-OQ-2_unparseable.jsonl (525),
                    ghost_curation.json (ghost ledger 7,298 ids)
  campaign_stats_v14.json   comparator block (basis note, NOT hard-reconciled)

METRICS DECOMPOSED (denominators = frozen audit_v2 values):
  S7@1  per type: failed = attempted - validated@1   (gap headline 93.8%)
  S7@10 per type: failed = attempted - validated@10
  S0    per type: failed = annotations - s0_validated
  unattempted channel per type (selection story, NOT mixed into above)
  entry-level any-validated@1 (audit basis; campaign v14 = comparator)

S7@K FAIL PRECEDENCE CHAIN (first match wins; modes are mutually exclusive;
documented per metric in the output):
  1. gt_unresolved        s7_class=='unresolved' OR s0_bucket=='unresolved_gt'
                          (per-row signals from the frozen audit; the ghost
                          ledger is pair-level and NOT used for per-row
                          classification -- 76% of ghost pairs have a live
                          InChIKey side per A3, so endpoint membership
                          would over-tag healthy GTs)
  2. structure_absent     all of s7_sim@1/5/10 == 0  (no similarity with any
                          hit in the top-10 window; ions: element absent from
                          the ion channel)
  3. no_verified_hits     n_hits == 0 while attempted  (safety class; in the
                          frozen data no attempted row has n_hits==0)
  4. rerank_residual      (K=1 only) verified within a deeper window:
                           rank_loss_top5  = validated@5 true, validated@1 false
                           rank_loss_top10 = validated@10 true, @5 false
  5. weak_below_gate      0 < max(s7_sim@K) < gate for all K
  6. residual_unclassified   anything else (expected 0; investigated if >0)
  Precedence rationale: GT-side data problems (1) are infra/curation, never
  metric blame; 2-3 distinguish absence from empty entry; 4 is the
  "verification found it, ranking lost it" residual (A6 closed: zero
  impairment -- these are GT-side/ranking-depth phenomena); 5 is
  genuine similarity gap (homolog-level constructs for seq, scaffold-level
  for chem).

S0 FAIL PRECEDENCE (buckets are already mutually exclusive; chain only adds
the ghost-ledger overlay and NMG subclass refinement):
  1. gt_unresolved        s7_class=='unresolved' OR s0_bucket=='unresolved_gt'
  2. unparseable_signature  (OQ-2 cohort; perception-gap advisory tag)
  3. no_matching_generator:<nmg_class>   (OQ-1 join; A5 curation cohorts
                           flagged in the advisory channel)
  4. no_sig_data
  5. below_gate:<sim_band>    (band edges = audit sim_hist, replicated)
  6. no_s0_row              s0_bucket is null (no S0 probe row for the key)
  7. residual_unclassified

UNATTEMPTED channel (S7 selection, separate denominators):
  zero_hit_entry        n_hits == 0  (OQ-6 census: mostly clean-but-empty)
  attempt_gate_unmet    n_hits > 0 but no family-window candidate

ADVISORY TAGS (parallel channel -- advisory, NOT metric blame, never mixed
into denominators): A5 curation cohorts (OQ-1 struct/lipid + chem-seg),
OQ-2 perception-gap cohort.  Ghost-ledger statistics (pair-level) are
reported in the report header as curation context, NOT as a per-row tag.

EXIT CODES: 0 ok · 2 missing input · 3 reconciliation failure (hard)
"""
import argparse
import collections
import glob
import json
import os
import sys
from datetime import datetime, timezone

DATA = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")

GATES = {"inchikey": 0.7, "ion": 0.7, "pdb": 0.9, "uniprot": 0.9}
KSET = (1, 5, 10)
TYPE_ORDER = ("inchikey", "ion", "pdb", "uniprot")

S7_MODES = [
    "gt_unresolved",
    "structure_absent",
    "no_verified_hits",
    "rank_loss_top5",
    "rank_loss_top10",
    "weak_below_gate",
    "residual_unclassified",
]
S7_MODES_AT10 = [
    "gt_unresolved",
    "structure_absent",
    "no_verified_hits",
    "weak_below_gate",
    "residual_unclassified",
]
S0_MODE_ORDER = [
    "gt_unresolved",
    "unparseable_signature",
    "no_matching_generator",
    "no_sig_data",
    "below_gate",
    "no_s0_row",
    "residual_unclassified",
]
UNATTEMPTED_MODES = ["zero_hit_entry", "attempt_gate_unmet"]

# audit sim_hist band edges (replicated from sigstage_audit.sim_hist)
_HIST_BINS = (0.0, 0.3, 0.6, 0.8, 0.9, 0.95, 0.999, 1.001)
_HIST_LABELS = ["0-.3", ".3-.6", ".6-.8", ".8-.9", ".9-.95", ".95-1", "1.0"]


def norm_value(gt_type, value):
    """Replicate sigstage_audit.norm_value so casefile joins line up with
    audit row keys (uppercased; pdb truncated to 4 chars)."""
    v = (value or "").strip().upper()
    return v[:4] if gt_type == "pdb" else v


def row_key(r):
    return (r["entry_id"], r["gt_type"], norm_value(r["gt_type"], r["gt_value"]))


def row_type(r):
    """Frozen audit_v2 type rule (reproduces the types block exactly)."""
    return "ion" if (r["gt_type"] == "inchikey" and r.get("s7_class") == "ion") \
        else r["gt_type"]


def sim_band(v):
    if v is None:
        return None
    for i, (lo, hi) in enumerate(zip(_HIST_BINS, _HIST_BINS[1:])):
        if lo <= v < hi:
            return _HIST_LABELS[i]
    return None


def max_sim(r, kset=KSET):
    vals = [r.get("s7_sim@%d" % k) for k in kset]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else 0.0


# ------------------------------------------------------------------ loaders

def load_rows(shards_dir):
    rows = []
    for fp in sorted(glob.glob(os.path.join(shards_dir, "shard_*.jsonl"))):
        with open(fp) as f:
            for ln in f:
                rows.append(json.loads(ln))
    rows.sort(key=lambda r: (r["entry_id"], r["gt_type"], r["gt_value"]))
    return rows


def load_frozen(path):
    with open(path) as f:
        return json.load(f)





def load_ghost_ledger(casefiles_dir):
    """Ghost ledger stats (advisory, curation-side).

    Returns {class_name: {"distinct_identifiers": int, "pairs": int}} from
    ghost_curation.json. The ledger is PAIR-level: a pair key like
    'skel-cid:0|skel-inchikey:IK' names two endpoints, and A3 found 76% of
    ghost pairs are dead-CID / live-InChIKey -- the InChIKey endpoint is
    usually a healthy GT. So endpoint membership is NOT used as a per-row
    GT-unresolved signal (that would over-tag); per-row unresolved status
    comes from the audit's own s7_class/s0_bucket fields.
    """
    classes = {}
    p = os.path.join(casefiles_dir, "ghost_curation.json")
    if os.path.exists(p):
        gc = json.load(open(p))
        rep = gc.get("report", {})
        for name, block in rep.get("classes", {}).items():
            classes[name] = {
                "distinct_identifiers": block.get("distinct_identifiers"),
                "pairs": block.get("pairs"),
            }
    return classes


def load_nmg(casefiles_dir):
    p = os.path.join(casefiles_dir, "S0-OQ-1_nmg.jsonl")
    m = {}
    if os.path.exists(p):
        with open(p) as f:
            for ln in f:
                r = json.loads(ln)
                m[row_key(r)] = r["nmg_class"]
    return m


def load_oq2(casefiles_dir):
    p = os.path.join(casefiles_dir, "S0-OQ-2_unparseable.jsonl")
    s = set()
    if os.path.exists(p):
        with open(p) as f:
            for ln in f:
                r = json.loads(ln)
                s.add((r["entry_id"], norm_value("inchikey", r["gt_value"])))
    return s


# ---------------------------------------------------------------- classifiers

def is_gt_unresolved(r):
    """Per-row GT-unresolved signal (era-consistent with frozen audit data)."""
    if r.get("s7_class") == "unresolved":
        return True
    if r.get("s0_bucket") == "unresolved_gt":
        return True
    return False


def classify_s7_fail(r, k):
    """Return mode id for a row that is attempted and NOT validated@k."""
    if is_gt_unresolved(r):
        return "gt_unresolved"
    mx = max_sim(r)
    if r.get("n_hits", 0) == 0:
        return "no_verified_hits"
    if mx == 0:
        return "structure_absent"
    if k == 1:
        if r.get("s7_validated@5"):
            return "rank_loss_top5"
        if r.get("s7_validated@10"):
            return "rank_loss_top10"
    if mx < GATES[row_type(r)]:
        return "weak_below_gate"
    return "residual_unclassified"


def classify_s0_fail(r, nmg_map):
    b = r.get("s0_bucket")
    if is_gt_unresolved(r):
        return "gt_unresolved"
    if b == "unparseable_signature":
        return "unparseable_signature"
    if b == "no_matching_generator":
        cls = nmg_map.get(row_key(r))
        return "no_matching_generator:%s" % (cls or "unjoined")
    if b == "no_sig_data":
        return "no_sig_data"
    if b == "below_gate":
        return "below_gate:%s" % (sim_band(r.get("s0_sim")) or "n/a")
    if b is None:
        return "no_s0_row"
    return "residual_unclassified"


def classify_unattempted(r):
    return "zero_hit_entry" if r.get("n_hits", 0) == 0 else "attempt_gate_unmet"


# ---------------------------------------------------------------- advisory

A5_STRUCT_CLASSES = {"struct_only_no_fasta_generator",
                     "nucleic_only_no_protein_fasta"}
A5_CHEM_CLASSES = {"chem_present_but_no_smiles", "no_chem_signatures",
                   "macro_only_no_ligand_signature"}


def advisory_flags(r, nmg_map, oq2):
    """Advisory (non-metric) cohort tags. Ghost-ledger membership is NOT a
    per-row tag: the ledger is pair-level and 76% of ghost pairs carry a live
    InChIKey endpoint (A3), so endpoint membership over-tags healthy GTs."""
    fl = set()
    cls = nmg_map.get(row_key(r))
    if cls in A5_STRUCT_CLASSES:
        fl.add("a5_curation_lipid_struct")
    if cls in A5_CHEM_CLASSES:
        fl.add("a5_curation_chem_seg")
    if (r["entry_id"], norm_value("inchikey", r.get("gt_value") or "")) in oq2:
        fl.add("oq2_perception_cohort")
    return fl


# ------------------------------------------------------------- reconciliation

def recompute_types_block(rows):
    per = collections.defaultdict(list)
    for r in rows:
        per[row_type(r)].append(r)
    out = {}
    for t in TYPE_ORDER:
        rs = per.get(t, [])
        n = len(rs)
        s0v = sum(1 for r in rs if r.get("s0_validated"))
        att = [r for r in rs if r.get("s7_attempted")]
        s0v_in_s7 = sum(1 for r in att if r.get("s0_validated"))
        zero_hit = [r for r in rs if r.get("n_hits", 0) == 0]
        s0v_zero = sum(1 for r in zero_hit if r.get("s0_validated"))
        blk = {
            "annotations": n,
            "s0_validated": s0v,
            "s0_pct": round(100.0 * s0v / n, 1) if n else None,
            "s7_attempted": len(att),
            "s0_validated_pct_on_s7_subset":
                round(100.0 * s0v_in_s7 / len(att), 1) if att else None,
            "s7_validated@1_pct": (
                round(100.0 * sum(1 for r in att if r.get("s7_validated@1")) / len(att), 1)
                if att else None),
            "s7_validated@10_pct": (
                round(100.0 * sum(1 for r in att if r.get("s7_validated@10")) / len(att), 1)
                if att else None),
            "zero_hit_entries_annotations": len(zero_hit),
            "s0_validated_pct_on_zero_hit":
                round(100.0 * s0v_zero / len(zero_hit), 1) if zero_hit else None,
            "crosstab@1": _crosstab(rs, 1),
            "crosstab@10": _crosstab(rs, 10),
            "s0_below_gate_sim_hist": _sim_hist(
                [r for r in rs if r.get("s0_bucket") == "below_gate"]),
        }
        out[t] = blk
    return out


def _crosstab(rs, k):
    tab = collections.Counter()
    for r in rs:
        if not r.get("s7_attempted"):
            continue
        tab[(bool(r.get("s0_validated")), bool(r.get("s7_validated@%d" % k)))] += 1
    return {(f"s0_{int(a)}_s7_{int(b)}"): v for (a, b), v in sorted(tab.items())}


def _sim_hist(rs):
    hist = collections.Counter()
    for r in rs:
        lb = sim_band(r.get("s0_sim"))
        if lb:
            hist[lb] += 1
    return dict(hist)


def reconcile(rows, frozen):
    """Hard equality vs the frozen audit_v2 types block. Returns (checks, ok)."""
    obs = recompute_types_block(rows)
    exp = frozen.get("types", {})
    checks = []
    ok = True
    for t in TYPE_ORDER:
        e, o = exp.get(t, {}), obs.get(t, {})
        if e != o:
            ok = False
            checks.append({
                "check": "types_block:%s" % t,
                "expected": e,
                "observed": o,
                "ok": False,
            })
        else:
            checks.append({"check": "types_block:%s" % t, "ok": True})
    return checks, ok


# ------------------------------------------------------------------ metrics

def _new_mode_table(mode_ids):
    return collections.OrderedDict((m, {"n": 0, "exemplars": []}) for m in mode_ids)


def aggregate(rows, nmg_map, oq2):
    types = collections.defaultdict(list)
    entries = collections.defaultdict(list)
    adv = collections.Counter()
    for r in rows:
        types[row_type(r)].append(r)
        entries[r["entry_id"]].append(r)
        for fl in advisory_flags(r, nmg_map, oq2, ghost_ik):
            adv[fl] += 1
    metrics = {}
    for t in TYPE_ORDER:
        rs = types.get(t, [])
        att = [r for r in rs if r.get("s7_attempted")]
        f1 = [r for r in att if not r.get("s7_validated@1")]
        f10 = [r for r in att if not r.get("s7_validated@10")]
        s0f = [r for r in rs if not r.get("s0_validated")]
        unatt = [r for r in rs if not r.get("s7_attempted")]

        t1 = _new_mode_table(S7_MODES)
        for r in f1:
            m = classify_s7_fail(r, 1, ghost_ik)
            t1[m]["n"] += 1
            t1[m]["exemplars"].append(r)
        t10 = _new_mode_table(S7_MODES_AT10)
        for r in f10:
            m = classify_s7_fail(r, 10, ghost_ik)
            t10[m]["n"] += 1
            t10[m]["exemplars"].append(r)
        t0 = collections.OrderedDict()  # S0 modes are subclassed; dynamic keys
        hist = collections.Counter()
        for r in s0f:
            m = classify_s0_fail(r, ghost_ik, nmg_map)
            t0.setdefault(m, {"n": 0, "exemplars": []})
            t0[m]["n"] += 1
            t0[m]["exemplars"].append(r)
            if m.startswith("below_gate:"):
                hist[m.split(":", 1)[1]] += 1
        tu = _new_mode_table(UNATTEMPTED_MODES)
        for r in unatt:
            m = classify_unattempted(r)
            tu[m]["n"] += 1
            tu[m]["exemplars"].append(r)

        metrics[t] = {
            "denominators": {
                "annotations": len(rs), "s7_attempted": len(att),
                "s7_fail@1": len(f1), "s7_fail@10": len(f10),
                "s0_fail": len(s0f), "unattempted": len(unatt),
            },
            "s7@1": t1, "s7@10": t10, "s0": t0, "unattempted": tu,
        }
    # sum-of-modes invariants (hard)
    for t, m in metrics.items():
        d = m["denominators"]
        assert sum(v["n"] for v in m["s7@1"].values()) == d["s7_fail@1"]
        assert sum(v["n"] for v in m["s7@10"].values()) == d["s7_fail@10"]
        assert sum(v["n"] for v in m["s0"].values()) == d["s0_fail"]
        assert sum(v["n"] for v in m["unattempted"].values()) == d["unattempted"]
    return metrics, adv, entries


def entry_level(entries):
    """Audit-basis entry any-validated@1 + failure roll-up.

    Entry participates iff >=1 annotation attempted. Failing entry mode =
    highest-precedence mode among its failed attempted annotations."""
    n_entries = len(entries)
    participating = 0
    passed = 0
    fail_modes = collections.Counter()
    fail_entries = 0
    for eid, rs in sorted(entries.items()):
        att = [r for r in rs if r.get("s7_attempted")]
        if not att:
            continue
        participating += 1
        if any(r.get("s7_validated@1") for r in att):
            passed += 1
            continue
        fail_entries += 1
        best = min(S7_MODES.index(classify_s7_fail(r, 1))
                   for r in att)
        fail_modes[S7_MODES[best]] += 1
    return {
        "entries_total": n_entries,
        "entries_participating": participating,
        "entries_any_validated@1": passed,
        "pct": round(100.0 * passed / participating, 1) if participating else None,
        "entries_failed": fail_entries,
        "failed_entry_mode_rollup": dict(fail_modes),
        "entries_no_attempted_annotation": n_entries - participating,
    }


# -------------------------------------------------------------- exemplars/md

def _ex(rows, limit=3):
    out = []
    for r in sorted(rows, key=lambda x: (x["entry_id"], x["gt_type"], x["gt_value"]))[:limit]:
        out.append({
            "entry_id": r["entry_id"], "gt_type": r["gt_type"],
            "gt_value": r["gt_value"], "n_hits": r.get("n_hits", 0),
            "s7_class": r.get("s7_class"),
            "sim@1": r.get("s7_sim@1"), "sim@5": r.get("s7_sim@5"),
            "sim@10": r.get("s7_sim@10"), "s0_bucket": r.get("s0_bucket"),
            "s0_sim": r.get("s0_sim"),
        })
    return out


def fmt(n, denom):
    pct = round(100.0 * n / denom, 1) if denom else 0.0
    return "%d (%.1f%% of %d)" % (n, pct, denom)


def build_report(rows, frozen, metrics, adv, ent, ghost_classes,
                 campaign, exemplars=3):
    checks, ok = reconcile(rows, frozen)
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": len(rows),
        "ghost_ledger": ghost_classes,
        "reconciliation": {"ok": ok, "checks": checks},
        "metrics": {},
        "advisory": dict(adv),
        "entry_level": ent,
        "campaign_v14_comparator": None,
    }
    if campaign is not None:
        s7 = campaign.get("full", {}).get("S7_similarity_hit_at_k", {})
        out["campaign_v14_comparator"] = {
            "per_type": {t: {k: s7[t].get(k) for k in
                             ("annotations", "attempted", "pct_validated@1",
                              "pct_validated@10")} for t in TYPE_ORDER if t in s7},
            "entry_any_validated@%": s7.get("entry_any_validated@%"),
            "note": ("campaign S7 denominators exclude zero-verified-hit "
                     "entries and use the campaign scan universe; the audit "
                     "join carries the full GT-covered set -- bases differ, "
                     "compare with care, never mix."),
        }
    # metrics tables with exemplars + pct discipline
    for t in TYPE_ORDER:
        m = metrics[t]
        d = m["denominators"]
        tm = {}
        for metric in ("s7@1", "s7@10", "s0", "unattempted"):
            tbl = m[metric]
            denom = {"s7@1": d["s7_attempted"], "s7@10": d["s7_attempted"],
                     "s0": d["annotations"], "unattempted": d["unattempted"]}[metric]
            rows_out = []
            for mode, v in tbl.items():
                rows_out.append({
                    "mode": mode, "n": v["n"],
                    "pct_of_denominator": round(100.0 * v["n"] / denom, 2)
                    if denom else 0.0,
                    "denominator": denom,
                    "render": fmt(v["n"], denom),
                    "exemplars": _ex(v["exemplars"], exemplars),
                })
            rows_out.sort(key=lambda x: -x["n"])
            tm[metric] = rows_out
        out["metrics"][t] = {"denominators": d, "tables": tm}
    # article paragraphs (auto-generated; numbers-only)
    para = []
    m = out["metrics"]["inchikey"]
    d = m["denominators"]
    lines = []
    for metric, label in (("s7@1", "S7@1"), ("s7@10", "S7@10"),
                          ("s0", "S0 signature stage")):
        denom = d["s7_attempted"] if metric.startswith("s7") else d["annotations"]
        parts = []
        for row in m["tables"][metric]:
            if row["n"]:
                parts.append("%s %d (%.1f%% of %d)" %
                             (row["mode"], row["n"], row["pct_of_denominator"], denom))
        failed = {"s7@1": d["s7_fail@1"], "s7@10": d["s7_fail@10"],
                  "s0": d["s0_fail"]}[metric]
        pct = round(100.0 * failed / denom, 1) if denom else 0.0
        lines.append("Organic-inchikey %s: the remaining %.1f%% (%d of %d) "
                     "decomposes as: %s." % (label, pct, failed, denom, "; ".join(parts)))
    para.append(" ".join(lines))
    out["article_paragraph"] = " ".join(para)
    return out


def render_md(report):
    L = []
    L.append("# Failure-mode audit of residual S0/v2 gaps")
    L.append("")
    gl = report.get("ghost_ledger") or {}
    gl_str = ", ".join(
        "%s: %s distinct ids / %s pairs"
        % (k, gl[k].get("distinct_identifiers"), gl[k].get("pairs"))
        for k in sorted(gl))
    L.append("Generated %s. Rows: %d. Ghost ledger (pair-level, advisory): %s."
             % (report["generated_at"], report["rows"], gl_str or "n/a"))
    L.append("")
    L.append("## Reconciliation vs frozen audit_v2 types block")
    L.append("")
    for c in report["reconciliation"]["checks"]:
        L.append("- %s: %s" % (c["check"], "PASS" if c["ok"] else "FAIL"))
    L.append("")
    for t in TYPE_ORDER:
        m = report["metrics"][t]
        d = m["denominators"]
        L.append("## %s (annotations %d)" % (t, d["annotations"]))
        for metric in ("s7@1", "s7@10", "s0", "unattempted"):
            L.append("")
            L.append("### %s" % metric)
            L.append("")
            L.append("| mode | n | pct | of (denominator) |")
            L.append("|---|---|---|---|")
            for row in m["tables"][metric]:
                L.append("| %s | %d | %.2f%% | %s |" %
                         (row["mode"], row["n"], row["pct_of_denominator"],
                          fmt(row["n"], row["denominator"])))
            L.append("")
            for row in m["tables"][metric]:
                if row["exemplars"]:
                    L.append("exemplars %s:" % row["mode"])
                    for e in row["exemplars"]:
                        L.append("  entry %s %s %s (hits=%s class=%s sim=%s/%s/%s "
                                 "s0=%s sim0=%s)" %
                                 (e["entry_id"], e["gt_type"], e["gt_value"],
                                  e["n_hits"], e["s7_class"], e["sim@1"],
                                  e["sim@5"], e["sim@10"], e["s0_bucket"],
                                  e["s0_sim"]))
        L.append("")
    L.append("## Entry level (audit basis)")
    L.append("")
    e = report["entry_level"]
    L.append("- entries total: %d; participating (>=1 attempted annotation): %d"
             % (e["entries_total"], e["entries_participating"]))
    L.append("- any-validated@1: %s (%.1f%% of %d)"
             % (e["entries_any_validated@1"], e["pct"] or 0.0, e["entries_participating"]))
    L.append("- failed entries: %d; mode roll-up: %s"
             % (e["entries_failed"], json.dumps(e["failed_entry_mode_rollup"], sort_keys=True)))
    comp = report.get("campaign_v14_comparator") or {}
    if comp.get("entry_any_validated@%"):
        L.append("- campaign v14 comparator (different basis): entry any@1 "
                 "= %.1f%%" % comp["entry_any_validated@%"]["1"])
    L.append("")
    L.append("## Advisory channels (curation/metadata-side; NOT metric blame)")
    L.append("")
    for k, v in sorted(report["advisory"].items()):
        L.append("- %s: %d annotations" % (k, v))
    L.append("")
    L.append("## Article paragraph")
    L.append("")
    L.append("> " + report["article_paragraph"])
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--shards-dir", default=os.path.join(DATA, "sigstage", "audit_v2", "shards"))
    ap.add_argument("--frozen-audit", default=os.path.join(DATA, "sigstage", "audit_v2", "audit_v2.json"))
    ap.add_argument("--casefiles", default=os.path.join(DATA, "sigstage", "casefiles"))
    ap.add_argument("--campaign", default=os.path.join(DATA, "campaign_stats_v14.json"))
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--exemplars", type=int, default=3)
    args = ap.parse_args(argv)

    for p in (args.shards_dir, args.frozen_audit, args.casefiles):
        if not os.path.exists(p):
            print("missing input: %s" % p, file=sys.stderr)
            return 2
    rows = load_rows(args.shards_dir)
    frozen = load_frozen(args.frozen_audit)
    ghost_classes = load_ghost_ledger(args.casefiles)
    nmg_map = load_nmg(args.casefiles)
    oq2 = load_oq2(args.casefiles)
    campaign = None
    if os.path.exists(args.campaign):
        campaign = load_frozen(args.campaign)

    checks, ok = reconcile(rows, frozen)
    if not ok:
        for c in checks:
            if not c["ok"]:
                print("RECONCILIATION FAIL %s\n expected: %s\n observed: %s"
                      % (c["check"], json.dumps(c["expected"], sort_keys=True),
                         json.dumps(c["observed"], sort_keys=True)), file=sys.stderr)
        return 3

    metrics, adv, entries = aggregate(rows, nmg_map, oq2)
    ent = entry_level(entries)
    report = build_report(rows, frozen, metrics, adv, ent, ghost_classes,
                          campaign, args.exemplars)
    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w") as f:
        json.dump(report, f, indent=1, sort_keys=True)
    with open(args.out_md, "w") as f:
        f.write(render_md(report))
    print("rows=%d reconciliation=PASS out=%s" % (len(rows), args.out_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
