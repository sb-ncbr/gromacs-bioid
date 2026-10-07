"""Offline unit tests for scripts/stats/sigstage_probe.py (S0 signature-stage probe).

No network, no Postgres, no NFS: all external resolution is injected via
FakeResolver. Empirical-evidence tests use real rdkit (skelfp) and real
Biopython (alignment) so the chemistry/sequence currency claims are
validated, not assumed. Drift-guard tests compare the probe's replicated
primitives against the live SimEngine implementations.
"""
import importlib.util
import json
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(REPO, "tests", "sigstage", "fixtures", "sigstage")


def _load_probe():
    spec = importlib.util.spec_from_file_location(
        "sigstage_probe", os.path.join(REPO, "scripts", "stats", "sigstage_probe.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sp = _load_probe()

CAFFEINE = "Cn1cnc2c1c(=O)n(C)c(=O)n2C"
BENZENE = "c1ccccc1"
ACETIC = "CC(=O)O"
ACETATE = "CC(=O)[O-]"
SEQ40 = "ACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWY"
NUC20 = "ACGUACGUACGUACGUACGU"


class FakeResolver:
    def __init__(self, smiles_map=None, class_map=None, element_map=None,
                 seq_map=None, pdb_map=None):
        self.smiles_map = smiles_map or {}
        self.class_map = class_map or {}
        self.element_map = element_map or {}
        self.seq_map = seq_map or {}
        self.pdb_map = pdb_map or {}
        self.network_uses = 0

    def smiles_for_inchikey(self, ik):
        return self.smiles_map.get(ik.upper(), (None, "fail"))

    def gt_class(self, ik):
        return self.class_map.get(ik.upper(), "organic")

    def ion_element(self, ik):
        return self.element_map.get(ik.upper())

    def uniprot_seq(self, acc):
        return self.seq_map[acc]

    def pdb_entity_seqs(self, pdb):
        return self.pdb_map[pdb]

    def align_identity(self, a, b):
        return sp.align_identity_local(a, b)


def load_fix(name):
    with open(os.path.join(FIX, name)) as fh:
        return json.load(fh)


# ------------------------------------------------------------ primitives

def test_clean_fasta():
    assert sp.clean_fasta(">h\nAC DE\nFG\n") == "ACDEFG"
    assert sp.clean_fasta("ACD") == "ACD"
    assert sp.clean_fasta(None) == ""


def test_extract_sig_pool_dedupe():
    pool, stats = sp.extract_sig_pool(load_fix("entry_organic.json"))
    assert stats == {"n_segments": 3, "n_unique_sigs": 2}
    segs = [s for s, _ in pool["smiles"]]
    assert segs == ["SEG_A", "SEG_B"]          # __v1 duplicate dropped
    assert dict(pool["smiles"])["SEG_A"] == CAFFEINE


def test_skelfp_identical():
    pytest.importorskip("rdkit")
    assert sp.skelfp_tanimoto(CAFFEINE, CAFFEINE) == pytest.approx(1.0)


def test_skelfp_protonation_insensitive():
    """Empirical core of the S0 claim: protonation state MUST NOT change the
    skeleton currency (charge/H-scrubbed FP). Acetic acid vs acetate -> 1.0."""
    pytest.importorskip("rdkit")
    assert sp.skelfp_tanimoto(ACETIC, ACETATE) == pytest.approx(1.0)


def test_skelfp_unrelated_low():
    pytest.importorskip("rdkit")
    assert sp.skelfp_tanimoto(CAFFEINE, BENZENE) < 0.3


def test_skelfp_invalid_smiles_returns_none():
    pytest.importorskip("rdkit")
    assert sp.skelfp_tanimoto("NOT_A_SMILES", CAFFEINE) is None
    assert sp.skelfp_tanimoto(None, CAFFEINE) is None


# ------------------------------------------------------------ entry scoring

def test_score_organic_entry():
    doc = load_fix("entry_organic.json")
    res = FakeResolver(smiles_map={"IKCAFF": (CAFFEINE, "mirror")})
    rows = sp.score_entry_doc(900001, doc, {"inchikey": {"IKCAFF"}}, res)
    assert len(rows) == 1
    r = rows[0]
    assert r["validated"] is True and r["bucket"] == "validated"
    assert r["sim"] == pytest.approx(1.0)
    assert r["best_segment"] == "SEG_A" and r["best_generator"] == "smiles"
    assert r["smiles_source"] == "mirror"
    assert r["attempted"] is True and r["threshold"] == sp.CHEM_VALIDATED
    assert (r["n_segments"], r["n_unique_sigs"]) == (3, 2)
    assert r["details"]["n_candidates"] == 2


def test_score_organic_protonated_gt_validates():
    """Headline S0 evidence: GT=acetate, segment=acetic acid -> validated.

    The protonation-variant sensitivity that hit verification-stage exact
    InChIKey matching cannot occur at signature stage: there is no second
    candidate to rerank, and the skeleton currency is charge/H-insensitive.
    """
    pytest.importorskip("rdkit")
    doc = {"data": {"signatures": {"LIG": {"generated": {"smiles": ACETIC}}}}}
    res = FakeResolver(smiles_map={"IKACET": (ACETATE, "mirror")})
    rows = sp.score_entry_doc(900010, doc, {"inchikey": {"IKACET"}}, res)
    assert rows[0]["sim"] == pytest.approx(1.0)
    assert rows[0]["validated"] is True


def test_score_ion_elements_channel():
    doc = load_fix("entry_ion_elements.json")
    res = FakeResolver(class_map={"IKCA": "ion", "IKZN": "ion"},
                       element_map={"IKCA": "Ca", "IKZN": "Zn"})
    rows = sp.score_entry_doc(900002, doc, {"inchikey": {"IKCA", "IKZN"}}, res)
    by_gt = {r["gt_value"]: r for r in rows}
    ca, zn = by_gt["IKCA"], by_gt["IKZN"]
    assert ca["validated"] is True and ca["sim"] == 1.0
    assert ca["best_generator"] == "ion_elements" and ca["details"]["element"] == "Ca"
    assert zn["validated"] is False and zn["bucket"] == "below_gate" and zn["sim"] == 0.0
    assert all(r["attempted"] for r in rows)


def test_score_ion_metals_pass_channel():
    doc = load_fix("entry_ion_metals.json")
    res = FakeResolver(class_map={"IKZN": "ion"}, element_map={"IKZN": "Zn"})
    rows = sp.score_entry_doc(900003, doc, {"inchikey": {"IKZN"}}, res)
    assert rows[0]["validated"] is True and rows[0]["details"]["element"] == "Zn"


def test_score_protein_entry_and_length_guard():
    doc = load_fix("entry_protein.json")
    res = FakeResolver(seq_map={"P99999": SEQ40}, pdb_map={"1ABC": [NUC20]})
    rows = sp.score_entry_doc(900004, doc,
                              {"uniprot": {"P99999"}, "pdb": {"1abc"}}, res)
    by_type = {r["gt_type"]: r for r in rows}
    uni = by_type["uniprot"]
    assert uni["sim"] == pytest.approx(1.0) and uni["validated"] is True
    assert uni["best_segment"] == "SEG_P" and uni["best_generator"] == "fasta_map_protein"
    assert uni["details"]["pairs"] == 2                 # SEG_P + SEG_Q
    assert uni["details"]["guard_skipped"] == 1         # 3-mer SEG_R guarded (40/3 > 10)
    pdb = by_type["pdb"]
    assert pdb["gt_value"] == "1ABC"                    # case-normalized
    assert pdb["validated"] is True and pdb["best_generator"] == "fasta_map_nucleic"
    assert pdb["details"]["pairs"] == 4


def test_no_sig_data_bucket():
    doc = load_fix("entry_nosig.json")
    res = FakeResolver(smiles_map={"IKCAFF": (CAFFEINE, "mirror")})
    rows = sp.score_entry_doc(900005, doc, {"inchikey": {"IKCAFF"}}, res)
    assert rows[0]["bucket"] == "no_sig_data" and rows[0]["attempted"] is False


def test_unresolved_gt_and_budget_source():
    doc = load_fix("entry_organic.json")
    rows = sp.score_entry_doc(900001, doc, {"inchikey": {"IKMISS"}}, FakeResolver())
    assert rows[0]["bucket"] == "unresolved_gt" and rows[0]["smiles_source"] == "fail"
    res = FakeResolver(smiles_map={"IKCAP": (None, "budget_exceeded")})
    rows = sp.score_entry_doc(900001, doc, {"inchikey": {"IKCAP"}}, res)
    assert rows[0]["bucket"] == "unresolved_gt"
    assert rows[0]["smiles_source"] == "budget_exceeded"


def test_no_matching_generator_bucket():
    doc = load_fix("entry_ion_elements.json")           # pool = {'formula'}
    res = FakeResolver(smiles_map={"IKCAFF": (CAFFEINE, "mirror")})
    rows = sp.score_entry_doc(900002, doc, {"inchikey": {"IKCAFF"}}, res)
    assert rows[0]["bucket"] == "no_matching_generator"
    assert rows[0]["attempted"] is False


# ------------------------------------------------------------ aggregation / io

def test_serialize_determinism():
    doc = load_fix("entry_organic.json")
    res = FakeResolver(smiles_map={"IKCAFF": (CAFFEINE, "mirror")},
                       class_map={"IKCA": "ion"}, element_map={"IKCA": "Ca"})
    rows_a = sp.score_entry_doc(900001, doc, {"inchikey": {"IKCAFF"}}, res)
    rows_b = sp.score_entry_doc(900002, load_fix("entry_ion_elements.json"),
                                {"inchikey": {"IKCA"}}, res)
    payload1 = sp.serialize_rows(rows_a + rows_b)
    payload2 = sp.serialize_rows(list(reversed(rows_a + rows_b)))
    assert payload1 == payload2
    assert sp.serialize_rows(sp.score_entry_doc(900001, doc,
                            {"inchikey": {"IKCAFF"}}, res)) == sp.serialize_rows(rows_a)


def test_aggregate_denominators():
    res = FakeResolver(smiles_map={"IKCAFF": (CAFFEINE, "mirror")},
                       class_map={"IKCA": "ion", "IKZN": "ion"},
                       element_map={"IKCA": "Ca", "IKZN": "Zn"})
    rows = sp.score_entry_doc(900001, load_fix("entry_organic.json"),
                              {"inchikey": {"IKCAFF"}}, res)
    rows += sp.score_entry_doc(900002, load_fix("entry_ion_elements.json"),
                               {"inchikey": {"IKCA", "IKZN"}}, res)
    agg = sp.aggregate(rows, {"ids": 2})
    blk = agg["per_type"]["inchikey"]
    assert blk["annotations"] == 3 and blk["attempted"] == 3
    assert blk["validated"] == 2 and blk["pct_validated"] == pytest.approx(66.7)
    assert blk["mean_sim_attempted"] == pytest.approx((1.0 + 1.0 + 0.0) / 3, abs=1e-4)
    assert blk["buckets"] == {"below_gate": 1, "validated": 2}
    assert agg["entries"] == {"seen": 2, "any_validated": 2, "any_validated_pct": 100.0}


# ------------------------------------------------------------ anchor gate

def test_anchor_gate_ok_and_reject():
    anchor = load_fix("anchor_v13.json")
    ok = sp.anchor_check({"scanned": 2, "gt_covered": 1}, anchor, "results-v13.json")
    assert ok["checked"] is True
    with pytest.raises(sp.AnchorMismatch):
        sp.anchor_check({"scanned": 3, "gt_covered": 1}, anchor, "results-v13.json")
    with pytest.raises(sp.AnchorMismatch):
        sp.anchor_check({"scanned": 2, "gt_covered": 1}, anchor, "results-v12.json")
    lax = sp.anchor_check({"scanned": 2, "gt_covered": 1}, anchor, "results-v12.json",
                          lax=True)
    assert lax["checked"] is True
    # narrowed (sampled/pilot) runs: denominator mismatch warns under lax,
    # but STRICT must still hard-abort even with matching pattern
    with pytest.raises(sp.AnchorMismatch):
        sp.anchor_check({"scanned": 93, "gt_covered": 91}, anchor, "results-v13.json")
    relaxed = sp.anchor_check({"scanned": 93, "gt_covered": 91}, anchor,
                              "results-v13.json", lax=True)
    assert relaxed["checked"] is True and len(relaxed["warnings"]) == 1


def test_gating_counts():
    docs_gate = [(True, True, True), (False, True, True),
                 (True, True, False), (False, False, False)]
    assert sp.gating_counts(docs_gate) == {"scanned": 2, "gt_covered": 1}


# ------------------------------------------------------------ drift guards

def _load_vsim():
    spec = importlib.util.spec_from_file_location(
        "validation_similarity", os.path.join(REPO, "scripts", "validation_similarity.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_seq_identity_matches_simengine():
    """align_identity_local must be a faithful replica of SimEngine._align_identity."""
    try:
        engine = _load_vsim().SimEngine(budget=1)
    except Exception as exc:
        pytest.skip(f"SimEngine not constructible offline: {exc}")
    for a, b in [("ACDEFGHIK", "ACDEFGHIK"),
                 ("ACDEFGHIKLMNPQRSTVWY", "ACDEGHIKLMNPQRSTVWA"),
                 ("GGGGAAAA", "AAAACCCC")]:
        assert sp.align_identity_local(a, b) == pytest.approx(
            engine._align_identity(a, b), abs=1e-9)


def test_skelfp_parity_with_simengine_currency():
    """Probe skelfp path must equal the S7 skel currency (same functions)."""
    pytest.importorskip("rdkit")
    try:
        vsim = _load_vsim()
        for a, b in [(CAFFEINE, CAFFEINE), (ACETIC, ACETATE), (CAFFEINE, BENZENE)]:
            ref = vsim._sk_tanimoto(
                vsim._sk_fp(vsim._sk_from_smiles(a)),
                vsim._sk_fp(vsim._sk_from_smiles(b)))
            assert sp.skelfp_tanimoto(a, b) == pytest.approx(ref, abs=1e-9)
    except AttributeError as exc:
        pytest.skip(f"validation_similarity internal API changed: {exc}")


# ------------------------------------------------------------ end-to-end

def _write_entry(root, eid, doc, pattern="results-v13.json"):
    d = os.path.join(root, str(eid))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, pattern), "w") as fh:
        json.dump(doc, fh)


def test_main_e2e_offline(tmp_path):
    root = str(tmp_path / "data")
    out = str(tmp_path / "sigstage")
    os.makedirs(root)
    _write_entry(root, 900101, {                       # load+verify OK, has GT
        "tasks": {"load_simulation": {"status": "success"},
                  "verify_results": {"status": "success"}},
        "data": {"signatures": {"SEG": {"generated": {"fasta_map_protein": SEQ40}}}}})
    _write_entry(root, 900102, {                       # verify FAILED -> probe-only row
        "tasks": {"load_simulation": {"status": "success"},
                  "verify_results": {"status": "failed"}},
        "data": {}})
    _write_entry(root, 900103, {                       # load FAILED -> skipped entirely
        "tasks": {"load_simulation": {"status": "failed"}}, "data": {}})
    _write_entry(root, 900104, {                       # load+verify OK, no GT
        "tasks": {"load_simulation": {"status": "success"},
                  "verify_results": {"status": "success"}},
        "data": {}})
    gt_path = tmp_path / "gt.json"
    gt_path.write_text(json.dumps({"900101": {"uniprot": ["P1"]},
                                   "900102": {"uniprot": ["P2"]}}))
    anchor = load_fix("anchor_v13.json")
    anchor_path = tmp_path / "anchor.json"
    anchor_path.write_text(json.dumps(anchor))

    res = FakeResolver(seq_map={"P1": SEQ40, "P2": "AAAAAAAAAA"})
    argv = ["--root", root, "--out-dir", out, "--gt-json", str(gt_path),
            "--anchor", str(anchor_path), "--threads", "4",
            "--since", "1970-01-01T00:00:00"]
    sp.main(argv, resolver_factory=lambda budget: res)

    shard = os.path.join(out, "shards", "shard_000.jsonl")
    agg_path = os.path.join(out, "sigstage_v1_shard000.json")
    assert os.path.isfile(shard) and os.path.isfile(agg_path)

    rows = [json.loads(ln) for ln in open(shard)]
    by_entry = {r["entry_id"]: r for r in rows}
    assert by_entry[900101]["validated"] is True      # sequence validated at S0
    assert by_entry[900102]["bucket"] == "no_sig_data"  # verify-failed entry INCLUDED
    assert 900103 not in by_entry                      # load-failed skipped
    assert 900104 not in by_entry                      # no GT -> no rows

    agg = json.load(open(agg_path))
    blk = agg["per_type"]["uniprot"]
    assert (blk["annotations"], blk["validated"]) == (2, 1)
    assert agg["entries"]["any_validated_pct"] == 50.0
    assert agg["scan"]["anchor"] == str(anchor_path)   # STRICT gate passed (else abort)

    # byte determinism across runs (threaded collection order must not leak)
    first = open(shard, "rb").read()
    sp.main(argv, resolver_factory=lambda budget: res)
    assert open(shard, "rb").read() == first
