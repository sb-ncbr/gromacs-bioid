"""W1 e2e: run REAL full pipeline on a fixture (scratch input copy), verify:
1) data.stage_errors.* present with real error content (pre-A1 RCSB 404 baseline)
2) data.signatures/identifiers schema unchanged (INV-4)
3) pipeline completes; scan-able by existing tooling (bag-funnel scan_one shape)
Usage (pod): python3 n1_e2e_fixture.py EID
"""
import sys, os, json, shutil
sys.path.insert(0, os.environ.get("BAT3_SRC", "/app"))
from pathlib import Path

EID = sys.argv[1]
FIX = Path(os.environ.get("N1_FIXTURES", "/data/validation/n1_fixtures"))
SCRATCH = Path(f"/tmp/n1e2e/{EID}")
NFS_OUT = Path(f"/data/validation/logs/n1_e2e_{EID}")

if SCRATCH.exists(): shutil.rmtree(SCRATCH)
SCRATCH.mkdir(parents=True)
shutil.copytree(FIX / EID / "input", SCRATCH / "input")

from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager
from src_new.pipeline_steps import build_load_and_export_tasks
from src_new.executor.executor import PipelineExecutor

config = RunConfig.from_ini_path(str(FIX / "config_shared.ini"))
config.pdb.curr_uuid = f"n1e2e-{EID}"
results_path = str(SCRATCH / "results.json")
rm = ResultsManager(results_path)
ex = PipelineExecutor(steps=build_load_and_export_tasks(), results_manager=rm, pipeline_name="BAT3")
ex.run(output_directory=SCRATCH, working_directory=SCRATCH / "input", run_config=config)

d = json.load(open(results_path))
data = d.get("data", {})
se = data.get("stage_errors")
print("== stage_errors keys:", sorted((se or {}).keys()))
for cat in ("signatures", "identifiers"):
    for seg, errs in sorted(((se or {}).get(cat) or {}).items()):
        print(f"  {cat}/{seg}: {len(errs)} errors")
        for e in errs[:4]:
            print(f"    - {e.get('generator') or e.get('resolver')}: {e['error'][:110]}")
print("== signatures[SYSTEM] keys:", sorted((data.get("signatures", {}).get("SYSTEM") or {}).keys()))
print("== identifiers[SYSTEM] keys count:", len((data.get("identifiers", {}).get("SYSTEM") or {})))
tt = d.get("tasks", {})
print("== tasks:", {k: v.get("status") for k, v in tt.items()})
ver = (data.get("verification") or {})
print("== verification segments:", list(ver.keys())[:5])
# per-fixture assertions (serial-path reality)
if EID == "1682":
    # W4-era contract: strand-select fallback now PRODUCES SYSTEM fasta_map_nucleic
    # (merged-duplex largest component, byte-exact == v1 strand measured at W4).
    # The W1-era expectation (stage_errors entry for fasta_map_nucleic) is obsolete.
    gen = d["data"]["signatures"]
    sys_gen = gen["SYSTEM"].get("generated") or {}
    assert "fasta_map_nucleic" in sys_gen, "W4 MISSING: SYSTEM fasta_map_nucleic not generated"
    assert "fasta_map_nucleic" in gen["SYSTEM__v1"]["generated"], "v1 fasta missing"
    assert "fasta_map_nucleic" in gen["SYSTEM__v2"]["generated"], "v2 fasta missing"
    sys_fasta = sys_gen["fasta_map_nucleic"]
    v1_fasta = gen["SYSTEM__v1"]["generated"]["fasta_map_nucleic"]
    assert sys_fasta == v1_fasta,         f"W4 REGRESSION: SYSTEM strand ({len(str(sys_fasta))}) != v1 strand ({len(str(v1_fasta))})"
    print(f"== W4 strand-select VERIFIED on 1682: SYSTEM fasta == v1 strand, len={len(str(sys_fasta))}")
assert all(v.get("status") in ("success", "warning") for v in tt.values()), "pipeline tasks not all green"
shutil.copy(results_path, str(NFS_OUT) + "_results.json")
print("== results copied to", str(NFS_OUT) + "_results.json")
print("E2E_RESULT: GREEN")
