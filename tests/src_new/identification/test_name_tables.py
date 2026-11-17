"""Offline checks of the curated force-field name table (name_tables/maps.json)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.name import NameResolverMAPS, _db_cache

REPO = Path(__file__).resolve().parents[3]
TABLE_DIR = REPO / "src_new" / "identification" / "name_tables"
MAPS = TABLE_DIR / "maps.json"
PROVENANCE = TABLE_DIR / "maps_provenance.json"

INCHIKEY_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
WATER_NAMES = {"SOL", "HOH", "WAT", "TIP3", "TIP3P", "TIP4P", "SPC", "SPCE", "T3P", "T4P"}

SODIUM = "FKNQFGJONOIPTF-UHFFFAOYSA-N"
POTASSIUM = "NPYPAHLBTDXSSS-UHFFFAOYSA-N"
CHLORIDE = "VEXZGXHMUGYJMC-UHFFFAOYSA-M"
CALCIUM = "BHPQYMZQTOCNFJ-UHFFFAOYSA-N"
CHOLESTEROL = "HVYWMOMLDIMFJA-DPAQBDIFSA-N"
POPC = "WTJKGGKOPKCXLL-VYOBOKEXSA-N"  # PubChem CID 5497103


@pytest.fixture(scope="module")
def maps() -> dict:
    return json.loads(MAPS.read_text())


@pytest.fixture(scope="module")
def provenance() -> list[dict]:
    return json.loads(PROVENANCE.read_text())


def test_maps_is_flat_str_to_str(maps: dict) -> None:
    assert isinstance(maps, dict) and maps
    for key, value in maps.items():
        assert isinstance(key, str) and key == key.strip() and key
        assert isinstance(value, str)


def test_maps_keys_sorted(maps: dict) -> None:
    assert list(maps) == sorted(maps)


def test_values_are_inchikeys(maps: dict) -> None:
    bad = {k: v for k, v in maps.items() if not INCHIKEY_RE.match(v)}
    assert not bad


def test_provenance_matches_maps_one_to_one(maps: dict, provenance: list[dict]) -> None:
    names = [p["name"] for p in provenance]
    assert len(names) == len(set(names))
    assert set(names) == set(maps)
    for p in provenance:
        assert p["inchikey"] == maps[p["name"]]


def test_provenance_records_complete(provenance: list[dict]) -> None:
    for p in provenance:
        for field in ("name", "molecule", "forcefields", "inchikey", "pubchem_cid",
                      "formula", "source_urls", "notes"):
            assert field in p, (p["name"], field)
        assert p["forcefields"] and all(isinstance(f, str) for f in p["forcefields"])
        assert isinstance(p["pubchem_cid"], int) and p["pubchem_cid"] > 0
        assert p["source_urls"] and all(u.startswith("https://") for u in p["source_urls"])
        assert any("pubchem.ncbi.nlm.nih.gov/compound/" in u for u in p["source_urls"])
        assert p["formula"]
        assert "martini" not in " ".join(p["forcefields"]).lower()


def test_no_water_names(maps: dict) -> None:
    assert not WATER_NAMES & set(maps)


def test_no_protein_residue_variants(maps: dict) -> None:
    assert not {"HSD", "HSE", "HSP", "HIE", "HID", "HIP", "CYX"} & set(maps)


@pytest.mark.parametrize("name,inchikey", [
    ("SOD", SODIUM), ("Na+", SODIUM), ("NA", SODIUM),
    ("POT", POTASSIUM), ("K+", POTASSIUM), ("K", POTASSIUM),
    ("CLA", CHLORIDE), ("Cl-", CHLORIDE), ("CL", CHLORIDE),
    ("CAL", CALCIUM), ("CA", CALCIUM),
    ("CHL1", CHOLESTEROL), ("CHOL", CHOLESTEROL), ("CHL", CHOLESTEROL),
    ("POPC", POPC),
])
def test_spot_checks(maps: dict, name: str, inchikey: str) -> None:
    assert maps[name] == inchikey


@pytest.mark.parametrize("a,b", [("TOCL1", "TOCL2"), ("OLE", "OLEP"), ("SAPI24", "SAPI25"),
                                 ("DYPC", "DXPC"), ("DUPC", "DLiPC")])
def test_variants_of_one_species_share_connectivity(maps: dict, a: str, b: str) -> None:
    # charge/protonation variants or alias names of one CHARMM species
    assert maps[a].split("-")[0] == maps[b].split("-")[0]


def test_name_resolver_returns_popc_inchikey() -> None:
    cfg = RunConfig()
    cfg.names.maps_db = str(MAPS)
    _db_cache.pop(str(MAPS), None)
    try:
        resolver = NameResolverMAPS(cfg)
        assert resolver.resolve("POPC", as_similarity=False) == [POPC]
        assert resolver.resolve("SOD", as_similarity=False) == [SODIUM]
        # exact, case-sensitive lookup
        assert resolver.resolve("popc", as_similarity=False) == []
        assert resolver.resolve("SOL", as_similarity=False) == []
    finally:
        _db_cache.pop(str(MAPS), None)


def test_server_config_uses_the_table():
    """The deployed config switches name_maps on and points at this table (2026-11-17)."""
    from src_new.config.loader import RunConfig
    from src_new.identification.resolvers.name import NameResolverMAPS
    cfg = RunConfig.from_default_ini()
    assert cfg.identifiers.name_maps is True
    assert cfg.names.maps_db.endswith("name_tables/maps.json")
    r = NameResolverMAPS(cfg)
    assert r.resolve("CLA") == ["VEXZGXHMUGYJMC-UHFFFAOYSA-M"]  # CHARMM chloride, not chlorophyll a
