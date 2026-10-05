#!/usr/bin/env python3
"""Inchikey-GT gap decomposition over full pop (7,342 GT entries).
Buckets per entry: gt unresolvable / no chem hits / hits no covering / covering.
For covering: best gsim (skeleton-FP) & best sim. Split by results.json era."""
import json, os, sys, hashlib, time
sys.path.insert(0, "/data/validation/patched_src")
from src_new.signatures.skeletize import from_smiles, skeleton_fp, tanimoto

VAL = "/data/validation"; SIM = os.path.join(VAL, "sim_cache")
CUTOFF = time.mktime(time.strptime("2026-09-21 14:30:00", "%Y-%m-%d %H:%M:%S"))
CHEM = ("PUBCHEM_CID","PUBCHEM_ID","PUBCHEM","INCHIKEY","INCHI_KEY","CHEMBL_ID","CHEBI_ID","SMILES","SELFIES")
CIDC = ("PUBCHEM_CID","PUBCHEM_ID","PUBCHEM")
entries = json.load(open(f"{VAL}/gt_entries.json"))
gtmap = {}
for eid, ik in json.load(open('/tmp/gt_inchikey_rows.json')):
    gtmap.setdefault(eid, []).append(ik)

def cache_get(sub, key):
    p = os.path.join(SIM, sub, hashlib.sha1(key.encode()).hexdigest()[:24] + ".json")
    try:
        with open(p) as fh: return json.load(fh)
    except Exception: return None

def cand_smiles(u, ident):
    u = (u or "").upper()
    if u in CIDC and str(ident).isdigit(): return cache_get("pubchem_smiles", f"cid:{ident}")
    if u == "CHEMBL_ID":
        c = str(ident).upper(); c = c[6:] if c.startswith("CHEMBL") else c
        return cache_get("pubchem_smiles", f"chemb:CHEMBL{c}")
    if u == "CHEBI_ID":
        c = str(ident).upper(); c = c[6:] if c.startswith("CHEBI:") else c
        return cache_get("pubchem_smiles", f"chebi:{c}")
    if u in ("INCHIKEY","INCHI_KEY"):
        return cache_get("inchikey_smiles", str(ident))
    return None

_fp = {}
def fp_of(smi):
    if not smi: return None
    if smi in _fp: return _fp[smi]
    r = None
    try:
        m = from_smiles(smi)
        if m is not None:
            fp = skeleton_fp(m)
            r = fp
    except Exception:
        r = None
    _fp[smi] = r
    return r

def c_smi(g):
    if isinstance(g, dict): return g.get("smiles") or g.get("canonical_smiles") or g.get("smile")
    return g

agg = {}
def rec(e, cat, val=None):
    a = agg.setdefault(e, {'gt_nores':0,'nochem':0,'hits_nocov':0,'cov':0,'v09':0,'v07':0,'sim_sum':0.0,'sim_n':0,'mean_list':[]})
    a[cat]+=1
    if val is not None:
        a['sim_sum']+=val; a['sim_n']+=1; a['mean_list'].append(val)

t0=time.time()
for idx, eid in enumerate(entries):
    f = f'{VAL}/{eid}/results.json'
    try: mt = os.path.getmtime(f)
    except Exception: continue
    era = 'F' if mt>=CUTOFF else 'L'
    try: d = json.load(open(f))
    except Exception: rec(era,'nochem'); continue
    hits=[]
    v = d.get('data',{}).get('verification') or {}
    for seg in v.values():
        hits += (seg or {}).get('verified_hits') or []
    chem_hits = [h for h in hits if (h.get('ident_type') or '').upper() in CHEM and h.get('is_verified')]
    gts_raw = gtmap.get(eid, [])
    gt_s = [c_smi(cache_get("inchikey_smiles", ik)) for ik in gts_raw]
    gt_s = [s for s in gt_s if s]
    if not gt_s:
        rec(era,'gt_nores'); continue
    gtf = [fp_of(s) for s in gt_s]
    if not chem_hits:
        rec(era,'nochem'); continue
    best = 0.0
    for h in chem_hits:
        cs = cand_smiles(h.get('ident_type'), h.get('identifier'))
        if not cs: continue
        cf = fp_of(cs)
        if cf is None: continue
        for gf in gtf:
            if gf is None: continue
            try: best = max(best, tanimoto(cf, gf))
            except Exception: pass
    if best>0: rec(era,'cov',best)
    else: rec(era,'hits_nocov')
    if best>=0.9: rec(era,'v09')
    if best>=0.7: rec(era,'v07')
    if idx%1000==0: print(f'  ..{idx}/{len(entries)} {time.time()-t0:.0f}s', flush=True)

print('ELAPSED', round(time.time()-t0))
for era in ('F','L'):
    a = agg.get(era,{})
    tot = sum(a.get(k,0) for k in ('gt_nores','nochem','hits_nocov','cov'))
    gtok = tot - a.get('gt_nores',0)
    print(f"{era}: entries={tot} gt_struct_ok={gtok} ({a.get('gt_nores',0)} no-structure)")
    print(f"   no_chem_hits={a.get('nochem',0)} ({a.get('nochem',0)/max(gtok,1)*100:.0f}% of gt-ok) | hits_no_covering={a.get('hits_nocov',0)} ({a.get('hits_nocov',0)/max(gtok,1)*100:.0f}%) | covering={a.get('cov',0)} ({a.get('cov',0)/max(gtok,1)*100:.0f}%)")
    if a.get('cov'):
        print(f"   covering validated: >=0.9 {a.get('v09',0)} ({a.get('v09',0)/max(gtok,1)*100:.1f}%) >=0.7 {a.get('v07',0)} ({a.get('v07',0)/max(gtok,1)*100:.1f}%) | mean covering gsim={a.get('sim_sum',0)/a.get('sim_n',1):.3f}")
