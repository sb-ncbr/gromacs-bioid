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


class TestThreadSafety:
    def test_shared_instance_across_threads(self, sample_db: Path) -> None:
        import threading

        db = PubChemDB(sample_db)
        errors, results = [], []

        def worker(cid, expect):
            try:
                for _ in range(50):
                    results.append(db.by_cid(cid).smiles == expect)
                    results.append(db.by_formula("C2H6O", limit=10) != [])
            except Exception as exc:  # noqa: BLE001 - record, assert after join
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(2, "CCO")),
                   threading.Thread(target=worker, args=(3, "CC(=O)OC1=CC=CC=C1C(=O)O")),
                   threading.Thread(target=worker, args=(5, "OCC")),
                   threading.Thread(target=worker, args=(7, "C1=CC=C(C=C1)C(=O)O"))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert results and all(results)


class TestAnnotationPrefill:
    """Item-4 correction (user ruling 11-03): the mirror gains iupac_name
    (CID-IUPAC.gz) and a has_synonyms flag (CID-Synonym-filtered.gz) — the
    pre-fill that removes the NCBI-throttle exposure for mirror-hit
    annotation rows (the only signals live fetch existed for)."""

    @pytest.fixture()
    def ann_db(self, tmp_path: Path) -> Path:
        smiles_gz = tmp_path / "CID-SMILES.gz"
        ik_gz = tmp_path / "CID-InChI-Key.gz"
        iup_gz = tmp_path / "CID-IUPAC.gz"
        syn_gz = tmp_path / "CID-Synonym-filtered.gz"
        _write_gz(smiles_gz, [f"{cid}\t{smi}" for cid, smi, _ in _ROWS])
        _write_gz(
            ik_gz,
            [f"{cid}\t{_IK_FAKE_INCHI}\t{ik}" for cid, _, ik in _ROWS if ik],
        )
        # IUPAC names for cids 2 and 3 only (gap coverage for the rest)
        _write_gz(iup_gz, ["2\tethanol", "3\tacetylsalicylic acid"])
        # synonyms: MULTIPLE rows per cid (2 has two); extra cid=99 ignored
        _write_gz(syn_gz, [
            "2\tdrinking alcohol", "2\talcohol", "3\taspirin",
            "5\thydroxyethane", "99\tignored",
        ])
        db_path = tmp_path / "pubchem.sqlite"
        stats = build(db_path, smiles_gz, ik_gz, iupac_gz=iup_gz,
                      synonyms_gz=syn_gz, workers=1)
        assert stats["rows_written"] == len(_ROWS)
        assert stats["iupac_matched"] == 2
        assert stats["synonyms_flagged"] == 3
        return db_path

    def test_rows_carry_annotation_columns(self, ann_db: Path) -> None:
        db = PubChemDB(ann_db)
        r2 = db.by_cid(2)
        assert r2.iupac_name == "ethanol"
        assert r2.has_synonyms is True
        r3 = db.by_cid(3)
        assert r3.iupac_name == "acetylsalicylic acid"
        assert r3.has_synonyms is True
        r5 = db.by_cid(5)
        assert r5.iupac_name is None      # no IUPAC row in the file
        assert r5.has_synonyms is True    # but synonyms flag set
        r1 = db.by_cid(1)
        assert r1.iupac_name is None
        assert r1.has_synonyms is False

    def test_by_inchikey_carries_annotations(self, ann_db: Path) -> None:
        db = PubChemDB(ann_db)
        row = db.by_inchikey("LFQSCWFLJHTTHZ-UHFFFAOYSA-N")
        assert row is not None
        assert row.iupac_name == "ethanol"
        assert row.has_synonyms is True

    def test_by_cids_carries_annotations(self, ann_db: Path) -> None:
        db = PubChemDB(ann_db)
        rows = db.by_cids(["2", "3", "999999"])
        assert set(rows) == {"2", "3"}
        assert rows["2"].iupac_name == "ethanol"

    def test_build_without_annotation_files_is_legacy(
            self, sample_db: Path) -> None:
        """A build with no CID-IUPAC/CID-Synonym paths yields NULL/False
        annotation fields (schema present, values absent)."""
        db = PubChemDB(sample_db)
        row = db.by_cid(2)
        assert row.smiles == "CCO"
        assert row.iupac_name is None
        assert row.has_synonyms is False

    def test_true_legacy_schema_degrades(self, tmp_path: Path) -> None:
        """A mirror file built before the extension (5-column schema, no
        annotation columns) still reads: NULL/0 via the PRAGMA fallback."""
        import sqlite3

        p = tmp_path / "pubchem.sqlite"
        conn = sqlite3.connect(p)
        conn.executescript("""
            CREATE TABLE compounds (
                cid          INTEGER PRIMARY KEY,
                smiles       TEXT NOT NULL,
                inchikey     TEXT,
                formula_hill TEXT NOT NULL,
                exact_mass   REAL
            );
        """)
        conn.execute(
            "INSERT INTO compounds VALUES (2,'CCO',"
            "'LFQSCWFLJHTTHZ-UHFFFAOYSA-N','C2H6O',46.07)")
        conn.commit()
        conn.close()
        db = PubChemDB(p)
        row = db.by_cid(2)
        assert row is not None
        assert row.smiles == "CCO"
        assert row.iupac_name is None
        assert row.has_synonyms is False
        by_ik = db.by_inchikey("LFQSCWFLJHTTHZ-UHFFFAOYSA-N")
        assert by_ik is not None and by_ik.cid == 2
        assert by_ik.has_synonyms is False

    def test_scorer_full_schema_without_live_calls(
            self, ann_db: Path, monkeypatch) -> None:
        """The item-4 pre-fill contract: a mirror-hit row with iupac_name +
        has_synonyms scores the FULL schema (100) with ZERO live calls —
        zero budget armed, so any live call would return None."""
        from src_new.verification.scorers import pubchem_scorer as mod
        from src_new.verification.scorers.pubchem_scorer import (
            PubChemAnnotationScorer,
        )

        db = PubChemDB(ann_db)
        monkeypatch.setattr(mod, "_local_db", lambda: db)
        scorer = PubChemAnnotationScorer()
        scorer.begin_segment(0)  # zero budget: live calls impossible
        quality = scorer.score("2", "PUBCHEM_CID")
        assert quality is not None
        assert quality.score == 100.0
        assert set(quality.signals) == {
            "canonical_smiles", "isomeric_smiles", "molecular_formula",
            "iupac_name", "synonyms"}

    def test_extended_mirror_absence_is_authoritative(
            self, ann_db: Path, monkeypatch) -> None:
        """M7 (user ruling 11-04: mirror first, live only on failure): a
        mirror hit the extended mirror records WITHOUT IUPAC/synonyms scores
        from the mirror — no live fill (zero budget would make it None)."""
        from src_new.verification.scorers import pubchem_scorer as mod
        from src_new.verification.scorers.pubchem_scorer import (
            PubChemAnnotationScorer,
        )

        db = PubChemDB(ann_db)
        assert db.has_annotation_columns()
        monkeypatch.setattr(mod, "_local_db", lambda: db)
        scorer = PubChemAnnotationScorer()
        scorer.begin_segment(0)  # live fetch on, zero budget
        quality = scorer.score("7", "PUBCHEM_CID")  # benzoic acid: no IUPAC, no synonyms
        assert quality is not None
        assert set(quality.signals) == {
            "canonical_smiles", "isomeric_smiles", "molecular_formula"}

    def test_legacy_mirror_still_live_fills(self, tmp_path: Path, monkeypatch) -> None:
        import sqlite3
        from src_new.verification.scorers import pubchem_scorer as mod
        from src_new.verification.scorers.pubchem_scorer import (
            PubChemAnnotationScorer,
        )

        p = tmp_path / "pubchem.sqlite"
        conn = sqlite3.connect(p)
        conn.execute("CREATE TABLE compounds (cid INTEGER PRIMARY KEY, smiles TEXT NOT NULL, "
                     "inchikey TEXT, formula_hill TEXT NOT NULL, exact_mass REAL)")
        conn.execute("INSERT INTO compounds VALUES (7,'C1=CC=C(C=C1)C(=O)O',NULL,'C7H6O2',122.04)")
        conn.commit()
        conn.close()
        db = PubChemDB(p)
        assert not db.has_annotation_columns()
        monkeypatch.setattr(mod, "_local_db", lambda: db)
        scorer = PubChemAnnotationScorer()
        scorer.begin_segment(0)  # live fill needed, budget 0 -> unprovable
        assert scorer.score("7", "PUBCHEM_CID") is None


