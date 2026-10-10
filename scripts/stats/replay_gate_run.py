"""Replay one or more stored runs' input through the CURRENT pipeline code.

Gate-1 (replay regression) driver: re-executes build_load_and_export_tasks()
on each run's input/ directory with that run's own config.ini for fidelity
(same resolver/limits as the baseline production run), writing fresh
results.json + exports into a scratch output tree. Originals are NEVER
mutated — inputs are read, outputs go to --out.

Usage (in-pod, repo mounted at /app):
  python /app/scripts/stats/replay_gate_run.py --run /app/runs/<id> --out /data/validation/replay_gate/new/<id>
  python /app/scripts/stats/replay_gate_run.py --runs /data/validation/replay_gate/runs.txt --out-root /data/validation/replay_gate/new

stdout: one COMPACT summary line per run (status, kind, strategy, molecules)
for verdict scripts; full results live in the scratch output tree.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def replay_run(run_dir: Path, out_dir: Path) -> dict:
    """Re-execute the load+export pipeline on run_dir/input -> out_dir."""
    from src_new import PipelineExecutor, ResultsManager, build_load_and_export_tasks
    from src_new.config.loader import RunConfig, load_config_from_path

    out_dir.mkdir(parents=True, exist_ok=True)

    config = None
    for cand in (run_dir / "config.ini", Path("/data/validation/config_shared.ini")):
        if cand.exists():
            config = load_config_from_path(str(cand))
            break
    if config is None:
        config = RunConfig()

    results = ResultsManager(out_dir / "results.json", pipeline_name="replay_gate")
    executor = PipelineExecutor(
        steps=build_load_and_export_tasks(),
        results_manager=results,
        pipeline_name="replay_gate",
    )
    executor.run(
        working_directory=run_dir / "input",
        output_directory=out_dir,
        input_kind=None,
        run_config=config,
    )

    payload = results.as_dict()
    pipe = payload.get("pipeline", {})
    molecules = results.get_data("molecules") or {}
    return {
        "run": run_dir.name,
        "status": pipe.get("status"),
        "input_kind": pipe.get("input_kind"),
        "final_strategy": results.get_data("loading/final_strategy"),
        "attempts": len(results.get_data("loading/attempts") or []),
        "molecules_count": molecules.get("count"),
        "type_counts": molecules.get("type_counts"),
        "results": str(out_dir / "results.json"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="single run dir (contains input/)")
    ap.add_argument("--runs", help="text file with one run dir per line")
    ap.add_argument("--out", help="output dir for --run")
    ap.add_argument("--out-root", help="output root for --runs (per-run subdir)")
    args = ap.parse_args()

    run_dirs: list[Path] = []
    if args.run:
        if not args.out:
            ap.error("--run requires --out")
        run_dirs.append(Path(args.run))
    elif args.runs:
        if not args.out_root:
            ap.error("--runs requires --out-root")
        for line in Path(args.runs).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                run_dirs.append(Path(line))
    else:
        ap.error("give --run or --runs")

    rc = 0
    for run_dir in run_dirs:
        out_dir = (
            Path(args.out) if args.run else Path(args.out_root) / run_dir.name
        )
        try:
            summary = replay_run(run_dir, out_dir)
            print(json.dumps(summary, sort_keys=True))
        except Exception as exc:  # noqa: BLE001 - batch must continue past one bad run
            rc = 1
            print(json.dumps({"run": run_dir.name, "status": "replay_error",
                              "error": f"{type(exc).__name__}: {exc}"}))
            traceback.print_exc(file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
