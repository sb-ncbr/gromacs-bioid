"""G5 for chemical hits: read-time display names (live run e1605717 showed
"PubChem PXXJHWLDUBFPOL-UHFFFAOYSA-N" and "Element CA")."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src_new.api import hit_names


class _FakeMirror:
    rows = {"2332": "benzenecarboximidamide",
            "PXXJHWLDUBFPOL-UHFFFAOYSA-N": "benzenecarboximidamide"}

    def by_cid(self, cid):
        n = self.rows.get(str(cid))
        return SimpleNamespace(iupac_name=n) if n else None

    def by_inchikey(self, key):
        n = self.rows.get(key)
        return SimpleNamespace(iupac_name=n) if n else None


@pytest.fixture(autouse=True)
def _mirror(monkeypatch):
    hit_names._pubchem_name.cache_clear()
    monkeypatch.setattr(hit_names, "_mirror", lambda: _FakeMirror())
    yield
    hit_names._pubchem_name.cache_clear()


def test_existing_name_wins():
    assert hit_names.hit_display_name(
        {"ident_type": "PDB_ID", "identifier": "1AQ7", "name": "TRYPSIN"}) == "TRYPSIN"


def test_element_symbol_to_name():
    # One-atom molecules in a simulation are ions (Cl2 gas is "Chlorine").
    assert hit_names.hit_display_name({"ident_type": "ELEMENT", "identifier": "CA"}) == "Calcium ion"
    assert hit_names.hit_display_name({"ident_type": "ELEMENT", "identifier": "Cl"}) == "Chloride"
    assert hit_names.hit_display_name({"ident_type": "ELEMENT", "identifier": "NA"}) == "Sodium ion"
    assert hit_names.hit_display_name({"ident_type": "ELEMENT", "identifier": "AR"}) == "Argon"
    assert hit_names.hit_display_name(
        {"ident_type": "ELEMENT", "identifier": "CL", "name": "Chlorine"}) == "Chloride"
    assert hit_names.hit_display_name({"ident_type": "ELEMENT", "identifier": "XX"}) is None


def test_pubchem_from_mirror_by_cid_and_inchikey():
    assert hit_names.hit_display_name({"ident_type": "PUBCHEM_CID", "identifier": "2332"}) \
        == "Benzenecarboximidamide"
    assert hit_names.hit_display_name(
        {"ident_type": "INCHIKEY", "identifier": "PXXJHWLDUBFPOL-UHFFFAOYSA-N"}) \
        == "Benzenecarboximidamide"


def test_unknown_or_unsupported_stays_none():
    assert hit_names.hit_display_name({"ident_type": "PUBCHEM_CID", "identifier": "1"}) is None
    assert hit_names.hit_display_name({"ident_type": "CHEBI_ID", "identifier": "CHEBI:1"}) is None
    assert hit_names.hit_display_name({"ident_type": "PUBCHEM_CID", "identifier": ""}) is None


def test_no_mirror_is_not_an_error(monkeypatch):
    hit_names._pubchem_name.cache_clear()
    monkeypatch.setattr(hit_names, "_mirror", lambda: None)
    assert hit_names.hit_display_name({"ident_type": "PUBCHEM_CID", "identifier": "2332"}) is None


@pytest.mark.parametrize("raw, shown", [
    ("oxidane", "Oxidane"),
    ("benzenecarboximidamide", "Benzenecarboximidamide"),
    ("[(2R)-3-hexadecanoyloxy-2-[(Z)-octadec-9-enoyl]oxypropyl] 2-(trimethylazaniumyl)ethyl phosphate",
     "[(2R)-3-Hexadecanoyloxy-2-[(Z)-octadec-9-enoyl]oxypropyl] 2-(trimethylazaniumyl)ethyl phosphate"),
    ("n-butane", "n-Butane"),
    ("(2S)-2-aminopropanoic acid", "(2S)-2-Aminopropanoic acid"),
    ("Serine protease 1", "Serine protease 1"),
    ("TRYPSIN WITH INHIBITOR AERUGINOSIN 98-B", "TRYPSIN WITH INHIBITOR AERUGINOSIN 98-B"),
    ("Calcium", "Calcium"),
    ("2", "2"),
])
def test_names_are_capitalized(raw, shown):
    assert hit_names.capitalize_name(raw) == shown


def test_display_name_applies_capitalization():
    assert hit_names.hit_display_name({"ident_type": "PUBCHEM_CID", "identifier": "2332"}) \
        == "Benzenecarboximidamide"
    assert hit_names.hit_display_name({"ident_type": "PDB_ID", "identifier": "1X",
                                       "name": "beta-lactamase"}) == "Beta-lactamase"


def test_water_shows_its_common_name():
    """UI pass 2026-11-07: water verified as PubChem CID 962 showed as
    "Oxidane" (the stored IUPAC name); the common name wins."""
    from src_new.api.hit_names import hit_display_name
    assert hit_display_name({"ident_type": "PUBCHEM_CID", "identifier": "962", "name": "oxidane"}) == "Water"
    assert hit_display_name({"ident_type": "INCHIKEY", "identifier": "XLYOFNOQVPJJNP-UHFFFAOYSA-N"}) == "Water"
    assert hit_display_name({"ident_type": "PUBCHEM_CID", "identifier": "2244", "name": "aspirin"}) == "Aspirin"


def test_pubchem_title_beats_iupac_and_misses_fall_back(monkeypatch):
    """A PubChem title (common name) wins for chemical hits; with no title
    the previous name (stored or IUPAC) is kept."""
    import src_new.api.hit_names as hn
    hn._pubchem_title.cache_clear()
    monkeypatch.setattr(hn, "_pubchem_title", lambda t, i: "Adenosine-5'-triphosphate" if i == "5957" else None)
    assert hn.hit_display_name({"ident_type": "PUBCHEM_CID", "identifier": "5957",
                                "name": "[[(2r,3s,4r,5r)-5-(6-aminopurin-9-yl)..."}) == "Adenosine-5'-triphosphate"
    assert hn.hit_display_name({"ident_type": "PUBCHEM_CID", "identifier": "999999999",
                                "name": "benzenecarboximidamide"}) == "Benzenecarboximidamide"
    assert hn.hit_display_name({"ident_type": "PDB_ID", "identifier": "1AQ7", "name": "Trypsin"}) == "Trypsin"
