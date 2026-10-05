"""N1 gate runner (no pytest dep) — mirrors tests/n1_wave/test_golden_parity.py.
Usage in-pod: python3 n1_run_gates.py [eid,...]  (default all 10)
Env: N1_FIXTURES, N1_GOLDEN, N1_ALLOW_DELTA, BAT3_SRC (default /app)."""
import json, os, sys, hashlib
from pathlib import Path

FIX = Path(os.environ.get("N1_FIXTURES", "/data/validation/n1_fixtures"))
GOLDEN = Path(os.environ.get("N1_GOLDEN", "/data/validation/n1_golden"))
ALLOW = Path(os.environ.get("N1_ALLOW_DELTA", "/data/validation/n1_allow_delta.json"))
EIDS = sys.argv[1].split(",") if len(sys.argv) > 1 else \
    ["4653", "1682", "1602", "1920", "1549", "1553", "1567", "4725", "1089", "6250"]
sys.path.insert(0, os.environ.get("BAT3_SRC", "/app"))

def probe(eid):
    from src_new.config.loader import RunConfig
    from src_new.input.discovery import inspect_directory, select_best_file_combination
    from src_new.loader.strategies import load_simulation
    from src_new.loader.repair import TopologyRepair
    from src_new.loader.universe_facade import LoadedUniverse
    from src_new.loader.fragment_store import FragmentStore
    from src_new.signatures.snapshot import build_signature_snapshot
    from src_new.pipeline_steps.workers import _generate_signatures_worker
    from src_new.results.results_manager import ResultsManager
    config = RunConfig.from_ini_path(str(FIX / "config_shared.ini"))
    ind = FIX / eid / "input"
    tmp = Path("/tmp/n1gate_rm.json")
    if tmp.exists(): tmp.unlink()
    rmgr = ResultsManager(str(tmp), "n1gate")
    bundle = inspect_directory(ind)
    decision = select_best_file_combination(bundle)
    res = load_simulation(decision, bundle, config, rmgr)
    assert res.success, f"load failed {eid}"
    rr = TopologyRepair(res.universe, config).run()
    facade = LoadedUniverse(universe=res.universe, decision=decision, repair_report=rr,
                            results=rmgr,
                            enhanced_nucleic_recognition=config.signatures.enhanced_nucleic_acid_recognition)
    store = FragmentStore(facade, rmgr)
    s2i = {}
    for inst in store.get_all_instances():
        if inst.segment_ids: s2i.setdefault(inst.segment_ids[0], inst)
    out = {}
    for seg in sorted(facade.get_segments()):
        props = facade.get_segment_properties(seg)
        row = {"flags": dict(props.flags), "residue_count": props.residue_count,
               "atom_count": props.atom_count_fragment}
        inst = s2i.get(seg)
        if inst is None:
            row["no_instance"] = True
        else:
            snap = build_signature_snapshot(seg, facade.get_fragment(seg), inst, facade)
            w = _generate_signatures_worker((snap.__dict__, config.to_dict()))
            row["attempted"] = w.get("attempted")
            gen = {}
            for k, v in sorted((w.get("generated") or {}).items()):
                s = v if isinstance(v, str) else json.dumps(v, default=str)
                if len(s) <= 20_000:
                    gen[k] = {"kind": "full", "text": s}
                else:
                    gen[k] = {"kind": "hash", "sha256": hashlib.sha256(s.encode()).hexdigest(),
                              "len": len(s), "head": s[:500]}
            row["generated"] = gen
            row["errors"] = [f"{e['generator']}: {e['error'][:200]}" for e in w.get("errors", [])]
        out[seg] = row
    return out

allow = json.loads(ALLOW.read_text()) if ALLOW.exists() else {}
fails = 0
for eid in EIDS:
    golden = json.loads((GOLDEN / f"{eid}.sig.golden.json").read_text())
    pr = probe(eid)
    al = allow.get(eid, {})
    diffs = []
    for seg, g in golden["segments"].items():
        p = pr.get(seg)
        if p is None:
            diffs.append(f"seg {seg} MISSING"); continue
        gg, pg = g.get("generated", {}), p.get("generated", {})
        for key in sorted(set(gg) | set(pg)):
            if al.get(f"{seg}|{key}") == "any": continue
            if gg.get(key) != pg.get(key):
                diffs.append(f"{seg}/{key} MISMATCH g={str(gg.get(key))[:60]} p={str(pg.get(key))[:60]}")
        for f in ("attempted","flags","residue_count","atom_count","errors"):
            if g.get(f) != p.get(f) and al.get(f"{seg}|@{f}") != "any":
                diffs.append(f"{seg}/@{f} MISMATCH")
    for seg in set(pr)-set(golden["segments"]):
        if al.get(f"{seg}|*") != "any": diffs.append(f"NEW seg {seg}")
    if diffs:
        fails += 1
        print(f"FAIL {eid}: {len(diffs)} diffs")
        for d in diffs[:12]: print("   ", d)
    else:
        print(f"PASS {eid}")
print(f"GATE_RESULT: {'GREEN' if fails==0 else f'RED ({fails}/{len(EIDS)})'}")
sys.exit(1 if fails else 0)
