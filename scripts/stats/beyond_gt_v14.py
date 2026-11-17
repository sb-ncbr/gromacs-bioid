#!/usr/bin/env python3
"""Beyond-GT measurement v14 (Section 3.4 backing).

Quantifies, per deposit, BioID verified annotations that have NO counterpart
in the deposit's own metadata (MDDBR ground-truth harvest), restricted to
chemistry and ions (the "coordinated metals, cofactors and box molecules"
claim). Proteins are out of scope by design: verified protein identities are
family-level (ranked homologs validate GT), id-string comparison would
mislabel them.

Inputs (read-only):
  results.json dirs   /data/validation/<eid>/results.json      (verified hits)
  GT dump             /data/validation/gt_sets_v14.json        (postgres harvest
                      + ion metadata; counters 9,626/12,541/14,787, 14,943 entries)
  PubChem mirror      /app/databases/pubchem/v2026-10-07/pubchem.sqlite
                      compounds(cid, smiles, inchikey, formula_hill, exact_mass)

Beyond-GT definitions:
  chem   verified identity (PUBCHEM_CID->inchikey via mirror, INCHIKEY direct)
         matched at InChIKey connectivity (first block) against the entry's GT
         INCHIKEYS connectivity set; absent = beyond-GT.
  ion    metal/halide elements present on protein-free fragments (results.json
         fragment index) vs GT ion elements (monoatomic GT inchikeys resolved
         to element via mirror formula + fallback table; metadata NA>0->Na,
         CL>0->Cl; councat/counani>0 suppress Na/Cl resp. = conservative).

Outputs (NFS):
  beyond_gt_v14.json        summary + top identities + exemplars
  beyond_gt_v14_rows.jsonl  per-entry beyond-GT listings
Stdout prints the gate block (anchors vs frozen v14 numbers).
"""
from __future__ import annotations

import collections
import json
import os
import re
import sqlite3
import sys
import time
from multiprocessing import Pool

DATA = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")
GT_DUMP = os.path.join(DATA, "gt_sets_v14.json")
MIRROR = os.environ.get("PUBCHEM_MIRROR", "/app/databases/pubchem/v2026-10-07/pubchem.sqlite")
OUT_JSON = os.path.join(DATA, "beyond_gt_v14.json")
OUT_ROWS = os.path.join(DATA, "beyond_gt_v14_rows.jsonl")

CHEM_TYPES = {"PUBCHEM_CID", "CHEMBL_ID", "CHEBI_ID", "INCHIKEY"}
PROT_TYPES = {"PDB_ID", "UNIPROT_ID", "SWISSPROT_ID"}

COORD_METALS = {"Zn", "Mg", "Ca", "Mn", "Fe", "Cu", "Ni", "Co", "Cd",
                "Mo", "W", "V", "Cr", "Ti", "Hg", "Pd", "Pt"}
# elements the scan records (mask applied in scan_one)
SCAN_ELEMENTS = {"Zn", "Mg", "Ca", "Mn", "Fe", "Cu", "Ni", "Co", "Cd", "Mo",
                 "W", "Cr", "V", "Ti", "Na", "K", "Cl"}
# coordination metals that essentially never appear as bulk salt/buffer
COORD_STRICT = {"Zn", "Cu", "Fe", "Mn", "Ni", "Co", "Cd", "Mo", "W", "V", "Cr", "Ti"}
# coordination-common but plausibly buffer (MgCl2/CaCl2): reported separately
COORD_SOFT = {"Mg", "Ca"}
# solvent-ambient species (salt/counterions): coverage-channel only
AMBIENT_IONS = {"Na", "K", "Cl"}


def lipid_like_formula(formula):
    """Membrane-lipid / detergent shape: C>=8, H/C >= 1.5, has P or >=3 oxygens."""
    if not formula:
        return False
    atoms = {}
    for m in HILL_TOKEN.finditer(formula):
        atoms[m.group(1)] = int(m.group(2) or 1)
    c, h = atoms.get("C", 0), atoms.get("H", 0)
    if c < 8 or h == 0:
        return False
    return (h / c) >= 1.5 and ("P" in atoms or atoms.get("O", 0) >= 3)

