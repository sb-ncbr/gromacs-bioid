"""Structure verification worker for PDB structures using TM-score or sequence proxy."""

from __future__ import annotations

import difflib
import logging
import tempfile
import os

import numpy as np
import gemmi

from ..base import VerificationWorker
from ..models import VerificationScore, ref_seq_sha1
from ..alignment import local_identity_coverage

logger = logging.getLogger(__name__)


# Try to import tmtools, fall back to sequence-based comparison if not available.
# NOTE (v3.138): `from tmtools import tmscore` used to bind the tmtools
# *submodule* (not a callable), so this worker silently fell back to the
# sequence proxy in every environment where tmtools was installed. The real
# entry point is tm_align(x, y, seqx, seqy) — coordinates first, then
# one-letter sequences; requires BOTH, aligned index-for-index.
try:
    from tmtools import tm_align
    _TMTOOLS_AVAILABLE = True
except ImportError:
    _TMTOOLS_AVAILABLE = False
    tm_align = None


# Red-team batch-4 (D-13): cap on (query chain, canonical chain) TM
# computations per verification. Within the cap, pairs are tried in
# sequence-similarity order; beyond it the best-matching pairs win.
_MAX_TM_PAIRS = 16

# TM-score is meaningless on near-atomic chains (tmtools returns ~1.0 for
# any 2-of-3-residue overlap); such pairs fall through to the sequence
# proxy, which handles them with real alignment semantics.
_MIN_TM_CHAIN_LEN = 5


