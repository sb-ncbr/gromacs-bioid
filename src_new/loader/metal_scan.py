"""Coordinated/free metal species scan (F19 — coordinated-metal awareness).

Design contract (user-approved 2026-10-01, audit-validated):
  * Presence-based, GT-blind, add-only. The S7 ion channel scores presence of
    an element in the box; bound metals were invisible because single-atom
    metal residues are orphaned from connectivity-based segmentation
    (audit: 27/27 blinded metals absent from EVERY instance composition;
    26/27 coordinated to protein/nucleic within 3.0 A).
  * Element vocabulary is EXACTLY the ion channel's
    (`_ion_elements_of.metals_like` in validation campaign_stats) — 31
    symbols INCLUDING halides. Scanning metals-only would miss Cl/Br/I/F
    (evidence battery v1 bug, fixed v2).
  * Hot path is a single pass over universe atoms — NO distance math
    (~15 ms at 300k atoms). Coordination context is computed only for
    transition-metal atoms, capped, via a lazily built cKDTree
    (O(n log n), ~8 ms at 33.6k / ~0.1 s at 300k), and degrades cleanly.
  * Nothing here feeds GT knowledge anywhere; S7 consumes only the
    presence set (union with the fragment-token channel).

Payload persisted as results data key `fragments/metals`.
"""
from __future__ import annotations

import collections

# Exact ion-channel vocabulary (campaign_stats._ion_elements_of.metals_like).
# Title case; halides included. Do not "improve" — the channel compares
# against this set verbatim.
ION_CHANNEL_VOCAB: tuple[str, ...] = (
    "Ca", "Mg", "Zn", "Ni", "K", "Na", "Fe", "Cu", "Co", "Mn",
    "Li", "Rb", "Cs", "Sr", "Ba", "Cd", "Hg", "Ag", "Au",
    "Cl", "F", "I", "Br", "Al", "Mo", "W", "V", "Ti", "Cr", "Sn", "Pb",
)

# Atoms of these elements receive per-atom coordination context (bounded).
# Alkali metals and halides (large solvent-borne populations) are emitted
# presence-only, keeping ionic/membrane boxes on the cheap path.
CONTEXT_METALS: frozenset[str] = frozenset({
    "Zn", "Fe", "Cu", "Co", "Mn", "Ni", "Cd", "Hg", "Ag", "Au",
    "Mg", "Ca", "Sr", "Ba", "Mo", "W", "V", "Ti", "Cr", "Al", "Sn", "Pb",
})

_PROTEIN_RES = frozenset({
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
    "HIE", "HID", "HIP", "CYX", "CYM", "ASH", "GLH", "MSE", "SEC", "PYL",
})
_NUCLEIC_RES = frozenset({
    "DA", "DC", "DG", "DT", "DU", "A", "C", "G", "U",
    "ADE", "CYT", "GUA", "THY", "URA",
})
_WATER_RES = frozenset({"HOH", "WAT", "SOL", "H2O", "TIP3", "TIP3P", "SPC",
                        "DOD"})

DEFAULT_MAX_CONTEXT_ATOMS = 200
DEFAULT_COORDINATION_CUTOFF = 3.0
_MAX_PARTNERS = 8

_VOCAB_UP = {s.upper(): s for s in ION_CHANNEL_VOCAB}


def _empty_payload(reason: str, cutoff: float, cap: int) -> dict:
    return {
        "schema": 1,
        "present_elements": [],
        "element_atom_counts": {},
        "atoms": [],
        "context": {
            "computed": False,
            "reason": reason,
            "transition_atom_count": 0,
            "cutoff_A": cutoff,
            "cap": cap,
        },
        "newly_visible_elements": [],
    }


def _residue_kind(resname: str) -> str:
    # A-18 (red-team 3.7): consult the SHARED residue tables too — the local
    # _PROTEIN_RES missed HSD/HSE/HSP (CHARMM) and other common variants, so
    # metal-context resnames were mislabelled "other" downstream.
    from ..constants import KNOWN_RESIDUE_CODES, KNOWN_NUCLEIC_ACIDS_CODES
    rn = (resname or "").upper()
    if rn in _PROTEIN_RES or rn in KNOWN_RESIDUE_CODES:
        return "protein"
    if rn in _NUCLEIC_RES or rn in KNOWN_NUCLEIC_ACIDS_CODES:
        return "nucleic"
    if rn in _WATER_RES:
        return "water"
    return "other"


