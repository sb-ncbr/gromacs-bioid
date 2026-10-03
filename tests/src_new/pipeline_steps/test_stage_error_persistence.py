"""Unit tests for F-N1e stage error persistence (bounded_stage_errors).

The helper normalizes+bounds stage error records written to results.json under
stage_errors/{signatures,identifiers}/{segment}. Errors were previously only
log warnings (N1 audit finding: dead-channel classes invisible postmortem).
"""
from __future__ import annotations

import pytest

from src_new.pipeline_steps import (
    bounded_stage_errors,
    _STAGE_ERRORS_MAX_PER_SEGMENT,
    _STAGE_ERROR_MAX_CHARS,
)


class TestBoundedStageErrors:
    def test_empty_and_non_list(self):
        assert bounded_stage_errors([]) == []
        assert bounded_stage_errors(None) == []
        assert bounded_stage_errors("nope") == []

    def test_normalization_keeps_generator_and_resolver(self):
        errs = [{"generator": "fasta_map_nucleic", "error": "boom"}]
        out = bounded_stage_errors(errs)
        assert out == [{"generator": "fasta_map_nucleic", "error": "boom"}]
        errs = [{"resolver": "mmcif_struct", "generator": "mmcif", "error": "404"}]
        out = bounded_stage_errors(errs)
        assert out[0]["resolver"] == "mmcif_struct"
        assert out[0]["generator"] == "mmcif"

    def test_cap_per_segment(self):
        errs = [{"generator": f"g{i}", "error": f"e{i}"} for i in range(_STAGE_ERRORS_MAX_PER_SEGMENT + 10)]
        out = bounded_stage_errors(errs)
        assert len(out) == _STAGE_ERRORS_MAX_PER_SEGMENT
        assert out[0]["generator"] == "g0"

    def test_truncation(self):
        long_msg = "x" * (_STAGE_ERROR_MAX_CHARS + 500)
        out = bounded_stage_errors([{"generator": "g", "error": long_msg}])
        assert len(out[0]["error"]) == _STAGE_ERROR_MAX_CHARS

    def test_drops_non_dict_and_empty_messages(self):
        errs = ["junk", {"generator": "g"}, {"error": ""}, {"generator": "ok", "error": "fine"}]
        out = bounded_stage_errors(errs)
        assert out == [{"generator": "ok", "error": "fine"}]

    def test_input_not_mutated(self):
        errs = [{"generator": "g", "error": "y" * 1000, "extra": 1}]
        snapshot = [dict(e) for e in errs]
        bounded_stage_errors(errs)
        assert errs == snapshot

    def test_no_unknown_keys_leak(self):
        errs = [{"generator": "g", "resolver": "r", "error": "m", "traceback": "T", "code": 5}]
        out = bounded_stage_errors(errs)
        assert set(out[0].keys()) == {"generator", "resolver", "error"}


class TestStageErrorsSchema:
    def test_results_roundtrip(self, tmp_path):
        """Persist via ResultsManager and re-read: stage_errors branch intact,
        results.json without the branch still parses additive-clean."""
        from src_new.results.results_manager import ResultsManager

        rm = ResultsManager(str(tmp_path / "results.json"), "t")
        errs = bounded_stage_errors([{"generator": "fasta_map_nucleic", "error": "Found 4 disjoint residue components"}])
        rm.set_data("stage_errors/signatures/SYSTEM", errs)
        payload = rm._payload
        assert payload["data"]["stage_errors"]["signatures"]["SYSTEM"][0]["error"].startswith("Found 4")
        # additivity: parallel payload lacking stage_errors parses fine
        rm2 = ResultsManager(str(tmp_path / "results2.json"), "t2")
        rm2.set_data("signatures/SYSTEM/attempted", ["mmcif"])
        assert "stage_errors" not in rm2._payload["data"]
        assert rm2._payload["data"]["signatures"]["SYSTEM"]["attempted"] == ["mmcif"]
