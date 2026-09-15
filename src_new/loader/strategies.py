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
    PDB = "pdb"
    MMCIF_GEMMI = "mmcif_gemmi"


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

        case LoadStrategy.PDB:
            pdb_files = _get_files_by_ext(bundle, ".pdb")
            if len(pdb_files) == 0:
                errors.append("No .pdb files found")
            elif len(pdb_files) == 1:
                selected_files["pdb"] = pdb_files[0]
            else:
                warnings.append("multiple_pdb_files")
                sorted_pdb = sorted(pdb_files, key=lambda p: p.name)
                selected_files["pdb"] = sorted_pdb[0]
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
            ]
        elif strategy == "TPR_GRO":
            base_strategies = [
                LoadStrategy.GROMACS_TPR_GRO,
                LoadStrategy.GROMACS_TPR,
                LoadStrategy.GROMACS_TOP_GRO,
                LoadStrategy.GROMACS_ITP_GRO,
            ]
        elif strategy == "TOP_GRO":
            base_strategies = [
                LoadStrategy.GROMACS_TOP_GRO,
                LoadStrategy.GROMACS_ITP_GRO,
                LoadStrategy.GROMACS_TPR_GRO,
                LoadStrategy.GROMACS_TPR,
            ]
        elif strategy == "ITP_GRO":
            base_strategies = [
                LoadStrategy.GROMACS_ITP_GRO,
                LoadStrategy.GROMACS_TOP_GRO,
                LoadStrategy.GROMACS_TPR_GRO,
                LoadStrategy.GROMACS_TPR,
            ]
        else:
            # Default fallback for GROMACS
            base_strategies = [
                LoadStrategy.GROMACS_TPR,
                LoadStrategy.GROMACS_TPR_GRO,
                LoadStrategy.GROMACS_TOP_GRO,
                LoadStrategy.GROMACS_ITP_GRO,
            ]
    elif input_kind == InputKind.AMBER:
        if strategy == "PRMTOP_NC":
            base_strategies = [
                LoadStrategy.AMBER_PRMTOP_XTC,
                LoadStrategy.AMBER_PRMTOP_NC,
                LoadStrategy.AMBER_PARM7_XTC,
                LoadStrategy.AMBER_PARM7_NC,
            ]
        else:
            base_strategies = [
                LoadStrategy.AMBER_PRMTOP_XTC,
                LoadStrategy.AMBER_PRMTOP_NC,
                LoadStrategy.AMBER_PARM7_XTC,
                LoadStrategy.AMBER_PARM7_NC,
            ]
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
            LoadStrategy.AMBER_PRMTOP_XTC,
                LoadStrategy.AMBER_PRMTOP_NC,
            LoadStrategy.AMBER_PARM7_XTC,
                LoadStrategy.AMBER_PARM7_NC,
            LoadStrategy.PDB,
            LoadStrategy.MMCIF_GEMMI,
        ]

    # For GROMACS, filter to only include strategies that have validation ok=True
    if input_kind == InputKind.GROMACS:
        filtered_strategies = []
        for strat in base_strategies:
            validation = validate_for_strategy(bundle, strat)
            # Include if ok=True (no errors), warnings are OK
            if validation.ok:
                filtered_strategies.append(strat)
        return filtered_strategies

    return base_strategies


