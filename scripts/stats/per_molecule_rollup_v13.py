#!/usr/bin/env python3
"""Per-molecule (per-segment) statistics rollup, v13 audit-heal era.

One CSV row per (entry, segment) across the frame: signature family
composition, identifier attempt/hit counts, verified-hit counts
(signatures/identifiers/verified hits" trio the user builds figures from).
Read-only over NFS; in-pod Pool; gates identical to campaign_stats full
(results.json success-gated on load+analyze tasks).

Usage: python3 per_molecule_rollup_v13.py [-o OUT_CSV] [--threads N]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from multiprocessing import Pool

ROOT = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")

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

CHEM_IDENT_TYPES = {"PUBCHEM_CID", "PUBCHEM_ID", "PUBCHEM", "INCHIKEY", "INCHI_KEY",
                    "CHEMBL_ID", "CHEBI_ID", "SMILES", "SELFIES", "IDS_CHEBI"}
SEQ_IDENT_TYPES = {"UNIPROT_ID", "PDB_ID", "BLAST", "SWISSPROT", "NR", "PDBNT", "CORENT",
                   "ACCESSION", "PDB_STRUCTURE"}


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
    rows = []
    for seg, blob in sigmap.items():
        gen = (blob or {}).get("generated") or {}
        attempted = (blob or {}).get("attempted") or (blob or {}).get("generators_attempted") or []
        keys = set(gen)
        props = (usegs.get(seg) or {}).get("properties") or {}
        idb = idents.get(seg) or {}
        # identifiers: for each generator, resolvers' results carry hits
        id_attempted = 0
        hit_union = set()
        def walk(o):
            nonlocal id_attempted
            if isinstance(o, dict):
                if "attempted" in o and isinstance(o.get("attempted"), list):
                    id_attempted += len(o["attempted"])
                hits = o.get("hits")
                if isinstance(hits, list):
                    for h in hits:
                        if isinstance(h, (list, tuple)) and h:
                            hit_union.add(h[0])
                        elif isinstance(h, str):
                            hit_union.add(h)
                for v in o.values():
                    if isinstance(v, dict):
                        walk(v)

        walk(idb)
        vb = ver.get(seg) or {}
        vhits = vb.get("verified_hits") or []
        v_tot = v_chem = v_seq = 0
        top_id, top_score = "", ""
        for h in vhits:
            if not isinstance(h, dict) or not h.get("is_verified"):
                continue
            it = (h.get("ident_type") or "").upper()
            score = h.get("final_confidence")
            if not isinstance(score, (int, float)):
                score = h.get("similarity_score")
            if not isinstance(score, (int, float)):
                score = h.get("score") or h.get("similarity") or 0
            v_tot += 1
            if any(c in it for c in ("PUBCHEM", "CHEMBL", "CHEBI", "INCHI", "SMILES", "IDS")):
                v_chem += 1
            else:
                v_seq += 1
            if not top_id or (isinstance(score, (int, float)) and score > (top_score if isinstance(top_score, (int, float)) else 0)):
                top_id, top_score = str(h.get("identifier") or ""), score
        rows.append({
            "entry_id": int(eid),
            "segment": seg,
            "is_virtual": 1 if "__v" in seg else 0,
            "is_protein": int(bool(props.get("is_protein"))),
            "is_nucleic": int(bool(props.get("is_nucleic"))),
            "n_signatures": len(keys),
            "n_sig_protein": len(keys & PROTEIN_GENS),
            "n_sig_nucleic": len(keys & NUCLEIC_GENS),
            "n_sig_chem": len(keys & CHEM_GENS),
            "n_sig_names": len(keys & NAME_GENS),
            "n_sig_other": len(keys - PROTEIN_GENS - NUCLEIC_GENS - CHEM_GENS - NAME_GENS),
            "n_generators_attempted": len(attempted) if isinstance(attempted, list) else "",
            "id_resolver_attempts": id_attempted,
            "id_distinct_hits": len(hit_union),
            "verified_hits": v_tot,
            "verified_chem_hits": v_chem,
            "verified_seq_hits": v_seq,
            "top_verified_id": top_id,
            "top_verified_score": top_score if isinstance(top_score, (int, float)) else "",
        })
    return rows or None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="/data/validation/per_molecule_stats_v13.csv")
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()

    ids = sorted(d for d in os.listdir(ROOT) if d.isdigit())
    print(f"scanning {len(ids)} entry dirs -> {args.out}", flush=True)
    t0 = time.time()
    total_rows = 0
    with Pool(args.threads) as pool, open(args.out, "w", newline="") as fh:
        writer = None
        done = 0
        for rows in pool.imap_unordered(scan_one, ids, chunksize=32):
            done += 1
            if rows:
                if writer is None:
                    writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                writer.writerows(rows)
                total_rows += len(rows)
            if done % 2000 == 0:
                print(f"  {done}/{len(ids)} entries, rows={total_rows}, {time.time()-t0:.0f}s", flush=True)
    print(f"DONE {total_rows} rows in {time.time()-t0:.0f}s -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
