#!/usr/bin/env python3
"""Scan inchikey-GT entries for the fingerprint_unavailable-residue class:
entries whose chemical verified_hits are dominated by conf==0.0 with
rejection_reason='fingerprint_unavailable' —> candidates for reverify."""
import json, os, sys
from collections import defaultdict
VAL = "/data/validation"
CHEM = ("PUBCHEM_CID","PUBCHEM_ID","PUBCHEM","INCHIKEY","INCHI_KEY","CHEMBL_ID","CHEBI_ID")
gt = defaultdict(set)
for line in open(f"{VAL}/inchikey_gt.csv"):
    eid, k = line.strip().split(",", 1); gt[int(eid)].add(k)
residue = []
tot = confzero = resin_entry = 0
for eid in sorted(gt):
    p = f"{VAL}/{eid}/results.json"
    try:
        with open(p, "rb") as fh:
            import re as _re
            txt = fh.read().decode("utf-8", "ignore")
    except OSError:
        continue
    hits = 0; unavailable = 0
    # cheap string scan (avoid full json parse for speed)
    for m in _re.finditer(r'"rejection_reason":\s*"fingerprint_unavailable"', txt):
        unavailable += 1
    for m in _re.finditer(r'"rejection_reason":\s*"(?!fingerprint_unavailable)', txt):
        pass
    if unavailable >= 5:
        resin_entry += 1
        residue.append((eid, unavailable))
    hits += 0
residue.sort(key=lambda x: -x[1])
with open(f"{VAL}/residue_entries.txt", "w") as fh:
    fh.write("\n".join(str(e) for e, _ in residue))
print(f"GT entries with >=5 fingerprint_unavailable rejections: {len(residue)}")
print("top:", residue[:10])
