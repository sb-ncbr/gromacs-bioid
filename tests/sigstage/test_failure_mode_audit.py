"""Offline tests for scripts/stats/failure_mode_audit.py (S0 final wave)."""
import importlib.util
import json
import os
import textwrap
import tempfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "fma", os.path.join(REPO, "scripts", "stats", "failure_mode_audit.py"))
fma = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fma)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _mk_row(entry_id=1, gt_type="inchikey", gt_value="IK001",
            s7_attempted=True, s7_class="organic",
            s7_v1=False, s7_v5=False, s7_v10=False,
            sim1=0.0, sim5=0.0, sim10=0.0,
            s0_validated=None, s0_bucket=None, s0_sim=None,
            n_hits=0):
    return {
        "entry_id": entry_id,
        "gt_type": gt_type,
        "gt_value": gt_value,
        "n_hits": n_hits,
        "s0_validated": s0_validated,
        "s0_bucket": s0_bucket,
        "s0_sim": s0_sim,
        "s7_attempted": s7_attempted,
        "s7_class": s7_class,
        "s7_sim@1": sim1,
        "s7_sim@5": sim5,
        "s7_sim@10": sim10,
        "s7_validated@1": s7_v1,
        "s7_validated@5": s7_v5,
        "s7_validated@10": s7_v10,
        "s5_hit@1": 0, "s5_hit@5": 0, "s5_hit@10": 0,
        "s0_best_segment": None, "s0_smiles_source": None,
    }


# ---------------------------------------------------------------------------
# row_type
# ---------------------------------------------------------------------------

class TestRowType:
    def test_ion(self):
        r = _mk_row(gt_type="inchikey", s7_class="ion")
        assert fma.row_type(r) == "ion"

    def test_organic(self):
        r = _mk_row(gt_type="inchikey", s7_class="organic")
        assert fma.row_type(r) == "inchikey"

    def test_unresolved_is_organic(self):
        r = _mk_row(gt_type="inchikey", s7_class="unresolved")
        assert fma.row_type(r) == "inchikey"

    def test_pdb(self):
        r = _mk_row(gt_type="pdb", s7_class=None)
        assert fma.row_type(r) == "pdb"


# ---------------------------------------------------------------------------
# classify_s7_fail — mode archetypes
# ---------------------------------------------------------------------------

