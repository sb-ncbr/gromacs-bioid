"""Supplementary databases (2026-11-09): UniRef50, Foldseek PDB, SIFTS,
SwissLipids, local ChEBI.

Pins the additivity contract (identification/supplementary.py):
  - the evaluation config enables none of them, and the second pass is a
    no-op without them;
  - their listings merge with, never replace, the regular ones;
  - verification keeps the regular window and appends groups only they found;
  - evidence families: a database already searched is not counted twice.
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from src_new.config.loader import IdentifiersConfig, RunConfig
from src_new.identification import reference_indexes
from src_new.identification.resolvers.blast import (BLASTResolverUNIREF50, BlastHit,
                                                   uniref50_accession)
from src_new.identification.resolvers.foldseek import (FoldseekPDBResolver,
                                                      normalize_foldseek_pdb_target)
from src_new.identification.supplementary import (SUPPLEMENTARY_RESOLVERS, derive_sifts_hits,
                                                  get_supplementary_resolvers,
                                                  run_supplementary_pass)
from src_new.results.results_manager import ResultsManager
from src_new.verification.dedup import RawHit, deduplicate_and_score
from src_new.verification.manager import VerificationManager, _extend_window

REPO = Path(__file__).resolve().parents[3]
EVAL_CONFIG = REPO / "tests/fixtures/n1/config_shared.ini"
SEQ = "IVGGYTCGANTVPYQVSLNSGYHFCGGSLINSQWVVSAAHCYKSGIQVRLGEDNINVVEGNEQ"


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_reference_indexes", REPO / "scripts/build_reference_indexes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _gz(path: Path, text: str) -> str:
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(text)
    return str(path)


@pytest.fixture
def indexes(tmp_path):
    """Tiny SIFTS / SwissLipids / ChEBI indexes built with the real builder."""
    b = _builder()
    sifts = tmp_path / "sifts.sqlite"
    b.build_sifts(_gz(tmp_path / "s.tsv.gz",
                      "# header\nPDB\tCHAIN\tSP_PRIMARY\tRES_BEG\n"
                      "1aq7\tA\tP00760\t1\n3ptb\tA\tP00760\t1\n"
                      "9fus\tA\tP11111\t1\n9fus\tA\tP22222\t200\n"), str(sifts))
    cols = ["Lipid ID", "Level", "Name", "Abbreviation*", "Synonyms*", "Lipid class*", "Parent",
            "Components*", "SMILES (pH7.3)", "InChI (pH7.3)", "InChI key (pH7.3)", "CHEBI",
            "LIPID MAPS"]

    def row(i, level, abbr, smiles, ik):
        vals = dict.fromkeys(cols, "")
        vals.update({"Lipid ID": i, "Level": level, "Name": f"lipid {i}", "Abbreviation*": abbr,
                     "SMILES (pH7.3)": smiles, "InChI key (pH7.3)": ik})
        return "\t".join(vals[c] for c in cols)

    lipids = tmp_path / "swisslipids.sqlite"
    b.build_swisslipids(_gz(tmp_path / "l.tsv.gz", "\n".join([
        "\t".join(cols),
        row("SLM:000000651", "Isomeric subspecies", "PC(16:0/18:1(9Z))", "CCC",
            "InChIKey=WTJKGGKOPKCXLL-VYOBOKEXSA-N"),
        row("SLM:000088143", "Structural subspecies", "PC(16:0/18:1(9Z))", "", "InChIKey=none"),
        row("SLM:000000999", "Isomeric subspecies", "PC(x)", "CCCC",
            "InChIKey=WTJKGGKOPKCXLL-ZZZZZZZZSA-N"),
    ]) + "\n"), str(lipids))
    chebi = tmp_path / "chebi.sqlite"
    b.build_chebi(
        _gz(tmp_path / "c.tsv.gz", "id\tname\tstatus_id\tchebi_accession\tascii_name\tstars\n"
                                   "41033\tbenzamidine\t1\tCHEBI:41033\tbenzamidine\t3\n"),
        _gz(tmp_path / "st.tsv.gz", "id\tcompound_id\tsmiles\tstandard_inchi_key\tdefault_structure\n"
                                    "1\t41033\tN=C(N)c1ccccc1\tPXXJHWLDUBFPOL-UHFFFAOYSA-N\tt\n"),
        str(chebi))
    reference_indexes._connections.clear()
    yield SimpleNamespace(sifts=str(sifts), lipids=str(lipids), chebi=str(chebi))
    reference_indexes._connections.clear()


def _ui_config(ix) -> RunConfig:
    cfg = RunConfig()
    ids = cfg.identifiers
    for name in ("swisslipids", "swisslipids_similarity", "chebi_local", "chebi_local_similarity",
                 "sifts_uniprot"):
        setattr(ids, name, True)
    ids.sifts_db, ids.swisslipids_db, ids.chebi_db = ix.sifts, ix.lipids, ix.chebi
    return cfg


# -- the evaluation stays untouched -------------------------------------------

def test_toggles_are_declared_off():
    ids = IdentifiersConfig()
    for name in SUPPLEMENTARY_RESOLVERS:
        assert getattr(ids, name) is False, name
        if name != "sifts_uniprot":
            assert getattr(ids, f"{name}_similarity") is False, name


def test_evaluation_config_enables_nothing(tmp_path):
    cfg = RunConfig.from_ini_path(EVAL_CONFIG)
    assert get_supplementary_resolvers(cfg) == []
    results = ResultsManager(tmp_path / "r.json")
    results.set_data("identifiers/A/fasta_map_protein/blast_pdb_protein", {
        "signature": SEQ, "hit_type": "identity", "hits": ["1AQ7_A"], "ident_type": "PDB_ID",
        "signature_type": "residue_sequence_protein"})
    before = json.dumps(results.get_data("identifiers"), sort_keys=True)
    out = run_supplementary_pass(results, [("A", {"fasta_map_protein": SEQ})], cfg, {},
                                 str(tmp_path), None, lambda: False)
    assert out == []
    assert json.dumps(results.get_data("identifiers"), sort_keys=True) == before


def test_repo_config_enables_them():
    ids = RunConfig.from_ini_path(REPO / "config.ini").identifiers
    assert ids.blast_uniref50 and ids.swisslipids and ids.chebi_local and ids.sifts_uniprot
    assert ids.foldseek_pdb_similarity


def test_missing_data_means_inactive(tmp_path):
    cfg = RunConfig()
    ids = cfg.identifiers
    ids.blast_uniref50 = ids.swisslipids = ids.chebi_local = True
    cfg.blast.uniref50_aa_db = str(tmp_path / "none")
    ids.swisslipids_db = ids.chebi_db = str(tmp_path / "none.sqlite")
    assert get_supplementary_resolvers(cfg) == []


# -- resolvers ----------------------------------------------------------------

def test_uniref50_accessions():
    assert uniref50_accession("UniRef50_P00760") == "P00760"
    assert uniref50_accession("UniRef50_A0A5A9P0L4") == "A0A5A9P0L4"
    assert uniref50_accession("UniRef50_UPI0001A2B3C4") is None
    assert uniref50_accession("P00760") is None


def test_uniref50_drops_uniparc_only_hits(monkeypatch):
    from src_new.identification.resolvers import blast
    hits = [BlastHit(["UniRef50_P00760"], 1e-100, 400, 1.0, 1.0),
            BlastHit(["UniRef50_UPI0001A2B3C4"], 1e-90, 300, 0.9, 1.0)]
    monkeypatch.setattr(blast.BLASTResolver, "_process_blast_results", lambda self, j: hits)
    r = BLASTResolverUNIREF50(RunConfig())
    kept = r._process_blast_results([{}])
    assert [h.accessions for h in kept] == [["P00760"]]
    assert r.name == "blast_uniref50" and r.identifier_type == "UNIPROT_ID"
    cfg = RunConfig()
    cfg.blast.uniref50_num_threads, cfg.blast.uniref50_timeout_s = 4, 900
    r = BLASTResolverUNIREF50(cfg)
    assert (r._num_threads(), r._search_timeout_s()) == (4, 900)
    # the other BLAST databases keep their own settings
    pdb = blast.BLASTResolverPDBAA(cfg)
    assert (pdb._num_threads(), pdb._search_timeout_s()) == (cfg.blast.blastp_num_threads,
                                                              cfg.blast.timeout_s)


@pytest.mark.parametrize("target,expected", [
    ("1abc-assembly1.cif.gz_A", "1ABC"), ("1abc_A", "1ABC"), ("1abc", "1ABC"),
    ("7XYZ_B some title", "7XYZ"), ("AF-P01542-F1-model_v6", None), ("", None),
])
def test_foldseek_pdb_targets(target, expected):
    assert normalize_foldseek_pdb_target(target) == expected


def test_foldseek_pdb_one_row_per_entry(tmp_path, monkeypatch):
    from src_new.identification.resolvers import foldseek
    monkeypatch.setattr(foldseek.Foldseek3DiResolver, "_check_binary", lambda self: False)
    r = FoldseekPDBResolver(RunConfig())
    assert r.name == "foldseek_pdb" and r.identifier_type == "PDB_ID"
    assert r._db_path == RunConfig().foldseek.pdb_db_path
    m8 = tmp_path / "r.m8"
    m8.write_text("q\t1abc-assembly1.cif.gz_A\t0.95\nq\t1abc-assembly1.cif.gz_B\t0.97\n"
                  "q\t2xyz_A\t0.5\nq\tjunk\t0.9\n")
    assert dict(r._parse_m8(str(m8))) == {"1ABC": 97.0, "2XYZ": 50.0}
    # no binary: no search, and never the public server
    assert r._resolve_similarity("ATOM  ...", str(tmp_path)) == []


def test_swisslipids_and_chebi(indexes):
    from src_new.identification.resolvers.chebi_local import ChebiLocalResolver
    from src_new.identification.resolvers.swisslipids import SwissLipidsResolver
    cfg = _ui_config(indexes)
    sl = SwissLipidsResolver(cfg)
    # shorthand -> isomeric subspecies only
    assert sl._resolve_identity("PC(16:0/18:1(9Z))", "") == ["SLM:000000651"]
    # protonation flag ignored (blocks 1+2), other stereo = similarity
    assert sl._resolve_identity("WTJKGGKOPKCXLL-VYOBOKEXSA-O", "") == ["SLM:000000651"]
    assert sl._resolve_similarity("WTJKGGKOPKCXLL-VYOBOKEXSA-N", "") == [("SLM:000000999", 90.0)]
    ch = ChebiLocalResolver(cfg)
    assert ch._resolve_identity("PXXJHWLDUBFPOL-UHFFFAOYSA-N", "") == ["CHEBI:41033"]
    assert ch._resolve_similarity("PXXJHWLDUBFPOL-UHFFFAOYSA-N", "") == []
    assert ch._is_applicable("not a key") is False
    assert {type(r).__name__ for r in get_supplementary_resolvers(cfg)} == {
        "SwissLipidsResolver", "ChebiLocalResolver"}


# -- SIFTS --------------------------------------------------------------------

def test_sifts_maps_identity_chains(indexes, tmp_path):
    cfg = _ui_config(indexes)
    results = ResultsManager(tmp_path / "r.json")
    base = "identifiers/A/fasta_map_protein"
    results.set_data(f"{base}/blast_pdb_protein", {
        "signature": SEQ, "hit_type": "identity", "ident_type": "PDB_ID",
        "hits": ["1AQ7_A", "3PTB_A", "9FUS_A", "4ZZZ_A"],
        "signature_type": "residue_sequence_protein"})
    results.set_data(f"{base}/blast_pdb_protein@sim", {
        "signature": SEQ, "hit_type": "similarity", "ident_type": "PDB_ID",
        "hits": [["5ABC_A", 80.0]], "signature_type": "residue_sequence_protein"})
    assert derive_sifts_hits(results, "A", cfg) == 1
    blob = results.get_data(f"{base}/sifts_uniprot")
    # fusion chain 9FUS_A (two accessions) and unmapped 4ZZZ_A are skipped
    assert blob["hits"] == ["P00760"] and blob["hit_type"] == "identity"
    assert blob["ident_type"] == "UNIPROT_ID" and blob["signature"] == SEQ
    assert blob["hits_metadata"]["P00760"]["pdb_chains"] == ["1AQ7_A", "3PTB_A"]
    assert results.get_data("identification/sifts/A") == {"1AQ7_A": "P00760", "3PTB_A": "P00760"}

    cfg.identifiers.sifts_mode = "xref"
    results.set_data(f"{base}/sifts_uniprot", None)
    assert derive_sifts_hits(results, "A", cfg) == 0
    assert not results.get_data(f"{base}/sifts_uniprot")


def test_second_pass_merges_attempted(indexes, tmp_path):
    cfg = _ui_config(indexes)
    results = ResultsManager(tmp_path / "r.json")
    results.set_data("identifiers/L/inchi_key/attempted", ["inchikey_pubchem", "inchikey_self"])
    results.set_data("identifiers/L/inchi_key/inchikey_self", {
        "signature": "PXXJHWLDUBFPOL-UHFFFAOYSA-N", "hit_type": "identity",
        "hits": ["PXXJHWLDUBFPOL-UHFFFAOYSA-N"], "ident_type": "INCHIKEY",
        "signature_type": "inchikey"})
    out = run_supplementary_pass(results, [("L", {"inchi_key": "PXXJHWLDUBFPOL-UHFFFAOYSA-N"})],
                                 cfg, {"inchi_key": "inchikey"}, str(tmp_path), None, lambda: False)
    assert out == [{"fragment_name": "L", "errors": []}]
    gen = results.get_data("identifiers/L/inchi_key")
    assert gen["inchikey_self"]["hits"] == ["PXXJHWLDUBFPOL-UHFFFAOYSA-N"]  # untouched
    assert gen["chebi_local"]["hits"] == ["CHEBI:41033"]
    assert gen["attempted"][:2] == ["inchikey_pubchem", "inchikey_self"]
    assert "chebi_local" in gen["attempted"] and "swisslipids" in gen["attempted"]


def test_second_pass_respects_budget(indexes, tmp_path):
    cfg = _ui_config(indexes)
    results = ResultsManager(tmp_path / "r.json")
    out = run_supplementary_pass(results, [("L", {"inchi_key": "PXXJHWLDUBFPOL-UHFFFAOYSA-N"})],
                                 cfg, {"inchi_key": "inchikey"}, str(tmp_path), None, lambda: True)
    assert out == [] and results.get_data("identifiers") is None


# -- evidence families ----------------------------------------------------------

def _hit(identifier, resolver, ident_type="UNIPROT_ID", hit_type="identity", score=100.0):
    return RawHit(identifier, ident_type, resolver, score, SEQ, "residue_sequence_protein", hit_type)


def test_uniref50_adds_no_family_where_swissprot_hit():
    base = deduplicate_and_score([_hit("P00760", "blast_swissprot_protein")])
    both = deduplicate_and_score([_hit("P00760", "blast_swissprot_protein"),
                                  _hit("P00760", "blast_uniref50")])
    key = ("P00760", "UNIPROT_ID")
    assert both[key]["belief"] == base[key]["belief"]
    assert both[key]["n_identity_sources"] == 1


def test_sifts_corroborates_with_pdb_evidence():
    base = deduplicate_and_score([_hit("P00760", "blast_swissprot_protein")])
    more = deduplicate_and_score([_hit("P00760", "blast_swissprot_protein"),
                                  _hit("P00760", "sifts_uniprot")])
    key = ("P00760", "UNIPROT_ID")
    assert base[key]["belief"] == pytest.approx(50.0)
    assert more[key]["belief"] == pytest.approx(75.0)


def test_foldseek_pdb_is_structure_evidence():
    hits = [_hit("1AQ7", "foldseek_pdb@sim", "PDB_ID", "similarity", 97.0)]
    assert deduplicate_and_score(hits, structure_mode="tiebreak")[("1AQ7", "PDB_ID")]["belief"] == 0.0


# -- verification window ----------------------------------------------------------

def _g(identifier, consensus, sources, ident_type="UNIPROT_ID"):
    return ((identifier, ident_type), {"consensus_score": consensus, "source_resolvers": sources})


def test_extend_window_keeps_regular_window_first():
    window = [_g("P1", 90, ["blast_swissprot_protein"]), _g("P2", 80, ["blast_swissprot_protein"])]
    all_groups = dict([
        _g("P1", 95, ["blast_swissprot_protein", "blast_uniref50"]),
        _g("P2", 80, ["blast_swissprot_protein"]),
        _g("P3", 99, ["blast_uniref50"]),
        _g("P4", 70, ["blast_uniref50"]),
        _g("1ABC", 98, ["foldseek_pdb"], "PDB_ID"),          # structure-only: excluded
        _g("P5", 99, ["blast_swissprot_protein"]),            # regular, outside the window
    ])
    out, n = _extend_window(window, all_groups, frozenset({"foldseek_pdb"}), 1)
    assert [k[0] for k, _m in out] == ["P1", "P2", "P3"] and n == 1
    assert out[0][1]["consensus_score"] == 95  # regular group carries all its evidence


def _manager():
    mgr = VerificationManager.__new__(VerificationManager)
    mgr._registry = SimpleNamespace(
        get_fetcher=lambda ident_type, signature_type=None: None,
        get_applicable_workers=lambda *a, **k: [],
        get_scorer=lambda *a, **k: None,
    )
    mgr._verification_config = RunConfig().verification
    return mgr


def _seed(results, n_regular, supplementary):
    for i in range(n_regular):
        results.set_data(f"identifiers/S/fasta_map_protein/res{i}", {
            "signature": SEQ, "hit_type": "identity", "hits": [f"Q{i:05d}"],
            "ident_type": "UNIPROT_ID", "signature_type": "residue_sequence_protein"})
    if supplementary:
        results.set_data("identifiers/S/fasta_map_protein/blast_uniref50", {
            "signature": SEQ, "hit_type": "identity", "hits": supplementary,
            "ident_type": "UNIPROT_ID", "signature_type": "residue_sequence_protein"})


def test_full_window_keeps_every_regular_group(tmp_path):
    """150 regular groups fill the 100-slot window; supplementary-only groups
    are verified in addition, never instead."""
    plain = ResultsManager(tmp_path / "a.json")
    _seed(plain, 150, None)
    _manager().verify_all(plain, deadline_epoch=time.time() + 300)
    plain_ids = [h["identifier"] for h in plain.get_data("verification/S/verified_hits")]

    supp = ResultsManager(tmp_path / "b.json")
    _seed(supp, 150, [f"N{i:05d}" for i in range(30)])
    _manager().verify_all(supp, deadline_epoch=time.time() + 300)
    supp_ids = [h["identifier"] for h in supp.get_data("verification/S/verified_hits")]

    assert len(plain_ids) == 100
    assert set(plain_ids) <= set(supp_ids)
    assert len(supp_ids) == 100 + 20  # verify_top_n_supplementary
    assert supp.get_data("verification/S/window")["n_supplementary"] == 20
    assert "n_supplementary" not in plain.get_data("verification/S/window")


def test_swisslipids_display_name_and_link(indexes, monkeypatch):
    from src_new.api.hit_names import hit_display_name
    from src_new.api.utils import build_database_url
    from src_new.verification.fetchers.compound_fetcher import CompoundSignatureFetcher
    monkeypatch.setattr(IdentifiersConfig, "swisslipids_db", indexes.lipids)
    hit = {"ident_type": "SLM_ID", "identifier": "SLM:000000651"}
    assert hit_display_name(hit) == "Lipid SLM:000000651"
    assert hit_display_name({**hit, "name": "POPC"}) == "POPC"
    assert build_database_url("SLM:000000651", "SLM_ID") == \
        "https://www.swisslipids.org/#/entity/SLM:000000651/"
    assert CompoundSignatureFetcher._fetch_swisslipids("SLM:000000651") == "CCC"
    assert CompoundSignatureFetcher._fetch_swisslipids("SLM:404") is None


# -- deferred slow resolvers -----------------------------------------------------

def test_deferral_is_off_in_the_evaluation_config():
    from src_new.identification.registry import deferred_resolver_names, get_default_resolvers
    cfg = RunConfig.from_ini_path(EVAL_CONFIG)
    assert deferred_resolver_names(cfg) == frozenset()
    names = [r.name for r in get_default_resolvers(cfg)]
    assert names == [r.name for r in get_default_resolvers(cfg, include_deferred=True)]


def test_deferred_resolvers_leave_the_first_pass():
    from src_new.identification.registry import get_default_resolvers, get_deferred_resolvers
    cfg = RunConfig()
    cfg.identifiers.deferred_resolvers = "blast_nr_protein, blast_nt"
    first = {r.name for r in get_default_resolvers(cfg)}
    assert "blast_nr_protein" not in first and "blast_nt" not in first
    assert "blast_swissprot_protein" in first
    assert sorted(r.name for r in get_deferred_resolvers(cfg)) == ["blast_nr_protein", "blast_nt"]
    ui = RunConfig.from_ini_path(REPO / "config.ini")
    assert {"blast_nr_protein", "blast_nt", "blast_core_nt"} <= {
        r.name for r in get_deferred_resolvers(ui)}


def test_second_pass_runs_deferred_after_all_supplementary(tmp_path, monkeypatch):
    from src_new.identification import registry, supplementary
    from src_new.identification.base import IdentifierResolver
    calls = []

    class Fake(IdentifierResolver):
        accepted_signatures = ["inchikey"]

        def __init__(self, name):
            super().__init__(RunConfig())
            self.name = name

        def _is_applicable(self, signature):
            return True

        def _resolve_identity(self, signature, wd):
            calls.append((self.name, signature))
            return []

        def _resolve_similarity(self, signature, wd):
            return []

    monkeypatch.setattr(supplementary, "get_supplementary_resolvers", lambda c: [Fake("supp")])
    monkeypatch.setattr(registry, "get_deferred_resolvers", lambda c: [Fake("slow")])
    results = ResultsManager(tmp_path / "r.json")
    out = run_supplementary_pass(results, [("A", {"inchi_key": "KA"}), ("B", {"inchi_key": "KB"})],
                                 RunConfig(), {"inchi_key": "inchikey"}, str(tmp_path), None,
                                 lambda: False)
    assert calls == [("supp", "KA"), ("supp", "KB"), ("slow", "KA"), ("slow", "KB")]
    assert [o["fragment_name"] for o in out] == ["A", "B"]
