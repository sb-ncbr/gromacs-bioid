"""Tier-2 structural fingerprints ("t2fp") — homologue/stereoisomer separation.

Red-team batch-4 (D-05/B-06). Tier-1 skelfp is deliberately coarse
(bond-order/charge/protonation-insensitive): it is the F7 GATE — "same
heavy-atom family?". But it collapses DPPC/DMPC (both 1.0), glucose/
galactose (1.0), even benzene/cyclohexane (1.0), so every ranking/grouping
downstream of it called distinct molecules "the same".

Tier-2 = hashed count-Morgan, radius 3, 4096 bits, chirality on, computed
on the ORIGINAL molecule (bond orders / aromaticity / charge / stereo all
count). Empirical separation table (probe 2026-10-23 over the audit pair
corpus; structures recorded in tests/src_new/verification/fixtures/d05/;
RDKit TanimotoSimilarity on count vectors):

    same-entity (re-parse)                    1.0000
    DPPC / DMPC                               0.9106  (tier-1: 1.0000)
    palmitic / stearic                        0.8889
    palmitic / oleic, stearic / oleic         0.6190 / 0.5652
    cholesterol / cholestanol                 0.5714
    D-glucose / D-galactose                   0.8049
    L-ala / D-ala                             0.7333
    ATP / ADP        ATP / ITP                0.8476 / 0.7025
    water / hydroxide, ammonia / ammonium     0.0000
    benzene / cyclohexane                     0.0000  (tier-1: 1.0000!)

Gate semantics stay tier-1 (protonation-safe — the deprotonated-MD-species
vs neutral-literature case still passes); tier-2 only refines ranking,
class identity, and fidelity ordering WITHIN tier-1-equal candidates.
"""
from __future__ import annotations

import hashlib
import logging

from rdkit import Chem
from rdkit.Chem import AllChem, DataStructs

logger = logging.getLogger("base")

T2FP_VERSION = "v1"
T2FP_RADIUS = 3
T2FP_BITS = 4096
T2FP_CHIRAL = True
T2FP_PREFIX = f"t2fp:{T2FP_VERSION}:"


def tier2_fp(mol: "Chem.Mol") -> "DataStructs.UIntSparseIntVect | None":
    """Hashed count-Morgan (r3, 4096, chiral) of the molecule AS GIVEN."""
    if mol is None:
        return None
    try:
        return AllChem.GetHashedMorganFingerprint(
            mol, T2FP_RADIUS, nBits=T2FP_BITS, useChirality=T2FP_CHIRAL)
    except Exception as exc:  # never poison the pipeline on structure quirks
        logger.warning("t2fp: fingerprint failed: %s", exc)
        return None


def tier2_tanimoto(fp_a, fp_b) -> float | None:
    """Tanimoto between two count vectors; None if either is missing."""
    if fp_a is None or fp_b is None:
        return None
    return float(DataStructs.TanimotoSimilarity(fp_a, fp_b))


def tier2_key(mol: "Chem.Mol") -> str | None:
    """Stable 8-char content discriminator for the tier-2 fingerprint.

    Used as the D-05 class-id suffix: two molecules with the same tier-1
    skeleton but DIFFERENT bond/stereo content get different class ids.
    Derived from the fp's nonzero elements only (deterministic, no nib
    layout leakage).
    """
    fp = tier2_fp(mol)
    if fp is None:
        return None
    items = sorted(fp.GetNonzeroElements().items())
    blob = ",".join(f"{k}:{v}" for k, v in items).encode("ascii")
    return hashlib.sha1(blob).hexdigest()[:8]