def _derive_hanging_on_sentinel(batch):
    """M3: stand-in for an RDKit spin on one pathological SMILES."""
    import time as _time
    from src_new.molecules import pubchem_db as _pdb
    if any(smi == "HANG" for _cid, smi in batch):
        _time.sleep(3600)
    return _pdb._REAL_DERIVE(batch)


class TestHungBatchIsolation:
    """M3 (b16 mirror build 2026-11-04): a worker spun in RDKit for 2 h on one
    SMILES while the parent blocked in AsyncResult.get() with no timeout."""

    def test_hanging_compound_is_isolated_and_build_completes(
            self, tmp_path: Path, monkeypatch) -> None:
        from src_new.molecules import pubchem_db as pdb
        monkeypatch.setattr(pdb, "_REAL_DERIVE", pdb._derive_chemistry, raising=False)
        monkeypatch.setattr(pdb, "_derive_chemistry", _derive_hanging_on_sentinel)
        monkeypatch.setattr(pdb, "_BATCH_TIMEOUT_S", 3.0)
        monkeypatch.setattr(pdb, "_ISOLATE_TIMEOUT_S", 2.0)
        monkeypatch.setattr(pdb, "_BATCH_ROWS", 4)
        rows = [(1, "CCO"), (2, "CC(=O)O"), (3, "HANG"), (4, "c1ccccc1"),
                (5, "CCN"), (6, "CCC"), (7, "O"), (8, "CO")]
        smiles_gz = tmp_path / "CID-SMILES.gz"
        ik_gz = tmp_path / "CID-InChI-Key.gz"
        _write_gz(smiles_gz, [f"{cid}\t{smi}" for cid, smi in rows])
        _write_gz(ik_gz, [])
        db_path = tmp_path / "pubchem.sqlite"
        stats = build(db_path, smiles_gz, ik_gz, workers=2)
        assert stats["rows_written"] == len(rows)
        db = PubChemDB(db_path)
        hung = db.by_cid(3)
        assert hung is not None and hung.smiles == "HANG" and not hung.formula_hill
        assert db.by_cid(1).formula_hill == "C2H6O"
        assert db.by_cid(8).formula_hill == "CH4O"


