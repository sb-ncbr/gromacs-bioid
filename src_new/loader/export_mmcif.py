from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import MDAnalysis

from ..results.results_manager import ResultsManager
from .universe_facade import LoadedUniverse

logger = logging.getLogger("base")

# Defer Biopython import to allow graceful handling
try:
    from Bio.PDB import MMCIFIO, Structure, Model, Chain, Residue, Atom
    BIOPYTHON_AVAILABLE = True
except ImportError:
    BIOPYTHON_AVAILABLE = False
    MMCIFIO = None
    Structure = None
    Model = None
    Chain = None
    Residue = None
    Atom = None


def _safe(val, default="."):
    if val is None or str(val).strip() == "":
        return default
    return str(val).strip()


def _build_biopython_structure(universe: MDAnalysis.Universe, filter_segment: str | None = None) -> Structure.Structure:
    """Build a Biopython Structure from an MDAnalysis Universe."""
    if not BIOPYTHON_AVAILABLE:
        raise ImportError("Biopython is required for mmCIF export. Install with: pip install biopython")
    
    structure = Structure.Structure("0")
    model = Model.Model(0)
    structure.add(model)
    
    cached_residues: dict[int, dict[str, Residue.Residue]] = {}
    chains = {}
    
    for atom in universe.atoms:
        chain_id = atom.segid
        if filter_segment is not None and chain_id != filter_segment:
            continue
        
        resname = _safe(atom.resname, default="UNK")
        atom_name = _safe(atom.name, default="X")
        element = _safe(getattr(atom, 'element', None), default="X")
        
        if chain_id not in chains:
            chain = Chain.Chain(chain_id)
            model.add(chain)
            chains[chain_id] = chain
        else:
            chain = chains[chain_id]
        
        resid = int(atom.resid) if hasattr(atom, 'resid') else 0
        
        if resid in cached_residues and resname in cached_residues[resid]:
            residue = cached_residues[resid][resname]
        else:
            residue = Residue.Residue((' ', resid, ' '), resname, '')
            if resid not in cached_residues:
                cached_residues[resid] = {}
            cached_residues[resid][resname] = residue
            chain.add(residue)
        
        pos = atom.position if hasattr(atom, 'position') else [0.0, 0.0, 0.0]
        bp_atom = Atom.Atom(
            atom_name, pos, 0.0, 0.0, '.', atom_name, atom.index, element=element.upper()
        )
        residue.add(bp_atom)
    
    return structure


def export_system_mmcif(facade: LoadedUniverse, output_path: Path, results: ResultsManager | None = None) -> Path:
    """Export the whole system to mmCIF."""
    if not BIOPYTHON_AVAILABLE:
        raise ImportError("Biopython is required for mmCIF export. Install with: pip install biopython")
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    structure = _build_biopython_structure(facade.universe)
    io = MMCIFIO()
    io.set_structure(structure)
    io.save(str(output_path))
    
    if results is not None:
        results.add_artifact("SYSTEM", output_path, description="Whole-system mmCIF export", kind="mmcif")
        results.set_data("exports/system_mmcif", str(output_path))
    
    logger.info(f"Exported whole-system mmCIF to {output_path}")
    return output_path


def export_segment_mmcif(facade: LoadedUniverse, segment_name: str, output_path: Path, results: ResultsManager | None = None) -> Path:
    """Export a single segment to mmCIF."""
    if not BIOPYTHON_AVAILABLE:
        raise ImportError("Biopython is required for mmCIF export. Install with: pip install biopython")
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    structure = _build_biopython_structure(facade.universe, filter_segment=segment_name)
    io = MMCIFIO()
    io.set_structure(structure)
    io.save(str(output_path))
    
    if results is not None:
        results.add_artifact(segment_name, output_path, description=f"Segment '{segment_name}' mmCIF export", kind="mmcif")
        results.set_data(f"exports/segment_mmcif/{segment_name}", str(output_path))
    
    logger.info(f"Exported segment '{segment_name}' mmCIF to {output_path}")
    return output_path
