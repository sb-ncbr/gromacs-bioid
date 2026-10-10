"""Unit tests for replay_gate_diff normalization + tiering."""

from __future__ import annotations

import copy

from scripts.stats.replay_gate_diff import compare, _attempts_shape, _norm


def _base_result() -> dict:
    return {
        "pipeline": {
            "name": "BAT3",
            "run_id": "uuid-1",
            "status": "success",
            "input_kind": "gromacs",
            "created_at": "2026-01-01T00:00:00Z",
            "started_at": "2026-01-01T00:00:01Z",
            "finished_at": "2026-01-01T00:01:00Z",
        },
        "data": {
            "input": {"kind": "gromacs", "decision": {"selected_strategy": "TPR_GRO"}},
            "loading": {
                "success": True,
                "final_strategy": "gromacs_tpr_gro",
                "attempts": [
                    {"strategy": "gromacs_tpr_gro", "status": "success",
                     "used_files": ["/app/runs/x/md.tpr", "/app/runs/x/md.gro"],
                     "timestamp": "2026-01-01T00:00:02Z"},
                ],
            },
            "universe": {"atom_count": 82308},
            "signatures": {"seg_0": {"pdb": {"value": "abc"}, "name": {"value": "X"}}},
            "molecules": {"count": 4, "unique_count": 3, "type_counts": {"lipid": 2, "ion": 2}},
            "fragments": {"count": 4},
            "exports": {"seg_0": "/app/runs/x/seg_0.mmcif"},
            "identifiers": {"seg_0": {"pdb": {"candidates": [{"id": "1abc"}]}}},
            "verification": {"seg_0": {"status": "verified", "method": "structure"}},
        },
    }


class TestNormalize:
    def test_timestamps_and_paths_dropped(self):
        n = _norm({"created_at": "x", "p": "/app/runs/1/in.tpr", "keep": 1})
        assert n == {"p": "<path>", "keep": 1}

    def test_attempts_shape_strips_used_files(self):
        a = _attempts_shape([{"strategy": "s", "status": "success", "used_files": ["/x"], "timestamp": "t"}])
        assert a == [{"strategy": "s", "status": "success"}]


class TestCompare:
    def test_identical_after_normalization(self):
        a, b = _base_result(), _base_result()
        b["pipeline"]["created_at"] = "2026-02-02T00:00:00Z"          # volatile
        b["data"]["loading"]["attempts"][0]["timestamp"] = "later"   # volatile
        b["data"]["loading"]["attempts"][0]["used_files"] = ["/data/validation/runs/y/t.tpr"]
        v = compare(a, b)
        assert v["ok"], v["strict"]

    def test_strategy_change_is_strict_diff(self):
        a, b = _base_result(), _base_result()
        b["data"]["loading"]["final_strategy"] = "gromacs_tpr"
        v = compare(a, b)
        assert not v["ok"]
        assert any("final_strategy" in s for s in v["strict"])

    def test_success_flip_is_strict_diff(self):
        a, b = _base_result(), _base_result()
        b["pipeline"]["status"] = "failed"
        b["data"]["loading"]["success"] = False
        v = compare(a, b)
        assert not v["ok"]

    def test_signature_change_is_strict_diff(self):
        a, b = _base_result(), _base_result()
        b["data"]["signatures"]["seg_0"]["pdb"]["value"] = "DIFFERENT"
        v = compare(a, b)
        assert not v["ok"]

    def test_molecule_type_counts_change_is_strict_diff(self):
        a, b = _base_result(), _base_result()
        b["data"]["molecules"]["type_counts"] = {"lipid": 1, "ion": 2}
        v = compare(a, b)
        assert not v["ok"]

    def test_verification_drift_is_info_not_fail(self):
        a, b = _base_result(), _base_result()
        b["data"]["verification"]["seg_0"]["status"] = "unverified"
        v = compare(a, b)
        assert v["ok"]
        assert any("verification drift" in i for i in v["info"])

    def test_identifier_drift_is_info_not_fail(self):
        a, b = _base_result(), _base_result()
        b["data"]["identifiers"]["seg_0"]["pdb"]["candidates"] = []
        v = compare(a, b)
        assert v["ok"]
        assert any("identifier" in i for i in v["info"])

    def test_bundle_role_widening_is_cosmetic_not_strict(self):
        """Legacy role 'input' vs new canonical roles must not trip the gate
        (documented provenance widening); extension-derived roles converge."""
        a = _base_result()
        a["data"]["input"]["bundle"] = {"files": [
            {"path": "/app/runs/x/md.tpr", "file_type": "GROMACS_TPR", "role": "structure"},
            {"path": "/app/runs/x/md.gro", "file_type": "GROMACS_GRO", "role": "input"},
        ]}
        b = copy.deepcopy(a)
        b["data"]["input"]["bundle"]["files"][1]["role"] = "coordinate"
        v = compare(a, b)
        assert v["ok"], v["strict"]

    def test_bundle_filetype_change_stays_strict(self):
        a = _base_result()
        a["data"]["input"]["bundle"] = {"files": [
            {"path": "/app/runs/x/md.tpr", "file_type": "GROMACS_TPR", "role": "structure"},
        ]}
        b = copy.deepcopy(a)
        b["data"]["input"]["bundle"]["files"][0]["file_type"] = "TAMPERED"
        assert not compare(a, b)["ok"]

    def test_legacy_role_strings_converge_by_extension(self):
        """role 'input' (legacy) vs 'coordinate' (new provenance) is cosmetic."""
        a, b = _base_result(), _base_result()
        a["data"]["input"]["bundle"] = {"files": [
            {"path": "/app/runs/x/md.tpr", "file_type": "GROMACS_TPR", "role": "structure"},
            {"path": "/app/runs/x/md.gro", "file_type": "GROMACS_GRO", "role": "input"},
        ]}
        b["data"]["input"]["bundle"] = {"files": [
            {"path": "/app/runs/x/md.tpr", "file_type": "GROMACS_TPR", "role": "structure"},
            {"path": "/app/runs/x/md.gro", "file_type": "GROMACS_GRO", "role": "coordinate"},
        ]}
        v = compare(a, b)
        assert v["ok"], v["strict"]

    def test_baseline_failed_never_passes_loading(self):
        """failed baseline + failed replay at same place = no strict diff
        (no success-invariant to violate)."""
        a, b = _base_result(), _base_result()
        for r in (a, b):
            r["pipeline"]["status"] = "failed"
            r["data"]["loading"]["success"] = False
        assert compare(a, b)["ok"]