def scan_metals(
    universe,
    *,
    visible_elements: set[str] | None = None,
    max_context_atoms: int = DEFAULT_MAX_CONTEXT_ATOMS,
    coordination_cutoff: float = DEFAULT_COORDINATION_CUTOFF,
) -> dict:
    """Scan a loaded universe for ion-channel elements.

    Args:
        universe: MDAnalysis Universe (loaded, repaired). Elements attr may
            be missing (degrades to reason="no_elements").
        visible_elements: optional set of element symbols already visible to
            the fragment-token channel (union of instance compositions), used
            to compute `newly_visible_elements` (mechanism evidence).
        max_context_atoms: hard cap on per-atom coordination computation;
            above cap the payload is presence-only (reason recorded).
        coordination_cutoff: contact distance in Angstrom.

    Returns:
        JSON-serialisable payload dict (see module docstring).
    """
    atoms = universe.atoms
    try:
        elements = atoms.elements
    except Exception:
        return _empty_payload("no_elements", coordination_cutoff,
                              max_context_atoms)

    present: collections.Counter = collections.Counter()
    labels: list[str | None] = []
    transition_idx: list[int] = []
    for i, raw in enumerate(elements):
        lab = _VOCAB_UP.get(str(raw).upper())
        labels.append(lab)
        if lab is not None:
            present[lab] += 1
            if lab in CONTEXT_METALS:
                transition_idx.append(i)

    payload = _empty_payload(None, coordination_cutoff, max_context_atoms)
    payload["present_elements"] = sorted(present)
    payload["element_atom_counts"] = dict(sorted(present.items()))
    payload["context"]["transition_atom_count"] = len(transition_idx)
    payload["context"]["computed"] = True

    # ----- per-atom coordination context (bounded) -----
    atom_records = []
    n_atoms = len(atoms)
    if transition_idx and len(transition_idx) > max_context_atoms:
        payload["context"]["computed"] = False
        payload["context"]["reason"] = "context_atom_cap_exceeded"
    elif transition_idx:
        try:
            resnames = [str(r) for r in atoms.resnames]
        except Exception:
            resnames = [""] * n_atoms
        try:
            positions = atoms.positions
        except Exception:
            positions = None
        if positions is None:
            payload["context"]["computed"] = False
            payload["context"]["reason"] = "no_positions"
        else:
            try:
                from scipy.spatial import cKDTree
            except Exception:
                cKDTree = None
            if cKDTree is None:
                payload["context"]["computed"] = False
                payload["context"]["reason"] = "no_scipy"
            else:
                import numpy as np

                # A-18 (red-team 3.7): periodic coordination — wrap positions
                # into the orthorhombic cell and pass boxsize to the tree;
                # a metal at x=0.2 coordinated by a ligand at x=9.9 (L=10)
                # was reported "free" before.
                box = None
                try:
                    dims = atoms.dimensions
                    dims = np.asarray(dims, dtype=float) if dims is not None else None
                    if (dims is not None and len(dims) >= 6
                            and np.all(dims[:3] > 0)
                            and np.allclose(dims[3:6], 90.0, atol=1e-4)):
                        box = dims[:3]
                except Exception:
                    box = None
                all_pos = np.asarray(positions, dtype=float)
                if box is not None:
                    all_pos = all_pos % box

                heavy = [i for i in range(n_atoms)
                         if str(elements[i]).upper() != "H"]
                tree = (cKDTree(all_pos[heavy], boxsize=box)
                        if box is not None else cKDTree(all_pos[heavy]))
                try:  # A-13: materialize once, not up to 200x per scan
                    resids_arr = list(atoms.resids)
                except Exception:
                    resids_arr = None
                try:
                    segids_arr = list(atoms.segids)
                except Exception:
                    segids_arr = None
                for i in transition_idx:
                    rec = _context_record(
                        i, atoms, elements, resnames, heavy, all_pos,
                        tree, labels[i], coordination_cutoff,
                        resids_arr=resids_arr, segids_arr=segids_arr)
                    atom_records.append(rec)

    payload["atoms"] = atom_records

    if visible_elements is not None:
        visible = {_VOCAB_UP.get(str(v).upper(), str(v))
                   for v in visible_elements}
        payload["newly_visible_elements"] = sorted(
            set(present) - visible)
    return payload


def _context_record(i, atoms, elements, resnames, heavy, positions, tree,
                    label, cutoff, resids_arr=None, segids_arr=None):
    rec = {
        "element": label,
        "resname": resnames[i],
        "single_atom_residue": None,
        "coordination": "unknown",
        "partners": [],
    }
    try:
        rec["resid"] = int(resids_arr[i] if resids_arr is not None else atoms.resids[i])
    except Exception:
        pass
    try:
        rec["segid"] = str(segids_arr[i] if segids_arr is not None else atoms.segids[i])
    except Exception:
        pass
    try:
        rec["single_atom_residue"] = bool(len(atoms[i].residue.atoms) == 1)
    except Exception:
        pass

    import numpy as np

    pt = np.asarray(positions[i])
    js = tree.query_ball_point(pt, cutoff)
    partners = []
    for j in js:
        src = heavy[j]
        if src == i:
            continue
        d = float(np.linalg.norm(pt - positions[src]))
        if d < 0.01:
            continue  # self / coincident
        rn = resnames[src]
        partners.append({
            "resname": rn,
            "kind": _residue_kind(rn),
            "distance_A": round(d, 2),
        })
    partners.sort(key=lambda p: p["distance_A"])
    rec["partners"] = partners[:_MAX_PARTNERS]
    kinds = {p["kind"] for p in partners}
    if kinds & {"protein", "nucleic"}:
        rec["coordination"] = "bound"
    elif kinds - {"water"}:
        rec["coordination"] = "associated"
    else:
        rec["coordination"] = "free"
    return rec
