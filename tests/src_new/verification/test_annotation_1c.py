"""Tests for the v3.142 1c annotation-term redesign.

Uniform per-kind signal schema (PubChem: mirror floor 70, live-fill to the
same 100-denominator), per-segment live-call budget with silent fallback,
and gap-kind scorer coverage (SWISSPROT, INCHIKEY, ALPHAFOLD bare accession,
CHEBI alias).
"""
from unittest.mock import Mock, patch

from src_new.verification.registry import VerificationRegistry
from src_new.verification.scorers.pubchem_scorer import PubChemAnnotationScorer
from src_new.verification.scorers.uniprot_scorer import UniProtAnnotationScorer


class _Row:
    def __init__(self, smiles="O", formula_hill="H2O"):
        self.smiles = smiles
        self.formula_hill = formula_hill


class _StubDB:
    def __init__(self, row):
        self._row = row

    def by_cid(self, cid):
        return self._row

    def by_inchikey(self, inchikey):
        return self._row


def _props(props):
    r = Mock()
    r.json.return_value = {"PropertyTable": {"Properties": [props]}}
    r.raise_for_status = Mock()
    return r


def _syns(syns):
    r = Mock()
    r.json.return_value = {"InformationList": {"Information": [{"Synonym": syns}]}}
    r.raise_for_status = Mock()
    return r


# ------------------------------------------------------------- pubchem mirror

def test_mirror_hit_live_disabled_stays_at_schema_floor(monkeypatch):
    from src_new.verification.scorers import pubchem_scorer as mod
    monkeypatch.setattr(mod, "_local_db", lambda: _StubDB(_Row()))
    scorer = PubChemAnnotationScorer()
    scorer.configure(live_fetch=False, timeout_s=3.0)
    scorer.begin_segment(25)
    with patch.object(mod.requests, "get") as mock_get:
        quality = scorer.score("962", "PUBCHEM_CID")
    assert quality is not None
    assert quality.score == 70.0
    assert set(quality.signals) == {
        "canonical_smiles", "isomeric_smiles", "molecular_formula"}
    assert mock_get.call_count == 0  # never touched the network


def test_mirror_hit_live_fill_reaches_full_schema(monkeypatch):
    from src_new.verification.scorers import pubchem_scorer as mod
    monkeypatch.setattr(mod, "_local_db", lambda: _StubDB(_Row()))
    scorer = PubChemAnnotationScorer()
    scorer.begin_segment(25)
    with patch.object(mod.requests, "get",
                      side_effect=[_props({"IUPACName": "oxidane"}), _syns(["water"])]):
        quality = scorer.score("962", "PUBCHEM_CID")
    assert quality is not None
    assert quality.score == 100.0
    assert "iupac_name" in quality.signals and "synonyms" in quality.signals


def test_mirror_hit_budget_exhaustion_keeps_partial_fill(monkeypatch):
    from src_new.verification.scorers import pubchem_scorer as mod
    monkeypatch.setattr(mod, "_local_db", lambda: _StubDB(_Row()))
    scorer = PubChemAnnotationScorer()
    scorer.begin_segment(1)  # one live call total -> props only, no synonyms
    with patch.object(mod.requests, "get",
                      side_effect=[_props({"IUPACName": "oxidane"}), _syns(["water"])]):
        quality = scorer.score("962", "PUBCHEM_CID")
    assert quality is not None
    assert quality.score == 85.0  # 70 floor + iupac 15; synonyms unproven


def test_mirror_hit_network_failure_is_silent_monkeypatch(monkeypatch):
    from src_new.verification.scorers import pubchem_scorer as mod
    monkeypatch.setattr(mod, "_local_db", lambda: _StubDB(_Row()))
    scorer = PubChemAnnotationScorer()
    scorer.begin_segment(25)
    with patch.object(mod.requests, "get", side_effect=Exception("banned")):
        quality = scorer.score("962", "PUBCHEM_CID")
    assert quality is not None
    assert quality.score == 70.0  # mirror floor retained


def test_inchikey_uses_mirror_inchikey_column(monkeypatch):
    from src_new.verification.scorers import pubchem_scorer as mod
    db = _StubDB(_Row())
    calls = []
    db_by_inchikey = db.by_inchikey

    def spy(ik):
        calls.append(ik)
        return db_by_inchikey(ik)
    db.by_inchikey = spy
    monkeypatch.setattr(mod, "_local_db", lambda: db)
    scorer = PubChemAnnotationScorer()
    scorer.configure(live_fetch=False, timeout_s=3.0)
    quality = scorer.score("LFQSCWFLJHTTHZ-UHFFFAOYSA-N", "INCHIKEY")
    assert quality is not None
    assert quality.score == 70.0
    assert calls == ["LFQSCWFLJHTTHZ-UHFFFAOYSA-N"]


# ----------------------------------------------------------------- gap kinds

def test_uniprot_scorer_supports_swissprot():
    assert UniProtAnnotationScorer().supports("SWISSPROT_ID")


@patch("src_new.verification.scorers.uniprot_scorer.requests.get")
def test_uniprot_scorer_alphafold_bare_accession(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = {
        "entryType": "UniProtKB reviewed (Swiss-Prot)",
        "annotationScore": 5,
        "proteinExistence": 1,
        "genes": [{"gene": {"locusName": "TP53"}}],
        "uniProtKBCrossReferences": [],
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response
    quality = UniProtAnnotationScorer().score("P99999", "ALPHAFOLD_ID")
    assert quality is not None
    assert quality.score > 0.0
    assert "P99999" in mock_get.call_args[0][0]


def test_chebi_alias_supported():
    from src_new.verification.scorers.chebi_scorer import ChebiAnnotationScorer
    assert ChebiAnnotationScorer().supports("CHEBI")


# ------------------------------------------------------------- registry wire

def test_registry_begin_segment_configures_budget_aware_scorers():
    scorer = PubChemAnnotationScorer()
    reg = VerificationRegistry(workers=[], fetchers=[], scorers=[scorer])
    reg.begin_segment(live_fetch=False, budget=7, timeout_s=2.5)
    assert scorer._remaining == 7
    assert scorer._live_fetch is False
    assert scorer._timeout_s == 2.5
