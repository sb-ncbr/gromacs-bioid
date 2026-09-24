"""Tests for the local PubChem mirror DB builder and reader.

Uses tiny synthetic gz fixtures shaped like the real Compound/Extras files
(verified layouts 2026-09-24): ``CID-SMILES``: ``CID\tSMILES``;
``CID-InChI-Key``: ``CID\tInChI\tInChIKey``. No network, no large downloads.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from src_new.molecules.pubchem_db import PubChemDB, build, normalize_formula

# cid, smiles, inchikey (keys shaped like real ones; only regex-relevant)
_ROWS = [
    (1, "C", None),  # methane: absent from inchikey file (gap coverage)
    (2, "CCO", "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"),
    (3, "CC(=O)OC1=CC=CC=C1C(=O)O", "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"),  # aspirin
    (4, "this-is-not-smiles!!", "AAAAAAAAAAAAAA-BBBBBBBBBB-N"),   # RDKit rejects
    (5, "OCC", "BBBBBBBBBBBBBB-CCCCCCCCCC-O"),                      # ethanol, other string
    (6  , "[Na+].[Cl-]", "CCCCCCCCCCCCCC-DDDDDDDDDD-N"),           # salt
    (7, "C1=CC=C(C=C1)C(=O)O", "DDDDDDDDDDDDDD-EEEEEEEEEE-N"),     # benzoic acid
    (8, "[13CH3]CO", "EEEEEEEEEEEEEE-FFFFFFFFFF-N"),              # 13C-labeled ethanol
    (9, "CC(=O)[O-]", "FFFFFFFFFFFFFF-GGGGGGGGGG-N"),             # acetate (charged)
]

_IK_FAKE_INCHI = "InChI=1S/fake"


def _write_gz(path: Path, lines: list[str]) -> None:
    with gzip.open(path, "wt") as fh:
        fh.write("\n".join(lines) + "\n")


@pytest.fixture()
def sample_db(tmp_path: Path) -> Path:
    smiles_gz = tmp_path / "CID-SMILES.gz"
    ik_gz = tmp_path / "CID-InChI-Key.gz"
    _write_gz(smiles_gz, [f"{cid}\t{smi}" for cid, smi, _ in _ROWS])
    # cid=1 intentionally missing; an extra cid=99 row must be ignored
    _write_gz(
        ik_gz,
        [f"{cid}\t{_IK_FAKE_INCHI}\t{ik}" for cid, _, ik in _ROWS if ik]
        + [f"99\t{_IK_FAKE_INCHI}\tZZZZZZZZZZZZZZ-ZZZZZZZZZZ-N"],
    )
    db_path = tmp_path / "pubchem.sqlite"
    stats = build(db_path, smiles_gz, ik_gz, workers=1)
    assert stats["rows_written"] == len(_ROWS)
    assert stats["smiles_parse_failures"] == 1  # cid=4
    return db_path


class TestNormalizeFormula:
    @pytest.mark.parametrize(
        "given, expected",
        [
            ("C2H6O", "C2H6O"),
            ("H6O2C2", "C2H6O2"),
            ("H2O", "H2O"),
            ("O2H2", "H2O2"),
            ("P3O13N5H16C10", "C10H16N5O13P3"),  # ATP
            ("NaCl", "ClNa"),
        ],
    )
    def test_hill_order(self, given: str, expected: str) -> None:
        assert normalize_formula(given) == expected

    @pytest.mark.parametrize("bad", ["", "C2H6O$", "123", "C2H6O1.5"])
    def test_rejects_garbage(self, bad: str) -> None:
        with pytest.raises(ValueError):
            normalize_formula(bad)


class TestReadApi:
    def test_by_cid(self, sample_db: Path) -> None:
        db = PubChemDB(sample_db)
        row = db.by_cid(3)
        assert row is not None
        assert row.smiles == "CC(=O)OC1=CC=CC=C1C(=O)O"
        assert row.inchikey == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
        assert row.formula_hill == "C9H8O4"
        assert row.exact_mass == pytest.approx(180.042, abs=1e-3)
        iso = db.by_cid(8)
        assert iso is not None and iso.formula_hill == "C2H6O" and iso.smiles == "[13CH3]CO"
        assert db.by_cid(424242) is None

    def test_charged_species_answers_plain_formula(self, sample_db: Path) -> None:
        # PUG is charge-insensitive (verified: dianion C20H24O2-2 answers C20H24O2)
        db = PubChemDB(sample_db)
        assert db.by_cid(9).formula_hill == "C2H3O2"
        assert db.by_formula("C2H3O2") == [9]

    def test_by_cid_missing_inchikey(self, sample_db: Path) -> None:
        db = PubChemDB(sample_db)
        row = db.by_cid(1)
        assert row is not None
        assert row.inchikey is None

    def test_by_inchikey(self, sample_db: Path) -> None:
        db = PubChemDB(sample_db)
        row = db.by_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
        assert row is not None and row.cid == 3
        assert db.by_inchikey("ZZZZZZZZZZZZZZ-ZZZZZZZZZZ-N") is None

    def test_by_formula(self, sample_db: Path) -> None:
        db = PubChemDB(sample_db)
        assert db.by_formula("C9H8O4") == [3]
        assert db.by_formula("O4H8C9") == [3]  # loose order normalized
        # salt: RDKit sums components, matching PubChem's own formula handling
        assert db.by_formula("ClNa") == [6]
        assert db.by_formula("C100H100") == []

    def test_by_formula_limit_and_order(self, sample_db: Path) -> None:
        db = PubChemDB(sample_db)
        # cid 2 ('CCO') and cid 5 ('OCC') are the same molecule -> same formula;
        # cid 8 is isotope-labeled ethanol - PUG semantics are
        # isotope-insensitive, so it answers under the plain formula too
        assert db.by_formula("C2H6O", limit=10) == [2, 5, 8]
        assert db.by_formula("C2H6O", limit=1) == [2]

    def test_unparseable_smiles_kept_for_cid_lookup(self, sample_db: Path) -> None:
        db = PubChemDB(sample_db)
        row = db.by_cid(4)
        assert row is not None
        assert row.formula_hill == ""  # parse failure keeps CID/SMILES answerable

    def test_count(self, sample_db: Path) -> None:
        assert PubChemDB(sample_db).count() == len(_ROWS)

    def test_by_formula_bad_input_raises(self, sample_db: Path) -> None:
        with pytest.raises(ValueError):
            PubChemDB(sample_db).by_formula("not a formula!")


class TestBuildResume:
    def test_resume_is_idempotent(self, tmp_path: Path) -> None:
        smiles_gz = tmp_path / "CID-SMILES.gz"
        ik_gz = tmp_path / "CID-InChI-Key.gz"
        _write_gz(smiles_gz, [f"{cid}\t{smi}" for cid, smi, _ in _ROWS])
        _write_gz(
            ik_gz,
            [f"{cid}\t{_IK_FAKE_INCHI}\t{ik}" for cid, _, ik in _ROWS if ik],
        )
        db_path = tmp_path / "pubchem.sqlite"
        build(db_path, smiles_gz, ik_gz, limit=2, workers=1)
        assert PubChemDB(db_path).count() == 2
        stats = build(db_path, smiles_gz, ik_gz, resume=True, workers=1)
        assert stats["rows_written"] == len(_ROWS) - 2 or PubChemDB(db_path).count() == len(_ROWS)
