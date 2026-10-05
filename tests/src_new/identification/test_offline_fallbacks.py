"""Tests for the offline-PUBCHEM identification fallbacks (2026-09-23).

InchiKeySelfResolver: InChIKey signature is itself the identity candidate
(cactus-first verification, no network). FormulaChEMBLResolver: exact-formula
-> ChEMBL IDs via EBI REST, gated by config flag or VALIDATION_SKIP_PUG.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.base import IdentifierResolutionError
from src_new.identification.resolvers.formula import (
    FormulaChEMBLResolver,
    fetch_chembl_ids_from_formula,
)
from src_new.identification.resolvers.inchikey import InchiKeySelfResolver


@pytest.fixture
def config() -> RunConfig:
    return RunConfig()


VALID_IK = "BSYNRYMUTXBXSQ-UHFFFAOYSA-n"


class TestInchiKeySelfResolver:
    def test_identity_passthrough_uppercases(self, config: RunConfig) -> None:
        r = InchiKeySelfResolver(config)
        assert r.resolve(VALID_IK, as_similarity=False) == [VALID_IK.upper()]

    def test_identifier_type_and_name(self, config: RunConfig) -> None:
        r = InchiKeySelfResolver(config)
        assert r.identifier_type == "INCHIKEY"
        assert r.name == "inchikey_self"
        assert r.accepted_signatures == ["inchikey"]

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "TOOSHORT",
            "BSYNRYMUTXBXSQ",
            "BSYNRYMUTXBXSQ-UHFFFAOYSA",
            "BSYNRYMUTXBXSQ-UHFFFAOYSA-NX",  # too many parts
            "B-UHFFFAOYSA-N",
            "BSYNRYMUTXBXSQBSA-UGHFFAOYSAA-N",  # wrong segment lengths
            None,
        ],
    )
    def test_rejects_non_inchikey(self, config: RunConfig, bad) -> None:
        r = InchiKeySelfResolver(config)
        assert r.is_applicable(bad, "inchikey", as_similarity=False) is False

    def test_similarity_empty(self, config: RunConfig) -> None:
        r = InchiKeySelfResolver(config)
        assert r.resolve(VALID_IK, as_similarity=True) == []


def _mock_response(status=200, payload=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json = MagicMock(return_value=payload or {})
    if status >= 400:
        import requests
        err = requests.HTTPError(response=resp)
        resp.raise_for_status = MagicMock(side_effect=err)
    else:
        resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def chembl_config() -> RunConfig:
    cfg = RunConfig()
    cfg.identifiers.formula_chembl = True  # resolver honors its enable flag
    return cfg


class TestFormulaChEMBL:
    def test_pattern(self, chembl_config: RunConfig) -> None:
        r = FormulaChEMBLResolver(chembl_config)
        assert r.is_applicable("C6H15N4O2", "formula", as_similarity=False)
        assert not r.is_applicable("protein", "formula", as_similarity=False)
        assert not r.is_applicable("", "formula", as_similarity=False)
        assert r.identifier_type == "CHEMBL_ID"
        assert r.name == "formula_chembl"

    def test_fetch_parses_unique_ids(self) -> None:
        session = MagicMock()
        session.get.return_value = _mock_response(
            200, {"molecules": [
                {"molecule_chembl_id": "CHEMBL112"},
                {"molecule_chembl_id": "CHEMBL112"},
                {"molecule_chembl_id": "CHEMBL25"},
                {"molecule_chembl_id": None},
            ]}
        )
        assert fetch_chembl_ids_from_formula("C8H9NO2", session) == ["CHEMBL112", "CHEMBL25"]
        url_used = session.get.call_args[0][0]
        assert "chembl/api/data/molecule.json" in url_used
        assert session.get.call_args[1]["params"]["molecule_structures__full_molformula__exact"] == "C8H9NO2"

    def test_fetch_empty_hits(self) -> None:
        session = MagicMock()
        session.get.return_value = _mock_response(200, {"molecules": []})
        assert fetch_chembl_ids_from_formula("C999H999", session) == []

    def test_400_is_soft_empty(self) -> None:
        session = MagicMock()
        session.get.return_value = _mock_response(400)
        assert fetch_chembl_ids_from_formula("bad", session) == []

    def test_transport_error_raises(self) -> None:
        session = MagicMock()
        session.get.side_effect = ConnectionError("down")
        with pytest.raises(IdentifierResolutionError):
            fetch_chembl_ids_from_formula("C6H6", session)

    def test_resolve_flow(self, chembl_config: RunConfig) -> None:
        r = FormulaChEMBLResolver(chembl_config)
        r._session = MagicMock()
        r._session.get.return_value = _mock_response(200, {"molecules": [{"molecule_chembl_id": "CHEMBL1562"}]})
        assert r.resolve("C37H38N8O7S2", as_similarity=False) == ["CHEMBL1562"]
        assert r.resolve("C37H38N8O7S2", as_similarity=True) == []


class TestRegistryGating:
    def test_self_always_registered(self, config: RunConfig, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VALIDATION_SKIP_PUG", raising=False)
        from src_new.identification.registry import get_default_resolvers
        names = [r.name for r in get_default_resolvers(config)]
        assert "inchikey_self" in names
        assert "formula_chembl" not in names  # default off

    def test_chembl_registered_with_config_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VALIDATION_SKIP_PUG", raising=False)
        from src_new.identification.registry import get_default_resolvers
        cfg = RunConfig()
        cfg.identifiers.formula_chembl = True
        names = [r.name for r in get_default_resolvers(cfg)]
        assert "formula_chembl" in names

    def test_chembl_registered_with_env(self, config: RunConfig, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VALIDATION_SKIP_PUG", "1")
        from src_new.identification.registry import get_default_resolvers
        names = [r.name for r in get_default_resolvers(config)]
        assert "formula_chembl" in names

    def test_chembl_flag_off_is_output_equivalent_containment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OQ-1 containment contract (ruling 2026-10-05): live ini
        `formula_chembl: no` under SKIP_PUG must keep the resolver
        registered (no import/registration breakage) while excluding it
        from identity selection -- byte-equivalent outputs to the
        dead-upstream era (attempt->400->[]) minus telemetry noise.
        """
        monkeypatch.setenv("VALIDATION_SKIP_PUG", "1")
        from src_new.identification.registry import IdentifierRegistry, get_default_resolvers
        cfg = RunConfig()
        assert cfg.identifiers.formula_chembl is False  # flag OFF = containment
        resolvers = get_default_resolvers(cfg)
        by_name = {r.name: r for r in resolvers}
        assert "formula_chembl" in by_name  # still registered (SKIP_PUG)
        assert by_name["formula_chembl"].enabled_identity is False
        reg = IdentifierRegistry(resolvers)
        identity_names = [r.name for r in reg.get_applicable_resolvers("formula", as_similarity=False)]
        assert "formula_chembl" not in identity_names
        # similarity listing may include it, but similarity is a designed no-op
        # (_resolve_similarity returns [] for exact-composition signatures)
        assert by_name["formula_chembl"]._resolve_similarity("C8H10N4O2", "") == []
