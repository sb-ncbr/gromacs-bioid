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
from ...molecules.nucleic_acid import select_na_backbone_atom
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
            # Wave-7: atomistic NA rejected here before (multi-atom == the
            # vast majority of DNA/RNA simulations) -> pdb_nucleic never
            # fired for them, defeating PDB structure search for NA. The
            # multi-atom restriction is dropped: coarse-grained (single-
            # atom residue) NA keeps working as before, atomistic NA gains
            # full/backbone PDB signatures.
            if not props.flags.get(SegmentProperty.IS_NUCLEIC.value, False):
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
        # Wave-7 B4: nucleic backbone trace uses the real guide atom
        # (C4' -> C3' -> P, PyMOL parity) at REAL coordinates instead of a
        # per-residue centroid pseudo-atom. Protein behavior is unchanged
        # (selector stays None).
        # B-12 (red-team 4.8): protein backbone variant selects the real CA
        # per residue (mirroring the NA guide-atom selector) instead of a
        # centroid pseudo-atom (RCS search accuracy, ~1.5 A mean deviation).
        if self._backbone_only and self._is_nucleotide:
            selector = select_na_backbone_atom
        elif self._backbone_only and self._is_protein:
            selector = _protein_backbone_atom
        else:
            selector = None
        pdb = fragment_to_pdb(fragment, self._backbone_only, backbone_selector=selector)
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


def fragment_to_pdb(
    fragment: AtomGroup,
    only_backbone: bool,
    backbone_selector=None,
) -> str:
    """Convert fragment to PDB string using various techniques.

    Args:
        backbone_selector: optional callable(residue_atoms) -> Atom picking
            the real backbone-tracing atom per residue (wave-7, nucleic
            acids). None preserves legacy pseudo-atom behavior exactly.
    """
    try:
        return fragment_to_pdb_biopython(fragment, only_backbone, backbone_selector)
    except Exception:
        pass

    try:
        return fragment_to_pdb_direct(fragment, only_backbone, include_bonds=True,
                                      backbone_selector=backbone_selector)
    except Exception:
        pass

    try:
        return fragment_to_pdb_direct(fragment, only_backbone, include_bonds=False,
                                      backbone_selector=backbone_selector)
    except Exception:
        pass

    raise RuntimeError("Unable to generate PDB signature")


def _protein_backbone_atom(residue_atoms):
    """B-12 (red-team 4.8): pick the REAL CA atom of one protein residue
    (mirrors the NA guide-atom selector). None falls back to the legacy
    per-residue pseudo-centroid below."""
    try:
        for atom in residue_atoms:
            if str(atom.name).strip() == "CA":
                return atom
    except Exception:
        pass
    return None


def _per_chain_labels_resseq(fragment):
    """B-12: residues keyed by (chain, resindex). Chain label from the
    first atom's chainID (fallback 'A'); resSeq restarts 1..n per chain in
    residue order (numbering restarts between chains no longer collide,
    and the 4-column resSeq field cannot overflow)."""
    labels = {}
    resseq = {}
    counters = {}
    try:
        chainids = fragment.atoms.chainIDs
        pos_of = {int(a): i for i, a in enumerate(fragment.atoms.indices)}
    except Exception:
        chainids = None
    for residue in fragment.residues:
        cid = "A"
        if chainids is not None:
            try:
                a0 = int(residue.atoms[0].index)
                cand = str(chainids[pos_of[a0]]).strip()
                if cand:
                    cid = cand
            except Exception:
                pass
        counters.setdefault(cid, 0)
        counters[cid] += 1
        labels[int(residue.resindex)] = cid
        resseq[int(residue.resindex)] = counters[cid]
    return labels, resseq


def _na_backbone_element(name: str) -> str:
    """Derive a PDB element from a backbone atom name (fallback when the
    topology carries no elements: backbone mode does not gate on elements).
    """
    stripped = name.replace("'", "").replace("*", "").strip()
    return stripped[0].upper() if stripped else "C"


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


def fragment_to_pdb_biopython(
    fragment: AtomGroup, only_backbone: bool, backbone_selector=None
) -> str:
    """Generate PDB string using Biopython.

    Bug fix: Use 1-based sequential serial numbers instead of mapping original IDs.
    Wave-7: with backbone_selector, emits the real guide atom per residue
    (real coordinates/element) instead of the centroid pseudo-atom.
    """
    structure = Structure.Structure("export")
    model = Model.Model(0)
    # B-12: key residues by (chain, resindex) — select_atoms("resid X")
    # merged same-numbered chains into one residue and crashed with
    # 'Atom N defined twice' (silent fallback to the direct writer).
    labels, resseq = _per_chain_labels_resseq(fragment)
    chains_out = {}
    serial = 0

    for residue in fragment.residues:
        rindex = int(residue.resindex)
        cid = labels[rindex]
        chain = chains_out.get(cid)
        if chain is None:
            chain = chains_out[cid] = Chain.Chain(cid)
        atoms = residue.atoms
        # c13 structure search (S1): PDB residue names (was [:3] truncation:
        # CYX reached RCSB verbatim -> 204 for the whole query; NALA -> NAL).
        residue_out = Residue.Residue(
            (" ", resseq[rindex], " "), _std_resname3(str(residue.resname)), "")

        if only_backbone:
            selected = (
                backbone_selector(atoms) if backbone_selector is not None else None
            )
            serial += 1
            if selected is not None:
                try:
                    element = str(selected.element).strip().upper()
                except Exception:
                    element = ""
                atom = Atom.Atom(
                    selected.name,
                    np.array(selected.position, dtype=float),
                    1.0,
                    1.0,
                    " ",
                    selected.name,
                    serial,
                    element or _na_backbone_element(selected.name),
                )
            else:
                # legacy centroid pseudo-atom (only when no selector atom)
                mean_position = np.array(atoms.positions, dtype=float)
                atom = Atom.Atom(
                    atoms.names[0],
                    np.array(mean_position.mean(axis=0)),
                    1.0,
                    1.0,
                    " ",
                    "CA",
                    serial,
                    "C"
                )
            residue_out.add(atom)
        else:
            for i in range(len(atoms)):
                serial += 1
                try:
                    element = str(atoms.elements[i]).strip().upper()
                except Exception:
                    element = ""
                atom = Atom.Atom(
                    atoms.names[i],
                    np.array(atoms.positions[i]),
                    1.0,
                    1.0,
                    " ",
                    atoms.names[i],
                    serial,
                    element
                )
                residue_out.add(atom)

        chain.add(residue_out)

    for chain in chains_out.values():
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