FALLBACK_ION_KEY = {
    "BHPQYMZQTOCNFJ": "Ca", "JLVVSXFLKOJNIY": "Mg", "PTFCDOFLOPIGGS": "Zn",
    "PXHVJJICTQNCMI": "Ni", "NPYPAHLBTDXSSS": "K", "VEXZGXHMUGYJMC": "Cl",
    "MDRDWERFGSJEHM": "Na", "FMLJBBPZFXZXKU": "Fe", "MAMIIQANAAEKHO": "Ca",
}

COFACTOR = {"ATP", "ADP", "AMP", "ANP", "GTP", "GDP", "GNP", "GSP", "CTP", "CDP",
            "UTP", "UDP", "UDPG", "TTP", "TMP", "CMP", "GMP", "UMP", "NAD", "NAI",
            "NAP", "NDP", "NADP", "NADH", "FAD", "FNS", "FMN", "COA", "ACO", "ACP",
            "SAH", "SAM", "HEM", "HEA", "HEB", "HEC", "HES", "PLP", "TPP", "PQQ",
            "MGD", "F43", "COQ", "B12", "BTN", "THB", "THG", "GSH", "GSSG", "G6P"}
LIPID = {"POPC", "POPE", "POPG", "POPS", "POPA", "POPI", "DOPC", "DOPE", "DOPG", "DOPS",
         "DPPC", "DPPE", "DPPG", "DMPC", "DLPC", "DSPC", "CHOL", "CHL1", "PLM", "PSM",
         "OSM", "SM", "CER", "LPA", "LPC", "DPPC"}
DETERGENT = {"DDM", "DM", "OG", "BNG", "BOG", "LDAO", "C12E8", "CYMAL", "FOS", "DPC",
             "SDS", "DTAC", "LMNG", "GDN", "UDM"}
BUFFER = {"GOL", "EDO", "PEG", "PG4", "PGE", "1PE", "SO4", "PO4", "ACT", "ACY", "MES",
          "TRS", "HEPES", "CIT", "EOH", "DMSO", "DMS", "SUCNAS", "IMD", "TRE", "SUC"}
CARBO = {"GLC", "BGC", "NAG", "BMA", "MAN", "GAL", "FUC", "NDG", "NGZ", "FRU", "SIA"}
GENERIC_RESNAMES = {"MOL", "LIG", "UNK", "DRG", "INH", "LG"}

ELEMENT_COUNT = re.compile(r"^[A-Z][a-z]?=[0-9]+$")
HILL_TOKEN = re.compile(r"([A-Z][a-z]?)([0-9]*)")


def parse_fragment_index(unique):
    index = {}
    for key, blob in (unique or {}).items():
        inst = (blob or {}).get("instance_id")
        if not inst:
            continue
        ent = index.setdefault(inst, {"types": set(), "elements": set()})
        for tok in key.split("|"):
            name, _, val = tok.partition(":")
            if name == "type" and val:
                ent["types"].add(val)
                continue
            cands = val.split(",") if name == "elements" else (tok.split(",") if "=" in tok else [])
            for cand in cands:
                if ELEMENT_COUNT.match(cand.strip()):
                    ent["elements"].add(cand.split("=")[0].strip())
    return index


def _as_str(v):
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, list) and v and isinstance(v[0], str):
        return v[0].strip()
    return ""


