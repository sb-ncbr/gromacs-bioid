"""W0.4 harness — N1 fix-wave gates (pytest). Runs where MDAnalysis/RDKit/BLAST
exist (worker image pod; see scripts/run_n1_gates.sh). NOT vanilla-CI-safe.

Gates:
  test_sig_golden_parity   INV-1/INV-2: signature outputs on fixtures equal
                           goldens harvested on v3.124 (byte/hash level),
                           except deltas explicitly allowlisted per workstream
                           (GOLDEN_ALLOW_DELTA in tests/n1_wave/allow_delta.json).
  test_ident_golden_parity same for identification controls.

Golden update discipline: goldens never "regenerated" during the wave except by
explicit wave-step commits that also update allow_delta.json with rationale.
"""
import json, os, sys, hashlib
from pathlib import Path

import pytest

FIX = Path(os.environ.get("N1_FIXTURES", "tests/fixtures/n1"))
GOLDEN = Path(os.environ.get("N1_GOLDEN", "tests/fixtures/n1/golden"))
ALLOW_PATH = Path(os.environ.get("N1_ALLOW_DELTA", "tests/n1_wave/allow_delta.json"))

EIDS = ["4653", "1682", "1602", "1920", "1549", "1553", "1567", "4725", "1089", "6250"]
IDENT_CONTROLS = ["1089", "6250", "1549", "1553", "1602", "1920", "4653", "1682", "1567", "4725"]

sys.path.insert(0, os.environ.get("BAT3_SRC", "/app"))

pytestmark = pytest.mark.skipif(not (FIX / "config_shared.ini").exists(),
                                reason="N1 fixtures not present")


def _load_allow():
    if ALLOW_PATH.exists():
        return json.loads(ALLOW_PATH.read_text())
    return {}


def _probe_fixture(eid: str):
    """Run load->repair->facade->snap->sig-worker for a fixture; canonical dict."""
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
    if tmp.exists():
        tmp.unlink()
    rmgr = ResultsManager(str(tmp), "n1gate")
    bundle = inspect_directory(ind)
    decision = select_best_file_combination(bundle)
    res = load_simulation(decision, bundle, config, rmgr)
    assert res.success, f"load failed for fixture {eid}"
    rr = TopologyRepair(res.universe, config).run()
    facade = LoadedUniverse(
        universe=res.universe, decision=decision, repair_report=rr, results=rmgr,
        enhanced_nucleic_recognition=config.signatures.enhanced_nucleic_acid_recognition)
    store = FragmentStore(facade, rmgr)
    s2i = {}
    for inst in store.get_all_instances():
        if inst.segment_ids:
            s2i.setdefault(inst.segment_ids[0], inst)
    out = {"segments": {}}
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
        out["segments"][seg] = row
    return out


def _canon_sig(probe: dict) -> dict:
    return {"segments": probe["segments"]}


@pytest.mark.parametrize("eid", EIDS)
def test_sig_golden_parity(eid):
    golden_path = GOLDEN / f"{eid}.sig.golden.json"
    assert golden_path.exists(), f"missing golden for {eid}"
    golden = json.loads(golden_path.read_text())
    probe = _canon_sig(_probe_fixture(eid))
    allow = _load_allow().get(eid, {})
    diffs = []
    for seg, g in golden["segments"].items():
        p = probe["segments"].get(seg)
        if p is None:
            diffs.append(f"{eid}/{seg}: segment MISSING in probe")
            continue
        # payload-level comparison (resilient to ordering)
        g_gen, p_gen = g.get("generated", {}), p.get("generated", {})
        for key in sorted(set(g_gen) | set(p_gen)):
            aseg = allow.get(f"{seg}|{key}")
            if aseg == "any":
                continue
            gv, pv = g_gen.get(key), p_gen.get(key)
            if gv != pv:
                diffs.append(f"{eid}/{seg}/{key}: MISMATCH "
                             f"(golden={str(gv)[:80]} vs probe={str(pv)[:80]})")
        for field in ("attempted", "flags", "residue_count", "atom_count", "errors"):
            if g.get(field) != p.get(field) and allow.get(f"{seg}|@{field}") != "any":
                diffs.append(f"{eid}/{seg}/@{field}: MISMATCH")
    extra = set(probe["segments"]) - set(golden["segments"])
    for seg in extra:
        if allow.get(f"{seg}|*") != "any":
            diffs.append(f"{eid}/{seg}: NEW segment in probe")
    assert not diffs, "\n" + "\n".join(diffs[:25])
