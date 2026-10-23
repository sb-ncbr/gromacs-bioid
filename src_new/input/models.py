from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class InputKind(str, Enum):
    GROMACS = "gromacs"
    AMBER = "amber"
    CHARMM = "charmm"  # covers NAMD deposits (psf+dcd family)
    LAMMPS = "lammps"
    PDB = "pdb"
    MMCIF = "mmcif"


@dataclass
class FileRecord:
    path: Path
    file_id: str
    file_type: str
    role: str
    size_bytes: int = 0
    checksum: str = ""

    @classmethod
    def from_path(cls, path: Path, file_id: str, file_type: str, role: str) -> FileRecord:
        # compute size and sha256 checksum from file contents
        # A-05 (red-team 3.1): stream in 1 MiB chunks — read_bytes() slurps the
        # whole file, which OOM-killed pods on multi-GB trajectories.
        size_bytes = path.stat().st_size
        hasher = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                hasher.update(chunk)
        checksum = hasher.hexdigest()
        return cls(
            path=path,
            file_id=file_id,
            file_type=file_type,
            role=role,
            size_bytes=size_bytes,
            checksum=checksum,
        )


@dataclass
class InputBundle:
    root_directory: Path
    files: list[FileRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        # serialize root_directory as str, files as list of __dict__
        return {
            "root_directory": str(self.root_directory),
            "files": [f.__dict__ for f in self.files],
        }


@dataclass
class LoadDecision:
    input_kind: InputKind | None
    selected_strategy: str
    topology_files: list[Path] = field(default_factory=list)
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        # input_kind as .value string, topology_files as list of str(path)
        return {
            "input_kind": self.input_kind.value if self.input_kind else None,
            "selected_strategy": self.selected_strategy,
            "topology_files": [str(p) for p in self.topology_files],
            "confidence": self.confidence,
            "warnings": self.warnings,
        }
