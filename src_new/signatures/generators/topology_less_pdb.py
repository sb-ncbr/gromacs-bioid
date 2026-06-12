"""Topology-less PDB signature generators."""

from __future__ import annotations

import logging
from io import StringIO

import numpy as np

from ...config.loader import SignaturesConfig
from ...loader.universe_facade import LoadedUniverse, SegmentProperty
from ...molecules.instances import MoleculeInstance
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class TopologyLessPDBGenerator(SignatureGenerator):
    """PDB generator that works without bond topology or element information."""
    
    name = "topology_less_pdb"
    signature_type = "topology_less_pdb"
    
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config)
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        """Check if fragment has positions and is protein or nucleic.
        
        Does NOT require elements, unique names, multi-atom residues, or bonds.
        """
        segment_name = fragment.segids[0] if len(fragment.segids) > 0 else ""
        props = facade.get_segment_properties(segment_name)
        
        # Need positions
        if not props.flags.get(SegmentProperty.HAS_POSITIONS.value, False):
            return False
        
        # Must be protein or nucleic
        is_protein = props.flags.get(SegmentProperty.IS_PROTEIN.value, False)
        is_nucleic = props.flags.get(SegmentProperty.IS_NUCLEIC.value, False)
        if not (is_protein or is_nucleic):
            return False
        
        return True
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        """Generate PDB string with ATOM records but no CONECT records.
        
        Handles missing elements gracefully by defaulting to empty string.
        """
        return fragment_to_pdb_topology_less(fragment)


class CAOnlyPDBGenerator(SignatureGenerator):
    """PDB generator that outputs only CA atoms from protein fragments."""
    
    name = "ca_only_pdb"
    signature_type = "ca_only_pdb"
    
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config)
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        """Check if fragment has positions and at least one CA atom.
        
        Limited to protein segments only.
        """
        segment_name = fragment.segids[0] if len(fragment.segids) > 0 else ""
        props = facade.get_segment_properties(segment_name)
        
        # Need positions
        if not props.flags.get(SegmentProperty.HAS_POSITIONS.value, False):
            return False
        
        # Must be protein
        if not props.flags.get(SegmentProperty.IS_PROTEIN.value, False):
            return False
        
        # Need at least one CA atom
        try:
            if hasattr(fragment.atoms, 'names') and fragment.atoms.names is not None:
                return np.any(fragment.atoms.names == "CA")
        except Exception:
            pass
        
        return False
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        """Generate PDB string with only CA atoms.
        
        Outputs one ATOM record per residue for CA atoms only.
        """
        return fragment_to_pdb_ca_only(fragment)


def fragment_to_pdb_topology_less(fragment: AtomGroup) -> str:
    """Convert fragment to PDB string without requiring topology.
    
    Writes all atoms as ATOM records, no CONECT records.
    Handles missing elements by defaulting to empty string.
    """
    fd = StringIO()
    fd.write("HEADER    export\n")
    
    serial = 1
    
    for atom_i in range(fragment.n_atoms):
        resname = str(fragment.atoms.resnames[atom_i])
        resnum = int(fragment.atoms.resnums[atom_i])
        atom_name = str(fragment.atoms.names[atom_i])
        pos = fragment.atoms.positions[atom_i]
        
        # Handle missing elements gracefully
        try:
            elem = str(fragment.atoms.elements[atom_i]).upper()
        except (IndexError, AttributeError, TypeError):
            elem = ""
        
        line = _pdb_atom_line(
            serial=serial,
            atom_name=atom_name,
            atom_elem=elem,
            residue_name=resname,
            residue_idx=resnum,
            pos_x=float(pos[0]),
            pos_y=float(pos[1]),
            pos_z=float(pos[2]),
        )
        fd.write(line + "\n")
        serial += 1
    
    fd.write("END\n")
    pdb = fd.getvalue()
    fd.close()
    return pdb


def fragment_to_pdb_ca_only(fragment: AtomGroup) -> str:
    """Convert fragment to PDB string with only CA atoms.
    
    Outputs one ATOM record per residue for atoms named exactly "CA".
    """
    fd = StringIO()
    fd.write("HEADER    export\n")
    
    serial = 1
    
    for atom_i in range(fragment.n_atoms):
        atom_name = str(fragment.atoms.names[atom_i])
        
        # Only include CA atoms
        if atom_name != "CA":
            continue
        
        resname = str(fragment.atoms.resnames[atom_i])
        resnum = int(fragment.atoms.resnums[atom_i])
        pos = fragment.atoms.positions[atom_i]
        
        line = _pdb_atom_line(
            serial=serial,
            atom_name="CA",
            atom_elem="C",
            residue_name=resname,
            residue_idx=resnum,
            pos_x=float(pos[0]),
            pos_y=float(pos[1]),
            pos_z=float(pos[2]),
        )
        fd.write(line + "\n")
        serial += 1
    
    fd.write("END\n")
    pdb = fd.getvalue()
    fd.close()
    return pdb


def _pdb_atom_line(
    serial: int,
    atom_name: str,
    atom_elem: str,
    residue_name: str,
    residue_idx: int,
    pos_x: float,
    pos_y: float,
    pos_z: float,
) -> str:
    """Create ATOM line for PDB file.
    
    Format follows PDB specification:
    ATOM   serial  name  resname chain resnum    x       y       z  occ   temp     elem
    """
    return "{:6s}{:5d} {:^4s}{:1s}{:3s} {:1s}{:4d}{:1s}   {:8.3f}{:8.3f}{:8.3f}{:6.2f}{:6.2f}          {:>2s}{:2s}".format(
        "ATOM",
        serial,
        atom_name,
        "",
        residue_name.upper(),
        "A",
        residue_idx,
        "",
        pos_x,
        pos_y,
        pos_z,
        1.0,
        0.0,
        atom_elem[:2].ljust(2) if atom_elem else "  ",
        "",
    )
