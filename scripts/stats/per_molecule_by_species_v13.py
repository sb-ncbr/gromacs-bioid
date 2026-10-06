#!/usr/bin/env python3
"""Per-UNIQUE-MOLECULE statistics, v13 audit-heal era.

Aggregates every (entry, segment) into species-level rows keyed by the
strongest identity signature available:
  chemical: inchikey:<inchi_key>   (fallback smiles:<md5>)
  protein : prot:<md5(fasta_resname_protein)>
  nucleic : nuc:<md5(fasta_resname_nucleic)>
  fallback: seg:<entry>:<segment>  (no usable signature; collapse nothing)

Per molecule: class, n_entries/n_segments, signature families present,
identifier distinct hits (union), verified hits (total/distinct/chem/seq),
top verified identifier + best confidence, representative entry/segment.
Companion to per_molecule_stats_v13.csv (which is per entry,segment).

Usage: python3 per_molecule_by_species_v13.py [-o OUT_CSV] [--threads N]
        [--summary SUMMARY_JSON]
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
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


def _md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:20]


def scan_one(eid: str):
    """Yield per-segment species records."""
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

    out = []
    for seg, blob in sigmap.items():
        gen = (blob or {}).get("generated") or {}
        if not gen:
            continue
        props = (usegs.get(seg) or {}).get("properties") or {}
        is_prot = bool(props.get("is_protein"))
        is_nuc = bool(props.get("is_nucleic"))
        # species key + class
        ik = gen.get("inchi_key")
        f_p = gen.get("fasta_map_protein") or gen.get("fasta_resname_protein")
        f_n = gen.get("fasta_map_nucleic") or gen.get("fasta_resname_nucleic")
        smi = gen.get("smiles_not_sanitized") or gen.get("smiles")
        if ik:
            key, cls = f"inchikey:{ik}", "chemical"
        elif smi and not is_prot and not is_nuc:
            key, cls = f"smiles:{_md5(smi)}", "chemical"
        elif f_p:
            key, cls = f"prot:{_md5(f_p)}", "protein"
        elif f_n:
            key, cls = f"nuc:{_md5(f_n)}", "nucleic"
        else:
            key, cls = f"seg:{eid}:{seg}", "other"

        # identifier hits union for this segment
        hits = set()
        idb = idents.get(seg) or {}
        def walk(o):
            if isinstance(o, dict):
                hv = o.get("hits")
                if isinstance(hv, list):
                    for h in hv:
                        if isinstance(h, (list, tuple)) and h:
                            hits.add(str(h[0]))
                        elif isinstance(h, str):
                            hits.add(h)
                for v in o.values():
                    if isinstance(v, dict):
                        walk(v)

        walk(idb)

        vhits = ver.get(seg) or {}
        vlist = vhits.get("verified_hits") or []
        v_tot = v_chem = v_seq = 0
        v_ids = set()
        top_id, top_score = "", 0.0
        for h in vlist:
            if not isinstance(h, dict) or not h.get("is_verified"):
                continue
            it = (h.get("ident_type") or "").upper()
            score = h.get("final_confidence")
            if not isinstance(score, (int, float)):
                score = h.get("similarity_score") or 0
            v_tot += 1
            v_ids.add(str(h.get("identifier") or ""))
            if any(c in it for c in ("PUBCHEM", "CHEMBL", "CHEBI", "INCHI", "SMILES", "IDS")):
                v_chem += 1
            else:
                v_seq += 1
            if score > top_score:
                top_id, top_score = str(h.get("identifier") or ""), float(score)

        out.append({
            "key": key, "cls": cls, "entry": int(eid), "segment": seg,
            "n_sig": len(gen),
            "p_fam": bool(gen.keys() & PROTEIN_GENS), "n_fam": bool(gen.keys() & NUCLEIC_GENS),
            "c_fam": bool(gen.keys() & CHEM_GENS),
            "hits": hits, "v_tot": v_tot, "v_chem": v_chem, "v_seq": v_seq,
            "v_ids": v_ids, "top_id": top_id, "top_score": top_score,
        })
    return out or None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="/data/validation/per_molecule_by_species_v13.csv")
    ap.add_argument("--summary", default="/data/validation/per_molecule_by_species_v13_summary.json")
    ap.add_argument("--threads", type=int, default=10)
    args = ap.parse_args()

    ids = sorted(d for d in os.listdir(ROOT) if d.isdigit())
    print(f"scanning {len(ids)} entries...", flush=True)
    t0 = time.time()
    species: dict = {}
    nseg = 0
    done = 0
    with Pool(args.threads) as pool:
        for recs in pool.imap_unordered(scan_one, ids, chunksize=32):
            done += 1
            if recs:
                for r in recs:
                    nseg += 1
                    s = species.setdefault(r["key"], {
                        "molecule_key": r["key"], "class": r["cls"],
                        "n_entries_set": set(), "n_segments": 0,
                        "families": set(), "hits": set(), "v_ids": set(),
                        "verified_hits": 0, "verified_chem_hits": 0, "verified_seq_hits": 0,
                        "top_verified_id": "", "top_verified_score": 0.0,
                        "rep_entry": r["entry"], "rep_segment": r["segment"],
                    })
                    s["n_entries_set"].add(r["entry"])
                    s["n_segments"] += 1
                    if r["p_fam"]: s["families"].add("protein")
                    if r["n_fam"]: s["families"].add("nucleic")
                    if r["c_fam"]: s["families"].add("chemical")
                    s["hits"] |= r["hits"]
                    s["v_ids"] |= r["v_ids"]
                    s["verified_hits"] += r["v_tot"]
                    s["verified_chem_hits"] += r["v_chem"]
                    s["verified_seq_hits"] += r["v_seq"]
                    if r["top_score"] > s["top_verified_score"]:
                        s["top_verified_score"] = r["top_score"]
                        s["top_verified_id"] = r["top_id"]
                        s["rep_entry"] = r["entry"]; s["rep_segment"] = r["segment"]
            if done % 3000 == 0:
                print(f"  {done}/{len(ids)} species={len(species)} segs={nseg} {time.time()-t0:.0f}s", flush=True)

    fields = ["molecule_key", "class", "n_entries", "n_segments", "families",
              "id_distinct_hits", "verified_hits", "verified_chem_hits",
              "verified_seq_hits", "n_distinct_verified_ids", "top_verified_id",
              "top_verified_score", "rep_entry", "rep_segment"]
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for key, s in sorted(species.items(), key=lambda kv: (kv[1]["class"], -kv[1]["verified_hits"])):
            w.writerow({
                "molecule_key": key,
                "class": s["class"],
                "n_entries": len(s["n_entries_set"]),
                "n_segments": s["n_segments"],
                "families": "|".join(sorted(s["families"])),
                "id_distinct_hits": len(s["hits"]),
                "verified_hits": s["verified_hits"],
                "verified_chem_hits": s["verified_chem_hits"],
                "verified_seq_hits": s["verified_seq_hits"],
                "n_distinct_verified_ids": len(s["v_ids"]),
                "top_verified_id": s["top_verified_id"],
                "top_verified_score": round(s["top_verified_score"], 3),
                "rep_entry": s["rep_entry"],
                "rep_segment": s["rep_segment"],
            })

    cls_count = collections.Counter(s["class"] for s in species.values())
    verified = collections.Counter()
    for s in species.values():
        if s["verified_hits"] > 0:
            verified[s["class"]] += 1
    summary = {
        "entries_scanned": len(ids),
        "segments_total": nseg,
        "species_rows": len(species),
        "by_class": dict(cls_count),
        "species_with_verified_hit": dict(verified),
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(args.summary, "w") as fh:
        json.dump(summary, fh, indent=1)
    print("DONE:", json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
