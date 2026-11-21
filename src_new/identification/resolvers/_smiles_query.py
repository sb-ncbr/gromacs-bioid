"""The SMILES a remote structure search is sent (IDSM, ChEMBL, PubChem).

2026-11-21 (mdval audit item 6): bonds guessed from distances on a large
system without a box gave SMILES such as ``C123456789%10%11%12%13%14[CH]%15``
(one carbon with 17 bonds). Sent as they were, IDSM answered QueryBadFormed
("CDKException: too high atom valence"), PubChem 400 PUGREST.BadRequest and
ChEMBL 500, which counted as an outage: the run was marked incomplete and
retried automatically for nothing. Such a SMILES is not a molecule; the
searches now decline it with the not-applicable reason ``invalid_valence``.

The check is deliberately permissive: only valences no compound has are
refused. Bonds to metals are coordination bonds and are not counted for the
ligand atom (heme N-Fe, Fe-CO, ferrocene's Fe-C), a metal may have up to 16
neighbours (uranocene), and atoms bonded to boron may have six (carborane
clusters). Charges are ignored and an aromatic bond counts 1, so pyridone
``O=c1cccc[nH]1`` or a ring-fusion carbon pass. A SMILES RDKit cannot parse
at all is left to the service.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("identifier")

INVALID_VALENCE = "invalid_valence"

# Non-metals and metalloids: their bonds to other such atoms are counted.
_NONMETALS = frozenset({1, 2, 5, 6, 7, 8, 9, 10, 14, 15, 16, 17, 18, 32, 33, 34,
                        35, 36, 51, 52, 53, 54, 85, 86})
# atomic number -> (most bond orders + hydrogens, most neighbours) any
# compound has: NH4+ 4 neighbours, nitro N(=O)=O valence 5, H3O+ / CO's O 3,
# SF6, PF6-, SiF6 2-, perchlorate and IF7 7, XeO4 8.
_LIMITS = {
    1: (1, 1), 5: (6, 6), 6: (4, 4), 7: (5, 4), 8: (3, 3), 9: (1, 1),
    14: (6, 6), 15: (6, 6), 16: (6, 6), 17: (7, 7),
    32: (6, 6), 33: (6, 6), 34: (6, 6), 35: (7, 7),
    51: (6, 6), 52: (6, 6), 53: (7, 7), 36: (2, 2), 54: (8, 8),
}
_BORON_CLUSTER = 6
_MAX_METAL_NEIGHBOURS = 16
_SELFIES_RE = re.compile(r"(?:\[[^\[\]]+\])+")


def query_smiles(signature: str, signature_type: str | None) -> str:
    """The SMILES of a smiles or selfies signature.

    2026-11-21 (mdval audit item 6): decided by the signature type. The
    resolvers decoded every signature containing '[' as SELFIES, so SMILES
    such as ``CC[C@H](N)O`` went through the SELFIES decoder first. Without
    a type (direct calls), only a string made of bracketed tokens alone is
    taken for SELFIES.
    """
    if signature_type is None:
        is_selfies = bool(_SELFIES_RE.fullmatch(signature or ""))
    else:
        is_selfies = signature_type == "selfies"
    if not is_selfies:
        return signature
    try:
        import selfies
        return selfies.decoder(signature)
    except ImportError:
        logger.warning("selfies package not installed; treating as SMILES")
    except Exception as exc:
        logger.warning(f"SELFIES decode failed: {exc}; treating as SMILES")
    return signature


def _order(bond) -> int:
    from rdkit import Chem

    kind = bond.GetBondType()
    if kind in (Chem.BondType.DATIVE, Chem.BondType.ZERO):
        return 0
    if bond.GetIsAromatic() or kind == Chem.BondType.AROMATIC:
        return 1
    return max(0, int(round(bond.GetBondTypeAsDouble())))


def valence_problem(smiles: str) -> str | None:
    """'C with 17 bonds' when an atom of the SMILES has a valence no compound
    has (module docstring); None when it is plausible or cannot be parsed."""
    try:
        from rdkit import Chem, RDLogger

        RDLogger.DisableLog("rdApp.*")
        mol = Chem.MolFromSmiles(smiles, sanitize=False)
    except Exception:
        return None
    if mol is None:
        return None
    for atom in mol.GetAtoms():
        z = atom.GetAtomicNum()
        if z == 0:
            continue
        if z not in _NONMETALS:
            n = atom.GetDegree()
            if n > _MAX_METAL_NEIGHBOURS:
                return f"{atom.GetSymbol()} with {n} neighbours"
            continue
        limit = _LIMITS.get(z)
        if limit is None:
            continue
        hs = atom.GetNumExplicitHs()
        valence, neighbours, boron = hs, hs, False
        for bond in atom.GetBonds():
            other = bond.GetOtherAtom(atom).GetAtomicNum()
            if other not in _NONMETALS:
                continue  # coordination bond to a metal (or a '*' atom)
            order = _order(bond)
            if order:
                valence += order
                neighbours += 1
            boron = boron or other == 5
        max_valence, max_neighbours = limit
        if boron:
            max_valence = max(max_valence, _BORON_CLUSTER)
            max_neighbours = max(max_neighbours, _BORON_CLUSTER)
        if neighbours > max_neighbours or valence > max_valence:
            return f"{atom.GetSymbol()} with {valence} bonds"
    return None


def refusal(smiles: str) -> str | None:
    """The not-applicable reason for a SMILES no search should be sent, or None."""
    problem = valence_problem(smiles)
    if problem is None:
        return None
    return f"{INVALID_VALENCE}: {problem}"
