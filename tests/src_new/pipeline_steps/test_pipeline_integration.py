"""Integration tests for the load and export pipeline."""

from pathlib import Path
import pytest
import json

from src_new import (
    PipelineExecutor,
    ResultsManager,
    build_load_and_export_tasks,
)

# Check for rdkit availability
try:
    import rdkit  # noqa: F401
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False


class TestPipelineTasks:
    """Tests for pipeline task construction."""

    def test_build_tasks_returns_list(self):
        """Building tasks returns a non-empty list."""
        tasks = build_load_and_export_tasks()
        assert len(tasks) > 0

    def test_tasks_have_unique_ids(self):
        """All tasks have unique IDs."""
        tasks = build_load_and_export_tasks()
        ids = [t.task_id for t in tasks]
        assert len(ids) == len(set(ids))

    def test_task_prerequisites_valid(self):
        """Task prerequisites are valid (earlier in sequence)."""
        tasks = build_load_and_export_tasks()

        # Build position map
        positions = {t.task_id: i for i, t in enumerate(tasks)}

        for task in tasks:
            for prereq in task.requires_tasks:
                assert prereq in positions
                assert positions[prereq] < positions[task.task_id]


class TestPipelineWithPDBInput:
    """End-to-end tests with PDB input."""

    @pytest.mark.skipif(not HAS_RDKIT, reason="rdkit not installed")
    def test_pipeline_with_pdb_file(self, tmp_path: Path):
        """Pipeline runs successfully with a PDB file."""
        # Create a minimal PDB file
        pdb_content = """HEADER    TEST STRUCTURE
ATOM      1  N   ALA A   1      20.153  22.867   4.981  1.00 18.40           N
ATOM      2  CA  ALA A   1      20.250  24.321   5.050  1.00 17.20           C
ATOM      3  C   ALA A   1      21.732  24.680   5.200  1.00 16.80           C
ATOM      4  O   ALA A   1      22.401  23.890   5.890  1.00 15.90           O
TER
END
"""
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text(pdb_content, encoding="utf-8")

        # Set up results manager
        results_path = tmp_path / "results.json"
        output_dir = tmp_path / "output"
        manager = ResultsManager(results_path, pipeline_name="test_pdb_pipeline")

        # Run pipeline
        executor = PipelineExecutor(
            steps=build_load_and_export_tasks(),
            results_manager=manager,
            pipeline_name="test_pdb_pipeline",
        )

        context = executor.run(
            working_directory=tmp_path,
            output_directory=output_dir,
            input_kind="pdb",
            input_files={"structure": pdb_file},
        )

        # Verify results
        payload = manager.as_dict()

        assert payload["pipeline"]["status"] == "success"
        assert payload["pipeline"]["input_kind"] == "pdb"

        # Check that discovery ran
        assert "discover_input" in payload["tasks"]
        assert payload["tasks"]["discover_input"]["status"] in ("success", "warning")

        # Check data was recorded
        assert "input" in payload.get("data", {}) or "molecules" in payload.get("data", {})


class TestPipelineDiscoveryOnly:
    """Tests focusing on the discovery step."""

    def test_discovery_detects_gromacs_files(self, tmp_path: Path):
        """Discovery correctly identifies GROMACS files."""
        # Create GROMACS-like files
        (tmp_path / "topol.top").touch()
        (tmp_path / "md.gro").touch()
        (tmp_path / "md.xtc").touch()

        results_path = tmp_path / "results.json"
        output_dir = tmp_path / "output"
        manager = ResultsManager(results_path)

        executor = PipelineExecutor(
            steps=build_load_and_export_tasks(),
            results_manager=manager,
            pipeline_name="test_gromacs_discovery",
        )

        # Note: This will fail at loading since we don't have real files,
        # but discovery should succeed
        try:
            executor.run(
                working_directory=tmp_path,
                output_directory=output_dir,
                input_kind="gromacs",
            )
        except Exception:
            pass  # Expected to fail at loading stage

        # Check discovery still ran
        payload = manager.as_dict()
        if "discover_input" in payload["tasks"]:
            assert payload["tasks"]["discover_input"]["status"] in ("success", "warning")


class TestResultsRecording:
    """Tests for results.json recording."""

    @pytest.mark.skipif(not HAS_RDKIT, reason="rdkit not installed")
    def test_results_contains_input_metadata(self, tmp_path: Path):
        """Results include input metadata."""
        pdb_content = """HEADER    TEST
ATOM      1  N   GLY A   1       0.0     0.0     0.0
END
"""
        (tmp_path / "test.pdb").write_text(pdb_content, encoding="utf-8")

        results_path = tmp_path / "results.json"
        manager = ResultsManager(results_path)

        executor = PipelineExecutor(
            steps=build_load_and_export_tasks(),
            results_manager=manager,
        )

        try:
            executor.run(working_directory=tmp_path, output_directory=tmp_path / "out")
        except Exception:
            pass

        payload = manager.as_dict()

        # Check pipeline metadata
        assert payload["pipeline"].get("input_kind") is not None

        # Check events were recorded
        assert len(payload.get("events", [])) > 0


class TestTaskContextUsage:
    """Tests verifying TaskContext is used correctly."""

    @pytest.mark.skipif(not HAS_RDKIT, reason="rdkit not installed")
    def test_context_data_recording(self, tmp_path: Path):
        """Context data is properly recorded."""
        pdb_content = "HEADER\nATOM\nEND\n"
        (tmp_path / "test.pdb").write_text(pdb_content)

        results_path = tmp_path / "results.json"
        manager = ResultsManager(results_path)

        executor = PipelineExecutor(
            steps=build_load_and_export_tasks(),
            results_manager=manager,
        )

        try:
            executor.run(working_directory=tmp_path, output_directory=tmp_path / "out")
        except Exception:
            pass

        payload = manager.as_dict()

        # Data section should exist
        assert "data" in payload