class StructureVerificationWorker(VerificationWorker):
    """Verifies structural identifications using TM-score or sequence alignment proxy."""

    SUPPORTED_IDENT_TYPES = {"PDB_ID", "ALPHAFIND_ID", "ALPHAFOLD_ID"}
    SUPPORTED_SIGNATURE_TYPES = {"pdb_protein", "pdb_nucleic", "ca_only_pdb", "mmcif"}

    # Legacy constant retained for reference; the enforced floors live in
    # models.SIMILARITY_FLOORS (red-team batch-4, known issue #2).
    TM_SCORE_THRESHOLD = 0.5

    def is_applicable(self, signature_type: str, ident_type: str) -> bool:
        """Check if this worker can verify the given signature and identifier types."""
        return (
            signature_type.lower() in self.SUPPORTED_SIGNATURE_TYPES and
            ident_type in self.SUPPORTED_IDENT_TYPES
        )

    def verify(
        self,
        signature: str,
        identifier: str,
        ident_type: str,
        canonical_signature: str | None = None,
        signature_type: str | None = None,
    ) -> VerificationScore | None:
        """Verify a structural hit by comparing PDB/mmCIF structures.

        Args:
            signature: The structure string extracted from simulation.
            identifier: The identifier (not used directly, canonical_signature is used).
            ident_type: The type of identifier.
            canonical_signature: The canonical structure from database. Required.

        Returns:
            VerificationScore if verification was performed, None on any
            failure (never a fabricated 0.0 score — red-team D-13).
        """
        # Cannot verify without canonical structure
        if canonical_signature is None:
            return None

        try:
            # Try primary method: TM-score via tmtools
            if _TMTOOLS_AVAILABLE:
                score = self._verify_with_tmscore(signature, canonical_signature)
                if score is not None:
                    return score

            # Fallback: sequence-based comparison
            return self._verify_with_sequence_proxy(signature, canonical_signature)

        except Exception as e:
            logger.warning(f"Structure verification failed: {e}")
            return None

    def _extract_ca_chains(
        self, struct_string: str
    ) -> list[tuple[str, str, np.ndarray]] | None:
        """Extract PER-CHAIN MODEL-1 CA traces via gemmi (PDB and mmCIF).

        Red-team batch-4 (D-13 defect 1): the previous Bio.PDB iteration
        walked ALL models and ALL chains into one concatenated trace, so
        NMR ensembles and multimers became chimera alignments. gemmi also
        auto-detects mmCIF, covering large entries that have no legacy .pdb
        (defect 3).

        Sequence and coordinates are collected in the same residue pass, so
        they stay aligned index-for-index — tm_align requires exactly that.

        Returns:
            [(chain_id, one-letter-seq, (N, 3) float64 coords)], or None.
        """
        if not struct_string or not struct_string.strip():
            return None
        suffix = ".cif" if struct_string.lstrip().startswith("data_") else ".pdb"
        fd, temp_path = tempfile.mkstemp(suffix=suffix)
        try:
            os.write(fd, struct_string.encode("utf-8", errors="replace"))
            os.close(fd)
            try:
                structure = gemmi.read_structure(temp_path)
            except Exception as e:
                logger.debug(f"gemmi structure parse failed: {e}")
                return None
            if structure is None or len(structure) == 0:
                return None
            model = structure[0]  # MODEL 1 ONLY — no ensemble chimeras
            traces: list[tuple[str, str, np.ndarray]] = []
            for chain in model:
                seq_chars: list[str] = []
                ca_coords: list[list[float]] = []
                for residue in chain:
                    ca = None
                    for atom in residue:
                        if atom.name == "CA":
                            ca = atom
                            break
                    if ca is None:
                        continue
                    try:
                        code = gemmi.find_tabulated_residue(
                            residue.name).fasta_code()
                        code = code.upper() if code and code.strip() else "X"
                    except Exception:
                        code = "X"
                    seq_chars.append(code)
                    ca_coords.append([ca.pos.x, ca.pos.y, ca.pos.z])
                if ca_coords:
                    traces.append(
                        (chain.name, "".join(seq_chars),
                         np.array(ca_coords, dtype=np.float64)))
            return traces or None
        finally:
            os.unlink(temp_path)

    @staticmethod
    def _seq_match_ratio(a: str, b: str) -> float:
        """Cheap sequence-similarity heuristic for CHAIN CHOICE ONLY (never
        reported as a verification measurement)."""
        return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()

    def _verify_with_tmscore(
        self,
        signature: str,
        canonical_signature: str
    ) -> VerificationScore | None:
        """Verify using TM-score via tmtools.

        Red-team batch-4 (D-13): chain pair chosen by sequence match (no
        chimera); score normalized by the QUERY length (defect 2 — a domain
        in a complex is a perfect partial match, not a diluted one); the
        reference-normalized value is retained in details.

        Returns:
            VerificationScore with tm_score metric, or None on failure.
        """
        query_traces = self._extract_ca_chains(signature)
        canonical_traces = self._extract_ca_chains(canonical_signature)
        if not query_traces or not canonical_traces:
            logger.warning("Could not extract CA chains for TM-score")
            return None

        # Match each query chain to its best canonical chain by sequence.
        pairs = []
        for q_id, q_seq, q_coords in query_traces:
            best, best_ratio = None, -1.0
            for c_id, c_seq, c_coords in canonical_traces:
                ratio = self._seq_match_ratio(q_seq, c_seq)
                if ratio > best_ratio:
                    best, best_ratio = (c_id, c_seq, c_coords), ratio
            if best is not None:
                pairs.append((best_ratio, q_id, q_seq, q_coords,
                              best[0], best[1], best[2]))
        pairs.sort(key=lambda p: -p[0])
        pairs = pairs[:_MAX_TM_PAIRS]

        best_tm = None  # (tm_norm_query, tm_norm_ref, q_id, c_id, len_q, len_c)
        for _ratio, q_id, q_seq, q_coords, c_id, c_seq, c_coords in pairs:
            if min(len(q_seq), len(c_seq)) < _MIN_TM_CHAIN_LEN:
                continue
            if np.any(np.isnan(q_coords)) or np.any(np.isnan(c_coords)):
                logger.warning(f"NaN detected in CA coordinates ({q_id}/{c_id})")
                continue
            try:
                result = tm_align(q_coords, c_coords, q_seq, c_seq)
            except Exception as e:
                logger.debug(f"tm_align failed for chain pair {q_id}/{c_id}: {e}")
                continue
            tm_q = float(result.tm_norm_chain1)   # normalized by QUERY length
            tm_c = float(result.tm_norm_chain2)   # normalized by reference length
            if np.isnan(tm_q):
                continue
            if best_tm is None or tm_q > best_tm[0]:
                best_tm = (tm_q, tm_c, q_id, c_id, len(q_seq), len(c_seq))

        if best_tm is None:
            return None
        tm_q, tm_c, q_id, c_id, len_q, len_c = best_tm
        return VerificationScore(
            kind="similarity",
            metric_name="tm_score",
            raw_score=tm_q,
            normalized_score=min(tm_q * 100.0, 100.0),
            details={
                "tm_score_ref_normalized": min(tm_c * 100.0, 100.0),
                "tm_chain_query": q_id,
                "tm_chain_ref": c_id,
                "tm_query_length": len_q,
                "tm_ref_length": len_c,
                "tm_normalization": "query",
                # D-06: reference-content key for equivalence classes
                "ref_seq_sha1": ref_seq_sha1(c_seq),
            },
        )

    def _verify_with_sequence_proxy(
        self,
        signature: str,
        canonical_signature: str
    ) -> VerificationScore | None:
        """Verify using sequence alignment as a proxy for structural similarity.

        Fallback when tmtools is unavailable/unsuccessful. Red-team batch-4
        (D-13 defects 4+5): any failure returns None — a fabricated 0.0 used
        to count as "a score" and verify the hit; and the alignment container
        is consumed with next(iter(...)) instead of len()/[0], which
        materialized the full combinatorial enumeration.

        Returns:
            VerificationScore with structure_sequence_proxy metric, or None.
        """
        try:
            query_traces = self._extract_ca_chains(signature)
            canonical_traces = self._extract_ca_chains(canonical_signature)
            if not query_traces or not canonical_traces:
                logger.warning("Could not extract sequences for proxy comparison")
                return None

            seq1 = "".join(s for _, s, _ in query_traces)
            seq2 = "".join(s for _, s, _ in canonical_traces)
            if not seq1 or not seq2:
                return None

            # Red-team batch-4 (D-01/5.2): local BLOSUM62 alignment via the
            # shared helper — identical semantics to the sequence worker
            # (the old global mode diluted any length difference).
            out = local_identity_coverage(seq1, seq2)
            if out is None:
                logger.warning("No usable local alignment for structure sequences")
                return None
            identity, coverage = out

            raw_score = identity * coverage
            return VerificationScore(
                kind="similarity",
                metric_name="structure_sequence_proxy",
                raw_score=raw_score,
                normalized_score=min(raw_score * 100.0, 100.0),
                details={
                    "alignment_identity": round(identity * 100.0, 2),
                    "query_coverage": round(coverage * 100.0, 2),
                    "ref_seq_sha1": ref_seq_sha1(seq2),
                },
            )

        except Exception as e:
            logger.warning(f"Sequence proxy verification failed: {e}")
            return None