def _derive_slow_batches_hang_sentinel(batch):
    """M5: full batches are slow (1.5 s), probes of <=2 rows are instant
    unless they contain the hanging sentinel."""
    import time as _time
    from src_new.molecules import pubchem_db as _pdb
    if any(smi == "HANG" for _cid, smi in batch):
        _time.sleep(3600)
    if len(batch) >= 4:
        _time.sleep(1.5)
    return _pdb._REAL_DERIVE(batch)


class TestIsolationNotStarvedByResubmittedBatches:
    """M5 (b19 build 2026-11-04): isolation probes queued behind the
    resubmitted in-flight batches, timed out before starting, and ordinary
    compounds (consecutive CIDs from 157783726) were stored unparsed."""

    def test_only_the_hanging_compound_is_unparsed(self, tmp_path: Path, monkeypatch) -> None:
        from src_new.molecules import pubchem_db as pdb
        monkeypatch.setattr(pdb, "_REAL_DERIVE", pdb._derive_chemistry, raising=False)
        monkeypatch.setattr(pdb, "_derive_chemistry", _derive_slow_batches_hang_sentinel)
        monkeypatch.setattr(pdb, "_BATCH_TIMEOUT_S", 3.0)
        monkeypatch.setattr(pdb, "_ISOLATE_TIMEOUT_S", 1.0)
        monkeypatch.setattr(pdb, "_BATCH_ROWS", 4)
        rows = [(1, "CCO"), (2, "HANG"), (3, "CCN"), (4, "CCC"),
                (5, "CO"), (6, "CC(=O)O"), (7, "O"), (8, "N"),
                (9, "CCCC"), (10, "c1ccccc1"), (11, "CCCl"), (12, "CCBr")]
        smiles_gz = tmp_path / "CID-SMILES.gz"
        ik_gz = tmp_path / "CID-InChI-Key.gz"
        _write_gz(smiles_gz, [f"{cid}\t{smi}" for cid, smi in rows])
        _write_gz(ik_gz, [])
        db_path = tmp_path / "pubchem.sqlite"
        build(db_path, smiles_gz, ik_gz, workers=2)
        db = PubChemDB(db_path)
        unparsed = [cid for cid, _ in rows if not db.by_cid(cid).formula_hill]
        assert unparsed == [2]


