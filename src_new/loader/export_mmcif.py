from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import MDAnalysis

from ..results.results_manager import ResultsManager
from .universe_facade import LoadedUniverse
from .unwrap import MMCIFIOWithCell

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


def _get_universe_dimensions(universe):
    """Safely get universe dimensions, returning None if unavailable.
    
    MDAnalysis raises AttributeError if no trajectory is loaded.
    """
    try:
        return universe.dimensions
    except AttributeError:
        return None


def _build_biopython_structure_from_atoms(atoms) -> Structure.Structure:
    """Build a Biopython Structure from an AtomGroup (virtual segments)."""
    class _Wrapper:
        pass
    w = _Wrapper()
    w.atoms = atoms
    # Reuse the same builder; atoms already carry their own segids, so no
    # filter is applied.
    return _build_biopython_structure(w)


def input_image_positions(universe: MDAnalysis.Universe, displacement) -> "Any | None":
    """Positions with every molecule back in the periodic image of the input.

    The PBC unwrap (reference="com") makes molecules whole and moves each
    one's centre into the primary cell. For the 3D view that second move is
    wrong whenever a molecule sat outside the cell next to its partner: a
    crystal ligand at x = -1.9 A went to +53.0 A, out of its pocket (3PTB).
    Per fragment (bonded molecule; residues without bonds), the whole-lattice
    part of the recorded displacement is undone: atoms of a molecule that was
    whole in the input return exactly to their input positions, and a
    molecule split by the box stays whole, in the image most of its atoms
    had. Identification never reads these positions. None when nothing moves.
    """
    import numpy as np

    if displacement is None:
        return None
    disp = np.asarray(displacement, dtype=np.float64)
    if disp.shape != (len(universe.atoms), 3):
        return None
    dims = _get_universe_dimensions(universe)
    if dims is None or not np.all(np.asarray(dims[:3], dtype=float) > 0):
        return None
    from MDAnalysis.lib.mdamath import triclinic_vectors

    box = np.asarray(triclinic_vectors(dims), dtype=np.float64)  # rows = cell vectors
    inv = np.linalg.inv(box)
    try:
        groups = [f.indices for f in universe.atoms.fragments] if len(universe.bonds) else None
    except Exception:  # noqa: BLE001 — no bonds topology
        groups = None
    if groups is None:
        groups = [r.atoms.indices for r in universe.residues]
    pos = universe.atoms.positions.astype(np.float64)
    moved = 0
    for idx in groups:
        if len(idx) == 0:
            continue
        n = np.rint(disp[idx].mean(axis=0) @ inv)
        if np.any(n):
            pos[idx] -= n @ box
            moved += 1
    if not moved:
        return None
    logger.info(f"System export: {moved} molecules returned to their input periodic image")
    return pos.astype(np.float32)


def _build_biopython_structure(universe: MDAnalysis.Universe, filter_segment: str | None = None,
                               residue_ids: dict | None = None, positions=None) -> Structure.Structure:
    """Build a Biopython Structure from an MDAnalysis Universe.

    residue_ids, when given, is filled with atom index -> (chain id,
    written auth_seq_id, insertion code) for the G9 residue-range selectors.
    positions, when given, replaces the universe positions (indexed by atom
    index; input_image_positions)."""
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
        # v3.143 (A-14): key the cache by true residue identity — (resid,
        # resname) collides across chains, so chain B's MET-1 landed in chain
        # A's residue and Biopython raised 'Atom N defined twice' on every
        # homo-oligomer whole-system export (recorded as system_export_failed).
        rindex = int(atom.resindex) if hasattr(atom, 'resindex') else (chain_id, resid, resname)
        
        if rindex in cached_residues:
            residue = cached_residues[rindex]
        else:
            residue = Residue.Residue(
                _free_residue_id(chain, resid, getattr(atom, 'icode', '')),
                resname, '')
            cached_residues[rindex] = residue
            chain.add(residue)
        
        if positions is not None:
            pos = positions[atom.index]
        else:
            pos = atom.position if hasattr(atom, 'position') else [0.0, 0.0, 0.0]
        bp_atom = Atom.Atom(
            atom_name, pos, 0.0, 0.0, '.', atom_name, atom.index, element=element.upper()
        )
        residue.add(bp_atom)
        if residue_ids is not None:
            residue_ids[int(atom.index)] = (chain_id, residue.id[1], residue.id[2])
    
    return structure


