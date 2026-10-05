"""W7 identify+verify replay (measurement-only): clone of replay_identify_verify.py
that (a) runs against a SHADOW root (REPLAY_ROOT, no campaign-data mutation),
(b) emits per-entry JSONL deltas covering ALL resolvers (not only chem),
(c) sets config.pdb.curr_uuid=validation-<eid>-<fixed-ts> so the revived RCSB
structure channel exercises its real file-URL path post-W6b.
Usage: n1_w7_replay.py --root /tmp/w7root --entries-file F [--threads N]
"""
import argparse, dataclasses, json, os, sys, time
sys.path.insert(0, "/app")
from src_new.config.loader import RunConfig, load_config_from_path

ROOT = None  # set by main

def _production_config():
    return load_config_from_path("/data/validation/config_shared.ini")

from src_new.results.results_manager import ResultsManager
from src_new.verification.manager import VerificationManager
from src_new.identification.registry import IdentifierRegistry, get_default_resolvers
from src_new.identification.resolution_manager import IdentifierResolutionManager

CHEM = ("PUBCHEM_CID","PUBCHEM_ID","PUBCHEM","INCHIKEY","INCHI_KEY","CHEMBL_ID","CHEBI_ID","SMILES","SELFIES")
TS = "20261003000000"

def _hit_ids(hits):
    out = set()
    for h in hits or []:
        if isinstance(h, dict):
            ident = h.get("identifier") or h.get("id") or ""
        elif isinstance(h, (list, tuple)) and h:
            ident = h[0]
        else:
            ident = h
        out.add(str(ident))
    return out

def _resolver_map(ids):
    """seg -> resolver -> hits list (normalized across schemas)."""
    m = {}
    for seg, gen_map in (ids or {}).items():
        if not isinstance(gen_map, dict): continue
        for gen, rmap in gen_map.items():
            if not isinstance(rmap, dict): continue
            for rname, blk in rmap.items():
                if rname == "attempted" or not isinstance(blk, dict): continue
                hits = blk.get("hits") or blk.get("results") or []
                if hits:
                    m.setdefault(seg, {}).setdefault(rname, []).extend(hits)
    return m

def _rebuild_for(eid, doc):
    if os.path.isdir("/app/databases") and not os.getcwd().startswith("/app"):
        os.chdir("/app")
    payload = json.loads(json.dumps(doc))
    rm = ResultsManager.__new__(ResultsManager)
    rm._payload = payload
    rm._save = lambda: None
    config = _production_config()
    config.pdb.curr_uuid = f"validation-{eid}-{TS}"
    registry = IdentifierRegistry(get_default_resolvers(config))
    mgr = IdentifierResolutionManager(registry, config)
    workdir = os.path.join(ROOT, str(eid))
    os.makedirs(workdir, exist_ok=True)
    mgr.resolve_all(rm, working_directory=workdir)
    new_ids = rm.get_data("identifiers") or {}
    per = VerificationManager(config).verify_all(rm)
    out_ver = {seg: {"verified_hits": [dataclasses.asdict(h) for h in hits]} for seg, hits in per.items()}
    return new_ids, out_ver

def _process_one(eid):
    path = os.path.join(ROOT, str(eid), "results.json")
    try:
        doc = json.load(open(path))
    except Exception as e:
        return {"eid": eid, "err": f"load: {e}"}
    old_ids = (doc.get("data") or {}).get("identifiers") or {}
    old_ver = (doc.get("data") or {}).get("verification") or {}
    try:
        new_ids, new_ver = _rebuild_for(eid, doc)
    except Exception as exc:
        return {"eid": eid, "err": f"{type(exc).__name__}: {str(exc)[:300]}"}
    om, nm = _resolver_map(old_ids), _resolver_map(new_ids)
    res_delta = {}
    for seg in sorted(set(om) | set(nm)):
        for r in sorted(set(om.get(seg, {})) | set(nm.get(seg, {}))):
            o = _hit_ids(om.get(seg, {}).get(r))
            n = _hit_ids(nm.get(seg, {}).get(r))
            gained, lost = sorted(n - o), sorted(o - n)
            if gained or lost:
                res_delta.setdefault(seg, {})[r] = {"gained": gained, "lost": lost, "old_n": len(o), "new_n": len(n)}
    def chem_cand(ids_map):
        n = 0
        for seg in ids_map.values():
            for r, hits in seg.items():
                for h in hits:
                    t = ((h.get("identifier_type") or h.get("type") or h.get("ident_type")) if isinstance(h, dict) else "") or ""
                    if t.upper() in CHEM: n += 1
        return n
    def chem_ver(ver):
        n = 0
        for seg in (ver or {}).values():
            for h in (seg or {}).get("verified_hits") or []:
                if h.get("is_verified") and (h.get("ident_type") or "").upper() in CHEM: n += 1
        return n
    return {"eid": eid, "changed": bool(res_delta), "resolver_delta": res_delta,
            "chem_cand_old": chem_cand(om), "chem_cand_new": chem_cand(nm),
            "chem_ver_old": chem_ver(old_ver), "chem_ver_new": chem_ver(new_ver)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--entries-file", required=True)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    global ROOT
    ROOT = a.root
    entries = [int(x) for x in open(a.entries_file) if x.strip()]
    t0 = time.time()
    from concurrent.futures import ThreadPoolExecutor, as_completed
    n_done = n_err = n_chg = 0
    with open(a.out, "w") as out, ThreadPoolExecutor(max_workers=a.threads) as ex:
        futs = {ex.submit(_process_one, e): e for e in entries}
        for fut in as_completed(futs):
            r = fut.result()
            out.write(json.dumps(r) + "\n"); out.flush()
            n_done += 1
            n_err += 1 if r.get("err") else 0
            n_chg += 1 if r.get("changed") else 0
            if n_done % 25 == 0:
                print(f"[{n_done}/{len(entries)}] chg={n_chg} err={n_err} {time.time()-t0:.0f}s", flush=True)
    print(f"DONE processed={n_done} changed={n_chg} errors={n_err} {time.time()-t0:.0f}s out={a.out}", flush=True)

if __name__ == "__main__":
    main()
