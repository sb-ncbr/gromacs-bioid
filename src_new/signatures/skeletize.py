"""Heavy-atom skeleton fingerprints ("skelfp").

Bond-order-, aromaticity-, charge- and protonation-insensitive molecular
fingerprint shared by the signature generator (F12), the verification gate
(F7), the fastformula resolver (F9) and the S7 validator.

Design + probe evidence: docs/CHEMISTRY_FIX_TODO.md
(probe: neutral vs -2H dianion Tanimoto 0.889; true vs formula-mate 0.19).
"""
from __future__ import annotations

import binascii
import logging
from collections import Counter
from typing import Optional, Tuple

from rdkit import Chem
from rdkit.Chem import AllChem, DataStructs

logger = logging.getLogger("base")

SKELFP_VERSION = "v1"
SKELFP_BITS = 2048
SKELFP_RADIUS = 2
SKELFP_PREFIX = f"skelfp:{SKELFP_VERSION}:"


def skeletize_mol(mol: "Chem.Mol") -> Optional["Chem.Mol"]:
    """Collapse a molecule to its heavy-atom, single-bond, uncharged skeleton."""
    if mol is None:
        return None
    try:
        m = Chem.Mol(mol)
        m = Chem.RemoveHs(m, sanitize=False)
        for bond in m.GetBonds():
            bond.SetBondType(Chem.BondType.SINGLE)
            bond.SetIsAromatic(False)
        for atom in m.GetAtoms():
            atom.SetIsAromatic(False)
            atom.SetFormalCharge(0)
            # scrub all H-state differences: protonation variants of the same
            # heavy skeleton must fingerprint identically (deprotonated MD
            # species vs neutral literature, e.g. azilsartan -2H)
            atom.SetNoImplicit(True)
            atom.SetNumExplicitHs(0)
        # unsanitized edits leave stale computed props; refresh cheaply so
        # downstream invariants (Morgan FP) see a consistent graph
        m.UpdatePropertyCache(strict=False)
        Chem.FastFindRings(m)
        return m
    except Exception as exc:  # never poison the pipeline on structure quirks
        logger.warning("skeletize: collapse failed: %s", exc)
        return None


def skeleton_fp(mol: "Chem.Mol") -> Optional["DataStructs.ExplicitBitVect"]:
    m = skeletize_mol(mol)
    if m is None:
        return None
    return AllChem.GetMorganFingerprintAsBitVect(m, SKELFP_RADIUS, nBits=SKELFP_BITS)


def heavy_formula(mol: "Chem.Mol") -> str:
    """Hill formula of heavy atoms only (H excluded), e.g. 'C25N4O5'."""
    if mol is None:
        return ""
    counts: Counter = Counter()
    for atom in mol.GetAtoms():
        sym = atom.GetSymbol()
        if sym != "H":
            counts[sym] += 1
    def _part(sym: str, n: int) -> str:
        return sym if n == 1 else f"{sym}{n}"
    parts = []
    if counts.get("C"):
        parts.append(_part("C", counts.pop("C")))
    for sym in sorted(counts):
        parts.append(_part(sym, counts[sym]))
    return "".join(parts)


def fp_to_hex(fp: "DataStructs.ExplicitBitVect") -> str:
    return binascii.hexlify(DataStructs.BitVectToBinaryText(fp)).decode("ascii")


def hex_to_fp(hex_str: str) -> Optional["DataStructs.ExplicitBitVect"]:
    if not hex_str:
        return None
    try:
        return DataStructs.CreateFromBinaryText(binascii.unhexlify(hex_str))
    except Exception as exc:
        logger.warning("skeletize: hexfp decode failed: %s", exc)
        return None


def tanimoto(fp_a, fp_b) -> float:
    if fp_a is None or fp_b is None:
        return 0.0
    return float(DataStructs.TanimotoSimilarity(fp_a, fp_b))


def _maybe_sig_hex(value: str) -> str:
    """Accept either a raw fp hex string or a full 'skelfp:v1:<hex>|<heavy>'."""
    if value and value.startswith(SKELFP_PREFIX):
        hex_part, _ = parse_signature(value)
        return hex_part or ""
    return value


def tanimoto_hex(hex_a: str, hex_b: str) -> float:
    return tanimoto(hex_to_fp(_maybe_sig_hex(hex_a or "")),
                    hex_to_fp(_maybe_sig_hex(hex_b or "")))


def from_smiles(smiles: str) -> Optional["Chem.Mol"]:
    if not smiles:
        return None
    try:
        return Chem.MolFromSmiles(smiles)
    except Exception:
        return None


def format_signature(mol: "Chem.Mol") -> Optional[str]:
    """Canonical signature value: 'skelfp:v1:<hex>|<heavyFormula>'."""
    fp = skeleton_fp(mol)
    if fp is None:
        return None
    return f"{SKELFP_PREFIX}{fp_to_hex(fp)}|{heavy_formula(skeletize_mol(mol))}"


def parse_signature(value: str) -> Tuple[Optional[str], str]:
    """Parse 'skelfp:v1:<hex>|<heavy>' -> (hex, heavy). Unversioned -> (None, '')."""
    if not value or not value.startswith(SKELFP_PREFIX):
        return None, ""
    rest = value[len(SKELFP_PREFIX):]
    hex_part, _, heavy = rest.partition("|")
    return hex_part or None, heavy