class TestClassifyS7:
    def test_gt_unresolved_by_class(self):
        r = _mk_row(s7_class="unresolved", n_hits=5, sim1=0.9, sim5=1.0, sim10=1.0)
        assert fma.classify_s7_fail(r, 1) == "gt_unresolved"

    def test_ledger_gt_value_not_tagged(self):
        # A GT string that merely appears in the ghost ledger (pair-level
        # endpoint) must NOT be tagged gt_unresolved when per-row signals
        # say the GT resolved fine.
        r = _mk_row(gt_value="GHOST-IK-AAA", s7_class="organic", n_hits=3,
                    s0_bucket="below_gate", s0_sim=0.5,
                    sim1=0.5, sim5=0.6, sim10=0.65)
        assert fma.classify_s7_fail(r, 1) == "weak_below_gate"

    def test_no_verified_hits(self):
        r = _mk_row(s7_class="organic", n_hits=0, sim1=0.0, sim5=0.0, sim10=0.0)
        assert fma.classify_s7_fail(r, 1) == "no_verified_hits"

    def test_structure_absent(self):
        r = _mk_row(s7_class="organic", n_hits=50, sim1=0.0, sim5=0.0, sim10=0.0)
        assert fma.classify_s7_fail(r, 1) == "structure_absent"

    def test_rank_loss_top5(self):
        r = _mk_row(s7_class="organic", n_hits=10,
                    sim1=0.3, sim5=0.95, sim10=0.95,
                    s7_v5=True, s7_v10=True)
        assert fma.classify_s7_fail(r, 1) == "rank_loss_top5"

    def test_rank_loss_top10(self):
        r = _mk_row(s7_class="organic", n_hits=15,
                    sim1=0.3, sim5=0.4, sim10=0.95,
                    s7_v5=False, s7_v10=True)
        assert fma.classify_s7_fail(r, 1) == "rank_loss_top10"

    def test_weak_below_gate(self):
        r = _mk_row(s7_class="organic", n_hits=10,
                    sim1=0.3, sim5=0.5, sim10=0.65)
        assert fma.classify_s7_fail(r, 1) == "weak_below_gate"

    def test_ion_element_absent(self):
        r = _mk_row(gt_type="inchikey", s7_class="ion", n_hits=30,
                    sim1=0.0, sim5=0.0, sim10=0.0)
        assert fma.classify_s7_fail(r, 1) == "structure_absent"

    def test_at_k10_no_rank_modes(self):
        """At K=10 rank_loss modes are impossible; below_gate catches it."""
        r = _mk_row(s7_class="organic", n_hits=20,
                    sim1=0.4, sim5=0.5, sim10=0.55)
        assert fma.classify_s7_fail(r, 10) == "weak_below_gate"

    # --- precedence / overlap (fail-on-unfixed proof) ---
    def test_unresolved_class_priority_over_no_hits(self):
        r = _mk_row(s7_class="unresolved", n_hits=0, sim1=0.0, sim5=0.0, sim10=0.0)
        assert fma.classify_s7_fail(r, 1) == "gt_unresolved"

    def test_unresolved_class_priority_over_rank_loss(self):
        r = _mk_row(s7_class="unresolved", n_hits=10,
                    sim1=0.2, sim5=1.0, sim10=1.0, s7_v5=True, s7_v10=True)
        assert fma.classify_s7_fail(r, 1) == "gt_unresolved"

    def test_no_verified_before_absent(self):
        # n_hits==0 AND all sims 0 → no_verified_hits (not structure_absent)
        r = _mk_row(s7_class="organic", n_hits=0, sim1=0.0, sim5=0.0, sim10=0.0)
        assert fma.classify_s7_fail(r, 1) == "no_verified_hits"

    def test_rank_loss_before_weak(self):
        # sim@1 low, sim@5 high (>=gate), verified@5 → rank_loss, not below_gate
        r = _mk_row(s7_class="organic", n_hits=8,
                    sim1=0.3, sim5=0.8, sim10=0.8, s7_v5=True)
        assert fma.classify_s7_fail(r, 1) == "rank_loss_top5"


# ---------------------------------------------------------------------------
# classify_s0_fail
# ---------------------------------------------------------------------------

class TestClassifyS0:
    def test_unresolved_gt_bucket(self):
        r = _mk_row(s0_validated=False, s0_bucket="unresolved_gt")
        assert fma.classify_s0_fail(r, {}) == "gt_unresolved"

    def test_unresolved_signal_overrides_bucket(self):
        r = _mk_row(gt_value="GHOST-IK-AAA", s7_class="unresolved",
                    s0_validated=False, s0_bucket="no_sig_data")
        assert fma.classify_s0_fail(r, {}) == "gt_unresolved"

    def test_ledger_gt_value_not_tagged_s0(self):
        # Ledger membership alone never overrides the row's own bucket.
        r = _mk_row(gt_value="GHOST-IK-AAA", s0_validated=False,
                    s0_bucket="no_sig_data")
        assert fma.classify_s0_fail(r, {}) == "no_sig_data"

    def test_unparseable(self):
        r = _mk_row(s0_validated=False, s0_bucket="unparseable_signature")
        assert fma.classify_s0_fail(r, {}) == "unparseable_signature"

    def test_nmg_with_class(self):
        nmg = {(1, "uniprot", "P1"): "struct_only_no_fasta_generator"}
        r = _mk_row(entry_id=1, gt_type="uniprot", gt_value="P1",
                    s0_validated=False, s0_bucket="no_matching_generator")
        assert fma.classify_s0_fail(r, nmg) == \
            "no_matching_generator:struct_only_no_fasta_generator"

    def test_nmg_without_join(self):
        r = _mk_row(s0_validated=False, s0_bucket="no_matching_generator")
        assert fma.classify_s0_fail(r, {}) == "no_matching_generator:unjoined"

    def test_no_sig_data(self):
        r = _mk_row(s0_validated=False, s0_bucket="no_sig_data")
        assert fma.classify_s0_fail(r, {}) == "no_sig_data"

    def test_below_gate_band(self):
        r = _mk_row(s0_validated=False, s0_bucket="below_gate", s0_sim=0.45)
        assert fma.classify_s0_fail(r, {}) == "below_gate:.3-.6"

    def test_no_s0_row(self):
        r = _mk_row(s0_validated=None, s0_bucket=None)
        assert fma.classify_s0_fail(r, {}) == "no_s0_row"

    def test_residual(self):
        r = _mk_row(s0_validated=False, s0_bucket="mystery_bucket")
        assert fma.classify_s0_fail(r, {}) == "residual_unclassified"


