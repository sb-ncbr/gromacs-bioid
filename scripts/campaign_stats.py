#!/usr/bin/env python3
"""BAT3 validation campaign statistics (v3).

S1 coverage - S2 failure taxonomy - S3 per-stage - S4 per-molecule -
S5 exact-match hit@K (lower bound) - S6 health extras -
S7 SIMILARITY hit@K vs MDDBR annotations (sequence identity via local
alignment; chemical InChIKey/PubChem fingerprint Tanimoto).

Usage inside a pod with DATABASE_URL + NFS:
  python3 campaign_stats.py                 # quick SQL
  python3 campaign_stats.py --full          # + NFS scan (results.json)
  python3 campaign_stats.py --full --sim    # + S7 similarity metrics
  python3 campaign_stats.py --full --sim --pattern results-v4.json --sample 456
"""
import argparse
import collections
import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import psycopg2

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://validation:validation-password-change-me@validation-postgres:5432/bat3_validation",
)
DATA_ROOT = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")
KSET = (1, 5, 10)
STAGES = [
    "discover_input", "load_simulation", "repair_topology",
    "unwrap_periodic_boundaries", "analyze_universe", "generate_signatures",
    "identify_molecules", "verify_results", "export_results",
]
FAIL_CLASSES = [
    ("float32-json", "%float32%not JSON serializable%"),
    ("loading", "%loading strategy succeeded%"),
    ("perm-nfs", "%Permission%"),
    ("download", "%download_failed%"),
    ("project-not-found", "%project_not_found%"),
    ("no-sim-files", "%no_simulation_files%"),
    ("celery-dispatch", "%celery dispatch failed%"),
    ("stale-timeout", "%stale_timeout%"),
    ("timeout", "%timeout%"),
]
SIM_VALIDATED = 0.9
# Per-family validated thresholds: sequences stay strict; skeleton-FP chemistry
# uses the F7 gate band (junk<=0.29 | prodrug 0.73 | exact 1.0; probe-validated).
SIM_VALIDATED_BY_TYPE = {"inchikey": 0.7}
def validated_threshold(t):
    return SIM_VALIDATED_BY_TYPE.get(t, SIM_VALIDATED)
# S7v2 family-aware scoring: post-F1 hit lists run into the hundreds, so a
# global [:10] window buried each annotation's own family (P2-18 follow-up).
# Score each GT type only against mappable hit families; bounded depths.
GT_FAMILIES = {
    "pdb": ("PDB", "ALPHAFOLD", "UNIPROT", "SWISSPROT"),
    "uniprot": ("UNIPROT", "SWISSPROT", "PDB", "ALPHAFOLD"),
    "inchikey": ("PUBCHEM", "INCHI"),
}
FAMILY_DEPTH = 50      # cap family-relevant hits per annotation
FALLBACK_DEPTH = 25    # shallow global window when no family candidate exists


def norm_ident(ident_type, value):
    v = (value or "").strip().upper()
    if not v:
        return ""
    t = (ident_type or "").strip().upper()
    if "PDB" in t:
        return v[:4]
    return v


def verified_hits(doc):
    out = []
    ver = (doc.get("data") or {}).get("verification") or {}
    for seg in ver.values():
        for h in (seg or {}).get("verified_hits") or []:
            if isinstance(h, dict):
                try:
                    conf = float(h.get("final_confidence") or 0.0)
                except Exception:
                    conf = 0.0
                out.append((h.get("ident_type"), h.get("identifier"), conf,
                            h.get("skeleton_sim"), h.get("skeleton_method"),
                            h.get("is_verified")))
    out.sort(key=lambda x: x[2], reverse=True)
    return out


def exact_hit_at_k(gt_map, hits):
    ranked = [norm_ident(t, v) for t, v, *_ in hits if norm_ident(t, v)]
    per = {}
    for t in sorted(set(gt_map) | {"overall"}):
        wanted = ({v for s in gt_map.values() for v in s} if t == "overall"
                  else gt_map.get(t, set()))
        row = {"gt": len(wanted)}
        for k in KSET:
            topk = set(ranked[:k])
            row[f"hit@{k}"] = (sum(1 for v in wanted if v in topk) / len(wanted)) if wanted else None
        per[t] = row
    return per


