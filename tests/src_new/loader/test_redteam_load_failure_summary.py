"""bughunt BH-014: load failures lose their reason.

The pipeline's generic "No loading strategy succeeded after N attempts"
hid F07's atom-count 30 vs 36, X01's bz2 EOFError, X02's
UnicodeDecodeError. summarize_load_failure extracts the ordered reason;
the pipeline step passes it into context.fail details; /loading reads the
REAL persisted schema (status/error_code/error_message).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src_new.loader.strategies import summarize_load_failure


def _att(strategy="pdb_direct", status="failed", error_code=None, message=""):
    return types.SimpleNamespace(
        strategy=types.SimpleNamespace(value=strategy),
        status=status,
        error_code=error_code,
        error_message=message,
    )


class TestSummarizeLoadFailure:
    def test_no_attempts_means_no_recognized_files(self):
        out = summarize_load_failure([])
        assert out["reason"] == "no_recognized_input_files"
        assert "20 strategies" in out["message"]

    def test_atom_count_mismatch_wins(self):
        out = summarize_load_failure([
            _att("pdb_direct", error_code="load_exception",
                 message="UnicodeDecodeError"),
            _att("gromacs_tpr_xtc", error_code="rejected_atoms",
                 message="atom count mismatch: topology has 36 atoms, "
                         "traj.xtc has 30"),
        ])
        assert out["reason"] == "atom_count_mismatch"
        assert "36" in out["message"] and "30" in out["message"]
        assert out["details"]["attempt_count"] == 2
        assert len(out["details"]["failed_strategies"]) == 2

    def test_first_load_exception_with_others_note(self):
        out = summarize_load_failure([
            _att("a", error_code="load_exception", message="EOFError"),
            _att("b", error_code="load_exception", message="IndexError"),
        ])
        assert out["reason"] == "load_exception"
        assert out["message"] == "EOFError (1 other strategies also failed)"

    def test_content_gate(self):
        out = summarize_load_failure([
            _att("x", error_code="empty_universe",
                 message="Universe built with zero atoms"),
        ])
        assert out["reason"] == "empty_universe"

    def test_structured_only_falls_to_code(self):
        out = summarize_load_failure([
            _att("y", error_code="probe_failed", message="could not probe"),
        ])
        assert out["reason"] == "probe_failed"
        assert out["details"]["error_code"] == "probe_failed"

    def test_successful_attempts_are_not_counted_as_failures(self):
        out = summarize_load_failure([
            _att("ok", status="success"),
            _att("bad", error_code="load_exception", message="IndexError"),
        ])
        assert out["reason"] == "load_exception"
        assert out["details"]["failed_strategies"] == ["bad"]