# v3.143 (B-04): hand-written PDB formatters pad but never TRUNCATE — 4-char
# residue names (LYSH/CYS2/HISE/NALA/terminal variants) and resSeq >= 10000
# shifted every following column and produced unparseable Foldseek/AlphaFind/
# RCSB inputs. Normalize to canonical 3-letter codes and renumber per chain.
# c13 structure search (S1): one normalizer for every PDB writer (was a
# drifting copy here), also mapping 3-char force-field names (CYX, HIE, ...).
from .topology_less_pdb import _std_resname3  # noqa: E402


def _renumber_writer_residues(resnums) -> dict:
    """Map original residue numbers to a clean 1..n sequence (order-of-first-
    appearance), so resSeq never overflows the 4-column PDB field."""
    seen: dict = {}
    nxt = 1
    for r in resnums:
        key = int(r)
        if key not in seen:
            seen[key] = nxt
            nxt += 1
    return seen


def _pdb_atom_line(
    atom_idx: int,
    atom_name: str,
    atom_elem: str,
    residue_name: str,
    residue_idx: int,
    pos_x: float,
    pos_y: float,
    pos_z: float,
    chain_id: str = "A",
) -> str:
    """Create ATOM line for PDB file (B-12: real chain column)."""
    return "{:6s}{:5d} {:^4s}{:1s}{:3s} {:1s}{:4d}{:1s}   {:8.3f}{:8.3f}{:8.3f}{:6.2f}{:6.2f}          {:>2s}{:2s}".format(
        "ATOM",
        atom_idx,
        atom_name,
        "",
        _std_resname3(residue_name),
        (chain_id or "A")[:1],
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
    backbone_selector=None,
) -> str:
    """Convert fragment to PDB string directly."""
    from io import StringIO

    processed_residues = set()
    fd = StringIO()

    fd.write("HEADER    export\n")

    # B-12: chain labels + per-chain 1..n resSeq; CONECT references the
    # serials actually written on the ATOM records.
    labels, resseq = _per_chain_labels_resseq(fragment)
    serial_of: dict[int, int] = {}
    try:
        atom_ids = fragment.atoms.ids
    except Exception:
        atom_ids = None

    if only_backbone and backbone_selector is not None:
        # Wave-7: real guide atom per residue at real coordinates
        # (nucleic backbone trace; B-12 adds the protein CA selector).
        for residue in fragment.residues:
            selected = backbone_selector(residue.atoms)
            atom = selected if selected is not None else residue.atoms[0]
            gidx = int(atom.index)
            try:
                serial = int(atom.id)
            except Exception:
                serial = gidx + 1
            try:
                element = str(atom.element).strip().upper()
            except Exception:
                element = ""
            serial_of[gidx] = serial
            fd.write(
                _pdb_atom_line(
                    serial,
                    atom.name,
                    element or _na_backbone_element(atom.name),
                    residue.resname,
                    resseq[int(residue.resindex)],
                    float(atom.position[0]),
                    float(atom.position[1]),
                    float(atom.position[2]),
                    chain_id=labels[int(residue.resindex)],
                ) + "\n"
            )
    else:
        for atom_i in range(fragment.n_atoms):
            if only_backbone:
                if fragment.atoms.resindices[atom_i] in processed_residues:
                    continue
                else:
                    processed_residues.add(fragment.atoms.resindices[atom_i])

            try:
                element = (fragment.atoms.elements[atom_i]
                           if not only_backbone else "C")
            except Exception:
                element = "" if not only_backbone else "C"
            serial = (int(atom_ids[atom_i]) if atom_ids is not None
                      else atom_i + 1)
            resindex = int(fragment.atoms.resindices[atom_i])
            serial_of[int(fragment.atoms.indices[atom_i])] = serial
            fd.write(
                _pdb_atom_line(
                    serial,
                    fragment.atoms.names[atom_i],
                    element,
                    fragment.atoms.resnames[atom_i],
                    resseq.get(resindex, resindex + 1),
                    float(fragment.atoms.positions[atom_i][0]),
                    float(fragment.atoms.positions[atom_i][1]),
                    float(fragment.atoms.positions[atom_i][2]),
                    chain_id=labels.get(resindex, "A"),
                ) + "\n"
            )

    if include_bonds:
        conns = defaultdict(set)
        for atom_idx1, atom_idx2 in fragment.atoms.bonds.indices:
            # B-12: reference written serials only (B-08: skip cross bonds)
            s1 = serial_of.get(int(atom_idx1))
            s2 = serial_of.get(int(atom_idx2))
            if s1 is None or s2 is None:
                continue
            conns[s1].add(s2)
            conns[s2].add(s1)
        for atom_serial in conns:
            for line in _pdb_bonds_line(atom_serial, conns[atom_serial]):
                fd.write(line + "\n")

        fd.write("END\n")
    
    pdb = fd.getvalue()
    fd.close()
    return pdb