def scan_one(eid):
    p = os.path.join(DATA, eid, "results.json")
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
    ver = data.get("verification") or {}
    usegs = ((data.get("universe") or {}).get("segments")) or {}
    frag_index = parse_fragment_index((data.get("fragments") or {}).get("unique"))

    verified = {}          # (ident_type, identifier) -> (best_conf, resname, seg_kind)
    seg_rows = 0
    seg_metals_prot = collections.Counter()   # element on protein-only segments
    seg_metals_mixed = collections.Counter()  # element on SYSTEM/protein-mixed segments
    seg_metals_free = collections.Counter()   # element on protein-free segments
    def _frag(seg):
        frag = frag_index.get(f"mol_{seg}")
        if frag is None and "__v" in seg:
            frag = frag_index.get(f"mol_{seg.split('__v')[0]}")
        return frag

    for seg, blob in ver.items():
        vhits = (blob or {}).get("verified_hits") or []
        gen = ((sigmap.get(seg) or {}).get("generated")) or {}
        resname = _as_str(gen.get("resname"))
        frag = _frag(seg) or {"types": set(), "elements": set()}
        seg_is_prot = bool(frag["types"] & {"protein", "nucleic"}) or bool(
            (usegs.get(seg) or {}).get("properties", {}).get("is_protein")) or bool(
            (usegs.get(seg) or {}).get("properties", {}).get("is_nucleic"))
        seg_kind = "prot" if seg_is_prot else "chem"
        for h in vhits:
            if not isinstance(h, dict) or not h.get("is_verified"):
                continue
            it = (h.get("ident_type") or "").upper()
            ident = str(h.get("identifier") or "").strip()
            if not ident:
                continue
            conf = h.get("final_confidence")
            if not isinstance(conf, (int, float)):
                conf = h.get("similarity_score") or 0
            key = (it, ident)
            try:
                conf = float(conf)
            except (TypeError, ValueError):
                conf = 0.0
            cur = verified.get(key)
            # chem-segment provenance preferred over prot-segment at equal conf
            if cur is None or conf > cur[0] or (conf == cur[0] and seg_kind == "chem" and cur[2] == "prot"):
                verified[key] = (conf, resname, seg_kind)
    for seg, blob in sigmap.items():
        seg_rows += 1
        frag = _frag(seg)
        if not frag:
            continue
        els = frag["elements"] & SCAN_ELEMENTS
        if not els:
            continue
        ft = frag["types"]
        if "protein" in ft and len(ft) == 1:
            tgt = seg_metals_prot
        elif "protein" in ft or "nucleic" in ft:
            tgt = seg_metals_mixed
        else:
            tgt = seg_metals_free
        for e in els:
            tgt[e] += 1
    return {
        "entry_id": int(eid),
        "n_segments": seg_rows,
        "verified": [{"it": k[0], "id": k[1], "conf": round(v[0], 2), "resname": v[1],
                      "seg_kind": v[2]}
                     for k, v in verified.items()],
        "metals_prot": dict(seg_metals_prot),
        "metals_mixed": dict(seg_metals_mixed),
        "metals_free": dict(seg_metals_free),
    }


