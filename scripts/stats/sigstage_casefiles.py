#!/usr/bin/env python3
"""sigstage_casefiles -- case-review lists for S0 open items S0-OQ-1 / S0-OQ-2.

S0-OQ-1 (no_matching_generator, 2,413 rows): entries whose GT needs a segment
signature family that no segment provides. Harvests per-entry generator census
+ stage_errors signature errors and classifies the coverage gap.

S0-OQ-2 (unparseable_signature, 525 rows): segment 'smiles' signature values
RDKit fails to parse. Harvests the raw strings + RDKit error first-lines
(fd-level stderr capture) for the signature-generator team.

Inputs: /data/validation/sigstage/audit/shards/shard_000.jsonl (audit rows)
+ per-entry results docs. Outputs (scratch):
  /data/validation/sigstage/casefiles/S0-OQ-1_nmg.jsonl
  /data/validation/sigstage/casefiles/S0-OQ-2_unparseable.jsonl
  /data/validation/sigstage/casefiles/summary.json
"""
import argparse
import collections
import contextlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")
AUDIT_ROWS = os.path.join(DATA, "sigstage", "audit", "shards", "shard_000.jsonl")
OUT_DIR = os.path.join(DATA, "sigstage", "casefiles")

MACRO_PROT = ("fasta_map_protein",)
MACRO_NA = ("fasta_map_nucleic",)
STRUCT = ("pdb", "mmcif", "pdb_structure", "structure", "topology_less_pdb")
CHEM = ("smiles", "inchi", "skeleton_fp", "morgan", "canonical_smiles",
        "isomeric_smiles", "selfies")


# ---------------------------------------------------------------- NMG

def nmg_class(gens, gt_type):
    """Coverage-gap class for a no_matching_generator row.

    gens = set of generator names present across the entry's segments.
    """
    gens = {g.lower() for g in gens}
    has_prot = any(g in MACRO_PROT for g in gens)
    has_na = any(g in MACRO_NA for g in gens)
    has_struct = any(g in STRUCT for g in gens)
    has_chem = any(g in CHEM for g in gens)
    if gt_type in ("uniprot", "pdb"):
        if has_prot:
            return "protein_fasta_present_but_unmatched"
        if has_na:
            return "nucleic_only_no_protein_fasta"
        if has_struct:
            return "struct_only_no_fasta_generator"
        if has_chem:
            return "ligand_only_signatures"
        return "no_macro_no_chem_signatures"
    if gt_type == "inchikey":
        if has_chem:
            return "chem_present_but_no_smiles"
        if has_prot or has_na:
            return "macro_only_no_ligand_signature"
        return "no_chem_signatures"
    return "unmapped_gt_type"


def scan_nmg_entry(eid, rows_for_entry, root, pattern):
    path = os.path.join(root, str(eid), pattern)
    with open(path) as fh:
        doc = json.load(fh)
    sigs = ((doc.get("data") or {}).get("signatures")) or {}
    gens = set()
    seg_gens = {}
    for seg, payload in sigs.items():
        g = sorted(((payload or {}).get("generated") or {}).keys())
        gens.update(g)
        seg_gens[seg] = g
    se = (((doc.get("data") or {}).get("stage_errors")) or {}).get("signatures") or {}
    err_first = []
    for seg, errs in se.items():
        for e in errs or []:
            err_first.append(f"{seg}:{e.get('generator')}:{str(e.get('error'))[:80]}")
    out = []
    for r in rows_for_entry:
        cls = nmg_class(gens, r["gt_type"])
        out.append({
            "entry_id": eid, "gt_type": r["gt_type"], "gt_value": r["gt_value"],
            "nmg_class": cls, "n_segments": len(sigs),
            "generators": sorted(gens),
            "stage_errors_first": err_first[:5],
        })
    return out


# ---------------------------------------------------------------- unparseable

def _parse_with_error(smiles):
    """Returns (ok, error_first_line). Captures RDKit stderr at fd level."""
    from rdkit import Chem
    import io
    old_fd = os.dup(2)
    rfd, wfd = os.pipe()
    try:
        os.dup2(wfd, 2)
        with contextlib.redirect_stderr(io.StringIO()):
            mol = Chem.MolFromSmiles(str(smiles))
    finally:
        try:
            sys.stderr.flush()
        except Exception:
            pass
        os.dup2(old_fd, 2)
        os.close(old_fd)
        os.close(wfd)
    with os.fdopen(rfd) as rf:
        captured = rf.read()
    if mol is not None:
        return True, None
    first = next((ln.strip() for ln in captured.splitlines() if ln.strip()
                  and "DEPRECATION" not in ln), "")
    return False, (first[:160] or "parse returned None (no stderr captured)")


