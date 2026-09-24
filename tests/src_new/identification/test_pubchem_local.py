"""Integration tests: local PubChem mirror wired into resolvers and fetchers.

Builds a tiny synthetic mirror via pubchem_db.build() (no network) and proves
the identify/verify paths answer from it without touching PUG.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from src_new.config.loader import RunConfig
from src_new.molecules.pubchem_db import build
from src_new.verification.fetchers import compound_fetcher

_ROWS = [
    (2, "CCO", "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"),                      # ethanol
    (3, "CC(=O)OC1=CC=CC=C1C(=O)O", "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"),  # aspirin
    (7, "C1=CC=C(C=C1)C(=O)O", "DDDDDDDDDDDDDD-EEEEEEEEEE-N"),     # benzoic acid
]
_IK_FAKE_INCHI = "InChI=1S/fake"


def _write_gz(path: Path, lines: list[str]) -> None:
    with gzip.open(path, "wt") as fh:
        fh.write("\n".join(lines) + "\n")


@pytest.fixture()
def mirror_db(tmp_path: Path) -> Path:
    smiles_gz = tmp_path / "CID-SMILES.gz"
    ik_gz = tmp_path / "CID-InChI-Key.gz"
    _write_gz(smiles_gz, [f"{cid}\t{smi}" for cid, smi, _ in _ROWS])
    _write_gz(ik_gz, [f"{cid}\t{_IK_FAKE_INCHI}\t{ik}" for cid, _, ik in _ROWS])
    db_path = tmp_path / "pubchem.sqlite"
    build(db_path, smiles_gz, ik_gz, workers=1)
    return db_path


@pytest.fixture()
def config(mirror_db: Path) -> RunConfig:
    cfg = RunConfig()
    cfg.pubchem.local_db_path = str(mirror_db)
    return cfg


@pytest.fixture(autouse=True)
def _reset_fetcher_singleton():
    compound_fetcher._LOCAL_DB = None
    compound_fetcher._LOCAL_DB_READY = False
    yield
    compound_fetcher._LOCAL_DB = None
    compound_fetcher._LOCAL_DB_READY = False


class TestFormulaLocalResolver:
    def test_identity_lookup(self, config: RunConfig) -> None:
        from src_new.identification.resolvers.formula_local import FormulaLocalResolver

        r = FormulaLocalResolver(config)
        assert r.name == "formula_pubchem_local"
        assert sorted(r._resolve_identity("C9H8O4", "")) == ["3"]

    def test_garbage_formula_empty_not_error(self, config: RunConfig) -> None:
        from src_new.identification.resolvers.formula_local import FormulaLocalResolver

        assert FormulaLocalResolver(config)._resolve_identity("not a formula!", "") == []

    def test_local_hit_means_no_network(self, config: RunConfig, monkeypatch) -> None:
        from src_new.identification.resolvers.formula_local import FormulaLocalResolver
        import requests

        monkeypatch.setattr(requests.Session, "get", lambda *a, **k: pytest.fail("network used"))
        r = FormulaLocalResolver(config)
        assert r.resolve("C2H6O", as_similarity=False) == ["2"]


class TestRegistryOrder:
    def test_local_before_pug(self, config: RunConfig) -> None:
        from src_new.identification.registry import get_default_resolvers

        names = [r.name for r in get_default_resolvers(config)]
        assert "formula_pubchem_local" in names
        assert names.index("formula_pubchem_local") < names.index("formula_pubchem")

    def test_missing_db_degrades(self, tmp_path: Path) -> None:
        from src_new.identification.registry import get_default_resolvers

        cfg = RunConfig()
        cfg.pubchem.local_db_path = str(tmp_path / "absent.sqlite")
        names = [r.name for r in get_default_resolvers(cfg)]
        assert "formula_pubchem_local" not in names
        assert "formula_pubchem" in names


class TestInchikeyLocalFirst:
    def test_variant_lookup_hits_mirror(self, config: RunConfig) -> None:
        from src_new.identification.resolvers.inchikey import fetch_cids_from_inchikey

        # protonation variant "-O": mirror knows the "-N" form under cid 3 ONLY;
        # so exact key resolves, variant falls through to network chain (404
        # tolerated: session=None is fine, exceptions are swallowed by design).
        assert fetch_cids_from_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N", session=None, config=config) == ["3"]


class TestHfamilyLocalFirst:
    def test_similarity_channel_uses_mirror(self, config: RunConfig, monkeypatch) -> None:
        from src_new.identification.resolvers.hfamily import FormulaHFamilyResolver

        r = FormulaHFamilyResolver(config)
        assert r._local_db is not None
        monkeypatch.setattr(r, "_pug_get", lambda path: pytest.fail("network used"))
        out = r._resolve_similarity("C9H8O4", "")
        cids = [cid for cid, _score in out]
        assert "3" in cids


class TestFetcherLocalFirst:
    def _no_network(self, monkeypatch) -> None:
        monkeypatch.setattr(
            compound_fetcher, "_polite_get", lambda *a, **k: pytest.fail("network used")
        )

    def test_fetch_pubchem_cid(self, mirror_db: Path, monkeypatch) -> None:
        self._no_network(monkeypatch)
        monkeypatch.setenv("PUBCHEM_LOCAL_DB", str(mirror_db))
        fetcher = compound_fetcher.CompoundSignatureFetcher()
        assert fetcher.fetch("3", "PUBCHEM_CID") == "CC(=O)OC1=CC=CC=C1C(=O)O"

    def test_fetch_inchikey(self, mirror_db: Path, monkeypatch) -> None:
        self._no_network(monkeypatch)
        monkeypatch.setenv("PUBCHEM_LOCAL_DB", str(mirror_db))
        fetcher = compound_fetcher.CompoundSignatureFetcher()
        assert fetcher.fetch("BSYNRYMUTXBXSQ-UHFFFAOYSA-N", "INCHIKEY") == "CC(=O)OC1=CC=CC=C1C(=O)O"

    def test_prefetch_resolves_offline(self, mirror_db: Path, monkeypatch, tmp_path: Path) -> None:
        self._no_network(monkeypatch)
        monkeypatch.setenv("PUBCHEM_LOCAL_DB", str(mirror_db))
        monkeypatch.setattr(compound_fetcher, "_SIM_CACHE", str(tmp_path / "cache"))
        assert compound_fetcher.prefetch_pubchem(["2", "3", "7"]) == 0  # nothing left for HTTP
        fetcher = compound_fetcher.CompoundSignatureFetcher()
        assert fetcher.fetch("7", "PUBCHEM_CID") == "C1=CC=C(C=C1)C(=O)O"


class TestOpsCLI:
    def test_pubchem_lookup_modes(self, mirror_db: Path) -> None:
        import subprocess
        import sys

        cli = ["scripts/pubchem_lookup.py", "--db", str(mirror_db)]
        r = subprocess.run([sys.executable, *cli, "--cid", "3"], capture_output=True, text=True)
        assert r.returncode == 0 and "BSYNRYMUTXBXSQ-UHFFFAOYSA-N" in r.stdout
        r = subprocess.run([sys.executable, *cli, "--formula", "C2H6O"], capture_output=True, text=True)
        assert r.stdout.startswith("2\tCCO")
        r = subprocess.run([sys.executable, *cli, "--inchikey", "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"],
                           capture_output=True, text=True)
        assert r.returncode == 0 and "cid=2" in r.stdout
        r = subprocess.run([sys.executable, *cli, "--stats"], capture_output=True, text=True)
        assert "rows: 3" in r.stdout
        r = subprocess.run([sys.executable, *cli, "--cid", "999999"], capture_output=True, text=True)
        assert r.returncode == 1 and "not found" in r.stdout
