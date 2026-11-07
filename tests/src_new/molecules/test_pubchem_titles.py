"""PubChem titles beside the mirror (UI pass 2026-11-07): common names
instead of IUPAC names; optional file, every miss is None."""

import gzip

from src_new.molecules.pubchem_titles import PubChemTitles, build, is_useful_title


def _gz(tmp_path, lines):
    p = tmp_path / "CID-Title.gz"
    with gzip.open(p, "wt") as fh:
        fh.write("\n".join(lines) + "\n")
    return str(p)


def test_build_and_lookup(tmp_path):
    src = _gz(tmp_path, ["5957\tAdenosine-5'-triphosphate", "5997\tCholesterol",
                         "12345678\tSCHEMBL1234567", "broken line", "962\tWater"])
    out = str(tmp_path / "titles.sqlite")
    meta = build(src, out)
    assert meta["rows"] == 4 and meta["skipped_lines"] == 1
    t = PubChemTitles(out)
    assert t.title(5957) == "Adenosine-5'-triphosphate"
    assert t.title("5997") == "Cholesterol"
    assert t.title(12345678) is None   # registry code, not a name
    assert t.title(1) is None          # CID without a title
    assert not (tmp_path / "titles.sqlite.tmp").exists()


def test_missing_file_is_silent(tmp_path):
    t = PubChemTitles(str(tmp_path / "absent.sqlite"))
    assert t.title(5957) is None


def test_useful_title_filter():
    assert is_useful_title("Benzamidine")
    assert is_useful_title("1-Palmitoyl-2-oleoyl-sn-glycero-3-phosphocholine")
    for code in ("SCHEMBL1234567", "AKOS015912345", "CHEMBL25", "ZINC000001234567", "MFCD00012345", "NSC 12345"):
        assert not is_useful_title(code), code
    assert not is_useful_title("") and not is_useful_title(None)