_ICODE_FALLBACK = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _free_residue_id(chain, resid: int, icode) -> tuple:
    """Biopython residue id (hetfield, resseq, icode) not yet used in chain.

    g1 (2026-11-06, 3PTB trypsin): the insertion code was dropped, so
    chymotrypsin-numbered 184/184A became two (' ', 184, ' ') residues and
    Biopython aborted the WHOLE system export ("defined twice") — no system
    mmCIF, no protein segment export, no G9 selectors. The deposited icode
    is kept; any remaining clash (two molecules sharing a number in one
    chain) gets the first free insertion letter instead of failing."""
    code = str(icode or "").strip()[:1] or " "
    rid = (" ", resid, code)
    if not chain.has_id(rid):
        return rid
    for letter in _ICODE_FALLBACK:
        alt = (" ", resid, letter)
        if not chain.has_id(alt):
            return alt
    n = 1
    while chain.has_id((f"H_{n}", resid, " ")):
        n += 1
    return (f"H_{n}", resid, " ")


def _indices_to_ranges(indices: list[int]) -> list[list[int]]:
    """Collapse sorted atom indices into [start, end_exclusive) ranges."""
    ranges: list[list[int]] = []
    start = prev = indices[0]
    for idx in indices[1:]:
        if idx == prev + 1:
            prev = idx
            continue
        ranges.append([start, prev + 1])
        start = prev = idx
    ranges.append([start, prev + 1])
    return ranges


def _residue_ranges(segment_atoms, residue_ids: dict, owners: dict) -> list[list] | None:
    """[[chain, beg_auth_seq_id, end_auth_seq_id], ...] covering exactly the
    segment's residues, or None when a residue number is shared with another
    segment in the same chain (an auth_seq_id range cannot tell them apart;
    the caller keeps atom-index addressing for that segment)."""
    per_chain: dict[str, set[int]] = {}
    for idx in segment_atoms.indices:
        rid = residue_ids.get(int(idx))
        if rid is None:
            return None
        per_chain.setdefault(rid[0], set()).add(int(rid[1]))
    ranges: list[list] = []
    for chain, numbers in sorted(per_chain.items()):
        # every number in a run must belong to this segment alone
        if any(len(owners.get((chain, n), ())) != 1 for n in numbers):
            return None
        ordered = sorted(numbers)
        beg = prev = ordered[0]
        for n in ordered[1:]:
            # a gap is fine only if no residue of ANY segment sits in it
            if n == prev + 1 or not any((chain, k) in owners for k in range(prev + 1, n)):
                prev = n
                continue
            ranges.append([chain, beg, prev])
            beg = prev = n
        ranges.append([chain, beg, prev])
    return ranges


def _segment_atoms(facade, segment: str):
    """All copies when the facade can list them, else the representative
    fragment's atoms; None when the facade knows neither."""
    if hasattr(facade, "get_segment_all_atoms"):
        try:
            return facade.get_segment_all_atoms(segment)
        except KeyError:
            pass
    frag = facade.get_fragment(segment) if hasattr(facade, "get_fragment") else None
    return getattr(frag, "atoms", frag) if frag is not None else None


def _segment_selectors(facade: LoadedUniverse, residue_ids: dict | None = None) -> dict[str, dict]:
    """Per-segment selectors into the exported system mmCIF (BACKEND_GAPS G9).

    ``_build_biopython_structure`` groups atoms into chains by segid
    (first-seen order), and Biopython's MMCIFIO renumbers
    ``_atom_site.id`` as the 1-based row position in write order
    (``preserve_atom_numbering`` is not used). The selector contract is
    therefore defined in FILE-ROW terms:

    - ``chains``: the ``auth_asym_id`` value(s) the segment's atoms land
      in. Virtual minority segments (``X__vN``) carry the PARENT segid,
      so chain-based highlighting alone cannot isolate them (the UI's
      documented fallback); the atom ranges below can.
    - ``atom_index_ranges``: sorted, merged ``[start, end_exclusive)``
      ranges of the segment's atom rows in the written atom_site loop,
      0-based (``_atom_site.id`` = row + 1). Exact even when a virtual
      segment's atoms interleave with its siblings' in the universe.
    """
    # Replicate the writer's row assignment: chains appear in first-seen
    # segid order; atoms within a chain in universe iteration order.
    universe = facade.universe
    row_of_atom: dict[int, int] = {}
    chain_order: list[str] = []
    per_chain_atoms: dict[str, list[int]] = {}
    for atom in universe.atoms:
        seg = str(atom.segid)
        if seg not in per_chain_atoms:
            chain_order.append(seg)
            per_chain_atoms[seg] = []
        per_chain_atoms[seg].append(int(atom.index))
    row = 0
    for seg in chain_order:
        for aidx in per_chain_atoms[seg]:
            row_of_atom[aidx] = row
            row += 1

    # W3 A2/B4 (BH-002): each segment's OWN atoms — a segid can hold several
    # species (chain + stray atom); selecting by segid would leak a virtual
    # sibling's atoms into the parent's ranges (cytc: HEM Fe -> B__v1 inside
    # seg B). G9 follow-up (user 2026-11-06): ALL copies of the molecule, so
    # 145 POPC / 62 crystal waters colour fully, not just the first copy.
    universe_segids = {str(s) for s in universe.atoms.segids}
    seg_atoms: dict[str, object] = {}
    for segment in sorted(facade.get_segments()):
        atoms = _segment_atoms(facade, segment)
        if atoms is None and segment in universe_segids:
            atoms = universe.atoms[universe.atoms.segids == segment]
        if atoms is not None and len(atoms.indices):
            seg_atoms[segment] = atoms

    # (chain, auth_seq_id) -> segments with a residue there (range purity)
    owners: dict = {}
    if residue_ids:
        for segment, atoms in seg_atoms.items():
            for idx in atoms.indices:
                rid = residue_ids.get(int(idx))
                if rid is not None:
                    owners.setdefault((rid[0], int(rid[1])), set()).add(segment)

    selectors: dict[str, dict] = {}
    for segment, atoms in seg_atoms.items():
        rows = sorted(row_of_atom[int(i)] for i in atoms.indices)
        if not rows:
            continue
        entry = {
            "chains": sorted({str(s) for s in atoms.segids}),
            "atom_index_ranges": _indices_to_ranges(rows),
            "atom_count": len(rows),
        }
        if residue_ids:
            ranges = _residue_ranges(atoms, residue_ids, owners)
            if ranges is not None:
                entry["residue_ranges"] = ranges
        selectors[segment] = entry
    return selectors


