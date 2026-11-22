"""2026-11-22: blast_pdb_nucleic_dc, dc-megablast against pdbnt with an
N-aware identity.

pdbnt (PDB SEQRES) stores modified nucleotides as N: 1EHZ_A (yeast
tRNA-Phe) is NCGGATTTANCTCAGNNGGG... with 15 N in 76 nt. megablast cannot
seed on it and BLAST counts N as a mismatch (81% identity for the
unmodified tRNA-Phe sequence), so it could never be an exact match.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.resolvers import blast as blast_mod
from src_new.identification.resolvers.blast import (
    NUCLEIC_MAX_N_MATCH_FRACTION, BLASTResolverPDBNT, BLASTResolverPDBNTDC, n_aware_counts,
)

# yeast tRNA-Phe, unmodified (DNA letters) and its pdbnt record 1EHZ_A
# (production pdbnt, blastdbcmd 2026-11-22)
TRNA_PHE = "GCGGATTTAGCTCAGTTGGGAGAGCGCCAGACTGAAGATCTGGAGGTCCTGTGTTCGATCCACAGAATTCGCACCA"
PDBNT_1EHZ_A = "NCGGATTTANCTCAGNNGGGAGAGCNCCAGANTNAANANNTGGAGNTCNTGTGNNCGNTCCACAGAATTCGCACCA"


def _json(query_len, hits):
    return [{"BlastOutput2": {"report": {"results": {"search": {
        "query_len": query_len, "hits": hits}}}}}]


def _hit(acc, subject_len, hsps):
    return {"description": [{"accession": acc}], "len": subject_len, "hsps": hsps}


def _hsp(qseq, hseq, q, s, strand="Plus"):
    """An HSP with BLAST's own identity (N counted as a mismatch)."""
    identity = sum(1 for a, b in zip(qseq, hseq) if a == b and a not in "-N")
    return {"identity": identity, "align_len": len(qseq), "gaps": qseq.count("-") + hseq.count("-"),
            "query_from": q[0], "query_to": q[1], "hit_from": s[0], "hit_to": s[1],
            "query_strand": "Plus", "hit_strand": strand,
            "evalue": 1e-20, "bit_score": 90.0, "qseq": qseq, "hseq": hseq}


def _with_n(seq, every=(8, 9, 10), start=4):
    s, i, k = list(seq), start, 0
    while i < len(s):
        s[i] = "N"
        i += every[k % len(every)]
        k += 1
    return "".join(s)


def _resolver(hits, query, subjects=None, cls=BLASTResolverPDBNTDC):
    r = cls(RunConfig())
    r._run_blast_local = lambda seq, wd: _json(len(query), hits)
    if cls is BLASTResolverPDBNTDC:
        r._subject_sequences = lambda accs: {a: subjects[a] for a in accs if a in (subjects or {})}
    return r


# --- invocation --------------------------------------------------------------