def parse_ts(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def sql_section(con):
    cur = con.cursor()
    out = {"generated_at": datetime.utcnow().isoformat() + "Z"}
    cur.execute("SELECT count(*) FROM mddb_entries")
    out["entries_total"] = cur.fetchone()[0]
    cur.execute("SELECT status, count(*) FROM validation_queue GROUP BY 1 ORDER BY 1")
    out["queue"] = dict(cur.fetchall())
    cur.execute("SELECT status, count(*) FROM bat3_runs GROUP BY 1 ORDER BY 1")
    out["runs"] = dict(cur.fetchall())
    cur.execute("SELECT signature_type, count(*) FROM ground_truth_signatures GROUP BY 1 ORDER BY 1")
    out["gt_signatures"] = dict(cur.fetchall())
    cur.execute("SELECT count(DISTINCT entry_id) FROM ground_truth_signatures")
    out["entries_with_gt"] = cur.fetchone()[0]
    cur.execute("SELECT status, count(*) FROM batch_runs GROUP BY 1 ORDER BY 1")
    out["batches"] = dict(cur.fetchall())
    fails = {}
    for cls, pattern in FAIL_CLASSES:
        cur.execute("SELECT count(*), min(entry_id)::text FROM validation_queue "
                    "WHERE status='failed' AND last_error LIKE %s", (pattern,))
        n, sample = cur.fetchone()
        if n:
            fails[cls] = {"count": n, "example_entry": sample}
    cur.execute("""SELECT count(*) FROM validation_queue
                   WHERE status='failed' AND last_error IS NOT NULL
                   AND NOT (last_error LIKE ANY(%s))""",
                ([p for _, p in FAIL_CLASSES],))
    other = cur.fetchone()[0]
    if other:
        fails["other"] = {"count": other, "example_entry": None}
    out["failure_taxonomy"] = fails
    for label, hours in (("1h", 1), ("6h", 6), ("24h", 24)):
        cur.execute("SELECT count(*) FROM validation_queue WHERE status='completed' "
                    "AND completed_at > now() - interval %s", (f"{hours} hours",))
        out.setdefault("completions_window", {})[label] = cur.fetchone()[0]
    out["rate_per_min"] = round(out["completions_window"]["1h"] / 60.0, 2)
    done = out["queue"].get("completed", 0)
    queued = out["queue"].get("queued", 0)
    rate_1h = out["completions_window"]["1h"] / 60.0
    rate_6h = out["completions_window"]["6h"] / 360.0
    rate = rate_1h if rate_1h > 0 else rate_6h
    out["eta_hours"] = round(queued / rate, 1) if rate else None
    out["completion_pct"] = round(
        100.0 * done / max(1, done + queued + out["queue"].get("failed", 0)
                           + out["queue"].get("processing", 0)), 1)
    return out


def attempted_any(by_sig):
    for info in (by_sig or {}).values():
        if (info or {}).get("attempted"):
            return True
    return False


def _ion_elements_of(doc):
    """Ion-element symbols visible in fragment-unique element summaries.

    Ions typically aren't separate small fragments (membrane/system clusters
    swallow them), so scan ALL unique keys' element compositions for any
    metal/halide symbol - presence in the universe = presence evidence
    for ion-type GT annotations (Ca/Mg/Zn/Ni/K/Na/Cl/Fe...).
    """
    fr = (((doc.get("data") or {}).get("fragments") or {}).get("unique"))
    out = set()
    if not isinstance(fr, dict):
        return out
    import re as _re
    el_re = _re.compile(r"elements:([^|]+)")
    metals_like = ("Ca", "Mg", "Zn", "Ni", "K", "Na", "Fe", "Cu", "Co", "Mn",
                   "Li", "Rb", "Cs", "Sr", "Ba", "Cd", "Hg", "Ag", "Au",
                   "Cl", "F", "I", "Br", "Al", "Mo", "W", "V", "Ti", "Cr", "Sn", "Pb")
    for k in fr.keys():
        kk = str(k)
        try:
            elems = el_re.search(kk)
            if not elems:
                continue
            for token in elems.group(1).split(","):
                if "=" in token:
                    sym = token.split("=", 1)[0].strip()
                    if sym in metals_like:
                        out.add(sym)
        except Exception:
            continue
    return out


def scan_entry(eid, root, pattern):
    path = os.path.join(root, str(eid), pattern)
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except Exception as exc:
        return eid, {"error": f"read:{type(exc).__name__}"}
    tasks = doc.get("tasks") or {}
    stage_status = {}
    deepest = None
    for name in STAGES:
        st = (tasks.get(name) or {}).get("status")
        stage_status[name] = st
        if st == "success":
            deepest = name
    pstart = parse_ts((doc.get("pipeline") or {}).get("started_at"))
    pfin = parse_ts((doc.get("pipeline") or {}).get("finished_at"))
    runtime = (pfin - pstart).total_seconds() if pstart and pfin else None
    data = doc.get("data") or {}
    ids = data.get("identifiers") or {}
    ver = data.get("verification") or {}
    molecules = len(ids) or len(ver)
    resolvers_attempted = collections.Counter()
    sig_attempts = collections.Counter()
    mol_identified = mol_verified = 0
    for mol, by_sig in ids.items():
        for sig_type, info in (by_sig or {}).items():
            attempted = (info or {}).get("attempted") or []
            if attempted:
                sig_attempts[sig_type] += 1
                for r in attempted:
                    resolvers_attempted[r] += 1
        if attempted_any(by_sig):
            mol_identified += 1
        if (ver.get(mol) or {}).get("verified_hits"):
            mol_verified += 1
    warns = [((w.get("code") or w.get("message") or str(w))[:120]
              if isinstance(w, dict) else str(w)[:120])
             for w in doc.get("warnings") or []][:10]
    dl = set()
    try:
        with open(os.path.join(root, str(eid), "download_report.json")) as fh:
            dl = {(f.get("resolver") or "unknown") for f in json.load(fh).get("files") or []}
    except Exception:
        pass
    return eid, {
        "stage_status": stage_status, "deepest": deepest, "runtime_s": runtime,
        "molecules": molecules, "mol_identified": mol_identified,
        "mol_verified": mol_verified,
        "resolvers": resolvers_attempted, "sig_attempts": sig_attempts,
        "hits": verified_hits(doc), "warnings": warns, "ion_elements": _ion_elements_of(doc),
        "critical": len(doc.get("critical_errors") or []),
        "dl_resolvers": sorted(dl) if dl else [],
        "status_pipeline": (doc.get("pipeline") or {}).get("status"),
    }


def full_section(con, root, sample, threads, pattern, sim_engine):
    cur = con.cursor()
    cur.execute("SELECT entry_id, signature_type, signature_value FROM ground_truth_signatures")
    gt = collections.defaultdict(lambda: collections.defaultdict(set))
    for eid, t, v in cur.fetchall():
        if v and t:
            gt[eid][t.strip().lower()].add(v.strip())

    min_mtime = 0.0
    since = os.environ.get("CAMPAIGN_STATS_SINCE", "2026-09-10T11:00:00")
    try:
        min_mtime = datetime.fromisoformat(since).timestamp()
    except Exception:
        pass
    try:
        ids = [int(d.name) for d in os.scandir(root)
               if d.is_dir() and d.name.isdigit()
               and os.path.exists(os.path.join(d.path, pattern))
               and os.path.getmtime(os.path.join(d.path, pattern)) >= min_mtime]
    except FileNotFoundError:
        ids = []
    ids.sort()
    if sample:
        ids = ids[:: max(1, len(ids) // sample)][:sample]

    agg = {
        "scanned": 0, "read_errors": 0,
        "stage_status": collections.defaultdict(collections.Counter),
        "deepest": collections.Counter(),
        "runtime": [], "molecules": [], "mol_verified_rates": [],
        "resolvers": collections.Counter(), "sig_attempts": collections.Counter(),
        "hit_agg": collections.defaultdict(lambda: collections.defaultdict(float)),
        "hit_n": collections.Counter(),
        "entries_with_verified_hit": 0, "gt_covered": 0,
        "warnings": collections.Counter(), "critical": 0,
        "dl_resolvers": collections.Counter(),
        "pipeline_status": collections.Counter(),
        "gate_verified_chem": 0,
        "gate_verified_chem_hits": 0,
    }
    sim_agg = {
        "per_type": collections.defaultdict(list),
        "any": {k: 0 for k in KSET}, "any_n": 0,
    }
    agg_sim_attempt = collections.defaultdict(lambda: {"total": 0, "attempted": 0, "no_family": 0})

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = {ex.submit(scan_entry, eid, root, pattern): eid for eid in ids}
        for i, fut in enumerate(as_completed(futs), 1):
            eid = futs[fut]
            _, r = fut.result()
            if i % 500 == 0:
                print(f"  ...scanned {i}/{len(ids)} ({time.time() - t0:.0f}s)", file=sys.stderr)
            if "error" in r:
                agg["read_errors"] += 1
                continue
            agg["scanned"] += 1
            for name, st in r["stage_status"].items():
                if st:
                    agg["stage_status"][name][st] += 1
            if r["deepest"]:
                agg["deepest"][r["deepest"]] += 1
            if r["runtime_s"] is not None:
                agg["runtime"].append(r["runtime_s"])
            agg["molecules"].append(r["molecules"])
            if r["molecules"]:
                agg["mol_verified_rates"].append(r["mol_verified"] / r["molecules"])
            agg["resolvers"].update(r["resolvers"])
            agg["sig_attempts"].update(r["sig_attempts"])
            for w in r["warnings"]:
                agg["warnings"][(w.split(":")[0][:60] or w[:60])] += 1
            agg["critical"] += r["critical"]
            for dlr in r["dl_resolvers"]:
                agg["dl_resolvers"][dlr] += 1
            agg["pipeline_status"][r["status_pipeline"]] += 1

            gt_map = gt.get(eid) or {}
            if gt_map:
                agg["gt_covered"] += 1
                scores = exact_hit_at_k(gt_map, r["hits"])
                for t, row in scores.items():
                    agg["hit_n"][t] += 1
                    for k in KSET:
                        if row[f"hit@{k}"] is not None:
                            agg["hit_agg"][t][f"hit@{k}"] += row[f"hit@{k}"]
                if r["hits"]:
                    agg["entries_with_verified_hit"] += 1
                if any(h[4] and h[5] for h in r["hits"] if len(h) > 5):
                    agg["gate_verified_chem"] += 1
                    agg["gate_verified_chem_hits"] += sum(1 for h in r["hits"] if len(h) > 5 and h[4] and h[5])

                if sim_engine is not None and r["hits"]:
                    annotations = [(t, v) for t, vals in gt_map.items() for v in vals]
                    best_by_k = {k: 0.0 for k in KSET}
                    for t, v in annotations:
                        if t == "inchikey":
                            ion_present_el = None
                            try:
                                from gt_rules import gt_class_for, ion_element
                                cls = gt_class_for(v)
                                if cls == "ion":
                                    el = ion_element(v)
                                    ion_present_el = (el in (r.get("ion_elements") or set())) if el else False
                            except Exception:
                                cls = "organic"
                            if cls == "ion":
                                agg_sim_attempt["ion"]["total"] += 1
                                att_ion = bool((r.get("ion_elements") or set()))
                                rec = {k: (1.0 if ion_present_el else 0.0) for k in KSET}
                                rec["_attempted"] = att_ion
                                if att_ion:
                                    agg_sim_attempt["ion"]["attempted"] += 1
                                else:
                                    agg_sim_attempt["ion"]["no_family"] += 1
                                sim_agg["per_type"]["ion"].append(rec)
                                for k in KSET:
                                    best_by_k[k] = max(best_by_k[k], rec[k])
                                continue
                        fam = GT_FAMILIES.get(t)
                        fhits = ([h for h in r["hits"]
                                  if any(f in (h[0] or "").upper() for f in fam)][:FAMILY_DEPTH]
                                 if fam else r["hits"][:FAMILY_DEPTH])
                        attempted = bool(fhits)
                        if not attempted:
                            fhits = r["hits"][:FALLBACK_DEPTH]
                        agg_sim_attempt[t]["total"] += 1
                        if attempted:
                            agg_sim_attempt[t]["attempted"] += 1
                        else:
                            agg_sim_attempt[t]["no_family"] += 1
                        row = {}
                        for idx, (ht, hid, _conf, *_g) in enumerate(fhits, 1):
                            s = sim_engine.sim(t, v, ht, hid)
                            for k in KSET:
                                if idx <= k:
                                    row[k] = max(row.get(k, 0.0), s)
                        rec = {k: row.get(k, 0.0) for k in KSET}
                        rec["_attempted"] = attempted
                        sim_agg["per_type"][t].append(rec)
                        for k in KSET:
                            best_by_k[k] = max(best_by_k[k], rec[k])
                    sim_agg["any_n"] += 1
                    for k in KSET:
                        if best_by_k[k] >= SIM_VALIDATED:
                            sim_agg["any"][k] += 1

    out = {"scanned_entries": agg["scanned"], "read_errors": agg["read_errors"],
           "gt_covered_scanned": agg["gt_covered"],
           "scan_seconds": round(time.time() - t0, 1), "pattern": pattern}
    out["S3_per_stage"] = {n: {"total": sum(c.values()), **dict(c)}
                           for n, c in agg["stage_status"].items()}
    out["S3_deepest_stage_reached"] = dict(agg["deepest"].most_common())
    rt = sorted(agg["runtime"])
    if rt:
        out["S6_runtime_s"] = {
            "p50": round(rt[len(rt) // 2], 1),
            "p95": round(rt[min(len(rt) - 1, int(len(rt) * 0.95))], 1),
            "max": round(rt[-1], 1),
        }
    out["S4_molecules"] = {
        "per_entry_mean": round(statistics.mean(agg["molecules"]), 2) if agg["molecules"] else None,
        "per_entry_max": max(agg["molecules"], default=None),
        "verified_rate_mean": round(statistics.mean(agg["mol_verified_rates"]), 3) if agg["mol_verified_rates"] else None,
    }
    out["S4_resolver_attempts"] = dict(agg["resolvers"].most_common())
    out["S4_signature_attempts"] = dict(agg["sig_attempts"].most_common())
    hitk = {}
    for t, row in agg["hit_agg"].items():
        n = agg["hit_n"][t]
        hitk[t] = {k: round(v / n, 4) if n else None for k, v in row.items()}
        hitk[t]["entries"] = n
    out["S5_exact_hit_at_k"] = hitk
    out["S5_entries_with_verified_hit_pct"] = round(
        100.0 * agg["entries_with_verified_hit"] / max(1, agg["gt_covered"]), 1)

    if sim_engine is not None:
        s7 = {"validated_threshold": SIM_VALIDATED, "validated_threshold_by_type": SIM_VALIDATED_BY_TYPE}
        for t, rows in sim_agg["per_type"].items():
            n = len(rows)
            att = agg_sim_attempt.get(t) or {}
            n_att = att.get("attempted", n)
            att_rows = [x for x in rows if x.get("_attempted")]
            s7[t] = {
                "annotations": n,
                "attempted": n_att,
                "attempted_pct": round(100.0 * n_att / n, 1) if n else None,
                **{f"mean_sim@{k}": round(
                       sum(r[k] for r in (att_rows or rows)) / max(1, len(att_rows or rows)), 4)
                   for k in KSET},
                **{f"pct_validated@{k}": round(100.0 * sum(1 for r in rows if r[k] >= validated_threshold(t)) / n, 1)
                   for k in KSET},
            }
        anyn = sim_agg["any_n"]
        if anyn:
            s7["entry_any_validated@%"] = {k: round(100.0 * sim_agg["any"][k] / anyn, 1) for k in KSET}
        s7["pairs_computed"] = sim_engine.new_pairs
        s7["unmapped"] = sim_engine.unmapped
        out["S7_similarity_hit_at_k"] = s7

    out["S7_gate_verified_chem_entries"] = agg["gate_verified_chem"]
    out["S7_gate_verified_chem_hits"] = agg["gate_verified_chem_hits"]
    out["S6_top_warnings"] = dict(agg["warnings"].most_common(20))
    out["S6_critical_errors_total"] = agg["critical"]
    out["S6_download_resolvers"] = dict(agg["dl_resolvers"].most_common())
    out["S6_pipeline_status"] = dict(agg["pipeline_status"].most_common())
    return out


def entry_section(con, root, eid, pattern):
    _, r = scan_entry(eid, root, pattern)
    cur = con.cursor()
    cur.execute("SELECT status, retry_count, left(last_error,200) FROM validation_queue WHERE entry_id=%s", (eid,))
    q = cur.fetchall()
    cur.execute("SELECT run_id, status, created_at FROM bat3_runs WHERE entry_id=%s ORDER BY id", (eid,))
    runs = cur.fetchall()
    cur.execute("SELECT signature_type, count(*) FROM ground_truth_signatures WHERE entry_id=%s GROUP BY 1", (eid,))
    gtsig = dict(cur.fetchall())
    r = dict(r)
    r["queue_rows"] = q
    r["runs"] = runs
    r["gt_signatures"] = gtsig
    if "hits" in r:
        r["hits"] = r["hits"][:15]
    r["resolvers"] = dict(r.get("resolvers") or {})
    r["sig_attempts"] = dict(r.get("sig_attempts") or {})
    return {"entry": eid, **r}


def print_report(rep):
    q = rep.get("queue", {})
    print("=" * 64)
    print("BAT3 VALIDATION CAMPAIGN -", rep["generated_at"])
    print("=" * 64)
    print(f"Entries total: {rep['entries_total']}  |  with GT: {rep['entries_with_gt']}"
          f"  |  GT signatures: {sum(rep['gt_signatures'].values())} {rep['gt_signatures']}")
    print(f"Queue: {q}")
    print(f"Runs:  {rep['runs']}")
    print(f"Batches: {rep['batches']}")
    print(f"Completion: {rep['completion_pct']}%   rate: {rep['rate_per_min']}/min"
          f"   windows(1h/6h/24h): {rep['completions_window']}"
          f"   ETA: {rep.get('eta_hours')} h")
    if rep.get("failure_taxonomy"):
        print("\n--- Failure taxonomy (queue 'failed') ---")
        for cls, v in sorted(rep["failure_taxonomy"].items(), key=lambda x: -x[1]["count"]):
            print(f"  {cls:<20} {v['count']:>5}  e.g. entry {v['example_entry']}")
    full = rep.get("full")
    if full:
        print(f"\n--- NFS scan[{full.get('pattern')}]: {full['scanned_entries']} entries"
              f" ({full.get('read_errors', 0)} read errors, {full['scan_seconds']}s) ---")
        print("S3 per-stage status:")
        for name in STAGES:
            s = full["S3_per_stage"].get(name, {})
            print(f"  {name:<28} {s}")
        print("S3 deepest successful stage (drop-off points):")
        for k, v in list(full["S3_deepest_stage_reached"].items())[:9]:
            print(f"  {k:<28} {v}")
        print(f"S4 molecules/entry: mean={full['S4_molecules']['per_entry_mean']}"
              f"  verified-rate={full['S4_molecules']['verified_rate_mean']}")
        print("S4 resolver attempts:", full["S4_resolver_attempts"])
        print("S4 signature-type attempts:", full["S4_signature_attempts"])
        print(f"S5 EXACT hit@K (lower bound, n={full['gt_covered_scanned']}):")
        for t, row in full["S5_exact_hit_at_k"].items():
            print(f"  {t:<10} hit@1={row['hit@1']}  hit@5={row['hit@5']}  hit@10={row['hit@10']}")
        print(f"S5 entries with >=1 verified hit: {full['S5_entries_with_verified_hit_pct']}%")
        s7 = full.get("S7_similarity_hit_at_k")
        if s7:
            print(f"\nS7 SIMILARITY hit@K (validated: sim>={s7['validated_threshold']};"
                  f" pairs computed: {s7.get('pairs_computed')}, unmapped: {s7.get('unmapped')}):")
            for t in sorted(k for k in s7 if isinstance(s7[k], dict) and "annotations" in s7[k]):
                row = s7[t]
                att_s = f" att={row.get('attempted')}({row.get('attempted_pct')}%)" if "attempted" in row else ""
                print(f"  {t:<10} n={row['annotations']:<5}{att_s}"
                      f"mean@1={row['mean_sim@1']:.3f} mean@5={row['mean_sim@5']:.3f} mean@10={row['mean_sim@10']:.3f}   "
                      f"validated@1={row['pct_validated@1']}% @5={row['pct_validated@5']}% @10={row['pct_validated@10']}%")
            anyrow = s7.get("entry_any_validated@%")
            if anyrow:
                print(f"  entry-any-validated: @1={anyrow.get(1)}% @5={anyrow.get(5)}% @10={anyrow.get(10)}%")
        g = rep.get("full", {})
        if g.get("S7_gate_verified_chem_entries") is not None:
            print(f"  gate-verified chemical hits: entries={g.get('S7_gate_verified_chem_entries')} hits={g.get('S7_gate_verified_chem_hits')}")
        print("S6 runtime:", full.get("S6_runtime_s"))
        print("S6 download resolver mix:", full["S6_download_resolvers"])
        print("S6 pipeline status:", full["S6_pipeline_status"])
        print("S6 top warnings:")
        for w, n in list(full["S6_top_warnings"].items())[:12]:
            print(f"  {n:>5}x {w}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true", help="SQL only (default)")
    ap.add_argument("--full", action="store_true", help="include NFS results scan")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--threads", type=int, default=32)
    ap.add_argument("--entry", type=int, default=0)
    ap.add_argument("--json-out", default="")
    ap.add_argument("--pattern", default="results.json",
                    help="results filename to scan (results.json | results-v4.json ...)")
    ap.add_argument("--sim", action="store_true",
                    help="compute S7 similarity-based hit@K (uses /data/validation/sim_cache)")
    ap.add_argument("--sim-budget", type=int, default=20000,
                    help="max NEW pairwise similarity computations for this run")
    args = ap.parse_args()

    sim_engine = None
    if args.sim:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from validation_similarity import SimEngine
        sim_engine = SimEngine(budget=args.sim_budget)
        print(f"sim engine: {len(sim_engine.pairs)} cached pairs loaded", file=sys.stderr)

    con = psycopg2.connect(DATABASE_URL)
    if args.entry:
        rep = entry_section(con, DATA_ROOT, args.entry, args.pattern)
        print(json.dumps(rep, indent=2, default=str))
    else:
        rep = sql_section(con)
        if args.full:
            rep["full"] = full_section(con, DATA_ROOT, args.sample, args.threads,
                                       args.pattern, sim_engine)
        print_report(rep)
        if args.json_out:
            with open(args.json_out, "w") as fh:
                json.dump(rep, fh, indent=2, default=str)
            print(f"\nJSON written to {args.json_out}")


if __name__ == "__main__":
    main()