# ---------------------------------------------------------------------------
# classify_unattempted
# ---------------------------------------------------------------------------

class TestUnattempted:
    def test_zero_hit(self):
        r = _mk_row(s7_attempted=False, n_hits=0)
        assert fma.classify_unattempted(r) == "zero_hit_entry"

    def test_gate_unmet(self):
        r = _mk_row(s7_attempted=False, n_hits=12)
        assert fma.classify_unattempted(r) == "attempt_gate_unmet"


# ---------------------------------------------------------------------------
# entry_level
# ---------------------------------------------------------------------------

class TestEntryLevel:
    def test_passing_entry(self):
        rows = {1: [_mk_row(entry_id=1, s7_v1=True, n_hits=5)]}
        out = fma.entry_level(rows)
        assert out["entries_any_validated@1"] == 1
        assert out["entries_failed"] == 0

    def test_failing_entry_mode_rollup(self):
        rows = {1: [_mk_row(entry_id=1, s7_v1=False, n_hits=5,
                            sim1=0.0, sim5=0.0, sim10=0.0)]}
        out = fma.entry_level(rows)
        assert out["entries_failed"] == 1
        assert out["failed_entry_mode_rollup"]["structure_absent"] == 1

    def test_no_attempted_excluded(self):
        rows = {1: [_mk_row(entry_id=1, s7_attempted=False, n_hits=0)]}
        out = fma.entry_level(rows)
        assert out["entries_participating"] == 0
        assert out["entries_no_attempted_annotation"] == 1


# ---------------------------------------------------------------------------
# reconciliation
# ---------------------------------------------------------------------------

class TestReconcile:
    def _frozen(self, rows):
        """Build a frozen types-block that matches the rows exactly."""
        # Use the module's own recompute to build the 'expected' — this is
        # a self-consistency check; in production the frozen file is external.
        return {"types": fma.recompute_types_block(rows)}

    def test_pass(self):
        rows = [
            _mk_row(entry_id=1, gt_type="pdb", gt_value="1A",
                    s7_v1=True, s7_v5=True, s7_v10=True,
                    sim1=1.0, sim5=1.0, sim10=1.0, n_hits=10,
                    s0_validated=True, s0_bucket="validated", s0_sim=1.0),
            _mk_row(entry_id=1, gt_type="pdb", gt_value="1B",
                    s7_v1=False, n_hits=5,
                    sim1=0.3, sim5=0.4, sim10=0.5,
                    s0_validated=False, s0_bucket="below_gate", s0_sim=0.35),
        ]
        frozen = self._frozen(rows)
        checks, ok = fma.reconcile(rows, frozen)
        assert ok is True
        assert all(c["ok"] for c in checks)

    def test_fail_on_mismatch(self):
        rows = [_mk_row(entry_id=1, gt_type="pdb", gt_value="1A",
                        s7_v1=True, s7_v5=True, s7_v10=True,
                        sim1=1.0, sim5=1.0, sim10=1.0, n_hits=10,
                        s0_validated=True, s0_bucket="validated", s0_sim=1.0)]
        frozen = self._frozen(rows)
        # tamper
        frozen["types"]["pdb"]["annotations"] = 999
        checks, ok = fma.reconcile(rows, frozen)
        assert ok is False
        assert any(not c["ok"] for c in checks)


