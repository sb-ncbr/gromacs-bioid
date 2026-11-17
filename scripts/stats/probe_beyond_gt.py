#!/usr/bin/env python3
"""Pre-flight probe for beyond_gt_v14: mirror schema, ident_type vocab, id mapping."""
import json, os, random, sqlite3, sys, collections

DATA = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")
MIRROR = os.environ.get("PUBCHEM_MIRROR", "/app/databases/pubchem/current/pubchem.sqlite")
CACHE = os.path.join(DATA, "mddbr_meta_cache")

print("=== 1. mirror probe ===")
print("mirror path:", MIRROR, "exists:", os.path.exists(MIRROR))
if os.path.exists(MIRROR):
    con = sqlite3.connect(f"file:{MIRROR}?mode=ro", uri=True)
    tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print("tables:", tabs)
    for t in tabs[:6]:
        cols = con.execute(f"PRAGMA table_info({t})").fetchall()
        print(t, [c[1] for c in cols])
    for t in tabs:
        if "compound" in t.lower() or "molecule" in t.lower() or "cid" in t.lower():
            try:
                row = con.execute(f"SELECT * FROM {t} WHERE cid=101025745 LIMIT 1").fetchone()
                print("sample cid 101025745 from", t, ":", str(row)[:300])
            except Exception as e:
                print("query err", t, e)
    con.close()

print("=== 2. verified_hits ident_type census (300 random entries) ===")
dirs = [d for d in os.listdir(DATA) if d.isdigit() and os.path.exists(os.path.join(DATA, d, "results.json"))]
random.seed(42)
sample = random.sample(dirs, min(300, len(dirs)))
census = collections.Counter()
ion_examples, prot_examples, inchi_examples, chembl_examples = [], [], [], []
for eid in sample:
    try:
        d = json.load(open(os.path.join(DATA, eid, "results.json")))
    except Exception:
        continue
    for seg, blob in ((d.get("data") or {}).get("verification") or {}).items():
        for h in (blob or {}).get("verified_hits") or []:
            if not isinstance(h, dict) or not h.get("is_verified"):
                continue
            it = (h.get("ident_type") or "?").upper()
            ident = str(h.get("identifier") or "")
            census[it] += 1
            if ("ION" in it or it == "ATOM" or (len(ident) <= 3 and ident[:1].isupper())) and len(ion_examples) < 8:
                ion_examples.append((eid, it, ident, h.get("final_confidence")))
            if it in ("UNIPROT", "PDB_ID", "PDB", "PDB_STRUCT", "SWISSPROT") and len(prot_examples) < 6:
                prot_examples.append((eid, it, ident, h.get("final_confidence")))
            if "INCHI" in it and len(inchi_examples) < 4:
                inchi_examples.append((eid, it, ident))
            if "CHEMBL" in it and len(chembl_examples) < 4:
                chembl_examples.append((eid, it, ident))
print("dirs:", len(dirs))
print("ident_type census:", dict(census.most_common()))
print("ion-ish examples:", ion_examples)
print("protein examples:", prot_examples)
print("inchi examples:", inchi_examples)
print("chembl examples:", chembl_examples)

print("=== 3. accession <-> internalId mapping ===")
for acc in ["MD-A00001", "MD-A00005", "MD-A00100"]:
    p = os.path.join(CACHE, acc + ".json")
    if os.path.exists(p):
        d = json.load(open(p))
        iid = d.get("internalId")
        print(acc, "internalId:", iid, "dir exists:", os.path.isdir(os.path.join(DATA, str(iid))))
        if acc == "MD-A00005":
            md_ = d.get("metadata") or {}
            print("  INCHIKEYS:", md_.get("INCHIKEYS"))
            print("  NA/CL/COUNION:", md_.get("NA"), md_.get("CL"), md_.get("COUNION"), md_.get("COUNCAT"), md_.get("COUNANI"))

print("=== 4. entry with known ion GT --- audit ion examples ===")
# entry 5311 from per_molecule_v2 had ion-ish rows; check its cache via reverse map is hard here,
# instead check dir 2310 results.json again for inchi types
print("done")
