from __future__ import annotations

import datetime
import logging
import os
import tempfile
import traceback
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import MDAnalysis
from MDAnalysis import Universe

from ..config.loader import RunConfig
from ..input.models import InputKind, InputBundle, LoadDecision
from ..results.results_manager import ResultsManager
from .probe import match_atoms
from .scale_guard import run_scale_guard

logger = logging.getLogger("base")


class LoadStrategy(str, Enum):
    GROMACS_TPR = "gromacs_tpr"
    GROMACS_TPR_GRO = "gromacs_tpr_gro"
    GROMACS_TOP_GRO = "gromacs_top_gro"
    GROMACS_ITP_GRO = "gromacs_itp_gro"
    AMBER_PRMTOP_NC = "amber_prmtop_nc"
    AMBER_PARM7_NC = "amber_parm7_nc"
    AMBER_PRMTOP_XTC = "amber_prmtop_xtc"
    AMBER_PARM7_XTC = "amber_parm7_xtc"
    CHARMM_PSF_PDB = "charmm_psf_pdb"
    CHARMM_PSF_CRD = "charmm_psf_crd"
    CHARMM_PSF_DCD = "charmm_psf_dcd"
    AMBER_PRMTOP_RST7 = "amber_prmtop_rst7"
    AMBER_PARM7_RST7 = "amber_parm7_rst7"
    AMBER_PRMTOP_MDCRD = "amber_prmtop_mdcrd"
    AMBER_PARM7_MDCRD = "amber_parm7_mdcrd"
    # A8 (BH-016): topology + static structure steps (new for prmtop/top)
    AMBER_PRMTOP_PDB = "amber_prmtop_pdb"
    AMBER_PARM7_PDB = "amber_parm7_pdb"
    GROMACS_TOP_PDB = "gromacs_top_pdb"
    GROMACS_ITP_PDB = "gromacs_itp_pdb"
    GROMACS_TPR_TRR = "gromacs_tpr_trr"
    GROMACS_GRO = "gromacs_gro"  # A-07 (3.3): topology-free GRO fallback
    LAMMPS_DATA = "lammps_data"
    PDB = "pdb"
    MMCIF_GEMMI = "mmcif_gemmi"


# LAMMPS .data atom styles tried in order when the file's own "# <style>"
# comment does not parse (deposits vary in their Masses/Atoms columns)
_LAMMPS_ATOM_STYLES: tuple[str | None, ...] = (
    None,  # trust the file's own "Atoms # <style>" declaration first
    "id resid type q x y z",  # full
    "id resid type x y z",    # molecular
    "id type q x y z",        # charge
    "id type x y z",          # atomic
)


def _rank_pdb_candidates(files: list[Path]) -> Path:
    """A-16 (red-team 3.3): prefer structure-like PDBs over time-AVERAGED ones.

    Plain sorted()[0] picked 'average.pdb' over 'structure.pdb' — the very
    file the loader warns breaks coordinate work. Deterministic total order:
    structure/model-like stems first, 'average'-named last, name tie-break.
    """
    def _key(p: Path):
        n = p.name.lower()
        s = p.stem.lower()
        good = any(k in s for k in ("structure", "model", "frame", "start", "min", "conf"))
        bad_avg = "average" in n
        return (bad_avg, not good, n)
    return sorted(files, key=_key)[0]


# topology/trajectory pairings that get atom-count probed before the Universe
# build (static text coordinate sources are checked by the build itself)
_PROBE_PAIRS: dict["LoadStrategy", tuple[str, str]] = {
    LoadStrategy.CHARMM_PSF_DCD: ("psf", "dcd"),
    LoadStrategy.AMBER_PRMTOP_NC: ("prmtop", "nc"),
    LoadStrategy.AMBER_PARM7_NC: ("parm7", "nc"),
    LoadStrategy.AMBER_PRMTOP_XTC: ("prmtop", "xtc"),
    LoadStrategy.AMBER_PARM7_XTC: ("parm7", "xtc"),
    LoadStrategy.AMBER_PRMTOP_MDCRD: ("prmtop", "mdcrd"),
    LoadStrategy.AMBER_PARM7_MDCRD: ("parm7", "mdcrd"),
    LoadStrategy.GROMACS_TPR_TRR: ("tpr", "trr"),
}


