"""N1 cross-class reference scan — per-resolver mol_with_hits by molecule class.
Read-only; same frame as bag_funnel_v11. Counters only."""
import json, os, sys, collections
from multiprocessing import Pool

ROOT="/data/validation"
OUT=f"{ROOT}/n1_xclass_matrix.json"
WATCH={"mmcif_struct","pdb_struct_nucleotide","pdb_struct_protein",
       "blast_pdb_nucleic","blast_pdb_protein","blast_swissprot_protein",
       "blast_uniprot","alphafind_struct","foldseek_3di"}

def scan_one(eid):
    p=os.path.join(ROOT,str(eid),"results.json")
    try:
        with open(p) as fh: d=json.load(fh)
    except Exception:
        return None
    t=d.get("tasks") or {}
    if (t.get("load_simulation") or {}).get("status")!="success": return None
    if (t.get("analyze_universe") or {}).get("status")!="success": return None
    data=d.get("data") or {}
    sigmap=data.get("signatures") or {}
    segs=[s for s,b in sigmap.items() if isinstance(b,dict) and (b.get("generated") or {})]
    if not segs: return None
    idemap=data.get("identifiers") or {}
    usegs=((data.get("universe") or {}).get("segments")) or {}
    out=[]
    for s in segs:
        props=(usegs.get(s) or {}).get("properties") or {}
        cls="protein" if props.get("is_protein") else ("nucleic" if props.get("is_nucleic") else "chem_other")
        att=set(); hit=set()
        for g,rmap in (idemap.get(s) or {}).items():
            if not isinstance(rmap,dict): continue
            for a in (rmap.get("attempted") or []):
                if a in WATCH: att.add(a)
            for rname,blk in rmap.items():
                if rname=="attempted" or not isinstance(blk,dict): continue
                if rname in WATCH and (blk.get("hits") or []): hit.add(rname)
        if att or hit: out.append((cls,sorted(att),sorted(hit)))
    return out

def main():
    lo,hi=(int(x) for x in (sys.argv[1:3] or ["1","14623"]))
    m=collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    mol_tot=collections.Counter()
    with Pool(6) as pool:
        for i,res in enumerate(pool.imap_unordered(scan_one, range(lo,hi+1), chunksize=16),1):
            if res:
                for cls,att,hit in res:
                    mol_tot[cls]+=1
                    for r in att: m[r][cls]["mol_attempted"]+=1
                    for r in hit: m[r][cls]["mol_with_hits"]+=1
            if i%4000==0: print(f"scanned {i}", flush=True)
    out={"molecules_by_class":dict(mol_tot),
         "resolver_class":{r:{c:dict(cnt) for c,cnt in d.items()} for r,d in m.items()}}
    json.dump(out,open(OUT,"w"),indent=2)
    print(json.dumps(out,indent=1))
if __name__=="__main__": main()
