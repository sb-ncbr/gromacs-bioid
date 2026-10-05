import sys, os, traceback
sys.path.insert(0, os.environ.get("BAT3_SRC", "/app"))
from pathlib import Path
FIX = Path(os.environ.get("N1_FIXTURES", "/data/validation/n1_fixtures"))
eid = sys.argv[1]
from src_new.config.loader import RunConfig
from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.loader.strategies import load_simulation
from src_new.loader.repair import TopologyRepair
from src_new.loader.universe_facade import LoadedUniverse
from src_new.loader.fragment_store import FragmentStore
from src_new.signatures.snapshot import build_signature_snapshot
from src_new.pipeline_steps.workers import MockAtomGroup
from src_new.results.results_manager import ResultsManager
from src_new.signatures.generators.pdb import fragment_to_pdb_biopython, fragment_to_pdb_direct
config = RunConfig.from_ini_path(str(FIX / "config_shared.ini"))
tmp = Path("/tmp/n1w3.json"); tmp.unlink(missing_ok=True)
rmgr = ResultsManager(str(tmp), "w3")
ind = FIX / eid / "input"
bundle = inspect_directory(ind); decision = select_best_file_combination(bundle)
res = load_simulation(decision, bundle, config, rmgr)
rr = TopologyRepair(res.universe, config).run()
facade = LoadedUniverse(res.universe, decision, rr, rmgr,
                        enhanced_nucleic_recognition=config.signatures.enhanced_nucleic_acid_recognition)
store = FragmentStore(facade, rmgr)
s2i = {}
for inst in store.get_all_instances():
    if inst.segment_ids: s2i.setdefault(inst.segment_ids[0], inst)
seg = sorted(s for s in facade.get_segments()
             if facade.get_segment_properties(s).flags.get("is_nucleic"))[0]
snap = build_signature_snapshot(seg, facade.get_fragment(seg), s2i[seg], facade)
mf = MockAtomGroup(snap)
print(f"== {eid} {seg} backbone sub-call diagnosis (mock)")
for tag, fn, kw in [
    ("biopython", fragment_to_pdb_biopython, {}),
    ("direct+bonds", fragment_to_pdb_direct, {"include_bonds": True}),
    ("direct-bonds", fragment_to_pdb_direct, {"include_bonds": False}),
]:
    for sel_tag, sel in [("no-selector", None)]:
        try:
            out = fn(mf, True, backbone_selector=sel) if fn is fragment_to_pdb_biopython else fn(mf, True, backbone_selector=sel, **kw)
            print(f"   {tag}: OK {len(out)} chars")
        except Exception:
            tb = traceback.format_exc().strip().splitlines()
            print(f"   {tag}:")
            for line in tb[-5:]: print("      ", line)
# also try the selector actually used

print("== with nucleic backbone_selector")
from src_new.signatures.generators.pdb import select_na_backbone_atom
for tag, fn, kw in [
    ("biopython+sel", fragment_to_pdb_biopython, {}),
    ("direct+bonds+sel", fragment_to_pdb_direct, {"include_bonds": True}),
    ("direct-bonds+sel", fragment_to_pdb_direct, {"include_bonds": False}),
]:
    try:
        out = fn(mf, True, backbone_selector=select_na_backbone_atom, **kw)
        print(f"   {tag}: OK {len(out)} chars")
    except Exception:
        tb = traceback.format_exc().strip().splitlines()
        print(f"   {tag}:")
        for line in tb[-6:]: print("      ", line)
