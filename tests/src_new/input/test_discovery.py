"""Tests for input discovery."""

from pathlib import Path
import pytest
import tempfile

from src_new.input.models import InputKind, FileRecord, InputBundle, LoadDecision
from src_new.input.discovery import (
    discover_input_kind,
    inspect_directory,
    select_best_file_combination,
)


class TestDiscoverInputKind:
    """Tests for input kind detection."""

    def test_detect_gromacs_tpr(self, tmp_path: Path):
        """Detect GROMACS from TPR file."""
        (tmp_path / "simulation.tpr").touch()
        result = discover_input_kind(tmp_path)
        assert result == InputKind.GROMACS

    def test_detect_gromacs_top_gro(self, tmp_path: Path):
        """Detect GROMACS from TOP + GRO files."""
        (tmp_path / "topol.top").touch()
        (tmp_path / "structure.gro").touch()
        result = discover_input_kind(tmp_path)
        assert result == InputKind.GROMACS

    def test_detect_amber_prmtop(self, tmp_path: Path):
        """Detect AMBER from PRMTOP file."""
        (tmp_path / "system.prmtop").touch()
        result = discover_input_kind(tmp_path)
        assert result == InputKind.AMBER

    def test_detect_amber_parm7_nc(self, tmp_path: Path):
        """Detect AMBER from PARM7 + NC files."""
        (tmp_path / "system.parm7").touch()
        (tmp_path / "trajectory.nc").touch()
        result = discover_input_kind(tmp_path)
        assert result == InputKind.AMBER

    def test_detect_pdb(self, tmp_path: Path):
        """Detect PDB structure."""
        (tmp_path / "structure.pdb").touch()
        result = discover_input_kind(tmp_path)
        assert result == InputKind.PDB

    def test_detect_mmcif(self, tmp_path: Path):
        """Detect mmCIF structure."""
        (tmp_path / "structure.cif").touch()
        result = discover_input_kind(tmp_path)
        assert result == InputKind.MMCIF

    def test_no_recognized_files(self, tmp_path: Path):
        """Return None when no recognized files present."""
        (tmp_path / "random.txt").touch()
        result = discover_input_kind(tmp_path)
        assert result is None

    def test_not_a_directory(self):
        """Return None for non-directory path."""
        result = discover_input_kind(Path("/nonexistent/path"))
        assert result is None


class TestInspectDirectory:
    """Tests for directory inspection."""

    def test_inspect_empty_directory(self, tmp_path: Path):
        """Empty directory produces empty bundle."""
        bundle = inspect_directory(tmp_path)
        assert bundle.root_directory == tmp_path
        assert len(bundle.files) == 0

    def test_inspect_with_pdb(self, tmp_path: Path):
        """PDB file is recorded in bundle."""
        pdb_file = tmp_path / "structure.pdb"
        pdb_file.write_text("HEADER test\nATOM\nEND\n")

        bundle = inspect_directory(tmp_path)
        assert len(bundle.files) == 1
        assert bundle.files[0].file_type == "PDB"
        assert bundle.files[0].role == "structure"

    def test_inspect_with_gromacs_files(self, tmp_path: Path):
        """GROMACS files are correctly identified."""
        (tmp_path / "topol.top").touch()
        (tmp_path / "md.gro").touch()
        (tmp_path / "md.xtc").touch()

        bundle = inspect_directory(tmp_path)
        file_types = {f.file_type for f in bundle.files}

        assert "GROMACS_TOP" in file_types
        assert "GROMACS_GRO" in file_types
        assert "GROMACS_XTC" in file_types

    def test_inspect_computes_checksums(self, tmp_path: Path):
        """File checksums are computed."""
        pdb_file = tmp_path / "structure.pdb"
        pdb_file.write_text("test content", encoding="utf-8")

        bundle = inspect_directory(tmp_path)
        assert bundle.files[0].checksum is not None
        assert len(bundle.files[0].checksum) == 64  # SHA256 hex length