def _load_mmcif_via_gemmi(cif_path: Path) -> Universe:
    """Load mmCIF file via gemmi and convert to Universe."""
    try:
        import gemmi
    except ImportError:
        raise ImportError("gemmi is required for MMCIF_GEMMI strategy. Install with: pip install gemmi")

    st = gemmi.read_structure(str(cif_path))
    # Use the first model
    if st.num_models() == 0:
        raise RuntimeError("No models in mmCIF file")

    # Try different approaches to get PDB string from gemmi
    pdb_str = None
    
    # Try make_minimal_pdb first (newer gemmi API)
    if hasattr(st, "make_minimal_pdb"):
        pdb_str = st.make_minimal_pdb()
    # Try make_pdb_string on first model
    elif hasattr(st, "__getitem__") and len(st) > 0:
        model = st[0]
        if hasattr(model, "make_pdb_string"):
            pdb_str = model.make_pdb_string()
    
    # If neither works, build a minimal PDB string manually
    if pdb_str is None:
        # Build minimal PDB from first model
        model = st[0] if len(st) > 0 else st
        lines = ["HEADER    GENERATED BY GEMMI\n"]
        atom_counter = 0
        for chain in model.chains if hasattr(model, 'chains') else []:
            for residue in chain.residues if hasattr(chain, 'residues') else []:
                res_name = residue.name if hasattr(residue, 'name') else "UNK"
                res_id = residue.seqid if hasattr(residue, 'seqid') else 1
                chain_id = chain.chain_id if hasattr(chain, 'chain_id') else "A"
                for atom in residue.atoms if hasattr(residue, 'atoms') else []:
                    atom_counter += 1
                    atom_name = atom.name if hasattr(atom, 'name') else "X"
                    pos = atom.pos if hasattr(atom, 'pos') else None
                    if pos is not None:
                        line = f"ATOM  {atom_counter:5d}  {atom_name:<3} {res_name:>3} {chain_id}{res_id:>4}    {pos.x:8.3f}{pos.y:8.3f}{pos.z:8.3f}  1.00  0.00           X\n"
                        lines.append(line)
        lines.append("TER\nEND\n")
        pdb_str = "".join(lines)

    # Write to temp file and load with MDAnalysis
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as tmp:
        tmp.write(pdb_str)
        tmp_path = tmp.name
    
    try:
        return Universe(tmp_path, in_memory=True)
    finally:
        os.unlink(tmp_path)


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
        case LoadStrategy.AMBER_PRMTOP_NC:
            return Universe(str(files["prmtop"]), str(files["nc"]))
        case LoadStrategy.AMBER_PARM7_NC:
            return Universe(str(files["parm7"]), str(files["nc"]))
        case LoadStrategy.AMBER_PRMTOP_XTC:
            return Universe(str(files["prmtop"]), str(files["xtc"]))
        case LoadStrategy.AMBER_PARM7_XTC:
            return Universe(str(files["parm7"]), str(files["xtc"]))
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
                    u = Universe(str(files["pdb"]), str(xtc), in_memory=True)
                    # Realize frame-0 coordinates (instantaneous, not averaged)
                    ts0 = u.trajectory[0]
                    return u
                except Exception:
                    # Any trajectory incompatibility: fall back to static PDB
                    pass
            return Universe(str(files["pdb"]), in_memory=True)
        case LoadStrategy.MMCIF_GEMMI:
            return _load_mmcif_via_gemmi(files["cif"])
        case _:
            raise ValueError(f"Unknown strategy: {strategy}")


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
        
        try:
            # Try to load
            universe = load_with_strategy(strategy, validation.selected_files, config)
            
            # Success!
            attempt.status = "success"
            attempt.universe = universe
            
            attempts.append(attempt)
            
            # Record final results
            results.set_data("loading/success", True)
            results.set_data("loading/final_strategy", strategy.value)
            results.set_data("loading/warnings", all_warnings)
            
            # Record all attempts
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
            
            return LoadingResult(
                success=True,
                universe=universe,
                final_strategy=strategy,
                attempts=attempts,
                warnings=all_warnings,
            )
            
        except Exception as exc:
            # Load failed
            attempt.status = "failed"
            attempt.error_code = "load_exception"
            attempt.error_message = str(exc)
            attempt.traceback = traceback.format_exc()
            
            logger.exception(f"Strategy {strategy} failed: {exc}")
            
            attempts.append(attempt)
            
            # Record attempt to results
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
            
            # Continue to next strategy
    
    # All strategies exhausted without success
    results.set_data("loading/success", False)
    results.set_data("loading/final_strategy", None)
    results.set_data("loading/warnings", all_warnings)
    
    # Record all attempts
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
    
    return LoadingResult(
        success=False,
        attempts=attempts,
        warnings=all_warnings,
    )
