from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src_new import PipelineExecutor, ResultsManager, Task, TaskResult, file_exists, non_empty_file
from src_new.utils.file_utils import ensure_directory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a small demo for the src_new pipeline backbone.")
    parser.add_argument(
        "--workdir",
        type=Path,
        default=REPO_ROOT / "tmp" / "src_new_backbone_demo",
        help="Directory where demo inputs, outputs, and results.json will be written.",
    )
    parser.add_argument(
        "--input-kind",
        choices=("gromacs", "amber", "pdb_mmcif"),
        default="pdb_mmcif",
        help="Example input kind to register in results.json.",
    )
    return parser.parse_args()


def create_demo_input(workdir: Path) -> Path:
    inputs_dir = ensure_directory(workdir / "inputs")
    input_file = inputs_dir / "structure.pdb"
    if not input_file.exists():
        input_file.write_text(
            "HEADER    DEMO STRUCTURE\n"
            "ATOM      1  C1  DEM A   1       0.000   0.000   0.000\n"
            "END\n",
            encoding="utf-8",
        )
    return input_file


def build_steps() -> list[Task]:
    def check_input(context):
        input_path = Path(context.require_value("input_file"))
        context.record_data("demo/input_file", str(input_path))
        return TaskResult(
            summary={
                "checked": True,
                "input_file": str(input_path),
                "size_bytes": input_path.stat().st_size,
            },
            context_updates={"checked_input_file": str(input_path)},
        )

    def write_intermediate(context):
        input_path = Path(context.require_value("checked_input_file"))
        intermediate_dir = ensure_directory(context.output_directory / "intermediate")
        intermediate_path = intermediate_dir / "fake_mapping.json"
        intermediate_payload = {
            "source_file": str(input_path),
            "source_kind": context.results.as_dict()["pipeline"]["input_kind"],
            "molecule_count": 1,
            "note": "This is a dummy intermediate artifact for the src_new backbone demo.",
        }
        intermediate_path.write_text(json.dumps(intermediate_payload, indent=2) + "\n", encoding="utf-8")
        return TaskResult(
            payload=str(intermediate_path),
            summary={"intermediate_written": True, "path": str(intermediate_path)},
            context_updates={"intermediate_file": str(intermediate_path)},
        )

    def validate_output(context):
        intermediate_path = Path(context.require_value("intermediate_file"))
        payload = json.loads(intermediate_path.read_text(encoding="utf-8"))
        context.record_data("demo/validated_output", str(intermediate_path))
        return TaskResult(
            summary={
                "validated": True,
                "path": str(intermediate_path),
                "keys": sorted(payload.keys()),
            }
        )

    return [
        Task(
            task_id="check_input",
            name="Check Input",
            handler=check_input,
            preconditions=(file_exists(lambda context, result: Path(context.require_value("input_file"))),),
        ),
        Task(
            task_id="write_intermediate",
            name="Write Intermediate",
            handler=write_intermediate,
            requires_tasks=("check_input",),
            output_paths=("intermediate/fake_mapping.json",),
        ),
        Task(
            task_id="validate_output",
            name="Validate Output",
            handler=validate_output,
            requires_tasks=("write_intermediate",),
            postconditions=(non_empty_file(lambda context, result: Path(context.require_value("intermediate_file"))),),
        ),
    ]


def main() -> int:
    args = parse_args()
    workdir = ensure_directory(args.workdir)
    output_dir = ensure_directory(workdir / "outputs")
    input_file = create_demo_input(workdir)
    results_path = workdir / "results.json"

    manager = ResultsManager(results_path, pipeline_name="src_new_backbone_demo")
    steps = build_steps()
    executor = PipelineExecutor(steps=steps, results_manager=manager, pipeline_name="src_new_backbone_demo")

    executor.run(
        initial_state={"input_file": str(input_file)},
        run_metadata={
            "demo": True,
            "description": "Small developer-facing example for the src_new pipeline backbone.",
        },
        input_kind=args.input_kind,
        input_files={"structure": input_file},
        working_directory=workdir,
        output_directory=output_dir,
    )

    payload = manager.as_dict()
    print("Final task statuses:")
    for task_id, task in payload["tasks"].items():
        print(f"  - {task_id}: {task['status']}")

    print(f"results.json: {results_path}")
    print(f"output directory: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