# ---------------------------------------------------------------------------
# advisory flags
# ---------------------------------------------------------------------------

class TestAdvisory:
    def test_oq2_tag(self):
        r = _mk_row(entry_id=4513, gt_type="inchikey", gt_value="IK999")
        oq2 = {(4513, "IK999")}
        assert "oq2_perception_cohort" in fma.advisory_flags(r, {}, oq2)

    def test_a5_struct_tag(self):
        r = _mk_row(entry_id=10, gt_type="uniprot", gt_value="P1")
        nmg = {(10, "uniprot", "P1"): "struct_only_no_fasta_generator"}
        assert "a5_curation_lipid_struct" in fma.advisory_flags(r, nmg, set())

    def test_no_ghost_tag(self):
        # Ledger is pair-level (76% dead-CID / live-InChIKey); endpoint
        # membership must NOT emit a per-row ghost tag.
        r = _mk_row(gt_value="GHOST-IK-AAA")
        assert "ghost_ledger_membership" not in fma.advisory_flags(r, {}, set())

    def test_no_tags(self):
        r = _mk_row(gt_value="NORMAL-IK")
        assert fma.advisory_flags(r, {}, set()) == set()


# ---------------------------------------------------------------------------
# fmt / numbers-only rendering
# ---------------------------------------------------------------------------

class TestFmt:
    def test_fmt_contains_denominator(self):
        out = fma.fmt(42, 1000)
        assert "1000" in out
        assert "42" in out
        assert "4.2%" in out

    def test_fmt_zero_denom(self):
        out = fma.fmt(0, 0)
        assert "of 0" in out


# ---------------------------------------------------------------------------
# sim_band edges
# ---------------------------------------------------------------------------

class TestSimBand:
    def test_boundaries(self):
        assert fma.sim_band(0.0) == "0-.3"
        assert fma.sim_band(0.29) == "0-.3"
        assert fma.sim_band(0.3) == ".3-.6"
        assert fma.sim_band(0.6) == ".6-.8"
        assert fma.sim_band(0.8) == ".8-.9"
        assert fma.sim_band(0.9) == ".9-.95"
        assert fma.sim_band(0.95) == ".95-1"
        assert fma.sim_band(1.0) == "1.0"

    def test_none(self):
        assert fma.sim_band(None) is None


# ---------------------------------------------------------------------------
# end-to-end main() on a synthetic fixture tree
# ---------------------------------------------------------------------------

