"""PDB signature generators."""

from __future__ import annotations

import logging
import os
import tempfile
import warnings
from collections import defaultdict

import numpy as np
from Bio.PDB import Structure, Model, Chain, Residue, Atom, PDBIO, PDBParser
from Bio.PDB.PDBExceptions import PDBConstructionWarning
from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse, SegmentProperty
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class PDBGenerator(SignatureGenerator):
    """PDB generator base class."""
    
    name = "pdb_protein"
    # signature_type is set by subclasses
    
    def __init__(
        self,
        config: SignaturesConfig,
        backbone_only: bool = False,
        sanitize: bool = True,
        is_protein: bool = False,
        is_nucleotide: bool = False,
    ) -> None:
        super().__init__(config)
        self._backbone_only = backbone_only
        self._sanitize = sanitize
        self._is_protein = is_protein
        self._is_nucleotide = is_nucleotide
        
        # Set name based on configuration
        if backbone_only:
            if sanitize:
                self.name = "pdb_backbone_protein" if is_protein else "pdb_backbone_nucleic"
            else:
                self.name = "pdb_backbone_not_sanitized_protein" if is_protein else "pdb_backbone_not_sanitized_nucleic"
        else:
            if sanitize:
                self.name = "pdb_protein" if is_protein else "pdb_nucleic"
            else:
                self.name = "pdb_not_sanitized_protein" if is_protein else "pdb_not_sanitized_nucleic"
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        segment_name = fragment.segids[0] if len(fragment.segids) > 0 else ""
        props = facade.get_segment_properties(segment_name)
        
        # Need positions
        if not props.flags.get(SegmentProperty.HAS_POSITIONS.value, False):
            return False
        
        # Need correct residue types
        if self._is_protein:
            if (
                not props.flags.get(SegmentProperty.IS_PROTEIN.value, False)
                or not props.flags.get(SegmentProperty.HAS_MULTI_ATOM_RESIDUES.value, False)
            ):
                return False
        else:
            if (
                not props.flags.get(SegmentProperty.IS_NUCLEIC.value, False)
                or props.flags.get(SegmentProperty.HAS_MULTI_ATOM_RESIDUES.value, False)
            ):
                return False
        
        # If not backbone-only, need elements
        if not self._backbone_only and not props.flags.get(SegmentProperty.HAS_ELEMENTS.value, False):
            return False
        
        # Need unique names
        if not props.flags.get(SegmentProperty.HAS_UNIQUE_NAMES.value, False):
            return False
        
        return True
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        pdb = fragment_to_pdb(fragment, self._backbone_only)
        if self._sanitize:
            temp_dir = tempfile.gettempdir()
            if not verify_pdb(pdb, temp_dir):
                raise RuntimeError("Generated PDB could not be parsed")
        return pdb


class PDBGeneratorSanitizeProtein(PDBGenerator):
    """PDB generator for proteins with sanitization."""
    signature_type = "pdb_protein"
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config, backbone_only=False, sanitize=True, is_protein=True)


class PDBGeneratorNoSanitizeProtein(PDBGenerator):
    """PDB generator for proteins without sanitization."""
    signature_type = "pdb_protein"
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config, backbone_only=False, sanitize=False, is_protein=True)


class PDBBackboneGeneratorSanitizeProtein(PDBGenerator):
    """PDB backbone generator for proteins with sanitization."""
    signature_type = "pdb_protein"
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config, backbone_only=True, sanitize=True, is_protein=True)


class PDBBackboneGeneratorNoSanitizeProtein(PDBGenerator):
    """PDB backbone generator for proteins without sanitization."""
    signature_type = "pdb_protein"
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config, backbone_only=True, sanitize=False, is_protein=True)


class PDBGeneratorSanitizeNucleic(PDBGenerator):
    """PDB generator for nucleic acids with sanitization."""
    signature_type = "pdb_nucleic"
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config, backbone_only=False, sanitize=True, is_nucleotide=True)


class PDBGeneratorNoSanitizeNucleic(PDBGenerator):
    """PDB generator for nucleic acids without sanitization."""
    signature_type = "pdb_nucleic"
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config, backbone_only=False, sanitize=False, is_nucleotide=True)


class PDBBackboneGeneratorSanitizeNucleic(PDBGenerator):
    """PDB backbone generator for nucleic acids with sanitization."""
    signature_type = "pdb_nucleic"
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config, backbone_only=True, sanitize=True, is_nucleotide=True)


class PDBBackboneGeneratorNoSanitizeNucleic(PDBGenerator):
    """PDB backbone generator for nucleic acids without sanitization."""
    signature_type = "pdb_nucleic"
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config, backbone_only=True, sanitize=False, is_nucleotide=True)


def fragment_to_pdb(fragment: AtomGroup, only_backbone: bool) -> str:
    """Convert fragment to PDB string using various techniques."""
    try:
        return fragment_to_pdb_biopython(fragment, only_backbone)
    except Exception:
        pass
    
    try:
        return fragment_to_pdb_direct(fragment, only_backbone, include_bonds=True)
    except Exception:
        pass
    
    try:
        return fragment_to_pdb_direct(fragment, only_backbone, include_bonds=False)
    except Exception:
        pass
    
    raise RuntimeError("Unable to generate PDB signature")