def parse_error_class(msg):
    m = (msg or "").lower()
    if "valence" in m:
        return "explicit_valence"
    if "unclosed ring" in m:
        return "unclosed_ring"
    if "ring closure" in m:
        return "ring_closure_mismatch"
    if "invalid" in m and "atom" in m:
        return "invalid_atom"
    if "parse error" in m:
        return "smiles_parse_error"
    if not m:
        return "unknown"
    return "other"


def scan_unparseable_entry(eid, rows_for_entry, root, pattern):
    path = os.path.join(root, str(eid), pattern)
    with open(path) as fh:
        doc = json.load(fh)
    sigs = ((doc.get("data") or {}).get("signatures")) or {}
    out = []
    for r in rows_for_entry:
        gtv = r["gt_value"]
        for seg, payload in sigs.items():
            raw = ((payload or {}).get("generated") or {}).get("smiles")
            if not raw:
                continue
            ok, msg = _parse_with_error(raw)
            if not ok:
                out.append({
                    "entry_id": eid, "gt_value": gtv, "segment": seg,
                    "raw_smiles": str(raw)[:400],
                    "rdkit_error": msg,
                    "error_class": parse_error_class(msg),
                })
    return out


# ---------------------------------------------------------------- driver

def load_targets(bucket):
    targets = collections.defaultdict(list)
    with open(AUDIT_ROWS) as fh:
        for ln in fh:
            r = json.loads(ln)
            if r.get("s0_bucket") == bucket:
                targets[r["entry_id"]].append(
                    {"gt_type": r["gt_type"], "gt_value": r["gt_value"]})
    return targets


def run(bucket, scan_fn, out_name, root, pattern, threads, limit):
    targets = load_targets(bucket)
    eids = sorted(targets)[: limit or None]
    print(f"{bucket}: {len(targets)} target rows over {len(targets)} entries "
          f"(processing {len(eids)})", file=sys.stderr)
    rows, errors = [], 0
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = {ex.submit(scan_fn, e, targets[e], root, pattern): e for e in eids}
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                rows.extend(fut.result())
            except Exception:
                errors += 1
            if i % 200 == 0:
                print(f"  ...{i}/{len(eids)}", file=sys.stderr)
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, out_name)
    with open(path, "w") as fh:
        for r in sorted(rows, key=lambda x: (x["entry_id"], x.get("gt_value", ""))):
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    print(f"wrote {len(rows)} rows -> {path} (entry errors: {errors})",
          file=sys.stderr)
    return rows, errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=DATA)
    ap.add_argument("--pattern", default="results.json")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--bucket", default="")
    args = ap.parse_args(argv)

    summary = {}
    if args.bucket in ("", "no_matching_generator"):
        rows, errors = run("no_matching_generator", scan_nmg_entry,
                           "S0-OQ-1_nmg.jsonl", args.root, args.pattern,
                           args.threads, args.limit)
        cls = collections.Counter(r["nmg_class"] for r in rows)
        by_type = collections.Counter(r["gt_type"] for r in rows)
        err_top = collections.Counter(
            e.split(":", 2)[-1][:60] for r in rows for e in r["stage_errors_first"])
        summary["S0-OQ-1"] = {
            "rows": len(rows), "entry_errors": errors,
            "class_counts": dict(cls.most_common()),
            "by_gt_type": dict(by_type.most_common()),
            "top_stage_errors": dict(err_top.most_common(10)),
        }
    if args.bucket in ("", "unparseable_signature"):
        rows, errors = run("unparseable_signature", scan_unparseable_entry,
                           "S0-OQ-2_unparseable.jsonl", args.root, args.pattern,
                           args.threads, args.limit)
        cls = collections.Counter(r["error_class"] for r in rows)
        summary["S0-OQ-2"] = {
            "rows": len(rows), "entry_errors": errors,
            "error_class_counts": dict(cls.most_common()),
            "examples": [dict(segment=r["segment"], raw_smiles=r["raw_smiles"][:120],
                              error_class=r["error_class"])
                         for r in rows[:5]],
        }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
    print(json.dumps(summary, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
