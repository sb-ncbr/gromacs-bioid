"""W0.2 golden harvest — run CURRENT v3.124 pipeline pieces on frozen N1 fixtures
and dump parity references used by every gate in the N1 fix wave.

Per fixture entry:
  sig golden     (all entries): per-segment flags/attempted/generated payloads
                  (full if <=20k chars else sha256+len+head) + worker errors
  ident golden   (control entries): resolver -> sorted hit identifiers per
                  segment (covers INV-1/INV-2 for W5 changes; NA blast
                  positives 1549/1553, shorts 1602/1920, protein 1089, chem 6250)

Usage (in pod, v3.124 code): python3 n1_golden_harvest.py FIXTURES_DIR OUT_DIR
Writes OUT_DIR/<eid>.sig.golden.json and OUT_DIR/<eid>.ident.golden.json
"""
import sys, os, json, hashlib, time
sys.path.insert(0, "/app")
from pathlib import Path

FIX = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/data/validation/n1_fixtures")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/data/validation/n1_golden")
OUT.mkdir(parents=True, exist_ok=True)

IDENT_CONTROLS = {"1089", "6250", "1549", "1553", "1602", "1920", "4653", "1682", "1567", "4725"}
PAY_FULL = 20_000

from src_new.config.loader import RunConfig
from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.loader.strategies import load_simulation
from src_new.loader.repair import TopologyRepair
from src_new.loader.universe_facade import LoadedUniverse
from src_new.loader.fragment_store import FragmentStore
from src_new.signatures.registry import get_default_generators
from src_new.signatures.snapshot import build_signature_snapshot
from src_new.pipeline_steps.workers import _generate_signatures_worker, _identify_molecules_worker
from src_new.results.results_manager import ResultsManager


def pack_payload(v):
    s = v if isinstance(v, str) else json.dumps(v, default=str)
    if len(s) <= PAY_FULL:
        return {"kind": "full", "text": s}
    return {"kind": "hash", "sha256": hashlib.sha256(s.encode()).hexdigest(),
            "len": len(s), "head": s[:500]}


def load_facade(input_dir: Path, config):
    tmp = "/tmp/n1golden_rm.json"
    if os.path.exists(tmp):
        os.remove(tmp)
    rmgr = ResultsManager(tmp, "n1golden")
    bundle = inspect_directory(input_dir)
    decision = select_best_file_combination(bundle)
    res = load_simulation(decision, bundle, config, rmgr)
    if not res.success:
        raise RuntimeError(f"load failed: {input_dir}")
    rr = TopologyRepair(res.universe, config).run()
    facade = LoadedUniverse(
        universe=res.universe, decision=decision, repair_report=rr, results=rmgr,
        enhanced_nucleic_recognition=config.signatures.enhanced_nucleic_acid_recognition)
    store = FragmentStore(facade, rmgr)
    s2i = {}
    for inst in store.get_all_instances():
        if inst.segment_ids:
            s2i.setdefault(inst.segment_ids[0], inst)
    return facade, store, s2i


def main():
    config = RunConfig.from_ini_path(str(FIX / "config_shared.ini")) if (FIX / "config_shared.ini").exists() \
        else RunConfig.from_ini_path("/data/validation/config_shared.ini")
    eids = sys.argv[3].split(",") if len(sys.argv) > 3 else \
        sorted(d.name for d in FIX.iterdir() if d.is_dir() and (d / "input").is_dir())
    for eid in eids:
        t0 = time.time()
        ind = FIX / eid / "input"
        facade, store, s2i = load_facade(ind, config)
        segs = sorted(facade.get_segments())
        sig_out = {"eid": eid, "code": "v3.124-golden", "segments": {}}
        for seg in segs:
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
                row["generated"] = {k: pack_payload(v) for k, v in sorted((w.get("generated") or {}).items())}
                row["errors"] = [f"{e['generator']}: {e['error'][:200]}" for e in w.get("errors", [])]
            sig_out["segments"][seg] = row
        (OUT / f"{eid}.sig.golden.json").write_text(json.dumps(sig_out, indent=1))
        print(f"[golden] {eid} sig: {len(segs)} segs ({time.time()-t0:.0f}s)", flush=True)

        if eid in IDENT_CONTROLS:
            ident_out = {"eid": eid, "code": "v3.124-golden", "segments": {}}
            from src_new.signatures.registry import get_signature_type_map
            st_map = get_signature_type_map(config.signatures)
            for seg in segs:
                row = sig_out["segments"][seg]
                if row.get("no_instance"):
                    continue
                sigs = {k: (v["text"] if v["kind"] == "full" else None)
                        for k, v in row["generated"].items()}
                # hashed payloads not needed for ident pass; skip None
                sigs = {k: v for k, v in sigs.items() if v is not None}
                if not sigs:
                    continue
                w = _identify_molecules_worker((seg, sigs, config.to_dict(), st_map))
                flat = w.get("results", {})
                res_map = {}
                for path_key, val in flat.items():
                    parts = path_key.split("/")
                    # shape: identifiers/{frag}/{generator}/{resolver} -> {"hits": [...]}
                    if len(parts) == 4 and parts[0] == "identifiers" and isinstance(val, dict):
                        hits = val.get("hits") or []
                        if not hits:
                            continue
                        gen_name, resolver = parts[2], parts[3]
                        ids = sorted(str(h.get("identifier", h)) if isinstance(h, dict) else str(h)
                                     for h in hits)
                        res_map[f"{gen_name}|{resolver}"] = {
                            "count": len(ids), "ids": ids[:50],
                            "hit_type": val.get("hit_type")}
                ident_out["segments"][seg] = {"resolver_hits": res_map,
                                              "errors": [f"{e['resolver']}:{e.get('generator','')}:{e['error'][:150]}"
                                                         for e in (w.get("errors") or [])][:20]}
            (OUT / f"{eid}.ident.golden.json").write_text(json.dumps(ident_out, indent=1))
            print(f"[golden] {eid} ident done ({time.time()-t0:.0f}s)", flush=True)
    print("[golden] ALL DONE", flush=True)


if __name__ == "__main__":
    main()