class TestSelectBestFileCombination:
    """Tests for file combination selection."""

    def test_select_tpr_only(self, tmp_path: Path):
        """TPR-only strategy selected when only TPR present."""
        tpr_file = tmp_path / "simulation.tpr"
        tpr_file.touch()

        bundle = inspect_directory(tmp_path)
        decision = select_best_file_combination(bundle)

        assert decision.input_kind == InputKind.GROMACS
        assert decision.selected_strategy == "TPR_ONLY"

    def test_select_top_gro(self, tmp_path: Path):
        """TOP+GRO strategy selected when both present."""
        (tmp_path / "topol.top").touch()
        (tmp_path / "md.gro").touch()

        bundle = inspect_directory(tmp_path)
        decision = select_best_file_combination(bundle)

        assert decision.input_kind == InputKind.GROMACS
        assert decision.selected_strategy == "TOP_GRO"

    def test_select_itp_gro(self, tmp_path: Path):
        """ITP+GRO strategy selected when ITP present."""
        (tmp_path / "molecule.itp").touch()
        (tmp_path / "md.gro").touch()

        bundle = inspect_directory(tmp_path)
        decision = select_best_file_combination(bundle)

        assert decision.input_kind == InputKind.GROMACS
        assert decision.selected_strategy == "ITP_GRO"

    def test_select_prmtop_nc(self, tmp_path: Path):
        """PRMTOP+NC strategy selected for AMBER."""
        (tmp_path / "system.prmtop").touch()
        (tmp_path / "trajectory.nc").touch()

        bundle = inspect_directory(tmp_path)
        decision = select_best_file_combination(bundle)

        assert decision.input_kind == InputKind.AMBER
        assert decision.selected_strategy == "PRMTOP_NC"

    def test_select_pdb_single(self, tmp_path: Path):
        """Single PDB file selected."""
        (tmp_path / "structure.pdb").touch()

        bundle = inspect_directory(tmp_path)
        decision = select_best_file_combination(bundle)

        assert decision.input_kind == InputKind.PDB
        assert decision.selected_strategy == "PDB_SINGLE"

    def test_select_mmcif_single(self, tmp_path: Path):
        """Single mmCIF file selected."""
        (tmp_path / "structure.cif").touch()

        bundle = inspect_directory(tmp_path)
        decision = select_best_file_combination(bundle)

        assert decision.input_kind == InputKind.MMCIF
        assert decision.selected_strategy == "MMCIF_SINGLE"


class TestFileRecord:
    """Tests for FileRecord dataclass."""

    def test_from_path_computes_metadata(self, tmp_path: Path):
        """FileRecord.from_path computes size and checksum."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world", encoding="utf-8")

        record = FileRecord.from_path(test_file, "file_001", "TEXT", "input")

        assert record.size_bytes == 11
        assert record.checksum is not None
        assert record.file_id == "file_001"

    def test_to_dict_serialization(self, tmp_path: Path):
        """FileRecord serializes to dictionary."""
        test_file = tmp_path / "test.pdb"
        test_file.touch()

        record = FileRecord.from_path(test_file, "file_001", "PDB", "structure")
        d = record.__dict__  # dataclass dict access

        assert d["path"] == test_file
        assert d["file_id"] == "file_001"
        assert d["file_type"] == "PDB"
        assert d["role"] == "structure"


class TestLoadDecision:
    """Tests for LoadDecision dataclass."""

    def test_to_dict_serialization(self):
        """LoadDecision serializes to dictionary."""
        decision = LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="TPR_ONLY",
            topology_files=[Path("/test.tpr")],
            confidence=0.95,
            warnings=["test warning"],
        )

        d = decision.to_dict()

        assert d["input_kind"] == "gromacs"
        assert d["selected_strategy"] == "TPR_ONLY"
        assert "/test.tpr" in d["topology_files"][0]
        assert d["confidence"] == 0.95
