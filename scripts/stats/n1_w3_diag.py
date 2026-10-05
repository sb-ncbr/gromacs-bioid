"""W3 diagnosis: build mock objects for fixture segments (real snapshots), call
FAILING generators directly, capture real tracebacks (W1 base now re-raises)."""
import sys, os, traceback
sys.path.insert(0, os.environ.get("BAT3_SRC", "/app"))
from pathlib import Path
FIX = Path(os.environ.get("N1_FIXTURES", "/data/validation/n1_fixtures"))

def diag(eid, targets):
    from src_new.config.loader import RunConfig
    from src_new.input.discovery import inspect_directory, select_best_file_combination
    from src_new.loader.strategies import load_simulation
    from src_new.loader.repair import TopologyRepair
    from src_new.loader.universe_facade import LoadedUniverse
    from src_new.loader.fragment_store import FragmentStore
    from src_new.signatures.registry import get_default_generators
    from src_new.signatures.snapshot import build_signature_snapshot
    from src_new.pipeline_steps.workers import MockAtomGroup, _build_mock_facade, _build_mock_instance
    from src_new.results.results_manager import ResultsManager
    config = RunConfig.from_ini_path(str(FIX / "config_shared.ini"))
    tmp = Path("/tmp/n1w3.json"); tmp.unlink(missing_ok=True)
    rmgr = ResultsManager(str(tmp), "w3")
    ind = FIX / eid / "input"
    bundle = inspect_directory(ind); decision = select_best_file_combination(bundle)
    res = load_simulation(decision, bundle, config, rmgr)
    assert res.success
    rr = TopologyRepair(res.universe, config).run()
    facade = LoadedUniverse(res.universe, decision, rr, rmgr,
                            enhanced_nucleic_recognition=config.signatures.enhanced_nucleic_acid_recognition)
    store = FragmentStore(facade, rmgr)
    s2i = {}
    for inst in store.get_all_instances():
        if inst.segment_ids: s2i.setdefault(inst.segment_ids[0], inst)
    gens = {g.name: g for g in get_default_generators(config.signatures)}
    for seg in sorted(facade.get_segments()):
        props = facade.get_segment_properties(seg)
        if not props.flags.get("is_nucleic"): continue
        inst = s2i.get(seg)
        if inst is None: continue
        snap = build_signature_snapshot(seg, facade.get_fragment(seg), inst, facade)
        mf, mfa, mi = MockAtomGroup(snap), _build_mock_facade(snap), _build_mock_instance(snap)
        print(f"== {eid} {seg} (mock path)")
        for name in targets:
            g = gens.get(name)
            if g is None: print(f"   {name}: NOT REGISTERED"); continue
            try:
                if not g.is_applicable(mi, mf, mfa):
                    print(f"   {name}: not applicable"); continue
                out = g.generate(mi, mf, mfa)
                print(f"   {name}: OK ({len(out) if out else 0} chars)")
            except Exception:
                tb = traceback.format_exc().strip().splitlines()
                print(f"   {name} REAL ERROR:")
                for line in tb[-6:]: print(f"      {line}")

if __name__ == "__main__":
    eid = sys.argv[1]
    diag(eid, ["topology_less_pdb", "pdb_backbone_nucleic", "pdb_backbone_not_sanitized_nucleic"])