def hill_elements(formula):
    """Return element set of a Hill formula (single-element check)."""
    return {m.group(1) for m in HILL_TOKEN.finditer(formula or "")}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    t0 = time.time()
    if mode in ("all", "scan"):
        dirs = sorted(d for d in os.listdir(DATA) if d.isdigit()
                      and os.path.exists(os.path.join(DATA, d, "results.json")))
        print(f"[scan] {len(dirs)} results.json dirs", flush=True)
        n_workers = int(os.environ.get("BGT_WORKERS", "8"))
        with Pool(n_workers) as pool:
            scan_path = os.path.join(DATA, "beyond_gt_v14_scan.jsonl")
            with open(scan_path, "w") as sf:
                n_keep = 0
                for r in pool.imap_unordered(scan_one, dirs, chunksize=40):
                    if r:
                        sf.write(json.dumps(r) + "\n")
                        n_keep += 1
        print(f"[scan] gate-pass entries: {n_keep} ({time.time()-t0:.0f}s) -> {scan_path}", flush=True)
        if mode == "scan":
            return

    t0 = time.time()
    rows = []
    with open(os.path.join(DATA, "beyond_gt_v14_scan.jsonl")) as sf:
        for line in sf:
            rows.append(json.loads(line))
    print(f"[join] loaded {len(rows)} scan rows ({time.time()-t0:.0f}s)", flush=True)

    # ---- anchors
    if "dirs" not in dir():
        dirs = [d for d in os.listdir(DATA) if d.isdigit()
                and os.path.exists(os.path.join(DATA, d, "results.json"))]
    n_segments = sum(r["n_segments"] for r in rows)
    ver_tot = collections.Counter()
    for r in rows:
        for v in r["verified"]:
            ver_tot["CHEM" if v["it"] in CHEM_TYPES else
                    ("PROT" if v["it"] in PROT_TYPES else "OTHER")] += 1
    print(f"[anchor] segments={n_segments} verified: {dict(ver_tot)}", flush=True)

    gt = json.load(open(GT_DUMP))["entries"]
    chem_gt_n = sum(1 for g in gt.values() if g["inchikey"])
    print(f"[gt] entries with metadata GT: {len(gt)} (with inchikey GT: {chem_gt_n})", flush=True)

    con = sqlite3.connect(f"file:{MIRROR}?mode=ro", uri=True)

    # ---- distinct verified CIDs -> inchikey connectivity
    cid_set = sorted({v["id"] for r in rows for v in r["verified"] if v["it"] == "PUBCHEM_CID"})
    cid2ik, cid2formula = {}, {}
    for cid in cid_set:
        row = con.execute("SELECT inchikey, formula_hill FROM compounds WHERE cid=?", (cid,)).fetchone()
        if row:
            cid2ik[cid] = row[0].split("-")[0] if row[0] else ""
            cid2formula[cid] = row[1] or ""
    resolved_share = len(cid2ik) / max(1, len(cid_set))
    print(f"[mirror] verified CIDs {len(cid_set)}, resolved {len(cid2ik)} ({resolved_share:.1%})", flush=True)

    # ---- GT ion elements: monoatomic GT inchikeys -> formula -> element
    gt_ik_all = sorted({ik for g in gt.values() for ik in g["inchikey"]})
    ik2formula = {}
    for ik in gt_ik_all:
        row = con.execute("SELECT formula_hill FROM compounds WHERE inchikey=?", (ik,)).fetchone()
        if row:
            ik2formula[ik] = row[0] or ""

    def norm_formula(formula):
        """Heavy-atom-only composition (protonation-state invariant)."""
        atoms = {m.group(1): int(m.group(2) or 1) for m in HILL_TOKEN.finditer(formula or "")}
        atoms.pop("H", None)
        return "".join(f"{e}{atoms[e]}" for e in sorted(atoms))
    gt_norm = {eid: {norm_formula(ik2formula[ik]) for ik in g["inchikey"] if ik2formula.get(ik)}
               for eid, g in gt.items()}
    def gt_elements(g):
        els = set()
        for ik in g["inchikey"]:
            fb = FALLBACK_ION_KEY.get(ik.split("-")[0])
            if fb:
                els.add(fb); continue
            f = ik2formula.get(ik)
            if f and len(hill_elements(f)) == 1:
                els.add(next(iter(hill_elements(f))))
        return els
    gt_ions = {eid: gt_elements(g) for eid, g in gt.items()}
    print(f"[gt] distinct GT inchikeys {len(gt_ik_all)}, mirror-resolved formulas {len(ik2formula)}", flush=True)

    # ---- join (chem only on chem-class segments; prot-segment chem hits are
    # amino-acid sidechain fragments and are counted separately as artifacts)
    def chem_conn(v):
        if v["it"] == "PUBCHEM_CID":
            return cid2ik.get(v["id"])
        if v["it"] == "INCHIKEY":
            return v["id"].split("-")[0]
        return None  # CHEMBL_ID / CHEBI_ID: currency not joinable

    # formulas for verified INCHIKEY hits (for the protonation-sibling guard)
    vik_set = sorted({v["id"] for r in rows for v in r["verified"] if v["it"] == "INCHIKEY"})
    vik2formula = {}
    for ik in vik_set:
        row = con.execute("SELECT formula_hill FROM compounds WHERE inchikey=?", (ik,)).fetchone()
        if row:
            vik2formula[ik] = row[0] or ""

    def chem_norm(v):
        if v["it"] == "PUBCHEM_CID":
            return norm_formula(cid2formula.get(v["id"], ""))
        if v["it"] == "INCHIKEY":
            return norm_formula(vik2formula.get(v["id"], ""))
        return ""

    n_beyond_chem_entries = 0
    n_beyond_chem_entries_zerogt = 0
    n_beyond_chem_entries_protgt = 0
    prot_sibling_hits = 0
    n_beyond_metal_entries = 0
    n_beyond_soft_entries = 0
    ambient_entry_n = 0
    prot_artifact_hits = 0
    beyond_conn = collections.Counter()           # conn14 -> n entries (distinct beyond identity)
    conn_info = {}                                # conn14 -> {cid, formula, resname}
    class_hist = collections.Counter()            # subclass -> n entries
    metal_hist = collections.Counter()            # strict coord metals -> n entries (beyond GT)
    soft_hist = collections.Counter()             # Mg/Ca -> n entries (beyond GT)
    metal_free_hist = collections.Counter()       # advisory: coord metals on protein-free segs
    ambient_hist = collections.Counter()          # Na/K/Cl -> n entries (beyond GT)
    unres_chem = collections.Counter()            # CHEMBL/CHEBI counters
    zero_gt_entries = 0
    exemplars = collections.defaultdict(list)
    io = open(OUT_ROWS, "w")
    for r in rows:
        eid = str(r["entry_id"])
        g = gt.get(eid)
        if g is None:
            zero_gt_entries += 1
            g_conn, g_norm, gt_el = set(), set(), set()
        else:
            g_conn = {ik.split("-")[0] for ik in g["inchikey"]}
            g_norm = gt_norm.get(eid, set())
            gt_el = gt_ions.get(eid, set())
        entry_beyond = {}
        for v in r["verified"]:
            if v["it"] not in CHEM_TYPES:
                continue
            if v.get("seg_kind") == "prot":
                prot_artifact_hits += 1
                continue
            if v["it"] in ("CHEMBL_ID", "CHEBI_ID"):
                unres_chem[v["it"]] += 1
                continue
            conn = chem_conn(v)
            if not conn:
                continue
            if conn in g_conn:
                continue
            # protonation-sibling guard: same heavy-atom composition as a GT
            # molecule means the deposit IS annotated for this compound
            if chem_norm(v) and chem_norm(v) in g_norm:
                prot_sibling_hits += 1
                continue
            entry_beyond[conn] = v
        if entry_beyond:
            n_beyond_chem_entries += 1
            if g is None:
                n_beyond_chem_entries_zerogt += 1
            elif not g["inchikey"]:
                n_beyond_chem_entries_protgt += 1
        classes = collections.Counter()
        for conn, v in entry_beyond.items():
            beyond_conn[conn] += 1
            rn = (v["resname"] or "").upper().strip()
            info = {"resname": conn_info.get(conn, {}).get("resname", "") or rn,
                    "formula": conn_info.get(conn, {}).get("formula", "") or
                               (cid2formula.get(v["id"], "") if v["it"] == "PUBCHEM_CID" else ""),
                    "cid": conn_info.get(conn, {}).get("cid", "") or (v["id"] if v["it"] == "PUBCHEM_CID" else "")}
            conn_info[conn] = info
            if rn in COFACTOR: cls = "cofactor"
            elif rn in LIPID: cls = "lipid_membrane"
            elif rn in DETERGENT: cls = "detergent"
            elif rn in BUFFER: cls = "buffer_solvent"
            elif rn in CARBO: cls = "carbohydrate"
            elif lipid_like_formula(info.get("formula", "")): cls = "lipid_membrane_formula"
            elif rn in GENERIC_RESNAMES: cls = "ligand_generic"
            elif rn: cls = "other_organic"
            else: cls = "unlabeled_organic"
            classes[cls] += 1
        for cls, n in classes.items():
            class_hist[cls] += 1   # entries with >=1 beyond identity of class
        # metals: protein-associated = protein-only OR SYSTEM-mixed segments
        prot_assoc = set(r.get("metals_prot", {})) | set(r.get("metals_mixed", {}))
        beyond_strict = {el: 1 for el in (prot_assoc & COORD_STRICT) if el not in gt_el}
        beyond_soft = {el: 1 for el in (prot_assoc & COORD_SOFT) if el not in gt_el}
        if beyond_strict:
            n_beyond_metal_entries += 1
            for el in beyond_strict:
                metal_hist[el] += 1
        if beyond_soft:
            n_beyond_soft_entries += 1
            for el in beyond_soft:
                soft_hist[el] += 1
        anywhere = prot_assoc | set(r.get("metals_free", {}))
        amb_hit = False
        for el in (anywhere & AMBIENT_IONS):
            if el not in gt_el:
                ambient_hist[el] += 1
                amb_hit = True
        if amb_hit:
            ambient_entry_n += 1
        for el in r.get("metals_free", {}):
            if el in (COORD_STRICT | COORD_SOFT) and el not in gt_el:
                metal_free_hist[el] += 1
        io.write(json.dumps({"entry_id": r["entry_id"],
                             "beyond_chem": {c: {"conf": v["conf"], "resname": v["resname"], "it": v["it"], "id": v["id"]}
                                             for c, v in entry_beyond.items()},
                             "beyond_metals_strict": sorted(beyond_strict),
                             "beyond_metals_soft": sorted(beyond_soft)}) + "\n")
        # exemplars: highest-confidence beyond hits per class
        for conn, v in entry_beyond.items():
            rn = (v["resname"] or "").upper().strip()
            cls = ("cofactor" if rn in COFACTOR else "lipid_membrane" if rn in LIPID else
                   "detergent" if rn in DETERGENT else "buffer_solvent" if rn in BUFFER else
                   "carbohydrate" if rn in CARBO else None)
            if cls:
                exemplars[cls].append((v["conf"], r["entry_id"], conn, rn))
    io.close()

    for k in exemplars:
        exemplars[k] = sorted(exemplars[k], reverse=True)[:5]

    top_idents = [{"conn": c, "entries": n,
                   "resname": conn_info.get(c, {}).get("resname", ""),
                   "formula": conn_info.get(c, {}).get("formula", ""),
                   "cid": conn_info.get(c, {}).get("cid", "")}
                  for c, n in beyond_conn.most_common(40)]

    summary = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "basis": "v14 results.json verified_hits + ground_truth_signatures (2026-10-07 harvest)",
        "gates": {
            "results_dirs": len(dirs),
            "gate_pass_entries": len(rows),
            "segments": n_segments,
            "verified_totals": dict(ver_tot),
            "gt_entries": len(gt),
            "chem_gt_entries": chem_gt_n,
            "gt_ik_distinct": len(gt_ik_all),
            "verified_cid_distinct": len(cid_set),
            "cid_mirror_resolved_pct": round(100 * resolved_share, 2),
        },
        "results": {
            "gate_pass_entries": len(rows),
            "chem_gt_annotated_entries": chem_gt_n,
            "entries_with_beyond_chem": n_beyond_chem_entries,
            "entries_with_beyond_chem_zerogt": n_beyond_chem_entries_zerogt,
            "entries_with_beyond_chem_protein_only_gt": n_beyond_chem_entries_protgt,
            "protonation_sibling_hits_guarded": prot_sibling_hits,
            "entries_with_beyond_coordmetal_strict": n_beyond_metal_entries,
            "entries_with_beyond_mg_ca": n_beyond_soft_entries,
            "entries_with_beyond_ambient_salt": ambient_entry_n,
            "entries_with_zero_gt": zero_gt_entries,
            "prot_segment_chem_artifact_hits_excluded": prot_artifact_hits,
            "beyond_identity_distinct": len(beyond_conn),
            "beyond_class_entries": dict(class_hist),
            "beyond_coordmetal_strict_elements": dict(metal_hist),
            "beyond_mg_ca_elements": dict(soft_hist),
            "beyond_ambient_salt_elements": dict(ambient_hist),
            "advisory_coordmetal_free_segments": dict(metal_free_hist),
            "unresolvable_currency_verified": dict(unres_chem),
        },
        "top_beyond_identities": top_idents,
        "exemplars": {k: [{"conf": c[0], "entry": c[1], "conn": c[2], "resname": c[3]} for c in v]
                      for k, v in exemplars.items()},
    }
    json.dump(summary, open(OUT_JSON, "w"), indent=1)
    print(json.dumps(summary["gates"], indent=1))
    print(json.dumps(summary["results"], indent=1))
    print(f"[done] {time.time()-t0:.0f}s -> {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
