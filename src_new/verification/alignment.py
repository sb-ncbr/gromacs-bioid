"""Shared local-alignment measurement for verification workers.

Red-team batch-4 (D-01): the old metric was "identity over a GLOBAL
alignment" with gaps cheaper than mismatches (open -0.5 / extend -0.1),
which (a) diluted any length difference — the correct full-length entry of
a simulated domain scored below a random sequence — and (b) made coverage
always 1.0 by construction.

This module is the single choke point: local Smith-Waterman alignment
(BLOSUM62, open -11 / extend -1; simple match/mismatch for nucleotide
alphabets), reporting
    identity = matches / aligned (both-residue) columns
    query_coverage = query residues inside the alignment / len(query)
Consumers typically score S = identity * query_coverage; both numbers are
also persisted additively in VerificationScore.details.
"""

from __future__ import annotations

import logging

from Bio.Align import PairwiseAligner, substitution_matrices

logger = logging.getLogger(__name__)

# DP-matrix cell cap for alignment (lenA * lenB). Above this the pairwise
# enumeration/matrix gets pathological (titin-vs-titin class pairs burned
# hours per call in production; see wave-3 postmortem). 25M cells covers all
# sane protein/PDB entity pairs (5k x 5k).
MAX_ALIGN_MATRIX_CELLS = 25_000_000

_NUC_ALPHABET = frozenset("ACGTUNX")


def _make_aligner(nucleotide: bool) -> PairwiseAligner:
    aligner = PairwiseAligner()
    aligner.mode = "local"
    if nucleotide:
        aligner.match_score = 2.0
        aligner.mismatch_score = -1.5
    else:
        aligner.substitution_matrix = substitution_matrices.load("BLOSUM62")
    aligner.open_gap_score = -11.0
    aligner.extend_gap_score = -1.0
    return aligner


# Configured-once aligners; PairwiseAligner objects are immutable after
# configuration and safe to share across calls.
_ALIGNER_AA = _make_aligner(nucleotide=False)
_ALIGNER_NT = _make_aligner(nucleotide=True)


def _is_nucleotide(seq: str) -> bool:
    """Heuristic alphabet gate: treat as nucleotide only when the sequence
    uses nothing outside the nuc alphabet (ACGTUNX)."""
    return bool(seq) and set(seq.upper()) <= _NUC_ALPHABET


def local_identity_coverage(query: str, reference: str) -> tuple[float, float] | None:
    """Local-align `query` against `reference`.

    Returns:
        (identity, query_coverage) with
          identity = matches / aligned (both-residue) columns,
          query_coverage = aligned query residues / len(query),
        or None on any failure (empty input, oversized DP matrix, no
        alignment, zero aligned columns).
    """
    if not query or not reference:
        return None
    if len(query) * len(reference) > MAX_ALIGN_MATRIX_CELLS:
        logger.warning(
            f"Sequence alignment skipped: matrix too large "
            f"({len(query)} x {len(reference)})"
        )
        return None
    try:
        aligner = _ALIGNER_NT if _is_nucleotide(query) and _is_nucleotide(reference) else _ALIGNER_AA
        # first optimal alignment only — never len()/materialize (see the
        # combinatorial-explosion note in the sequence worker history)
        aln = next(iter(aligner.align(query, reference)), None)
        if aln is None:
            return None
        aln_q = str(aln[0])
        aln_r = str(aln[1])
        aligned_cols = 0
        matches = 0
        for x, y in zip(aln_q, aln_r):
            if x != "-" and y != "-":
                aligned_cols += 1
                if x == y:
                    matches += 1
        if aligned_cols == 0:
            return None
        identity = matches / aligned_cols
        q_residues = sum(1 for c in aln_q if c != "-")
        coverage = q_residues / len(query)
        return identity, coverage
    except Exception as e:
        logger.warning(f"Local alignment failed: {e}")
        return None
