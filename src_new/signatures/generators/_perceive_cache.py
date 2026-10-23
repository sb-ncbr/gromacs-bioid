"""B-14 (red-team 4.1): perceive-once cache for RDKit chemistry generators.

Historically every RDKit-based generator rebuilt the molecule from the SAME
fragment (atoms -> topology bonds / coordinate perception -> bond-order
determination). The bond-order step (rdDetermineBonds) is the expensive part
(B-01's 106 s NAD case). Generator families with byte-identical build
procedures (smiles-class x2; inchi == selfies) now share one pristine
built Mol per fragment; each generator receives a private Chem.Mol copy for
its own post-processing (RemoveHs/sanitize/encodings), so results are
bit-identical to the uncached path.

Semantics:
- cache key is the AtomGroup itself (MDAnalysis value-hashes by atom
  selection -> one entry per fragment instance even across re-selects);
- build errors are cached too and re-raised to later family members
  (fail-fast; identical error strings recorded per generator, as today);
- BAT3_PERCEIVE_CACHE_OFF=1 bypasses the cache entirely (A/B testing +
  rollback switch);
- timeout_s is a SOFT cap (SIGALRM where preemptible): RDKit C++ calls
  cannot be interrupted mid-flight; the hard subprocess cap is deliberately
  part of the 4.3 (B-07) deadline plumbing.
"""
from __future__ import annotations

import logging
import os
import signal
import threading
import weakref

from rdkit import Chem

logger = logging.getLogger("base")

_cache: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


class PerceiveTimeoutError(RuntimeError):
    """Perceive build exceeded its soft timeout budget."""


def clear_cache() -> None:
    _cache.clear()


def cache_enabled() -> bool:
    return os.environ.get("BAT3_PERCEIVE_CACHE_OFF", "0") != "1"


def _with_soft_timeout(seconds: float, fn):
    if (seconds and seconds > 0
            and threading.current_thread() is threading.main_thread()
            and hasattr(signal, "SIGALRM")):
        def _handler(signum, frame):
            raise PerceiveTimeoutError(f"perceive build exceeded {seconds}s")
        old = signal.signal(signal.SIGALRM, _handler)
        signal.setitimer(signal.ITIMER_REAL, float(seconds))
        try:
            return fn()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            signal.signal(signal.SIGALRM, old)
    return fn()


def build_once_cached(fragment, family: str, builder, timeout_s: float = 0.0):
    """Return a private copy of the fragment's built Mol for `family`.

    The FIRST family member to call pays the build; later members receive
    Chem.Mol copies of the cached pristine Mol, or the same exception again.
    """
    if not cache_enabled():
        return _with_soft_timeout(timeout_s, builder)

    fam = _cache.get(fragment)
    if fam is None:
        fam = _cache[fragment] = {}
    entry = fam.get(family)
    if entry is not None:
        kind, payload = entry
        if kind == "ok":
            return Chem.Mol(payload)
        raise payload
    try:
        mol = _with_soft_timeout(timeout_s, builder)
    except Exception as exc:
        fam[family] = ("err", exc)
        raise
    fam[family] = ("ok", mol)
    return Chem.Mol(mol)


# --- shared family builders -------------------------------------------------

def _atoms_into(fragment, atom_idx_to_index, molecule_build):
    """Atom construction identical to the inchi/selfies family helpers."""
    from rdkit import Chem as _Chem
    atom_idx_to_rdkit_idx = {}
    for atom_idx in fragment.atoms.indices:
        i = atom_idx_to_index[atom_idx]
        rdkit_atom = _Chem.Atom(str(fragment.atoms.elements[i]).title())
        rdkit_atom.SetNoImplicit(True)
        rdkit_idx = molecule_build.AddAtom(rdkit_atom)
        atom_idx_to_rdkit_idx[atom_idx] = rdkit_idx
    return atom_idx_to_rdkit_idx


def _bonds_into(fragment, atom_idx_to_rdkit_idx, molecule_build):
    from rdkit import Chem as _Chem
    for atom_idx1, atom_idx2 in fragment.bonds.indices:
        molecule_build.AddBond(
            atom_idx_to_rdkit_idx[int(atom_idx1)],
            atom_idx_to_rdkit_idx[int(atom_idx2)],
            _Chem.BondType.SINGLE,
        )


def build_once_family_mol(fragment):
    """inchi/selfies family build: atoms + topology bonds + ONE bond-order
    attempt at formal-charge 0 (exception deliberately swallowed, mol keeps
    whatever bond orders were assigned) — byte-identical to both modules'
    historical code."""
    from rdkit import Chem as _Chem
    from rdkit.Chem import rdDetermineBonds as _rdb
    atom_idx_to_index = {
        atom_idx: i for i, atom_idx in enumerate(fragment.atoms.indices)}
    molecule_build = _Chem.EditableMol(_Chem.Mol())
    rdkit_idx = _atoms_into(fragment, atom_idx_to_index, molecule_build)
    _bonds_into(fragment, rdkit_idx, molecule_build)
    molecule = molecule_build.GetMol()
    try:
        charge = sum(a.GetFormalCharge() for a in molecule.GetAtoms())
        _rdb.DetermineBondOrders(
            molecule, allowChargedFragments=True, embedChiral=False,
            charge=charge)
    except Exception:
        pass  # historical behavior: unsanitized/all-single is fine here
    return molecule