def _derive_blowing_up_on_sentinel(batch):
    """M8: stand-in for an RDKit runaway allocation on one SMILES. Refuses to
    run uncapped so a missing cap fails the build instead of eating RAM."""
    import resource
    from src_new.molecules import pubchem_db as _pdb
    soft, _hard = resource.getrlimit(resource.RLIMIT_AS)
    if soft == resource.RLIM_INFINITY:
        raise RuntimeError("derivation worker runs without a memory cap")
    if any(smi == "BLOWUP" for _cid, smi in batch):
        bytearray(soft)  # one request the size of the whole cap
    return _pdb._REAL_DERIVE(batch)


class TestRunawayAllocationIsCapped:
    """M8 (b20 build 2026-11-04): one compound past CID ~164.67M made a
    worker allocate without bound; the container was OOMKilled at 32Gi and
    64Gi on every resume."""

    def test_only_the_runaway_compound_is_unparsed(self, tmp_path: Path, monkeypatch) -> None:
        import resource
        from src_new.molecules import pubchem_db as pdb
        with open("/proc/self/statm") as fh:
            vsz = int(fh.read().split()[0]) * resource.getpagesize()
        monkeypatch.setattr(pdb, "_WORKER_MEM_BYTES", vsz + 512 * 2**20)
        monkeypatch.setattr(pdb, "_REAL_DERIVE", pdb._derive_chemistry, raising=False)
        monkeypatch.setattr(pdb, "_derive_chemistry", _derive_blowing_up_on_sentinel)
        monkeypatch.setattr(pdb, "_BATCH_TIMEOUT_S", 30.0)
        monkeypatch.setattr(pdb, "_ISOLATE_TIMEOUT_S", 30.0)
        monkeypatch.setattr(pdb, "_BATCH_ROWS", 4)
        rows = [(1, "CCO"), (2, "CCN"), (3, "BLOWUP"), (4, "CCC"),
                (5, "CO"), (6, "CC(=O)O"), (7, "O"), (8, "N")]
        smiles_gz = tmp_path / "CID-SMILES.gz"
        ik_gz = tmp_path / "CID-InChI-Key.gz"
        _write_gz(smiles_gz, [f"{cid}\t{smi}" for cid, smi in rows])
        _write_gz(ik_gz, [])
        db_path = tmp_path / "pubchem.sqlite"
        stats = build(db_path, smiles_gz, ik_gz, workers=2)
        assert stats["rows_written"] == len(rows)
        db = PubChemDB(db_path)
        unparsed = [cid for cid, _ in rows if not db.by_cid(cid).formula_hill]
        assert unparsed == [3]

    def test_memory_error_inside_rdkit_stores_the_compound_unparsed(self, monkeypatch) -> None:
        from src_new.molecules import pubchem_db as pdb
        real = pdb._derive_one

        def one(Chem, desc, cid, smiles):
            if smiles == "BLOWUP":
                raise MemoryError
            return real(Chem, desc, cid, smiles)

        monkeypatch.setattr(pdb, "_derive_one", one)
        out = pdb._derive_chemistry([(1, "CCO"), (2, "BLOWUP")])
        assert out[0][2] == "C2H6O" and out[1] == (2, "BLOWUP", "", None, False)
