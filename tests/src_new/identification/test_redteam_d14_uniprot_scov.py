"""D-14 gate: UniProt/Swiss-Prot identity rule (subject-coverage dropped,
aligned-length floor replaces it).

Reviewer decision (2026-10-27, pre-full-corpus): UniProt/Swiss-Prot
accession spaces carry the full-length protein by definition, so
construct-vs-reference terminal overhang is biology, not a PDB fusion
artefact. Roughly half of the covered ground-truth references overhang the
deposited MD construct by >60 residues, and the C-03/D-13
subject-coverage machinery demoted those correct matches (two of the 12
earlier d13 regressions — 5619, 6003 — were exactly this). Rule for
`blast_uniprot` and `blast_swissprot_protein` only:

    identity = identity >= 0.99 AND query coverage >= 0.99
               AND aligned length >= 50 aa

PDB-family resolvers (and NR) keep the D-13 terminal-overhang rule.
"""

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.blast import (
    BLASTResolverPDBAA,
    BLASTResolverSWISSPROT,
    BLASTResolverUNIPROT,
    BlastHit,
)


def _uniprot() -> BLASTResolverUNIPROT:
    return BLASTResolverUNIPROT(RunConfig())


def _swissprot() -> BLASTResolverSWISSPROT:
    return BLASTResolverSWISSPROT(RunConfig())


def _pdb() -> BLASTResolverPDBAA:
    return BLASTResolverPDBAA(RunConfig())


def _hit(*, identity: float = 1.0, qcov: float = 1.0, scov: float | None = 0.30,
         span: tuple[int, int] | None = (61, 240), subject_len: int | None = 240,
         gap: int | None = 0) -> BlastHit:
    return BlastHit(
        accessions=["P12345"],
        evalue=0.0,
        bits=300.0,
        identity_p=identity,
        coverage_p=qcov,
        subject_len=subject_len,
        subject_cov_p=scov,
        subject_span=span,
        subject_max_internal_gap=gap,
    )


class TestD14UniprotSubjectCoverageDropped:
    """Core D-14: the UniProt/Swiss-Prot scov gate is gone."""

    def test_uniprot_full_length_reference_overhang_accepted(self):
        # 180-aa exact alignment inside a 240-aa full-length reference:
        # 60-aa N-terminal overhang — the old scov path (overhang > 25)
        # would fail this with "scov".
        assert _uniprot()._identity_gate_fail(_hit()) is None

    def test_swissprot_full_length_reference_overhang_accepted(self):
        h = _hit(identity=0.995, qcov=0.995, scov=0.20, span=(51, 200))
        assert _swissprot()._identity_gate_fail(h) is None

    def test_pdb_still_fails_far_overhang(self):
        # PDB fusion geometry is unchanged territory: the D-13
        # terminal-overhang rule stays — same hit must fail 'scov'.
        assert _pdb()._identity_gate_fail(_hit()) == "scov"

    def test_pdb_still_passes_terminal_overhang(self):
        # D-13 override itself untouched: overhangs <= 25, internal gap <= 5.
        h = _hit(scov=0.85, span=(26, 240), gap=3)
        assert _pdb()._identity_gate_fail(h) is None


class TestD14AlignedLengthFloor:
    """The floor: short peptides must not identity-list against
    UniProt/Swiss-Prot even with the scov gate dropped."""

    def test_uniprot_short_alignment_rejected_as_alen(self):
        # 45-aa span, perfect identity/coverage — below the 50-aa floor.
        h = _hit(scov=0.99, span=(1, 45), subject_len=45)
        assert _uniprot()._identity_gate_fail(h) == "alen"

    def test_swissprot_short_alignment_rejected_as_alen(self):
        h = _hit(scov=0.60, span=(100, 123), subject_len=200)
        assert _swissprot()._identity_gate_fail(h) == "alen"

    def test_uniprot_floor_uses_query_len_when_span_unknown(self):
        # span unknown: aligned = round(coverage_p * query_len).
        h = _hit(scov=0.99, span=None, subject_len=None)
        assert _uniprot()._identity_gate_fail(h, query_len=60) is None
        assert _uniprot()._identity_gate_fail(h, query_len=40) == "alen"


class TestD14GateOrderUnchanged:
    """identity/qcov stay the first two gates for every source."""

    def test_uniprot_identity_fails_first(self):
        h = _hit(identity=0.985)
        assert _uniprot()._identity_gate_fail(h) == "identity"

    def test_uniprot_qcov_fails_second(self):
        h = _hit(qcov=0.985)
        assert _uniprot()._identity_gate_fail(h) == "qcov"

    def test_swissprot_identity_fails_first(self):
        h = _hit(identity=0.90)
        assert _swissprot()._identity_gate_fail(h) == "identity"
