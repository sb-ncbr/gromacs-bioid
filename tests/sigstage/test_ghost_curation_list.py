"""Offline tests for scripts/stats/ghost_curation_list.py (A3)."""
import importlib.util
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "ghost_curation_list", os.path.join(REPO, "scripts", "stats", "ghost_curation_list.py"))
gc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gc)

IK_OK = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"          # aspirin shape, 27 chars
IK_BAD_SHORT = "TOOSHORT"
IK_BAD_DASH = "BSYNRYMUTXBXSQXUHFFFAOYSAXN"    # no dashes
IK_LOWERCASE = "bsynrymutxbxsq-uhfffaoysa-n"


def test_classify_side_cid_zero_and_invalid():
    assert gc.classify_side("cid", "0") == ("cid_zero", "cid:0")
    assert gc.classify_side("cid", "-3") == ("cid_zero", "cid:-3")
    assert gc.classify_side("cid", "abc") == ("cid_zero", "cid:abc")


def test_classify_side_valid_cid_is_legacy_candidate():
    assert gc.classify_side("cid", "2244") == ("unresolved_legacy", "cid:2244")


def test_classify_side_inchikey_shape():
    assert gc.classify_side("inchikey", IK_OK) == ("unresolved_legacy", f"inchikey:{IK_OK}")
    assert gc.classify_side("inchikey", IK_BAD_SHORT)[0] == "inchikey_malformed"
    assert gc.classify_side("inchikey", IK_BAD_DASH)[0] == "inchikey_malformed"
    # lowercase is normalized before classification
    assert gc.classify_side("inchikey", IK_LOWERCASE)[0] == "unresolved_legacy"


def test_classify_side_unknown_kind():
    assert gc.classify_side("seq-acc", "P12345")[0] == "unknown_kind"


def test_split_key():
    assert gc.split_key("skel-cid:1|skel-inchikey:ABC") == [("cid", "1"), ("inchikey", "ABC")]
    assert gc.split_key("garbage") == []
    assert gc.split_key("fp-cid:1|skel-cid:2") == []   # legacy kinds rejected


def test_classify_keys_aggregates_deterministically():
    keys = [
        f"skel-cid:0|skel-inchikey:{IK_OK}",      # cid_zero + legacy ik
        f"skel-cid:0|skel-inchikey:{IK_OK}",      # same pair again (dup)
        f"skel-cid:2244|skel-inchikey:{IK_OK}",   # both legacy
        "skel-cid:0|skel-cid:0",                  # both cid_zero
        "not-a-key",
    ]
    rep = gc.classify_keys(keys)
    cl = rep["classes"]
    assert cl["cid_zero"]["identifiers"] == [("cid:0", 4)]   # 4 side occurrences
    assert cl["cid_zero"]["pairs"] == 3                       # ...over 3 pairs
    assert cl["unresolved_legacy"]["identifiers"] == [
        ("cid:2244", 1), (f"inchikey:{IK_OK}", 3)]
    assert cl["unresolved_legacy"]["pairs"] == 3
    assert rep["bad_keys"] == ["not-a-key"]
    # determinism: same call twice -> byte-identical json
    a = json.dumps(gc.classify_keys(keys), sort_keys=True)
    b = json.dumps(gc.classify_keys(keys), sort_keys=True)
    assert a == b


def test_main_writes_json_and_md(tmp_path, capsys):
    ghosts = tmp_path / "warmup_ghosts.json"
    ghosts.write_text(json.dumps({
        "dropped_input": 2,
        "ghosts": [f"skel-cid:0|skel-inchikey:{IK_OK}",
                   "skel-cid:2244|skel-inchikey:ABC-DEF-N"],
        "unparseable": ["skel-cid:142865856|skel-inchikey:XYZXYZXYZXYZXY-ABCDEFGHIJ-N"],
        "bad_keys": []}))
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    gc.main(["--ghosts", str(ghosts), "--out-json", str(out_json),
             "--out-md", str(out_md)])
    rep = json.load(open(out_json))["report"]
    assert rep["classes"]["cid_zero"]["distinct_identifiers"] == 1
    assert rep["classes"]["smiles_unparseable"]["pairs"] == 1
    md = out_md.read_text()
    assert "## cid_zero" in md and "## unresolved_legacy" in md
    assert "guidance" in md and "`cid:0`" in md
