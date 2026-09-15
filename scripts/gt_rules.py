"""GT-class rules: split inchikey annotations into organic vs ion for scoring.

Rationale (2026-09-15 session): ~45% of inchikey 'no_molecule' cases were ion
annotations (Ca/Mg/Zn/Ni/K/Cl...), organic machinery structurally blind to
single-atom ions. Ion GTs get presence-scored (element instance present in
the simulation) instead of structure-similarity.

Ion detection: parse structure from the harvested cache; heavy-atom count <=2
is the robust ion signal. Heavy-atom -> element symbol (literal first).
"""

from __future__ import annotations

import functools
import os
import sys

_REPO = os.path.dirname(os.path.abspath(__file__))
for _p in ("/app", _REPO, os.path.dirname(_REPO)):
    if os.path.isdir(os.path.join(_p, "src_new")) and _p not in sys.path:
        sys.path.insert(0, _p)
if not any(p.endswith("scripts") or p == _REPO for p in sys.path):
    sys.path.insert(0, _REPO)

# Bare-ion InChIKey -> element fallback (structure unparsed cases; trimmed on sight)
_FALLBACK_ION_KEY = {
    "BHPQYMZQTOCNFJ": "Ca", "JLVVSXFLKOJNIY": "Mg", "PTFCDOFLOPIGGS": "Zn",
    "PXHVJJICTQNCMI": "Ni", "NPYPAHLBTDXSSS": "K", "VEXZGXHMUGYJMC": "Cl",
    "MDRDWERFGSJEHM": "Na", "FMLJBBPZFXZXKU": "Fe", "MAMIIQANAAEKHO": "Ca",
}

_METALS = {
    "Li", "Na", "K", "Rb", "Cs", "Be", "Mg", "Ca", "Sr", "Ba",
    "Zn", "Cd", "Hg", "Cu", "Ag", "Au", "Ni", "Pd", "Pt", "Fe", "Co",
    "Mn", "Cr", "V", "Ti", "Al", "Sn", "Pb", "Mo", "W",
}

_IONIC_ATOMS = _METALS | {"Cl", "F", "I", "S", "N", "O", "B", "C"}


def _rd_mol(smiles):
    try:
        from src_new.signatures.skeletize import from_smiles
        return from_smiles(smiles)
    except Exception:
        return None


def _smiles_for(ik: str) -> str:
    try:
        from validation_similarity import _inchikey_smiles
        return _inchikey_smiles(ik) or ""
    except Exception:
        return ""


@functools.lru_cache(maxsize=20000)
def gt_class_for(inchikey: str) -> str:
    """Classify an inchikey GT: 'organic' | 'ion' | 'unresolved'."""
    ik = (inchikey or "").strip().upper()
    if not ik:
        return "unresolved"
    smi = _smiles_for(ik)
    if not smi:
        key14 = ik.split("-")[0]
        return "ion" if key14 in _FALLBACK_ION_KEY else "unresolved"
    m = _rd_mol(smi)
    if m is None:
        key14 = ik.split("-")[0]
        return "ion" if key14 in _FALLBACK_ION_KEY else "unresolved"
    heavy = [a for a in m.GetAtoms() if a.GetSymbol() != "H"]
    if len(heavy) <= 2 and all(a.GetSymbol() in _IONIC_ATOMS for a in heavy):
        return "ion"
    return "organic"


@functools.lru_cache(maxsize=20000)
def ion_element(inchikey: str) -> str | None:
    """Element the ion GT refers to (e.g. 'Ca', 'Mg', 'Zn'), or None."""
    ik = (inchikey or "").strip().upper()
    if not ik:
        return None
    key14 = ik.split("-")[0]
    smi = _smiles_for(ik)
    if smi:
        m = _rd_mol(smi)
        if m is not None:
            heavy = [a.GetSymbol() for a in m.GetAtoms() if a.GetSymbol() != "H"]
            if 1 <= len(heavy) <= 2:
                # prefer metals as the ion identity
                for sym in heavy:
                    if sym in _METALS:
                        return sym
                # simple anions: last atom otherwise
                return heavy[-1]
    return _FALLBACK_ION_KEY.get(key14)