def export_system_mmcif(facade: LoadedUniverse, output_path: Path, results: ResultsManager | None = None,
                        unwrap_displacement=None) -> Path:
    """Export the whole system to mmCIF.

    unwrap_displacement: the per-atom PBC-unwrap displacement (PbcRepair);
    molecules are written in their input periodic image (input_image_positions)."""
    if not BIOPYTHON_AVAILABLE:
        raise ImportError("Biopython is required for mmCIF export. Install with: pip install biopython")
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    residue_ids: dict = {}
    try:
        positions = input_image_positions(facade.universe, unwrap_displacement)
    except Exception as exc:  # noqa: BLE001 — display aid; never fail the export
        logger.warning(f"Input-image positions skipped: {exc}")
        positions = None
    structure = _build_biopython_structure(facade.universe, residue_ids=residue_ids, positions=positions)
    
    # Use MMCIFIOWithCell to preserve box dimensions
    cell = _get_universe_dimensions(facade.universe)
    if cell is not None:
        io = MMCIFIOWithCell(cell=cell)
    else:
        io = MMCIFIO()
    
    io.set_structure(structure)
    io.save(str(output_path))
    
    if results is not None:
        results.add_artifact("SYSTEM", output_path, description="Whole-system mmCIF export", kind="mmcif")
        results.set_data("exports/system_mmcif", str(output_path))
        # v3.143 (BACKEND_GAPS G9, additive): per-segment selectors into the
        # system mmCIF (auth chain + exact atom-index ranges; 0-based
        # universe atom id = _atom_site.id). Best-effort: selector failure
        # must not fail the export.
        try:
            results.set_data("render/segment_selectors",
                             _segment_selectors(facade, residue_ids))
        except Exception as exc:
            logger.warning(f"Segment-selector computation failed: {exc}")
    
    logger.info(f"Exported whole-system mmCIF to {output_path}")
    return output_path


def export_segment_mmcif(facade: LoadedUniverse, segment_name: str, output_path: Path, results: ResultsManager | None = None) -> Path:
    """Export a single segment to mmCIF."""
    if not BIOPYTHON_AVAILABLE:
        raise ImportError("Biopython is required for mmCIF export. Install with: pip install biopython")
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # v3.143 (A-14): virtual segments carry the PARENT segid on their atoms —
    # filtering the universe by the virtual name matched nothing and wrote
    # empty mmCIFs; export the facade's fragment directly instead.
    if segment_name is not None and segment_name not in set(facade.universe.segments.segids):
        structure = _build_biopython_structure_from_atoms(facade.get_fragment(segment_name))
    else:
        # A-13 (red-team 3.8): vectorized mask first — no all-universe Python
        # iteration per segment (was O(S x N))
        seg_atoms = facade.universe.atoms[facade.universe.atoms.segids == segment_name]
        structure = _build_biopython_structure(seg_atoms)
    
    # Use MMCIFIOWithCell to preserve box dimensions
    cell = _get_universe_dimensions(facade.universe)
    if cell is not None:
        io = MMCIFIOWithCell(cell=cell)
    else:
        io = MMCIFIO()
    
    io.set_structure(structure)
    io.save(str(output_path))
    
    if results is not None:
        results.add_artifact(segment_name, output_path, description=f"Segment '{segment_name}' mmCIF export", kind="mmcif")
        results.set_data(f"exports/segment_mmcif/{segment_name}", str(output_path))
    
    logger.info(f"Exported segment '{segment_name}' mmCIF to {output_path}")
    return output_path
