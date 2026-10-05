"""W0 fixture trim: frame-0 XTC for oversized entries + SIGNATURE PARITY VERIFICATION.
Never touches /data/validation/<eid> (campaign data). Works only on n1_fixtures staging.
For each oversized entry: write trajectory.xtc with frame 0 only (remove offsets cache),
then run probe (load->repair->facade->signatures) on TRIMMED staging copy AND on ORIGINAL
campaign dir; compare per-segment signature payload hashes. Mismatch => keep untrimmed."""
import sys, os, json, hashlib, shutil, subprocess
sys.path.insert(0,"/app")

OVERSIZE={"1682","1920","1567","1089"}
STAG="/data/validation/n1_fixtures"

def trim(eid):
    ind=f"{STAG}/{eid}/input"
    xtc=f"{ind}/trajectory.xtc"
    bak=f"{ind}/trajectory.full.xtc"
    if not os.path.exists(bak):
        shutil.move(xtc,bak)
    import MDAnalysis as mda
    u=mda.Universe(f"{ind}/topology.prmtop", bak)
    with mda.Writer(xtc, u.atoms.n_atoms) as W:
        W.write(u.atoms[:])  # frame 0 only (universe positioned at ts[0] on load)
    off=f"{ind}/.trajectory.xtc_offsets.npz"
    if os.path.exists(off): os.remove(off)
    print(f"[trim] {eid}: {os.path.getsize(bak)} -> {os.path.getsize(xtc)} bytes", flush=True)

def sig_hashes(input_dir):
    """Run probe machinery, return {seg:{gen:{sig:sha256}}} + flags."""
    from pathlib import Path
    from src_new.config.loader import RunConfig
    from src_new.input.discovery import inspect_directory, select_best_file_combination
    from src_new.loader.strategies import load_simulation
    from src_new.loader.repair import TopologyRepair
    from src_new.loader.universe_facade import LoadedUniverse
    from src_new.loader.fragment_store import FragmentStore
    from src_new.signatures.registry import get_default_generators
    from src_new.signatures.snapshot import build_signature_snapshot
    from src_new.pipeline_steps.workers import _generate_signatures_worker
    from src_new.results.results_manager import ResultsManager
    tmp="/tmp/n1trim_rm.json"
    if os.path.exists(tmp): os.remove(tmp)
    rmgr=ResultsManager(tmp,"n1trim")
    config=RunConfig.from_ini_path("/data/validation/config_shared.ini")
    bundle=inspect_directory(Path(input_dir))
    decision=select_best_file_combination(bundle)
    res=load_simulation(decision,bundle,config,rmgr)
    assert res.success, f"load failed {input_dir}"
    rr=TopologyRepair(res.universe,config).run()
    facade=LoadedUniverse(universe=res.universe,decision=decision,repair_report=rr,results=rmgr,
                          enhanced_nucleic_recognition=config.signatures.enhanced_nucleic_acid_recognition)
    store=FragmentStore(facade,rmgr)
    s2i={}
    for inst in store.get_all_instances():
        if inst.segment_ids: s2i.setdefault(inst.segment_ids[0],inst)
    out={}
    for seg in sorted(facade.get_segments()):
        props=facade.get_segment_properties(seg)
        inst=s2i.get(seg)
        row={"flags":{k:v for k,v in props.flags.items()},"rc":props.residue_count,"gen":{},"errors":[]}
        if inst is None:
            row["errors"].append("no_instance"); out[seg]=row; continue
        snap=build_signature_snapshot(seg,facade.get_fragment(seg),inst,facade)
        w=_generate_signatures_worker((snap.__dict__,config.to_dict()))
        for k,v in (w.get("generated") or {}).items():
            row["gen"][k]=hashlib.sha256(str(v).encode()).hexdigest()[:16]
        row["attempted"]=w.get("attempted")
        row["errors"]=[f"{e['generator']}:{e['error'][:60]}" for e in w.get("errors",[])]
        out[seg]=row
    return out

if __name__=="__main__":
    eid=sys.argv[1]
    mode=sys.argv[2] if len(sys.argv)>2 else "all"
    if mode in ("all","trim"): trim(eid)
    if mode in ("all","verify"):
        orig=sig_hashes(f"/data/validation/{eid}/input")
        trimd=sig_hashes(f"{STAG}/{eid}/input")
        same=(orig==trimd)
        print(f"[verify] {eid} parity={same}", flush=True)
        if not same:
            for seg in sorted(set(orig)|set(trimd)):
                if orig.get(seg)!=trimd.get(seg):
                    print(f"  DIFF seg={seg}\n   orig={json.dumps(orig.get(seg))[:300]}\n   trim={json.dumps(trimd.get(seg))[:300]}", flush=True)
        print(f"[result] {eid} {'KEEP_TRIMMED' if same else 'REVERT_TO_FULL'}", flush=True)