class _GateFailure(Exception):
    """Post-build load-gate rejection carrying a structured error code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class FileValidation:
    ok: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    selected_files: dict[str, Path] = field(default_factory=dict)
    # e.g., {"tpr": Path("..."), "gro": Path("...")}


@dataclass
class LoadAttempt:
    strategy: LoadStrategy
    status: str = "attempting"  # attempting, success, failed
    used_files: list[str] = field(default_factory=list)
    error_code: str = ""
    error_message: str = ""
    traceback: str = ""
    timestamp: str = ""
    universe: Universe | None = None


@dataclass
class LoadingResult:
    success: bool
    universe: Universe | None = None
    final_strategy: LoadStrategy | None = None
    attempts: list[LoadAttempt] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scale_report: dict | None = None


def _get_files_by_ext(bundle: InputBundle, ext: str) -> list[Path]:
    """Return files matching extension (case-insensitive suffix)."""
    ext_lower = ext.lower()
    return [f.path for f in bundle.files if f.path.suffix.lower() == ext_lower]


def validate_for_strategy(bundle: InputBundle, strategy: LoadStrategy) -> FileValidation:
    """Validate files for a given loading strategy."""
    warnings: list[str] = []
    errors: list[str] = []
    selected_files: dict[str, Path] = {}

    match strategy:
        case LoadStrategy.GROMACS_TPR:
            tpr_files = _get_files_by_ext(bundle, ".tpr")
            if len(tpr_files) == 0:
                errors.append("No .tpr files found")
            elif len(tpr_files) == 1:
                selected_files["tpr"] = tpr_files[0]
            else:
                warnings.append("multiple_tpr_files")
                # Pick alphabetically first
                sorted_tpr = sorted(tpr_files, key=lambda p: p.name)
                selected_files["tpr"] = sorted_tpr[0]

        case LoadStrategy.GROMACS_TPR_GRO:
            tpr_files = _get_files_by_ext(bundle, ".tpr")
            gro_files = _get_files_by_ext(bundle, ".gro")
            
            if len(tpr_files) == 0:
                errors.append("No .tpr files found")
            elif len(tpr_files) == 1:
                selected_files["tpr"] = tpr_files[0]
            else:
                warnings.append("multiple_tpr_files")
                sorted_tpr = sorted(tpr_files, key=lambda p: p.name)
                selected_files["tpr"] = sorted_tpr[0]
            
            if len(gro_files) == 0:
                errors.append("No .gro files found")
            elif len(gro_files) == 1:
                selected_files["gro"] = gro_files[0]
            else:
                warnings.append("multiple_gro_files")
                sorted_gro = sorted(gro_files, key=lambda p: p.name)
                selected_files["gro"] = sorted_gro[0]

        case LoadStrategy.GROMACS_TOP_GRO:
            top_files = _get_files_by_ext(bundle, ".top")
            gro_files = _get_files_by_ext(bundle, ".gro")
            
            if len(top_files) == 0:
                errors.append("No .top files found")
            elif len(top_files) == 1:
                selected_files["top"] = top_files[0]
            else:
                warnings.append("multiple_top_files")
                sorted_top = sorted(top_files, key=lambda p: p.name)
                selected_files["top"] = sorted_top[0]
            
            if len(gro_files) == 0:
                errors.append("No .gro files found")
            elif len(gro_files) == 1:
                selected_files["gro"] = gro_files[0]
            else:
                warnings.append("multiple_gro_files")
                sorted_gro = sorted(gro_files, key=lambda p: p.name)
                selected_files["gro"] = sorted_gro[0]

        case LoadStrategy.GROMACS_ITP_GRO:
            itp_files = _get_files_by_ext(bundle, ".itp")
            gro_files = _get_files_by_ext(bundle, ".gro")
            
            if len(itp_files) == 0:
                errors.append("No .itp files found")
            elif len(itp_files) == 1:
                selected_files["itp"] = itp_files[0]
            else:
                warnings.append("multiple_itp_files")
                sorted_itp = sorted(itp_files, key=lambda p: p.name)
                selected_files["itp"] = sorted_itp[0]
            
            if len(gro_files) == 0:
                errors.append("No .gro files found")
            elif len(gro_files) == 1:
                selected_files["gro"] = gro_files[0]
            else:
                warnings.append("multiple_gro_files")
                sorted_gro = sorted(gro_files, key=lambda p: p.name)
                selected_files["gro"] = sorted_gro[0]

        case LoadStrategy.AMBER_PRMTOP_NC:
            prmtop_files = _get_files_by_ext(bundle, ".prmtop")
            nc_files = _get_files_by_ext(bundle, ".nc")
            
            if len(prmtop_files) == 0:
                errors.append("No .prmtop files found")
            elif len(prmtop_files) == 1:
                selected_files["prmtop"] = prmtop_files[0]
            else:
                warnings.append("multiple_prmtop_files")
                sorted_prmtop = sorted(prmtop_files, key=lambda p: p.name)
                selected_files["prmtop"] = sorted_prmtop[0]
            
            if len(nc_files) == 0:
                errors.append("No .nc files found")
            elif len(nc_files) == 1:
                selected_files["nc"] = nc_files[0]
            else:
                warnings.append("multiple_nc_files")
                sorted_nc = sorted(nc_files, key=lambda p: p.name)
                selected_files["nc"] = sorted_nc[0]

        case LoadStrategy.AMBER_PARM7_NC:
            parm7_files = _get_files_by_ext(bundle, ".parm7")
            nc_files = _get_files_by_ext(bundle, ".nc")
            
            if len(parm7_files) == 0:
                errors.append("No .parm7 files found")
            elif len(parm7_files) == 1:
                selected_files["parm7"] = parm7_files[0]
            else:
                warnings.append("multiple_parm7_files")
                sorted_parm7 = sorted(parm7_files, key=lambda p: p.name)
                selected_files["parm7"] = sorted_parm7[0]
            
            if len(nc_files) == 0:
                errors.append("No .nc files found")
            elif len(nc_files) == 1:
                selected_files["nc"] = nc_files[0]

        case LoadStrategy.AMBER_PRMTOP_XTC:
            prmtop_files = _get_files_by_ext(bundle, ".prmtop")
            xtc_files = _get_files_by_ext(bundle, ".xtc")
            
            if len(prmtop_files) == 0:
                errors.append("No .prmtop files found")
            elif len(prmtop_files) == 1:
                selected_files["prmtop"] = prmtop_files[0]
            else:
                warnings.append("multiple_prmtop_files")
                sorted_prmtop = sorted(prmtop_files, key=lambda p: p.name)
                selected_files["prmtop"] = sorted_prmtop[0]
            
            if len(xtc_files) == 0:
                errors.append("No .xtc files found")
            elif len(xtc_files) == 1:
                selected_files["xtc"] = xtc_files[0]
            else:
                warnings.append("multiple_xtc_files")
                sorted_xtc = sorted(xtc_files, key=lambda p: p.name)
                selected_files["xtc"] = sorted_xtc[0]

        case LoadStrategy.AMBER_PARM7_XTC:
            parm7_files = _get_files_by_ext(bundle, ".parm7")
            xtc_files = _get_files_by_ext(bundle, ".xtc")

            if len(parm7_files) == 0:
                errors.append("No .parm7 files found")
            elif len(parm7_files) == 1:
                selected_files["parm7"] = parm7_files[0]
            else:
                warnings.append("multiple_parm7_files")
                sorted_parm7 = sorted(parm7_files, key=lambda p: p.name)
                selected_files["parm7"] = sorted_parm7[0]

            if len(xtc_files) == 0:
                errors.append("No .xtc files found")
            elif len(xtc_files) == 1:
                selected_files["xtc"] = xtc_files[0]
            else:
                warnings.append("multiple_xtc_files")
                sorted_xtc = sorted(xtc_files, key=lambda p: p.name)
                selected_files["xtc"] = sorted_xtc[0]

        case LoadStrategy.AMBER_PRMTOP_RST7 | LoadStrategy.AMBER_PARM7_RST7:
            topo_key = "prmtop" if strategy == LoadStrategy.AMBER_PRMTOP_RST7 else "parm7"
            topo_files = _get_files_by_ext(bundle, f".{topo_key}")
            if len(topo_files) == 0:
                errors.append(f"No .{topo_key} files found")
            else:
                selected_files[topo_key] = sorted(topo_files, key=lambda p: p.name)[0]
                if len(topo_files) > 1:
                    warnings.append(f"multiple_{topo_key}_files")
            # amber restart coordinates: any of the three suffix conventions
            rst7_files = _get_files_by_ext(bundle, ".rst7") or _get_files_by_ext(bundle, ".inpcrd") or _get_files_by_ext(bundle, ".restrt")
            if len(rst7_files) == 0:
                errors.append("No .rst7/.inpcrd/.restrt files found (AMBER restart coordinates)")
            else:
                selected_files["rst7"] = sorted(rst7_files, key=lambda p: p.name)[0]

        case LoadStrategy.AMBER_PRMTOP_MDCRD | LoadStrategy.AMBER_PARM7_MDCRD:
            topo_key = "prmtop" if strategy == LoadStrategy.AMBER_PRMTOP_MDCRD else "parm7"
            topo_files = _get_files_by_ext(bundle, f".{topo_key}")
            if len(topo_files) == 0:
                errors.append(f"No .{topo_key} files found")
            else:
                selected_files[topo_key] = sorted(topo_files, key=lambda p: p.name)[0]
                if len(topo_files) > 1:
                    warnings.append(f"multiple_{topo_key}_files")
            mdcrd_files = _get_files_by_ext(bundle, ".mdcrd")
            if len(mdcrd_files) == 0:
                errors.append("No .mdcrd files found")
            else:
                selected_files["mdcrd"] = sorted(mdcrd_files, key=lambda p: p.name)[0]
                if len(mdcrd_files) > 1:
                    warnings.append("multiple_mdcrd_files")

        case LoadStrategy.GROMACS_GRO:
            # A-07 (red-team 3.3): topology-free fallback — needs only the .gro
            gro_files = _get_files_by_ext(bundle, ".gro")
            if len(gro_files) == 0:
                errors.append("No .gro files found")
            else:
                selected_files["gro"] = sorted(gro_files, key=lambda p: p.name)[0]
                if len(gro_files) > 1:
                    warnings.append("multiple_gro_files")
        case LoadStrategy.LAMMPS_DATA:
            data_files = _get_files_by_ext(bundle, ".data")
            if len(data_files) == 0:
                errors.append("No .data files found (LAMMPS)")
            else:
                selected_files["data"] = sorted(data_files, key=lambda p: p.name)[0]
                if len(data_files) > 1:
                    warnings.append("multiple_data_files")

        case LoadStrategy.GROMACS_TPR_TRR:
            tpr_files = _get_files_by_ext(bundle, ".tpr")
            if len(tpr_files) == 0:
                errors.append("No .tpr files found")
            else:
                selected_files["tpr"] = sorted(tpr_files, key=lambda p: p.name)[0]
                if len(tpr_files) > 1:
                    warnings.append("multiple_tpr_files")
            trr_files = _get_files_by_ext(bundle, ".trr")
            if len(trr_files) == 0:
                errors.append("No .trr files found")
            else:
                selected_files["trr"] = sorted(trr_files, key=lambda p: p.name)[0]
                if len(trr_files) > 1:
                    warnings.append("multiple_trr_files")

        case LoadStrategy.PDB:
            # B3 (BH-014 rest): .ent is PDB-format content (X03)
            pdb_files = (_get_files_by_ext(bundle, ".pdb")
                         + _get_files_by_ext(bundle, ".ent"))
            if len(pdb_files) == 0:
                errors.append("No .pdb files found")
            elif len(pdb_files) == 1:
                selected_files["pdb"] = pdb_files[0]
            else:
                warnings.append("multiple_pdb_files")
                selected_files["pdb"] = _rank_pdb_candidates(pdb_files)
            # Optional trajectory companion: time-averaged PDBs (e.g. MDDBR
            # average.pdb) break coordinate-based structure work; pairing with
            # the trajectory lets us source instantaneous frame positions.
            xtc_files = _get_files_by_ext(bundle, ".xtc")
            if len(xtc_files) == 1:
                selected_files["xtc"] = xtc_files[0]
            elif len(xtc_files) > 1:
                warnings.append("multiple_xtc_files")
                selected_files["xtc"] = sorted(xtc_files, key=lambda p: p.name)[0]

        case LoadStrategy.MMCIF_GEMMI:
            cif_files = _get_files_by_ext(bundle, ".cif")
            if len(cif_files) == 0:
                errors.append("No .cif files found")
            elif len(cif_files) == 1:
                selected_files["cif"] = cif_files[0]
            else:
                warnings.append("multiple_cif_files")
                sorted_cif = sorted(cif_files, key=lambda p: p.name)
                selected_files["cif"] = sorted_cif[0]

        case LoadStrategy.AMBER_PRMTOP_PDB | LoadStrategy.AMBER_PARM7_PDB:
            key = ".prmtop" if strategy == LoadStrategy.AMBER_PRMTOP_PDB else ".parm7"
            prmtop_files = _get_files_by_ext(bundle, key)
            pdb_files = _get_files_by_ext(bundle, ".pdb")
            if len(prmtop_files) == 0:
                errors.append(f"No {key} files found")
            else:
                selected_files[key.strip(".")] = sorted(prmtop_files, key=lambda p: p.name)[0]
            if len(pdb_files) == 0:
                errors.append("No .pdb files found")
            else:
                selected_files["pdb"] = sorted(pdb_files, key=lambda p: p.name)[0]

        case LoadStrategy.GROMACS_TOP_PDB | LoadStrategy.GROMACS_ITP_PDB:
            key = ".top" if strategy == LoadStrategy.GROMACS_TOP_PDB else ".itp"
            top_files = _get_files_by_ext(bundle, key)
            pdb_files = _get_files_by_ext(bundle, ".pdb")
            if len(top_files) == 0:
                errors.append(f"No {key} files found")
            else:
                selected_files[key.strip(".")] = sorted(top_files, key=lambda p: p.name)[0]
            if len(pdb_files) == 0:
                errors.append("No .pdb files found")
            else:
                selected_files["pdb"] = sorted(pdb_files, key=lambda p: p.name)[0]

        case LoadStrategy.CHARMM_PSF_PDB | LoadStrategy.CHARMM_PSF_CRD | LoadStrategy.CHARMM_PSF_DCD:
            psf_files = _get_files_by_ext(bundle, ".psf")
            if len(psf_files) == 0:
                errors.append("No .psf files found")
            elif len(psf_files) == 1:
                selected_files["psf"] = psf_files[0]
            else:
                warnings.append("multiple_psf_files")
                selected_files["psf"] = sorted(psf_files, key=lambda p: p.name)[0]

            # coordinate source for this strategy: pdb (structure) is required,
            # crd/dcd optional per strategy
            coord_ext = {
                LoadStrategy.CHARMM_PSF_PDB: "pdb",
                LoadStrategy.CHARMM_PSF_CRD: "crd",
                LoadStrategy.CHARMM_PSF_DCD: "dcd",
            }[strategy]
            coord_files = _get_files_by_ext(bundle, f".{coord_ext}")
            if len(coord_files) == 0:
                errors.append(f"No .{coord_ext} files found (CHARMM coordinate source)")
            elif len(coord_files) == 1:
                selected_files[coord_ext] = coord_files[0]
            else:
                warnings.append(f"multiple_{coord_ext}_files")
                selected_files[coord_ext] = sorted(coord_files, key=lambda p: p.name)[0]

        case _:
            errors.append(f"Unknown strategy: {strategy}")

    ok = len(errors) == 0
    return FileValidation(ok=ok, warnings=warnings, errors=errors, selected_files=selected_files)


def get_fallback_strategies(decision: LoadDecision, bundle: InputBundle) -> list[LoadStrategy]:
    """Return an ordered list of strategies to try based on the decision."""
    input_kind = decision.input_kind
    strategy = decision.selected_strategy

    # Build the initial ordered list based on strategy
    if input_kind == InputKind.GROMACS:
        if strategy == "TPR_ONLY":
            base_strategies = [
                LoadStrategy.GROMACS_TPR,
                LoadStrategy.GROMACS_TPR_GRO,
                LoadStrategy.GROMACS_TOP_GRO,
                LoadStrategy.GROMACS_ITP_GRO,
                LoadStrategy.GROMACS_TPR_TRR,
                LoadStrategy.GROMACS_TOP_PDB,   # A8: topology + structure
                LoadStrategy.GROMACS_ITP_PDB,   # A8: topology + structure
            ]
        elif strategy == "TPR_GRO":
            base_strategies = [
                LoadStrategy.GROMACS_TPR_GRO,
                LoadStrategy.GROMACS_TPR,
                LoadStrategy.GROMACS_TOP_GRO,
                LoadStrategy.GROMACS_ITP_GRO,
                LoadStrategy.GROMACS_TPR_TRR,
                LoadStrategy.GROMACS_TOP_PDB,   # A8: topology + structure
                LoadStrategy.GROMACS_ITP_PDB,   # A8: topology + structure
            ]
        elif strategy == "TOP_PDB":
            # A8 (BH-016): {top, pdb} without .gro — topology + structure
            base_strategies = [
                LoadStrategy.GROMACS_TOP_PDB,
                LoadStrategy.GROMACS_ITP_PDB,
                LoadStrategy.GROMACS_GRO,   # step 4: structure-alone tail
                LoadStrategy.PDB,           # (broken-include pins cross-kind)
            ]
        elif strategy == "ITP_PDB":
            base_strategies = [
                LoadStrategy.GROMACS_ITP_PDB,
                LoadStrategy.GROMACS_TOP_PDB,
                LoadStrategy.GROMACS_GRO,   # step 4: structure-alone tail
                LoadStrategy.PDB,
            ]
        elif strategy == "TOP_GRO":
            base_strategies = [
                LoadStrategy.GROMACS_TOP_GRO,
                LoadStrategy.GROMACS_ITP_GRO,
                LoadStrategy.GROMACS_TPR_GRO,
                LoadStrategy.GROMACS_TPR,
                LoadStrategy.GROMACS_TOP_PDB,   # A8: topology + structure
                LoadStrategy.GROMACS_ITP_PDB,   # A8: topology + structure
                LoadStrategy.GROMACS_GRO,  # A-07 topology-free tail
                LoadStrategy.PDB,          # A-07 cross-kind tail
            ]
        elif strategy == "ITP_GRO":
            base_strategies = [
                LoadStrategy.GROMACS_ITP_GRO,
                LoadStrategy.GROMACS_TOP_GRO,
                LoadStrategy.GROMACS_TPR_GRO,
                LoadStrategy.GROMACS_TPR,
                LoadStrategy.GROMACS_TPR_TRR,
                LoadStrategy.GROMACS_TOP_PDB,   # A8: topology + structure
                LoadStrategy.GROMACS_ITP_PDB,   # A8: topology + structure
                LoadStrategy.GROMACS_GRO,  # A-07 topology-free tail
                LoadStrategy.PDB,          # A-07 cross-kind tail
            ]
        else:
            # Default fallback for GROMACS
            base_strategies = [
                LoadStrategy.GROMACS_TPR,
                LoadStrategy.GROMACS_TPR_GRO,
                LoadStrategy.GROMACS_TOP_GRO,
                LoadStrategy.GROMACS_ITP_GRO,
                LoadStrategy.GROMACS_TPR_TRR,
                LoadStrategy.GROMACS_TOP_PDB,   # A8: topology + structure
                LoadStrategy.GROMACS_ITP_PDB,   # A8: topology + structure
                LoadStrategy.GROMACS_GRO,  # A-07 topology-free tail
                LoadStrategy.PDB,          # A-07 cross-kind tail
            ]
    elif input_kind == InputKind.AMBER:
        # static/restart coordinates first, netCDF second, xtc/mdcrd last
        # (old chains had xtc first); new rst7/mdcrd strategies appended
        if strategy == "PRMTOP_MDCRD":
            base_strategies = [
                LoadStrategy.AMBER_PRMTOP_MDCRD,
                LoadStrategy.AMBER_PRMTOP_RST7,
                LoadStrategy.AMBER_PRMTOP_XTC,
                LoadStrategy.AMBER_PRMTOP_NC,
                LoadStrategy.AMBER_PRMTOP_PDB,   # A8: structure step
                LoadStrategy.AMBER_PARM7_MDCRD,
                LoadStrategy.AMBER_PARM7_RST7,
                LoadStrategy.AMBER_PARM7_XTC,
                LoadStrategy.AMBER_PARM7_NC,
                LoadStrategy.AMBER_PARM7_PDB,    # A8: structure step
            ]
        elif strategy == "PRMTOP_RST7":
            base_strategies = [
                LoadStrategy.AMBER_PRMTOP_RST7,
                LoadStrategy.AMBER_PRMTOP_MDCRD,
                LoadStrategy.AMBER_PRMTOP_XTC,
                LoadStrategy.AMBER_PRMTOP_NC,
                LoadStrategy.AMBER_PARM7_RST7,
                LoadStrategy.AMBER_PARM7_MDCRD,
                LoadStrategy.AMBER_PARM7_XTC,
                LoadStrategy.AMBER_PARM7_NC,
            ]
        elif strategy == "PRMTOP_PDB":
            # A8 (BH-016): {prmtop, pdb} — topology + static structure step
            base_strategies = [
                LoadStrategy.AMBER_PRMTOP_PDB,
                LoadStrategy.AMBER_PARM7_PDB,
            ]
        elif strategy == "PARM7_PDB":
            base_strategies = [
                LoadStrategy.AMBER_PARM7_PDB,
                LoadStrategy.AMBER_PRMTOP_PDB,
            ]
        else:  # PRMTOP_NC / PRMTOP_XTC (existing decisions, order preserved)
            base_strategies = [
                LoadStrategy.AMBER_PRMTOP_XTC,
                LoadStrategy.AMBER_PRMTOP_NC,
                LoadStrategy.AMBER_PRMTOP_MDCRD,
                LoadStrategy.AMBER_PRMTOP_RST7,
                LoadStrategy.AMBER_PRMTOP_PDB,   # A8: structure step
                LoadStrategy.AMBER_PARM7_XTC,
                LoadStrategy.AMBER_PARM7_NC,
                LoadStrategy.AMBER_PARM7_MDCRD,
                LoadStrategy.AMBER_PARM7_RST7,
                LoadStrategy.AMBER_PARM7_PDB,    # A8: structure step
            ]
    elif input_kind == InputKind.LAMMPS:
        base_strategies = [LoadStrategy.LAMMPS_DATA]
    elif input_kind == InputKind.CHARMM:
        # coordinate-source-first ordering; validation filtering below prunes
        # strategies whose files are absent
        if strategy == "PSF_CRD":
            base_strategies = [LoadStrategy.CHARMM_PSF_CRD, LoadStrategy.CHARMM_PSF_PDB, LoadStrategy.CHARMM_PSF_DCD]
        elif strategy == "PSF_DCD":
            base_strategies = [LoadStrategy.CHARMM_PSF_DCD, LoadStrategy.CHARMM_PSF_PDB, LoadStrategy.CHARMM_PSF_CRD]
        else:  # PSF_PDB (and PSF_ONLY honest-failure path)
            base_strategies = [LoadStrategy.CHARMM_PSF_PDB, LoadStrategy.CHARMM_PSF_CRD, LoadStrategy.CHARMM_PSF_DCD]
        # A8 follow-up (user condition): same structure-file-alone tail as
        # AMBER — a PSF that cannot parse must not sink a deposit whose
        # .pdb loads fine; the topology_ignored warning records the reason.
        base_strategies.append(LoadStrategy.PDB)
    elif input_kind == InputKind.PDB:
        if strategy == "PDB_SINGLE":
            base_strategies = [LoadStrategy.PDB]
        else:
            base_strategies = [LoadStrategy.PDB]
    elif input_kind == InputKind.MMCIF:
        if strategy == "MMCIF_SINGLE":
            base_strategies = [LoadStrategy.MMCIF_GEMMI]
        else:
            base_strategies = [LoadStrategy.MMCIF_GEMMI]
    else:
        # Unknown input kind - try all strategies
        base_strategies = [
            LoadStrategy.GROMACS_TPR,
            LoadStrategy.GROMACS_TPR_GRO,
            LoadStrategy.GROMACS_TOP_GRO,
            LoadStrategy.GROMACS_ITP_GRO,
            LoadStrategy.GROMACS_TPR_TRR,
            LoadStrategy.AMBER_PRMTOP_RST7,
            LoadStrategy.AMBER_PRMTOP_MDCRD,
            LoadStrategy.AMBER_PRMTOP_XTC,
            LoadStrategy.AMBER_PRMTOP_NC,
            LoadStrategy.AMBER_PARM7_RST7,
            LoadStrategy.AMBER_PARM7_MDCRD,
            LoadStrategy.AMBER_PARM7_XTC,
            LoadStrategy.AMBER_PARM7_NC,
            LoadStrategy.CHARMM_PSF_PDB,
            LoadStrategy.CHARMM_PSF_CRD,
            LoadStrategy.CHARMM_PSF_DCD,
            LoadStrategy.GROMACS_GRO,  # A-07
            LoadStrategy.LAMMPS_DATA,
            LoadStrategy.PDB,
            LoadStrategy.MMCIF_GEMMI,
        ]

    # A8 (BH-016): AMBER families keep a flat-PDB last resort — the
    # pre-A8 deposit path was flat PDB and silently lost the topology;
    # step 4 of the ladder keeps that floor but records topology_ignored.
    if input_kind == InputKind.AMBER:
        base_strategies.append(LoadStrategy.PDB)

    # For GROMACS, AMBER and CHARMM, filter to only include strategies that
    # have validation ok=True (files may be absent; fallbacks try alternates)
    if input_kind in (InputKind.GROMACS, InputKind.AMBER, InputKind.CHARMM):
        filtered_strategies = []
        for strat in base_strategies:
            validation = validate_for_strategy(bundle, strat)
            # Include if ok=True (no errors), warnings are OK
            if validation.ok:
                filtered_strategies.append(strat)
        return filtered_strategies

    return base_strategies


def _load_mmcif_via_gemmi(cif_path: Path) -> Universe:
    """Load mmCIF via gemmi and build the Universe DIRECTLY from gemmi arrays.

    A-06 (red-team 3.4): the old route (`make_minimal_pdb` -> PDB text ->
    MDAnalysis) truncated multi-char chain IDs to their last column — chains
    AA and BA merged into one segment. No PDB round-trip: chain.name survives
    verbatim, positions/resids/elements are native, and bonds are recovered
    downstream by element-based guessing (post-3.2 repair), same as before.
    """
    try:
        import gemmi
    except ImportError:
        raise ImportError("gemmi is required for MMCIF_GEMMI strategy. Install with: pip install gemmi")
    import numpy as np
    from MDAnalysis.core.topology import Topology
    from MDAnalysis.core.topologyattrs import (
        Atomnames, Atomtypes, Elements, Resids, Resnames, Segids)

    st = gemmi.read_structure(str(cif_path))
    if len(st) == 0:
        raise RuntimeError("No models in mmCIF file")
    model = st[0]

    names: list[str] = []
    elements: list[str] = []
    positions: list[tuple[float, float, float]] = []
    atom_resindex: list[int] = []
    resnames: list[str] = []
    resids: list[int] = []
    residue_segindex: list[int] = []
    chain_names: list[str] = []

    for ci, chain in enumerate(model):
        chain_names.append(chain.name)
        for residue in chain:
            rindex = len(resnames)
            resnames.append(residue.name if residue.name else "UNK")
            resids.append(int(residue.seqid.num))
            residue_segindex.append(ci)
            for atom in residue:
                names.append(atom.name if atom.name else "X")
                elements.append(atom.element.name if atom.element else "X")
                positions.append((float(atom.pos.x), float(atom.pos.y), float(atom.pos.z)))
                atom_resindex.append(rindex)

    if not names:
        raise RuntimeError("No atoms in first model of mmCIF file")

    top = Topology(len(names), len(resnames), len(chain_names),
                   atom_resindex=atom_resindex,
                   residue_segindex=residue_segindex)
    top.add_TopologyAttr(Atomnames(names))
    top.add_TopologyAttr(Atomtypes(elements))   # element = type default
    top.add_TopologyAttr(Elements(elements))
    top.add_TopologyAttr(Resids(resids))
    top.add_TopologyAttr(Resnames(resnames))
    top.add_TopologyAttr(Segids(chain_names))
    u = Universe(top)
    u.load_new(np.array(positions, dtype=np.float32), format="memory")
    return u



def _load_lammps_data(data_path: Path) -> Universe:
    """Load a LAMMPS .data file, retrying common atom styles.

    Deposits vary in their Masses/Atoms columns; the file's own
    'Atoms # <style>' declaration is trusted first, then common styles.
    All failures are compiled into one sub-attempt record in the raised message.
    """
    failures: list[str] = []
    for style in _LAMMPS_ATOM_STYLES:
        try:
            if style is None:
                return Universe(str(data_path), format="DATA")
            return Universe(str(data_path), format="DATA", atom_style=style)
        except Exception as exc:
            label = style if style is not None else "<file-declared>"
            failures.append(f"{label}: {type(exc).__name__}: {exc}")
    raise RuntimeError(
        f"LAMMPS .data load failed for all atom styles: " + " | ".join(failures)
    )


def load_with_strategy(strategy: LoadStrategy, files: dict[str, Path], config: RunConfig) -> Universe:
    """Load a Universe using the specified strategy and files."""
    match strategy:
        case LoadStrategy.GROMACS_TPR:
            return Universe(str(files["tpr"]), tpr_resid_from_one=True, in_memory=True)
        case LoadStrategy.GROMACS_TPR_GRO:
            return Universe(str(files["tpr"]), str(files["gro"]), tpr_resid_from_one=True, in_memory=True)
        case LoadStrategy.GROMACS_TOP_GRO:
            return Universe(
                str(files["top"]), 
                str(files["gro"]), 
                topology_format="ITP", 
                tpr_resid_from_one=True, 
                in_memory=True
            )
        case LoadStrategy.GROMACS_ITP_GRO:
            return Universe(
                str(files["itp"]), 
                str(files["gro"]), 
                topology_format="ITP", 
                tpr_resid_from_one=True, 
                in_memory=True,
                infer_system=True
            )
        case LoadStrategy.GROMACS_GRO:
            # A-07 (red-team 3.3): names/resids from the .gro; bonds guessed
            # downstream by topology repair (element-based after 3.2).
            return Universe(str(files["gro"]))
        case LoadStrategy.AMBER_PRMTOP_NC:
            return Universe(str(files["prmtop"]), str(files["nc"]))
        case LoadStrategy.AMBER_PARM7_NC:
            return Universe(str(files["parm7"]), str(files["nc"]))
        case LoadStrategy.AMBER_PRMTOP_XTC:
            return Universe(str(files["prmtop"]), str(files["xtc"]))
        case LoadStrategy.AMBER_PARM7_XTC:
            return Universe(str(files["parm7"]), str(files["xtc"]))
        case LoadStrategy.AMBER_PRMTOP_PDB | LoadStrategy.AMBER_PARM7_PDB:
            # A8 (BH-016): topology + static structure (prmtop carries
            # charges/types/bonds; pdb provides frame-0 coordinates)
            key = "prmtop" if "prmtop" in files else "parm7"
            return Universe(str(files[key]), str(files["pdb"]),
                            topology_format="PRMTOP", format="PDB")
        case LoadStrategy.GROMACS_TOP_PDB:
            return Universe(str(files["top"]), str(files["pdb"]),
                            topology_format="ITP", tpr_resid_from_one=True,
                            in_memory=True)
        case LoadStrategy.GROMACS_ITP_PDB:
            return Universe(str(files["itp"]), str(files["pdb"]),
                            topology_format="ITP", tpr_resid_from_one=True,
                            in_memory=True, infer_system=True)
        case LoadStrategy.CHARMM_PSF_PDB:
            return Universe(str(files["psf"]), str(files["pdb"]), in_memory=True)
        case LoadStrategy.CHARMM_PSF_CRD:
            return Universe(str(files["psf"]), str(files["crd"]), in_memory=True)
        case LoadStrategy.CHARMM_PSF_DCD:
            # trajectory as frame-0 coordinate source; NOT in_memory — DCD files
            # can be GB-scale. Downstream consumes frame-0 positions only.
            u = Universe(str(files["psf"]), str(files["dcd"]))
            _ = u.trajectory[0]
            return u
        case LoadStrategy.AMBER_PRMTOP_RST7:
            # 2.10 needs explicit formats: prmtop via amber-aware TOPParser,
            # amber restart via RESTRT (no .rst7/.inpcrd suffix mapping in core)
            return Universe(
                str(files["prmtop"]), str(files["rst7"]),
                topology_format="PRMTOP", format="RESTRT",
            )
        case LoadStrategy.AMBER_PARM7_RST7:
            return Universe(
                str(files["parm7"]), str(files["rst7"]),
                topology_format="PRMTOP", format="RESTRT",
            )
        case LoadStrategy.AMBER_PRMTOP_MDCRD:
            u = Universe(str(files["prmtop"]), str(files["mdcrd"]), topology_format="PRMTOP")
            _ = u.trajectory[0]
            return u
        case LoadStrategy.AMBER_PARM7_MDCRD:
            u = Universe(str(files["parm7"]), str(files["mdcrd"]), topology_format="PRMTOP")
            _ = u.trajectory[0]
            return u
        case LoadStrategy.GROMACS_TPR_TRR:
            u = Universe(str(files["tpr"]), str(files["trr"]), tpr_resid_from_one=True)
            _ = u.trajectory[0]
            return u
        case LoadStrategy.LAMMPS_DATA:
            return _load_lammps_data(files["data"])
        case LoadStrategy.PDB:
            src_pref = None
            try:
                import os
                src_pref = os.environ.get("LOADER_STRUCTURE_SOURCE", "trajectory")
            except Exception:
                src_pref = "trajectory"
            xtc = files.get("xtc")
            if src_pref == "trajectory" and xtc:
                try:
                    # A-05 (red-team 3.1): no in_memory=True — MDAnalysis used to
                    # copy EVERY frame into a MemoryReader (n_atoms*n_frames*12 B,
                    # OOM on 200k-atom x 5000-frame deposits) although only frame
                    # 0 is consumed. Stream the reader and keep frame 0 only.
                    u = Universe(str(files["pdb"]), str(xtc))
                    u.transfer_to_memory(start=0, stop=1)
                    # Realize frame-0 coordinates (instantaneous, not averaged)
                    _ = u.trajectory[0]
                    return u
                except Exception as exc:
                    # Any trajectory incompatibility: fall back to static PDB.
                    # A-05: this used to be a silent `except: pass`.
                    logging.getLogger(__name__).warning(
                        "pdb_xtc_pairing failed, falling back to static PDB: %s", exc)
            pdb_path = files["pdb"]
            if str(pdb_path).lower().endswith(".ent"):
                # B3 (X03): .ent carries PDB-format content but the suffix
                # defeats MDAnalysis' format inference
                return Universe(str(pdb_path), format="PDB", in_memory=True)
            return Universe(str(pdb_path), in_memory=True)
        case LoadStrategy.MMCIF_GEMMI:
            return _load_mmcif_via_gemmi(files["cif"])
        case _:
            raise ValueError(f"Unknown strategy: {strategy}")


# A8 (BH-041): topology + static-structure pairings whose abandonment on
# load failure earns a coordinate_source_ignored warning (S27 class).
_STATIC_PAIR_STRATEGIES = frozenset({
    LoadStrategy.GROMACS_TPR_GRO,
    LoadStrategy.GROMACS_TOP_GRO,
    LoadStrategy.GROMACS_ITP_GRO,
    LoadStrategy.AMBER_PRMTOP_RST7,
    LoadStrategy.AMBER_PARM7_RST7,
    LoadStrategy.AMBER_PRMTOP_MDCRD,
    LoadStrategy.AMBER_PARM7_MDCRD,
    LoadStrategy.AMBER_PRMTOP_PDB,
    LoadStrategy.AMBER_PARM7_PDB,
    LoadStrategy.GROMACS_TOP_PDB,
    LoadStrategy.GROMACS_ITP_PDB,
    LoadStrategy.CHARMM_PSF_PDB,
    LoadStrategy.CHARMM_PSF_CRD,
})


def _topology_n_atoms(path: Path) -> int | None:
    """Parse a (binary) topology to get its declared atom count; None on failure.

    Only used for _PROBE_PAIRS topologies (.psf/.prmtop/.parm7/.tpr) — text
    topologies (.top/.itp) would need the ITP machinery and are skipped.
    """
    try:
        return Universe(str(path)).atoms.n_atoms
    except Exception:
        return None


def _record_attempts(results: ResultsManager, attempts: list[LoadAttempt]) -> None:
    """Persist the attempt table (chosen pair + outcome codes + messages)."""
    attempt_dicts = []
    for a in attempts:
        ad = {
            "strategy": a.strategy.value,
            "status": a.status,
            "used_files": a.used_files,
            "timestamp": a.timestamp,
        }
        if a.error_code:
            ad["error_code"] = a.error_code
        if a.error_message:
            ad["error_message"] = a.error_message
        attempt_dicts.append(ad)
    results.set_data("loading/attempts", attempt_dicts)
    # A8 (BH-016/BH-041): the ladder record — strategy, outcome, reason
    # per step, directly readable in triage dumps.
    results.set_data("loading/ladder", [
        {
            "strategy": getattr(a.strategy, "value", a.strategy),
            "outcome": a.status,
            "reason": a.error_code or ("success" if a.status == "success"
                                       else ""),
            **({"error_message": a.error_message[:200]}
               if getattr(a, "error_message", None) else {}),
        } for a in attempts])


def summarize_load_failure(attempts: list, decision=None,
                           bundle=None) -> dict:
    """bughunt BH-014: user-facing reason from the attempt table.

    The pipeline's generic message ("No loading strategy succeeded after N
    attempts") hid every real cause: F07's atom-count 30 vs 36, X01's bz2
    EOFError, X02's UnicodeDecodeError, X06's invalid tpr. Ordered by
    informativeness: atom-count mismatch first (both counts in the message),
    then content gates, then the first real exception with a note about how
    many other strategies also failed.
    """
    # B3 (BH-014 rest): an UNKNOWN-kind deposit must name its REAL
    # problem instead of the first strategy's validation noise
    # ("No .tpr files found" for a dcd-only/xyz/gz deposit — F06/X07/S26).
    if (decision is not None and getattr(decision, "input_kind", None) is None
            and bundle is not None):
        recs = list(getattr(bundle, "files", []) or [])
        gz = [f.path.name for f in recs
              if f.path.name.lower().endswith(".gz")]
        if gz:
            return {
                "reason": "compressed_input",
                "message": (f"compressed input cannot be loaded directly "
                            f"({', '.join(gz)}); decompress and deposit "
                            f"the plain file"),
                "details": {"attempt_count": len(attempts),
                            "compressed_files": gz},
            }
        coords = [f.path.name for f in recs
                  if getattr(f, "role", "") in ("trajectory", "coordinate")]
        topologies = [f for f in recs
                      if getattr(f, "role", "") in ("topology", "structure")]
        if coords and not topologies:
            return {
                "reason": "missing_topology",
                "message": (f"found coordinate/trajectory file(s) "
                            f"({', '.join(coords)}) but no topology to "
                            f"interpret them — pair with .tpr, .psf, "
                            f".prmtop/.parm7 or .top + structure"),
                "details": {"attempt_count": len(attempts),
                            "unpaired_files": coords},
            }
        unknown_exts = sorted({f.path.suffix.lower() for f in recs
                               if getattr(f, "file_type", "") == "UNKNOWN"})
        if unknown_exts:
            return {
                "reason": "unsupported_extension",
                "message": (f"unsupported input extension(s) "
                            f"{', '.join(unknown_exts)} (files: "
                            f"{', '.join(f.path.name for f in recs)})"),
                "details": {"attempt_count": len(attempts),
                            "unsupported_extensions": unknown_exts},
            }

    failed = [a for a in attempts if getattr(a, "status", None) != "success"]
    if not attempts:
        return {
            "reason": "no_recognized_input_files",
            "message": ("No file combination in the input matched a "
                        "supported loading strategy (20 strategies tried)."),
            "details": {"attempt_count": 0},
        }

    def _summary(reason, attempt, extra=None):
        def _strategy_name(a):
            s = getattr(a, "strategy", "?")
            return getattr(s, "value", s)
        out = {
            "reason": reason,
            "message": getattr(attempt, "error_message", "") or reason,
            "details": {
                "attempt_count": len(attempts),
                "failed_strategies": [_strategy_name(a) for a in failed],
                **(extra or {}),
            },
        }
        if getattr(attempt, "error_code", None):
            out["details"]["error_code"] = attempt.error_code
        return out

    for a in failed:
        if getattr(a, "error_code", None) == "rejected_atoms":
            return _summary("atom_count_mismatch", a)
    for code, reason in (("empty_universe", "empty_universe"),
                         ("no_positions", "no_positions")):
        for a in failed:
            if getattr(a, "error_code", None) == code:
                return _summary(reason, a)
    for a in failed:
        if getattr(a, "error_code", None) == "load_exception":
            out = _summary("load_exception", a)
            others = len(failed) - 1
            if others > 0:
                out["message"] += f" ({others} other strategies also failed)"
            return out
    # structured failures only (gates/probes without an exception message)
    a = failed[0]
    return _summary(getattr(a, "error_code", None) or "unknown", a)


def load_simulation(
    decision: LoadDecision,
    bundle: InputBundle,
    config: RunConfig,
    results: ResultsManager
) -> LoadingResult:
    """Orchestrate loading a simulation with strategy cycling."""
    from datetime import timezone
    
    # Record decision
    results.set_data("loading/decision", decision.to_dict())
    
    # Get ordered fallback strategies
    strategies = get_fallback_strategies(decision, bundle)
    
    # Initialize result
    all_warnings: list[str] = []
    attempts: list[LoadAttempt] = []
    
    for strategy in strategies:
        # Validate for this strategy
        validation = validate_for_strategy(bundle, strategy)
        
        if not validation.ok:
            # Validation failed - record attempt and continue
            attempt = LoadAttempt(
                strategy=strategy,
                status="failed",
                error_code="validation_failed",
                error_message="; ".join(validation.errors),
                timestamp=datetime.datetime.now(timezone.utc).isoformat(),
            )
            attempts.append(attempt)
            
            # Record attempt to results
            _record_attempts(results, attempts)
            
            continue
        
        # Merge validation warnings
        all_warnings.extend(validation.warnings)
        
        # Create attempt record
        used_files = [str(f) for f in validation.selected_files.values()]
        attempt = LoadAttempt(
            strategy=strategy,
            status="attempting",
            used_files=used_files,
            timestamp=datetime.datetime.now(timezone.utc).isoformat(),
        )

        # atom-count probe for topology/trajectory pairings (before the
        # expensive Universe build; mdpc 'rejected_atoms' semantics)
        if strategy in _PROBE_PAIRS:
            topo_key, traj_key = _PROBE_PAIRS[strategy]
            topo_atoms = _topology_n_atoms(validation.selected_files[topo_key])
            if topo_atoms is not None:
                probe = match_atoms(topo_atoms, validation.selected_files[traj_key])
                if not probe.ok:
                    attempt.status = "failed"
                    attempt.error_code = probe.error_code
                    attempt.error_message = probe.error_message
                    attempts.append(attempt)
                    # A8 (BH-016): trajectory atom-count mismatch must NEVER
                    # abort the run — warn and fall on to the structure
                    # step instead of silently dropping the trajectory.
                    all_warnings.append(
                        f"trajectory_ignored: {probe.error_message}")
                    _record_attempts(results, attempts)
                    continue
                if probe.error_code == "probe_failed":
                    all_warnings.append(probe.error_message)

        try:
            # Try to load
            universe = load_with_strategy(strategy, validation.selected_files, config)

            # Post-build success gates (mdpc executor). Deliberately NO protein
            # gate: bat3 catalogs every molecule, so solvent-only / empty-catalog
            # deposits are a valid success.
            if universe.atoms.n_atoms == 0:
                raise _GateFailure("empty_universe", "Universe built with zero atoms")
            try:
                positions = universe.atoms.positions
            except Exception as no_coords:  # NoDataError in MDAnalysis 2.x
                raise _GateFailure("no_positions", "Universe built without coordinates") from no_coords
            if positions is None or len(positions) == 0:
                raise _GateFailure("no_positions", "Universe built without coordinates")

            # Universal coordinate-scale guard (geometry-only detection; heals
            # nm/angstrom collapse for any strategy, codes per severity).
            scale_report = run_scale_guard(universe, strategy, validation.selected_files)
            results.set_data("loading/scale_correction", scale_report.to_dict())
            if scale_report.warning_message:
                all_warnings.append(scale_report.warning_message)

            # Success!
            attempt.status = "success"
            attempt.universe = universe
            
            attempts.append(attempt)
            
            # A8 (step 4 of the ladder): the usable system came from a
            # structure file ALONE while the bundle shipped a topology —
            # the run must carry the reason explicitly.
            if (strategy in (LoadStrategy.PDB, LoadStrategy.GROMACS_GRO)
                    and decision.input_kind in (InputKind.AMBER,
                                                InputKind.GROMACS,
                                                InputKind.CHARMM)):
                prev_fail = next((a for a in reversed(attempts)
                                  if a.status != "success"), None)
                reason = (prev_fail.error_message
                          if prev_fail is not None and
                          getattr(prev_fail, "error_message", None)
                          else "topology strategies exhausted")
                all_warnings.append(
                    f"topology_ignored: falling back to {strategy.value} "
                    f"without topology metadata ({reason[:160]})")

            # Record final results
            results.set_data("loading/success", True)
            results.set_data("loading/final_strategy", strategy.value)
            results.set_data("loading/warnings", all_warnings)
            
            # Record all attempts
            _record_attempts(results, attempts)
            
            return LoadingResult(
                success=True,
                universe=universe,
                final_strategy=strategy,
                attempts=attempts,
                warnings=all_warnings,
                scale_report=scale_report.to_dict(),
            )
            
        except _GateFailure as gate:
            # post-build gate rejected: structured outcome, try next strategy
            attempt.status = "failed"
            attempt.error_code = gate.code
            attempt.error_message = str(gate)

            logger.info(f"Strategy {strategy} rejected by gate {gate.code}: {gate}")

            attempts.append(attempt)
            _record_attempts(results, attempts)
            # Continue to next strategy

        except Exception as exc:
            # Load failed
            attempt.status = "failed"
            attempt.error_code = "load_exception"
            attempt.error_message = str(exc)
            attempt.traceback = traceback.format_exc()

            logger.exception(f"Strategy {strategy} failed: {exc}")

            # A8 (BH-041/S27): a topology+structure pair whose load fails
            # (e.g. TPR/GRO atom-count mismatch) was previously dropped
            # SILENTLY with the system continuing from the topology's own
            # coordinates. Record the abandonment as a warning.
            if strategy in _STATIC_PAIR_STRATEGIES:
                all_warnings.append(
                    f"coordinate_source_ignored: {strategy.value} failed "
                    f"({str(exc)[:160]}); continuing without that "
                    "coordinate source")

            attempts.append(attempt)
            
            # Record attempt to results
            _record_attempts(results, attempts)
            
            # Continue to next strategy
    
    # All strategies exhausted without success
    results.set_data("loading/success", False)
    results.set_data("loading/final_strategy", None)
    results.set_data("loading/warnings", all_warnings)
    # bughunt BH-014: persist the structured failure summary (reason,
    # message, which strategies failed) next to the attempt table
    results.set_data("loading/failure_summary",
                     summarize_load_failure(attempts, decision=decision,
                                            bundle=bundle))
    
    # Record all attempts
    _record_attempts(results, attempts)

    return LoadingResult(
        success=False,
        attempts=attempts,
        warnings=all_warnings,
    )