def _captured_cmd(resolver, query, monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        seen["input"] = kw.get("input")
        out = cmd[cmd.index("-out") + 1]
        with open(out, "w") as fh:
            fh.write('{"BlastOutput2": []}')
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(blast_mod.subprocess, "run", fake_run)
    resolver._run_blast_local(query, str(tmp_path))
    return seen


def test_dc_megablast_invocation(monkeypatch, tmp_path):
    seen = _captured_cmd(BLASTResolverPDBNTDC(RunConfig()), TRNA_PHE, monkeypatch, tmp_path)
    cmd = seen["cmd"]
    assert cmd[cmd.index("-task") + 1] == "dc-megablast"
    assert cmd[cmd.index("-template_type") + 1] == "coding_and_optimal"
    assert cmd[cmd.index("-template_length") + 1] == "16"
    assert cmd[cmd.index("-db") + 1] == RunConfig().blast.pdb_nt_db


def test_query_with_modified_residues_uses_blastn(monkeypatch, tmp_path):
    """dc-megablast drops query words that contain N: a query with modified
    residues (X from the generators, N for BLAST) is searched with blastn."""
    query = TRNA_PHE[:20] + "X" + TRNA_PHE[21:]
    seen = _captured_cmd(BLASTResolverPDBNTDC(RunConfig()), query, monkeypatch, tmp_path)
    assert seen["cmd"][seen["cmd"].index("-task") + 1] == "blastn"
    assert "-template_type" not in seen["cmd"]
    assert seen["input"][20] == "N" and len(seen["input"]) == len(query)


def test_existing_resolver_keeps_megablast_and_blastn_short(monkeypatch, tmp_path):
    seen = _captured_cmd(BLASTResolverPDBNT(RunConfig()), TRNA_PHE, monkeypatch, tmp_path)
    assert "-task" not in seen["cmd"]
    seen = _captured_cmd(BLASTResolverPDBNT(RunConfig()), TRNA_PHE[:20], monkeypatch, tmp_path)
    assert seen["cmd"][seen["cmd"].index("-task") + 1] == "blastn-short"


def test_not_applicable_below_the_short_search_threshold():
    r = BLASTResolverPDBNTDC(RunConfig())
    threshold = r.blast_config.local_instance_run_short_search_if_under_X_residues
    assert not r._is_applicable(TRNA_PHE[:threshold - 1])
    assert r._is_applicable(TRNA_PHE[:threshold])
    # blast_pdb_nucleic covers the short ones (blastn-short)
    assert BLASTResolverPDBNT(RunConfig())._is_applicable(TRNA_PHE[:threshold - 1])


def test_x_in_a_nucleotide_query_becomes_n():
    """blastn's FASTA reader drops X ("Ignoring invalid residues"): one gap
    per modified base. The sanitizer sends N; proteins keep X."""
    assert BLASTResolverPDBNT(RunConfig())._sanitize_sequence("ACGXU") == "ACGNU"
    from src_new.identification.resolvers.blast import BLASTResolverPDBAA
    assert BLASTResolverPDBAA(RunConfig())._sanitize_sequence("MKXV") == "MKXV"


def test_mostly_modified_query_is_not_applicable():
    assert not BLASTResolverPDBNTDC(RunConfig())._is_applicable("X" * 20 + "ACGU" * 4)


# --- N-aware identity ----------------------------------------------------------

def test_n_aware_counts():
    # match, N column (either side), mismatch, gap; U == T
    assert n_aware_counts([{"qseq": "ACGNTA-", "hseq": "ANGAUCA"}]) == (3, 2, 7)
    assert n_aware_counts([{"qseq": "ACG"}]) is None


def test_modified_trna_like_subject_is_identity():
    """N every 8-10 nt in the subject: BLAST identity 0.89, N-aware 1.0."""
    subject = _with_n(TRNA_PHE)
    n = len(TRNA_PHE)
    hits = [_hit("9TRN_A", n, [_hsp(TRNA_PHE, subject, (1, n), (1, n))])]
    r = _resolver(hits, TRNA_PHE)
    assert r._run_blast_identity(TRNA_PHE, "") == ["9TRN_A"]
    meta = r.get_last_resolution_metadata()["9TRN_A"]
    assert meta["identity_p"] == 1.0
    assert meta["blast_identity_p"] == pytest.approx(1 - subject.count("N") / n)
    assert meta["n_match_p"] == pytest.approx(subject.count("N") / n, abs=1e-4)
    # the existing resolver: BLAST's identity, never an exact match
    assert _resolver(hits, TRNA_PHE, cls=BLASTResolverPDBNT)._run_blast_identity(TRNA_PHE, "") == []


def test_measured_1ehz_with_terminal_n_is_identity():
    """Production dc-megablast: 1EHZ_A aligned 2-76 (a local alignment never
    starts on the N at position 1), 61/75. The ungapped N-aware extension
    covers position 1: query coverage 1.0, identity 1.0."""
    hits = [_hit("1EHZ_A", 76, [_hsp(TRNA_PHE[1:], PDBNT_1EHZ_A[1:], (2, 76), (2, 76))])]
    r = _resolver(hits, TRNA_PHE, subjects={"1EHZ_A": PDBNT_1EHZ_A})
    assert r._run_blast_identity(TRNA_PHE, "") == ["1EHZ_A"]
    meta = r.get_last_resolution_metadata()["1EHZ_A"]
    assert meta["coverage_p"] == 1.0 and meta["subject_cov_p"] == 1.0
    assert meta["blast_identity_p"] == pytest.approx(61 / 75)
    assert meta["n_match_p"] == pytest.approx(15 / 76, abs=1e-4)


def test_without_the_subject_sequence_the_terminal_n_stays_uncovered():
    hits = [_hit("1EHZ_A", 76, [_hsp(TRNA_PHE[1:], PDBNT_1EHZ_A[1:], (2, 76), (2, 76))])]
    r = _resolver(hits, TRNA_PHE, subjects={})
    assert r._run_blast_identity(TRNA_PHE, "") == []
    r._run_blast_similarity(TRNA_PHE, "")
    assert r.get_last_resolution_metadata()["1EHZ_A"]["identity_gate_fail"] == "qcov"


def test_extension_stops_at_a_real_mismatch():
    subject = "A" + TRNA_PHE[1:]  # G -> A at position 1: a real base differs
    hits = [_hit("9EXT_A", 76, [_hsp(TRNA_PHE[1:], subject[1:], (2, 76), (2, 76))])]
    r = _resolver(hits, TRNA_PHE, subjects={"9EXT_A": subject})
    assert r._run_blast_identity(TRNA_PHE, "") == []
    assert r._processed_hits(TRNA_PHE, "")[0].coverage_p == pytest.approx(75 / 76)


def test_too_many_ns_are_not_identity():
    """More than NUCLEIC_MAX_N_MATCH_FRACTION of the columns N: a run of Ns
    is no evidence; BLAST's identity is kept for similarity."""
    n = len(TRNA_PHE)
    subject = _with_n(TRNA_PHE, every=(3,), start=0)
    assert subject.count("N") / n > NUCLEIC_MAX_N_MATCH_FRACTION
    hits = [_hit("9NNN_A", n, [_hsp(TRNA_PHE, subject, (1, n), (1, n))])]
    r = _resolver(hits, TRNA_PHE)
    assert r._run_blast_identity(TRNA_PHE, "") == []
    sim = dict(r._run_blast_similarity(TRNA_PHE, ""))
    assert sim["9NNN_A"] == pytest.approx(100.0 * (1 - subject.count("N") / n))
    assert r.get_last_resolution_metadata()["9NNN_A"]["identity_gate_fail"] == "n_fraction"


def test_real_mismatch_with_ns_is_similarity():
    """N columns are credited, a real mismatch is not: 75/76 < 0.99."""
    subject = _with_n(TRNA_PHE)
    subject = subject[:60] + ("A" if subject[60] != "A" else "C") + subject[61:]
    assert subject[60] != "N"
    n = len(TRNA_PHE)
    hits = [_hit("9MIS_A", n, [_hsp(TRNA_PHE, subject, (1, n), (1, n))])]
    r = _resolver(hits, TRNA_PHE)
    assert r._run_blast_identity(TRNA_PHE, "") == []
    sim = dict(r._run_blast_similarity(TRNA_PHE, ""))
    assert sim["9MIS_A"] == pytest.approx(100.0 * 75 / 76)
    assert r.get_last_resolution_metadata()["9MIS_A"]["identity_gate_fail"] == "identity"


def test_gaps_count_against_n_aware_identity():
    subject = _with_n(TRNA_PHE)
    qseq = TRNA_PHE[:40] + "-" + TRNA_PHE[40:]
    hseq = subject[:40] + "A" + subject[40:]
    n = len(TRNA_PHE)
    hits = [_hit("9GAP_A", n + 1, [_hsp(qseq, hseq, (1, n), (1, n + 1))])]
    r = _resolver(hits, TRNA_PHE)
    assert r._run_blast_identity(TRNA_PHE, "") == []
    assert r._processed_hits(TRNA_PHE, "")[0].identity_p == pytest.approx(76 / 77)


def test_query_side_n_is_credited():
    """A simulated chain with its modified residues kept (X -> N) against
    the unmodified PDB entry."""
    query = _with_n(TRNA_PHE).replace("N", "X")
    n = len(query)
    hits = [_hit("9UNM_A", n, [_hsp(query.replace("X", "N"), TRNA_PHE, (1, n), (1, n))])]
    r = _resolver(hits, query)
    assert r._run_blast_identity(query, "") == ["9UNM_A"]


def test_opposite_strand_still_fails():
    subject = _with_n(TRNA_PHE)
    n = len(TRNA_PHE)
    hits = [_hit("9REV_B", n, [_hsp(TRNA_PHE, subject, (1, n), (n, 1), strand="Minus")])]
    r = _resolver(hits, TRNA_PHE)
    assert r._run_blast_identity(TRNA_PHE, "") == []
    r._run_blast_similarity(TRNA_PHE, "")
    assert r.get_last_resolution_metadata()["9REV_B"]["identity_gate_fail"] == "strand"


def test_hsps_are_not_kept_in_the_hits_cache():
    n = len(TRNA_PHE)
    hits = [_hit("9TRN_A", n, [_hsp(TRNA_PHE, _with_n(TRNA_PHE), (1, n), (1, n))])]
    r = _resolver(hits, TRNA_PHE)
    assert r._processed_hits(TRNA_PHE, "")[0].hsps is None
    r2 = _resolver(hits, TRNA_PHE, cls=BLASTResolverPDBNT)
    parsed = r2._processed_hits(TRNA_PHE, "")[0]
    assert parsed.hsps is None and parsed.n_match_p is None and parsed.raw_identity_p is None


# --- wiring --------------------------------------------------------------------

def test_registry_config_and_presets():
    from src_new.config.presets import TUNABLE, resolve_run_config
    from src_new.identification.registry import get_default_resolvers, get_deferred_resolvers

    assert RunConfig().identifiers.blast_pdb_nucleic_dc is False  # evaluation configs: off
    server = RunConfig.from_default_ini()
    assert server.identifiers.blast_pdb_nucleic_dc and server.identifiers.blast_pdb_nucleic_dc_similarity
    names = [r.name for r in get_default_resolvers(server)]
    assert names.index("blast_pdb_nucleic_dc") == names.index("blast_pdb_nucleic") + 1
    assert "blast_pdb_nucleic_dc" not in [r.name for r in get_deferred_resolvers(server)]
    assert {"blast_pdb_nucleic_dc", "blast_pdb_nucleic_dc_similarity"} <= TUNABLE["identifiers"]
    for preset in ("balanced", "quick", "deep"):
        ids = resolve_run_config(preset, None).identifiers
        assert ids.blast_pdb_nucleic_dc and ids.blast_pdb_nucleic_dc_similarity, preset
    exact = resolve_run_config("exact", None).identifiers
    assert exact.blast_pdb_nucleic_dc and not exact.blast_pdb_nucleic_dc_similarity


def test_cache_name_carries_the_database_release(monkeypatch):
    from src_new.identification.resolvers import blast_service_client
    monkeypatch.setattr(blast_service_client, "release_of", lambda p: "pdbnt-20260729-123757")
    r = BLASTResolverPDBNTDC(RunConfig())
    assert r.cache_name() == "blast_pdb_nucleic_dc@pdbnt-20260729-123757"
    assert r.cache_name() != BLASTResolverPDBNT(RunConfig()).cache_name()


def test_same_evidence_family_as_blast_pdb_nucleic():
    from src_new.verification.dedup import RawHit, _resolver_source, deduplicate_and_score
    assert _resolver_source("blast_pdb_nucleic_dc") == _resolver_source("blast_pdb_nucleic") == "rcsb-seq"
    out = deduplicate_and_score([
        RawHit("1EHZ_A", "PDB_ID", name, 100.0, TRNA_PHE, "residue_sequence_nucleotide", "identity")
        for name in ("blast_pdb_nucleic", "blast_pdb_nucleic_dc")])
    meta = next(iter(out.values()))
    assert meta["n_identity_sources"] == 1
    assert meta["belief"] == pytest.approx(50.0)


def test_exact_dc_match_skips_deferred_nt():
    from src_new.identification import supplementary

    class _Results:
        def get_data(self, path):
            return {"fasta_map_nucleic": {"blast_pdb_nucleic_dc": {
                "hit_type": "identity", "hits": ["1EHZ_A"],
                "hits_metadata": {"1EHZ_A": {"identity_p": 1.0, "coverage_p": 1.0}}}}}

    skipped = supplementary.skipped_deferred(_Results(), "seg", ["blast_nt", "blast_core_nt"],
                                             RunConfig.from_default_ini())
    assert skipped == {"blast_nt", "blast_core_nt"}


# --- local blastn on a tiny database ----------------------------------------------

@pytest.mark.skipif(not (shutil.which("blastn") and shutil.which("makeblastdb")
                         and shutil.which("blastdbcmd")), reason="BLAST+ not installed")
def test_local_blastn_finds_modified_trna(tmp_path):
    import random
    rnd = random.Random(7)
    decoy = "".join(rnd.choice("ACGT") for _ in range(400))
    fasta = tmp_path / "db.fa"
    fasta.write_text(f">1EHZ_A mol:na tRNA-Phe\n{PDBNT_1EHZ_A}\n>9DEC_A mol:na decoy\n{decoy}\n")
    db = tmp_path / "pdbnt"
    subprocess.run(["makeblastdb", "-in", str(fasta), "-dbtype", "nucl", "-parse_seqids",
                    "-out", str(db)], check=True, capture_output=True)
    config = RunConfig()
    config.blast.pdb_nt_db = str(db)
    config.blast.blastn_exec = shutil.which("blastn")
    query = TRNA_PHE.replace("T", "U")  # RNA letters, as the generators emit them
    dc = BLASTResolverPDBNTDC(config)
    assert dc._run_blast_identity(query, str(tmp_path)) == ["1EHZ_A"]
    meta = dc.get_last_resolution_metadata()["1EHZ_A"]
    assert meta["coverage_p"] == 1.0 and meta["identity_p"] == 1.0
    assert BLASTResolverPDBNT(config)._run_blast_identity(query, str(tmp_path)) == []
    # the simulated chain with its modified residues kept (X), blastn task
    simulated = "".join("X" if s == "N" else q for q, s in zip(query, PDBNT_1EHZ_A))
    assert BLASTResolverPDBNTDC(config)._run_blast_identity(simulated, str(tmp_path)) == ["1EHZ_A"]
