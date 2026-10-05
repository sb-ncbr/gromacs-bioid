"""N1 P0 live probe — replicate load->repair->analyze->snapshot->signature stage for ONE entry
on v3.124 code in-pod; print per-segment flags, per-generator applicability and
generation outcome/errors for nucleic segments. Measurement only; writes nothing
to campaign data (stdout only). Usage: python3 n1_probe.py EID
"""
import sys, json, traceback
sys.path.insert(0, "/app")
from pathlib import Path

EID = sys.argv[1]
IN_DIR = Path(f"/data/validation/{EID}/input")
ENTRY_CFG = Path(f"/data/validation/{EID}/config.ini")
SHARED_CFG = Path("/data/validation/config_shared.ini")

from src_new.config.loader import RunConfig
from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.loader.strategies import load_simulation
from src_new.loader.repair import TopologyRepair
from src_new.loader.unwrap import PbcRepair
from src_new.loader.universe_facade import LoadedUniverse
from src_new.loader.fragment_store import FragmentStore
from src_new.signatures.registry import get_default_generators
from src_new.signatures.snapshot import build_signature_snapshot

cfg_path = ENTRY_CFG if ENTRY_CFG.exists() else SHARED_CFG
print(f"[probe] eid={EID} config={cfg_path}", flush=True)
config = RunConfig.from_ini_path(cfg_path)

input_cfg_path = IN_DIR / "config.ini"
if input_cfg_path.exists():
    config = RunConfig.from_ini_path(input_cfg_path)
    print(f"[probe] using input/config.ini instead", flush=True)

bundle = inspect_directory(IN_DIR)
decision = select_best_file_combination(bundle)
print(f"[probe] decision={decision}", flush=True)

from src_new.results.results_manager import ResultsManager
rmgr = ResultsManager("/tmp/n1_probe_results.json", "n1_probe")
res = load_simulation(decision, bundle, config, rmgr)
if not res.success:
    print(f"[probe] LOAD FAILED attempts={len(res.attempts)}", flush=True)
    sys.exit(2)
universe = res.universe
print(f"[probe] loaded: strategy={res.final_strategy.value} atoms={universe.atoms.n_atoms}", flush=True)

repair = TopologyRepair(universe, config)
repair_report = repair.run()
print(f"[probe] repair done: {repair_report.to_dict()}", flush=True)

try:
    pbc = PbcRepair(universe, config)
    pbc_report = pbc.run()
    print(f"[probe] pbc: unwrapped={getattr(pbc_report,'unwrapped',None)} jumps={getattr(pbc_report,'jumps_detected',None)} err={getattr(pbc_report,'error',None)}", flush=True)
except Exception as e:
    print(f"[probe] pbc step raised (continuing): {e}", flush=True)

facade = LoadedUniverse(
    universe=universe,
    decision=decision,
    repair_report=repair_report,
    results=rmgr,
    enhanced_nucleic_recognition=(config.signatures.enhanced_nucleic_acid_recognition),
)
store = FragmentStore(facade, rmgr)

segment_to_instance = {}
for inst in store.get_all_instances():
    if inst.segment_ids:
        segment_to_instance.setdefault(inst.segment_ids[0], inst)

generators = get_default_generators(config.signatures)
nuc_segs = 0
for segment_name in sorted(facade.get_segments()):
    props = facade.get_segment_properties(segment_name)
    flags = props.flags
    if not flags.get("is_nucleic"):
        continue
    nuc_segs += 1
    print(f"\n=== SEGMENT {segment_name} flags={json.dumps(flags)}", flush=True)
    print(f"    props: residue_count={props.residue_count} atoms={props.atom_count_fragment} bonds={props.bond_count_fragment}", flush=True)
    inst = segment_to_instance.get(segment_name)
    if inst is None:
        print(f"    !! no MoleculeInstance for {segment_name} -> signatures SKIPPED in pipeline", flush=True)
        continue
    fragment = facade.get_fragment(segment_name)
    try:
        snapshot = build_signature_snapshot(segment_name, fragment, inst, facade)
    except Exception as e:
        print(f"    !! snapshot build failed: {e}", flush=True)
        traceback.print_exc()
        continue
    print(f"    snapshot: atoms={snapshot.atom_count} bonds={len(snapshot.bonds)} "
          f"elements_present={all(e for e in snapshot.elements)} n_empty_elem={sum(1 for e in snapshot.elements if not e)}", flush=True)

    # Faithful worker-path: reconstruct mock objects exactly like _generate_signatures_worker
    from src_new.pipeline_steps.workers import _generate_signatures_worker
    out = _generate_signatures_worker((snapshot.__dict__, config.to_dict()))
    print(f"    worker: attempted={out['attempted']}", flush=True)
    print(f"    worker: generated_keys={sorted((out['generated'] or {}).keys())}", flush=True)
    for err in out.get("errors", []):
        print(f"    ERROR {err['generator']}: {err['error'][:300]}", flush=True)

print(f"\n[probe] nucleic segments probed: {nuc_segs}", flush=True)
