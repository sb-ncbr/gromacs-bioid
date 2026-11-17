#!/usr/bin/env python3
"""Per-molecule (per-segment) rollup v14 + fragment/anatomy enrichment.

Purpose: regenerate the Fig. 3 basis (funnel + per-molecule scale) at the v14
final-drain corpus and export the nucleic-anatomy rows needed for the panel-(c)
"still observable" quantification. Logic is a verbatim extension of
per_molecule_rollup_v13.py (same gates: load+analyze success) so the v13 frozen
numbers can be reconciled exactly; enrichment adds per-segment structural fields:

  residue_count / atom_count_total / molecule_count / na_detection
  parent_seg          (SYSTEM for SYSTEM__vN virtual splits)
  frag_types          (fragment unique type vocabulary joined via instance_id
                       mol_<segment>: protein/nucleic/lipid/small_molecule/unknown)
  frag_elements       (union of element names across that segment's fragments)
  fasta_len/fasta_head (first nucleic fasta signature, for short-oligo re-scan)

Outputs (NFS /data/validation, read-only scan of results.json):
  per_molecule_stats_v14.csv     one row per (entry, segment), core = v13 schema
  nucleic_anatomy_v14.jsonl      one row per nucleic segment, anatomy fields

Usage: python3 per_molecule_rollup_v14_anatomy.py [--threads N]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import re
import sys
import time
from multiprocessing import Pool

ROOT = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")
OUT_CSV = os.path.join(ROOT, "per_molecule_stats_v14.csv")
OUT_ANATOMY = os.path.join(ROOT, "nucleic_anatomy_v14.jsonl")

PROTEIN_GENS = {"pdb_protein", "pdb_not_sanitized_protein", "pdb_backbone_protein",
                "pdb_backbone_not_sanitized_protein", "fasta_map_protein",
                "fasta_resname_protein", "topology_less_pdb", "ca_only_pdb", "tdi"}
NUCLEIC_GENS = {"pdb_nucleic", "pdb_not_sanitized_nucleic", "pdb_backbone_nucleic",
                "pdb_backbone_not_sanitized_nucleic", "fasta_map_nucleic",
                "fasta_resname_nucleic", "mmcif"}
CHEM_GENS = {"smiles", "smiles_not_sanitized", "inchi_key", "molecular_formula",
             "fingerprint", "skeleton_fp", "selfies", "morgan_fingerprint",
             "glycan_composition", "lipid_shorthand"}
NAME_GENS = {"name_chain", "name_molecule", "name_segment", "atom"}
NUCLEIC_FASTA_GENS = {"fasta_map_nucleic", "fasta_resname_nucleic"}
ELEMENT_COUNT = re.compile(r"^[A-Z][a-z]?=[0-9]+$")


def parse_fragment_index(unique: dict) -> dict:
    """instance_id -> {types: Counter, elements: set} over fragment unique keys.

    Keys appear in two shapes (both seen in campaign data):
      type:nucleic|atoms:9374|residues:296|elements:C=2886,H=3333,...
      type:small_molecule|1res|C=3,H=4,N=1,O=5,P=1|form...
    so 'type' is read as the first label:value pair and elements are collected
    from any pipe/comma token of the form <Element>=<count>."""
    index: dict = {}
    for key, blob in (unique or {}).items():
        inst = (blob or {}).get("instance_id")
        if not inst:
            continue
        entry = index.setdefault(inst, {"types": collections.Counter(), "elements": set()})
        for tok in key.split("|"):
            name, _, val = tok.partition(":")
            if name == "type" and val:
                entry["types"][val] += 1
                continue
            candidates = val.split(",") if name == "elements" else (tok.split(",") if "=" in tok else [])
            for cand in candidates:
                if ELEMENT_COUNT.match(cand.strip()):
                    entry["elements"].add(cand.split("=")[0].strip())
    return index


def walk_hits(obj, state):
    """Accumulate identifier-resolver attempt counts and distinct hit ids."""
    if isinstance(obj, dict):
        if isinstance(obj.get("attempted"), list):
            state["attempts"] += len(obj["attempted"])
        hits = obj.get("hits")
        if isinstance(hits, list):
            for h in hits:
                if isinstance(h, (list, tuple)) and h:
                    state["ids"].add(h[0])
                elif isinstance(h, str):
                    state["ids"].add(h)
        for v in obj.values():
            if isinstance(v, dict):
                walk_hits(v, state)


def verified_counts(vhits):
    """(total, chem, seq, top_id, top_score) over is_verified verification hits."""
    v_tot = v_chem = v_seq = 0
    top_id, top_score = "", ""
    chem_markers = ("PUBCHEM", "CHEMBL", "CHEBI", "INCHI", "SMILES", "IDS")
    for h in vhits or []:
        if not isinstance(h, dict) or not h.get("is_verified"):
            continue
        ident_type = (h.get("ident_type") or "").upper()
        score = h.get("final_confidence")
        if not isinstance(score, (int, float)):
            score = h.get("similarity_score")
        if not isinstance(score, (int, float)):
            score = h.get("score") or h.get("similarity") or 0
        v_tot += 1
        if any(c in ident_type for c in chem_markers):
            v_chem += 1
        else:
            v_seq += 1
        if not top_id or score > (top_score if isinstance(top_score, (int, float)) else 0):
            top_id, top_score = str(h.get("identifier") or ""), score
    return v_tot, v_chem, v_seq, top_id, top_score


def scan_one(eid: str):
    p = os.path.join(ROOT, eid, "results.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p) as fh:
            d = json.load(fh)
    except Exception:
        return None
    tasks = d.get("tasks") or {}
    if (tasks.get("load_smoke") or tasks.get("load_simulation") or {}).get("status") != "success":
        return None
    if (tasks.get("analyze_universe") or {}).get("status") != "success":
        return None
    data = d.get("data") or {}
    sigmap = data.get("signatures") or {}
    idents = data.get("identifiers") or {}
    ver = data.get("verification") or {}
    usegs = ((data.get("universe") or {}).get("segments")) or {}
    frag_index = parse_fragment_index((data.get("fragments") or {}).get("unique"))
    rows, anatomy = [], []
    for seg, blob in sigmap.items():
        gen = (blob or {}).get("generated") or {}
        attempted = (blob or {}).get("attempted") or (blob or {}).get("generators_attempted") or []
        keys = set(gen)
        props = (usegs.get(seg) or {}).get("properties") or {}
        frag = frag_index.get(f"mol_{seg}") or {"types": collections.Counter(), "elements": set()}
        state = {"attempts": 0, "ids": set()}
        walk_hits(idents.get(seg) or {}, state)
        v_tot, v_chem, v_seq, top_id, top_score = verified_counts((ver.get(seg) or {}).get("verified_hits"))
        is_virtual = 1 if "__v" in seg else 0
        parent = seg.split("__v")[0] if is_virtual else seg
        is_protein = int(bool(props.get("is_protein")))
        is_nucleic = int(bool(props.get("is_nucleic")))
        rows.append({
            "entry_id": int(eid),
            "segment": seg,
            "is_virtual": is_virtual,
            "parent_seg": parent,
            "is_protein": is_protein,
            "is_nucleic": is_nucleic,
            "residue_count": props.get("residue_count", ""),
            "atom_count_total": props.get("atom_count_total", ""),
            "molecule_count": props.get("molecule_count", ""),
            "na_detection": props.get("na_detection", ""),
            "frag_types": ";".join(sorted(frag["types"])) or "",
            "frag_elements": ",".join(sorted(frag["elements"])),
            "n_signatures": len(keys),
            "n_sig_protein": len(keys & PROTEIN_GENS),
            "n_sig_nucleic": len(keys & NUCLEIC_GENS),
            "n_sig_chem": len(keys & CHEM_GENS),
            "n_sig_names": len(keys & NAME_GENS),
            "n_sig_other": len(keys - PROTEIN_GENS - NUCLEIC_GENS - CHEM_GENS - NAME_GENS),
            "n_generators_attempted": len(attempted) if isinstance(attempted, list) else "",
            "id_resolver_attempts": state["attempts"],
            "id_distinct_hits": len(state["ids"]),
            "verified_hits": v_tot,
            "verified_chem_hits": v_chem,
            "verified_seq_hits": v_seq,
            "top_verified_id": top_id,
            "top_verified_score": top_score if isinstance(top_score, (int, float)) else "",
        })
        if is_nucleic:
            fasta = next((g for g in NUCLEIC_FASTA_GENS if g in gen), None)
            seq = gen.get(fasta) if fasta else ""
            anatomy.append({
                "entry_id": int(eid),
                "segment": seg,
                "is_virtual": is_virtual,
                "parent_seg": parent,
                "residue_count": props.get("residue_count"),
                "molecule_count": props.get("molecule_count"),
                "na_detection": props.get("na_detection",""),
                "frag_types": ";".join(sorted(frag["types"])),
                "has_fasta": bool(fasta),
                "fasta_gen": fasta or "",
                "fasta_len": len(seq) if isinstance(seq, str) else None,
                "fasta_seq": seq if isinstance(seq, str) and len(seq) <= 40 else "",
                "id_distinct_hits": len(state["ids"]),
                "verified_hits": v_tot,
            })
    return (rows, anatomy) if rows else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()
    ids = sorted(d for d in os.listdir(ROOT) if d.isdigit())
    print(f"scanning {len(ids)} entry dirs -> {OUT_CSV} + {OUT_ANATOMY}", flush=True)
    t0 = time.time()
    total_rows = total_anatomy = 0
    with Pool(args.threads) as pool, \
         open(OUT_CSV, "w", newline="") as csvfh, \
         open(OUT_ANATOMY, "w") as anfh:
        writer = None
        done = 0
        for res in pool.imap_unordered(scan_one, ids, chunksize=32):
            done += 1
            if res:
                rows, anatomy = res
                if writer is None:
                    writer = csv.DictWriter(csvfh, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                writer.writerows(rows)
                total_rows += len(rows)
                for a in anatomy:
                    anfh.write(json.dumps(a) + "\n")
                total_anatomy += len(anatomy)
            if done % 2000 == 0:
                print(f"  {done}/{len(ids)} entries, rows={total_rows}, "
                      f"anatomy={total_anatomy}, {time.time()-t0:.0f}s", flush=True)
    print(f"DONE rows={total_rows} anatomy={total_anatomy} in {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
