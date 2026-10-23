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
    """Atom construction identical to the inchi/selfies family helpers
    (+B-10 H-deficiency correction, h_map=None reproduces it exactly)."""
    from rdkit import Chem as _Chem
    h_map = _h_deficiency(fragment)
    atom_idx_to_rdkit_idx = {}
    for atom_idx in fragment.atoms.indices:
        i = atom_idx_to_index[atom_idx]
        rdkit_atom = _Chem.Atom(str(fragment.atoms.elements[i]).title())
        rdkit_atom.SetNoImplicit(True)
        rdkit_idx = molecule_build.AddAtom(rdkit_atom)
        atom_idx_to_rdkit_idx[atom_idx] = rdkit_idx
        # B-10 counts-mode: inject the mass-inferred implicit H as explicit
        # atoms (open-mode {} and all-atom None: no correction).
        if h_map:
            n = h_map.get(i, 0)
            if n > 0:
                _inject_inferred_hydrogens(molecule_build, rdkit_idx, n)
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
        # B-01 (red-team 4.2): topology net charge first, then ladder —
        # replaces the charge=0 single attempt (wrong keys for charged
        # ligands: first-block identical, protonation/charge layer wrong)
        determine_bond_orders_safely(molecule, net_charge=_net_charge(fragment))
    except Exception:
        pass  # historical behavior: unsanitized/all-single is fine here
    return molecule


# --- B-01 (red-team 4.2): charge-aware bond-order determination -------------

_TRIAL_CHARGES = (0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6)


def _net_charge(fragment) -> int:
    """Net molecular charge from topology partial charges (prmtop/tpr/psf/
    itp carry them; PDB/GRO typically do not -> 0, unchanged behavior)."""
    try:
        q = float(fragment.atoms.charges.sum())
    except Exception:
        return 0
    return int(round(q))


def _reset_to_single_bonds(mol) -> None:
    """Undo a DetermineBondOrders attempt: historical build state was
    all-SINGLE bonds with zero formal charges (atoms built SetNoImplicit)."""
    from rdkit import Chem as _Chem
    for b in mol.GetBonds():
        b.SetBondType(_Chem.BondType.SINGLE)
    for a in mol.GetAtoms():
        a.SetFormalCharge(0)
        a.SetNoImplicit(True)


def _has_bare_proton_fragment(mol) -> bool:
    """Charge-0 misfit artifact: an isolated [H+] with no bonds (arises when
    RDKit balances a wrong input charge by dumping a bare proton). A correct
    zwitterion (e.g. glycine NH3+/COO-) has its charges bonded in-framework
    and is NOT rejected."""
    for a in mol.GetAtoms():
        if (a.GetAtomicNum() == 1 and a.GetFormalCharge() == 1
                and a.GetDegree() == 0):
            return True
    return False


def determine_bond_orders_safely(mol, net_charge: int = 0) -> bool:
    """B-01: try the topology net charge first, then a 0,+-1..+-6 ladder.

    A successful DetermineBondOrders call is ACCEPTED only when the
    solution carries no bare-[H+] fragment artifact (evidence the input
    charge was wrong) and its formal-charge sum matches q. Mol is reset to
    the all-single state between attempts for determinism. Non-ValueError
    failures propagate (smiles semantics); callers that historically
    swallow exceptions keep doing so. Returns True when accepted."""
    from rdkit.Chem import rdDetermineBonds as _rdb
    order = [net_charge] + [q for q in _TRIAL_CHARGES if q != net_charge]
    for q in order:
        try:
            _rdb.DetermineBondOrders(
                mol, allowChargedFragments=True, embedChiral=False, charge=q)
        except ValueError:
            _reset_to_single_bonds(mol)
            continue
        no_bare_h = not _has_bare_proton_fragment(mol)
        charge_match = (sum(a.GetFormalCharge() for a in mol.GetAtoms()) == q)
        if no_bare_h and charge_match:
            return True
        # unacceptable solution: reset and continue the ladder
        _has_bare = not no_bare_h
        _reset_to_single_bonds(mol)
        logger.debug(
            "bond-order solution at charge %d rejected (%s)",
            q, "bare [H+] fragment" if _has_bare else "charge mismatch")
    return False


# --- B-10 (red-team 4.4): united-atom / H-less correction ---------------------

_NOMINAL_MASSES = {
    "C": 12.011, "N": 14.007, "O": 15.999, "H": 1.008, "S": 32.06,
    "P": 30.974, "F": 18.998, "CL": 35.45, "BR": 79.904, "I": 126.904,
    "SE": 78.971, "NA": 22.990, "MG": 24.305, "K": 39.098, "CA": 40.078,
    "FE": 55.845, "ZN": 65.38, "MN": 54.938, "CU": 63.546, "B": 10.81,
    "SI": 28.085,
}


def _h_deficiency(fragment):
    """Detect H-deficient (united-atom / H-less) heavy-atom fragments.

    Returns:
      None  -- all-atom system (explicit H present): NO correction, the
               historical SetNoImplicit(True) behavior is untouched;
      {}    -- H-less system whose masses carry no united-atom counts
               (PDB ligands): apply SetNoImplicit(False), RDKit fills
               valences instead of producing radicals/carbanions;
      {pos: n} -- masses-mode (GROMOS/ATB/CHARMM19 UA masses 13/14/15...):
               set exactly n implicit H on fragment atom position pos.
    """
    try:
        els = [str(e).title() for e in fragment.atoms.elements]
    except Exception:
        return None
    if not els or any(e == "H" for e in els):
        return None
    try:
        masses = fragment.atoms.masses
    except Exception:
        return {}
    counts = {}
    for pos, (e, m) in enumerate(zip(els, masses)):
        nominal = _NOMINAL_MASSES.get(e)
        m = float(m) if m else 0.0
        if not nominal or not m:
            continue
        h = int(round((m - nominal) / 1.008))
        if h > 0:
            counts[pos] = h
    if counts:
        return counts
    heavy = [e for e in els if e in _NOMINAL_MASSES and e != "H"]
    return {} if heavy else None


def _inject_inferred_hydrogens(molecule_build, parent_rdkit_idx, count):
    """B-10 counts-mode: united-atom masses name their exact implicit H
    count; materialise those H as explicit atoms so bond-order
    determination sees the true valence budget (UA ethanol -> CCO)."""
    from rdkit import Chem as _Chem
    for _ in range(count):
        h = _Chem.Atom("H")
        h_idx = molecule_build.AddAtom(h)
        molecule_build.AddBond(parent_rdkit_idx, h_idx, _Chem.BondType.SINGLE)