class TestEndToEnd:
    @pytest.fixture
    def tree(self, tmp_path):
        rows = [
            # inchikey @1 fail: rank loss within top-5 (IK deliberately in
            # the ghost ledger's InChIKey list -- must NOT reclassify it)
            _mk_row(entry_id=1, gt_value="IK_AAA", n_hits=10,
                    sim1=0.3, sim5=0.8, sim10=0.8,
                    s7_v5=True, s7_v10=True,
                    s0_validated=True, s0_bucket="validated", s0_sim=1.0),
            # inchikey @1 fail: weak below gate at all depths
            _mk_row(entry_id=2, gt_value="IK_BBB", n_hits=10,
                    sim1=0.3, sim5=0.4, sim10=0.5,
                    s0_validated=False, s0_bucket="below_gate", s0_sim=0.4),
            # inchikey @1 fail: GT unresolved (both per-row signals)
            _mk_row(entry_id=3, gt_value="IK_CCC", s7_class="unresolved",
                    n_hits=5, s0_validated=False,
                    s0_bucket="unresolved_gt"),
            # inchikey unattempted: zero-hit entry
            _mk_row(entry_id=4, gt_value="IK_DDD", s7_attempted=False,
                    n_hits=0, s0_validated=False,
                    s0_bucket="no_sig_data"),
            # ion @1 fail: element absent (all sims 0, hits present)
            _mk_row(entry_id=5, gt_value="IK_EEE", s7_class="ion",
                    n_hits=50, s0_validated=False,
                    s0_bucket="below_gate", s0_sim=0.0),
            # pdb @1 fail: rank loss within top-5 (seq gate 0.9)
            _mk_row(entry_id=6, gt_type="pdb", gt_value="1ABC",
                    s7_class=None, n_hits=100,
                    sim1=0.8, sim5=1.0, sim10=1.0,
                    s7_v5=True, s7_v10=True,
                    s0_validated=True, s0_bucket="validated", s0_sim=1.0),
            # uniprot @1 pass, S0 below-gate .8-.9
            _mk_row(entry_id=7, gt_type="uniprot", gt_value="P0001",
                    s7_class=None, n_hits=50,
                    sim1=0.95, sim5=0.99, sim10=1.0, s7_v1=True,
                    s7_v5=True, s7_v10=True,
                    s0_validated=False, s0_bucket="below_gate", s0_sim=0.85),
            # uniprot unattempted zero-hit, no S0 row at all
            _mk_row(entry_id=8, gt_type="uniprot", gt_value="P0002",
                    s7_class=None, s7_attempted=False, n_hits=0),
            # uniprot @1 fail: rank loss; S0 = NMG lipid-struct cohort
            _mk_row(entry_id=9, gt_type="uniprot", gt_value="P0003",
                    s7_class=None, n_hits=10,
                    sim1=0.8, sim5=0.9, sim10=0.9,
                    s7_v5=True, s7_v10=True,
                    s0_validated=False, s0_bucket="no_matching_generator"),
            # inchikey @1 fail: weak; S0 = OQ-2 unparseable cohort
            _mk_row(entry_id=10, gt_value="IK_JJJ", n_hits=20,
                    sim1=0.1, sim5=0.2, sim10=0.3,
                    s0_validated=False, s0_bucket="unparseable_signature"),
        ]
        sd = tmp_path / "shards"; sd.mkdir()
        with open(sd / "shard_000.jsonl", "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        fa = tmp_path / "audit_v2.json"
        fa.write_text(json.dumps({"rows": len(rows),
                                  "types": fma.recompute_types_block(rows)}))
        cf = tmp_path / "casefiles"; cf.mkdir()
        (cf / "S0-OQ-1_nmg.jsonl").write_text(json.dumps(
            {"entry_id": 9, "gt_type": "uniprot", "gt_value": "P0003",
             "nmg_class": "struct_only_no_fasta_generator"}) + "\n")
        (cf / "S0-OQ-2_unparseable.jsonl").write_text(json.dumps(
            {"entry_id": 10, "gt_value": "IK_JJJ",
             "error_class": "explicit_valence", "raw_smiles": "[NH+]",
             "rdkit_error": "x", "segment": "seg"}) + "\n")
        (cf / "ghost_curation.json").write_text(json.dumps({
            "source": "test", "pair_keys": 2,
            "report": {"classes": {
                "unresolved_legacy": {"distinct_identifiers": 2, "pairs": 2,
                    "identifiers": [["cid:10008735", 1], ["inchikey:IK_AAA", 1]]},
                "cid_zero": {"distinct_identifiers": 1, "pairs": 1,
                             "identifiers": [["cid:0", 1]]},
            }}}))
        cp = tmp_path / "campaign.json"
        cp.write_text(json.dumps({"full": {"S7_similarity_hit_at_k": {
            "inchikey": {"annotations": 5, "attempted": 4,
                          "pct_validated@1": 25.0, "pct_validated@10": 25.0},
            "entry_any_validated@%": {"1": 98.6}}}}))
        return rows, sd, fa, cf, cp

    def test_main_pipeline(self, tree, tmp_path):
        rows, sd, fa, cf, cp = tree
        outj = tmp_path / "out.json"
        outmd = tmp_path / "out.md"
        rc = fma.main(["--shards-dir", str(sd), "--frozen-audit", str(fa),
                       "--casefiles", str(cf), "--campaign", str(cp),
                       "--out-json", str(outj), "--out-md", str(outmd)])
        assert rc == 0
        rep = json.load(open(outj))
        assert rep["reconciliation"]["ok"] is True

        # inchikey S7@1: 4 attempted failures; ledger membership of IK_AAA
        # must NOT pull row 1 into gt_unresolved.
        by_mode = {r["mode"]: r["n"] for r in rep["metrics"]["inchikey"]["tables"]["s7@1"]}
        assert by_mode["rank_loss_top5"] == 1
        assert by_mode["weak_below_gate"] == 2
        assert by_mode["gt_unresolved"] == 1
        assert by_mode["structure_absent"] == 0

        ion = {r["mode"]: r["n"] for r in rep["metrics"]["ion"]["tables"]["s7@1"]}
        assert ion["structure_absent"] == 1

        s0u = {r["mode"]: r["n"] for r in rep["metrics"]["uniprot"]["tables"]["s0"]}
        assert s0u["no_matching_generator:struct_only_no_fasta_generator"] == 1
        assert s0u["below_gate:.8-.9"] == 1
        assert s0u["no_s0_row"] == 1

        s0i = {r["mode"]: r["n"] for r in rep["metrics"]["inchikey"]["tables"]["s0"]}
        assert s0i["unparseable_signature"] == 1
        assert s0i["no_sig_data"] == 1

        unatt = {r["mode"]: r["n"] for r in rep["metrics"]["uniprot"]["tables"]["unattempted"]}
        assert unatt["zero_hit_entry"] == 1

        # advisory: OQ-2 + A5 struct tagged, no per-row ghost tag
        assert rep["advisory"]["oq2_perception_cohort"] == 1
        assert rep["advisory"]["a5_curation_lipid_struct"] == 1
        assert "ghost_ledger_membership" not in rep["advisory"]
        assert rep["ghost_ledger"]["unresolved_legacy"]["distinct_identifiers"] == 2

        # entry level
        ent = rep["entry_level"]
        assert ent["entries_total"] == 10
        assert ent["entries_participating"] == 8
        assert ent["entries_any_validated@1"] == 1
        assert ent["entries_failed"] == 7
        roll = ent["failed_entry_mode_rollup"]
        assert roll == {"rank_loss_top5": 3, "weak_below_gate": 2,
                        "gt_unresolved": 1, "structure_absent": 1}

        md = outmd.read_text()
        assert "PASS" in md
        assert "of 4" in md  # numbers-only rendering carries denominator
        assert "campaign v14 comparator" in md

    def test_reconcile_mismatch_exit_code(self, tree, tmp_path):
        rows, sd, fa, cf, cp = tree
        broken = json.loads(fa.read_text())
        broken["types"]["ion"]["annotations"] = 999
        fa2 = tmp_path / "audit_bad.json"
        fa2.write_text(json.dumps(broken))
        rc = fma.main(["--shards-dir", str(sd), "--frozen-audit", str(fa2),
                       "--casefiles", str(cf), "--campaign", str(cp),
                       "--out-json", str(tmp_path / "o.json"),
                       "--out-md", str(tmp_path / "o.md")])
        assert rc == 3