def verify_pdb(pdb: str, temp_directory: str) -> bool:
    """Verify PDB can be parsed.
    
    Bug fix: Ensure temp file is unlinked even if parsing raises.
    Do not turn warnings into errors - only fail on actual exceptions.
    """
    fd, path = tempfile.mkstemp(suffix=".pdb", dir=temp_directory)
    try:
        os.close(fd)
        with open(path, 'w') as f:
            f.write(pdb)
        
        success = True
        try:
            parser = PDBParser(QUIET=True)
            parser.get_structure("export", path)
        except Exception:
            success = False
        
        return success
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def fragment_to_pdb_biopython(fragment: AtomGroup, only_backbone: bool) -> str:
    """Generate PDB string using Biopython.
    
    Bug fix: Use 1-based sequential serial numbers instead of mapping original IDs.
    """
    structure = Structure.Structure("export")
    model = Model.Model(0)
    chain = Chain.Chain("A")
    
    for resid, resname in zip(fragment.residues.resnums, fragment.residues.resnames):
        atoms = fragment.select_atoms(f"resid {resid}")
        residue = Residue.Residue((" ", resid, " "), resname, "")
        
        if only_backbone:
            mean_position = np.array(atoms.atoms.positions, dtype=float)
            # Use 1-based serial number
            atom = Atom.Atom(
                atoms.atoms.names[0],
                np.array(mean_position.mean(axis=0)),
                1.0,
                1.0,
                " ",
                "CA",
                resid + 1,
                "C"
            )
            residue.add(atom)
        else:
            for i in range(len(atoms)):
                # Use 1-based sequential serial number
                atom = Atom.Atom(
                    atoms.names[i],
                    np.array(atoms.positions[i]),
                    1.0,
                    1.0,
                    " ",
                    atoms.names[i],
                    i + 1,
                    str(atoms.elements[i]).upper()
                )
                residue.add(atom)
        
        chain.add(residue)
    
    model.add(chain)
    structure.add(model)
    
    io = PDBIO()
    io.set_structure(structure)
    
    from io import StringIO
    pdb_string_io = StringIO()
    io.save(pdb_string_io)
    pdb = pdb_string_io.getvalue()
    pdb_string_io.close()
    return pdb


def _pdb_atom_line(
    atom_idx: int,
    atom_name: str,
    atom_elem: str,
    residue_name: str,
    residue_idx: int,
    pos_x: float,
    pos_y: float,
    pos_z: float,
) -> str:
    """Create ATOM line for PDB file."""
    return "{:6s}{:5d} {:^4s}{:1s}{:3s} {:1s}{:4d}{:1s}   {:8.3f}{:8.3f}{:8.3f}{:6.2f}{:6.2f}          {:>2s}{:2s}".format(
        "ATOM",
        atom_idx,
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
        atom_elem,
        "",
    )


def _pdb_bonds_line(atom_idx: int, other_atoms: set[int]) -> list[str]:
    """Create CONECT line(s) for PDB file.
    
    Bug fix: Handle >4 bonds by writing multiple CONECT lines.
    PDB spec limits 4 bonded atoms per CONECT line.
    """
    lines = []
    other_list = sorted(other_atoms)
    
    # Write CONECT lines in chunks of 4
    for i in range(0, len(other_list), 4):
        chunk = other_list[i:i+4]
        if len(chunk) == 1:
            fmt = "{:6s}{:5d}{:5d}"
            lines.append(fmt.format("CONECT", atom_idx, chunk[0]))
        elif len(chunk) == 2:
            fmt = "{:6s}{:5d}{:5d}{:5d}"
            lines.append(fmt.format("CONECT", atom_idx, chunk[0], chunk[1]))
        elif len(chunk) == 3:
            fmt = "{:6s}{:5d}{:5d}{:5d}{:5d}"
            lines.append(fmt.format("CONECT", atom_idx, chunk[0], chunk[1], chunk[2]))
        else:  # 4
            fmt = "{:6s}{:5d}{:5d}{:5d}{:5d}{:5d}"
            lines.append(fmt.format("CONECT", atom_idx, chunk[0], chunk[1], chunk[2], chunk[3]))
    
    return lines


def fragment_to_pdb_direct(
    fragment: AtomGroup,
    only_backbone: bool,
    include_bonds: bool,
) -> str:
    """Convert fragment to PDB string directly."""
    from io import StringIO
    
    processed_residues = set()
    fd = StringIO()
    
    fd.write("HEADER    export\n")
    
    for atom_i in range(fragment.n_atoms):
        if only_backbone:
            if fragment.atoms.resindices[atom_i] in processed_residues:
                continue
            else:
                processed_residues.add(fragment.atoms.resindices[atom_i])
        
        fd.write(
            _pdb_atom_line(
                fragment.atoms.ids[atom_i],
                fragment.atoms.names[atom_i],
                fragment.atoms.elements[atom_i] if not only_backbone else "C",
                fragment.atoms.resnames[atom_i],
                fragment.atoms.resindices[atom_i],
                float(fragment.atoms.positions[atom_i][0]),
                float(fragment.atoms.positions[atom_i][1]),
                float(fragment.atoms.positions[atom_i][2]),
            ) + "\n"
        )
    
    if include_bonds:
        conns = defaultdict(set)
        for atom_idx1, atom_idx2 in fragment.atoms.bonds.indices:
            conns[atom_idx1].add(atom_idx2)
            conns[atom_idx2].add(atom_idx1)
        for atom_idx in conns:
            # Bug fix: _pdb_bonds_line now returns list of lines for >4 bonds
            for line in _pdb_bonds_line(atom_idx, conns[atom_idx]):
                fd.write(line + "\n")
        
        fd.write("END\n")
    
    pdb = fd.getvalue()
    fd.close()
    return pdb
