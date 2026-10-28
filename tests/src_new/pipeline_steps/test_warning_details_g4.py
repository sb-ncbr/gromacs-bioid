"""BACKEND_GAPS G4: warning details carry segment/service at emit sites.

The redesigned warnings panel (ui/src/features/results/viewmodel/
notes.ts) reads `details.segment` directly and fills {service} /
{molecule} from it instead of message parsing. This duplicates the
additive data at the three emit sites the panel surfaces:

  - identifier_resolver_failed (attention): segment + service+generator
  - verification_failed      (attention): segment (service N/A)
  - signature_generator_failed     (info): segment already present —
    service=generator added for parity

Legacy warnings without details keep the UI's message-parsing fallback
(untouched — the UI contract is additive-only).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from src_new.pipeline_steps import _identify_molecules, _verify_results
from src_new.config.loader import RunConfig


SEG_A = "A"
SEG_B = "B"


class _FakeResults:
    """Just enough ResultsManager surface for the aggregation paths."""

    def __init__(self, data: dict):
        self._data = data
        self.written: dict = {}

    def get_data(self, path, _doc=None):
        node = self._data
        for part in path.split("/"):
            if not isinstance(node, dict):
                return None
            node = node.get(part)
        return node

    def set_data(self, path, value, _doc=None):
        self.written[path] = value


class _FakeContext:
    def __init__(self, results, config):
        self.results = results
        self.config = config
        self.warnings: list = []

    def get_value(self, key):
        if key == "facade":
            return object()
        return None  # no stage budget

    def fail(self, code, msg):
        raise AssertionError(f"context.fail: {code}: {msg}")

    def add_warning(self, code, message, details=None):
        self.warnings.append((code, message, details or {}))


def _cfg(parallel: bool) -> RunConfig:
    cfg = RunConfig()
    cfg.executor.identifiers_parallel = parallel
    cfg.executor.verification_parallel = parallel
    cfg.executor.n_threads = 2
    return cfg


class TestVerifyWarningDetails:
    def test_verification_failed_carries_segment(self, monkeypatch):
        results = _FakeResults({
            "identifiers": {SEG_A: {"atom": {"atom": {"hits": ["Na"]}}}},
            "signatures": {},
        })
        ctx = _FakeContext(results, _cfg(parallel=False))

        monkeypatch.setattr(
            "src_new.pipeline_steps.workers._verify_results_worker",
            lambda item: {
                "segment": item[0], "verified_hits": [], "partial": False,
                "errors": [{"error": "timeout contacting foldseek"}],
            },
        )
        _verify_results(ctx)

        assert len(ctx.warnings) == 1
        code, message, details = ctx.warnings[0]
        assert code == "verification_failed"
        assert details.get("segment") == SEG_A  # G4 — the new additive key


class TestIdentifyWarningDetails:
    def test_resolver_failed_carries_segment_and_service(self, monkeypatch):
        results = _FakeResults({
            "signatures": {
                SEG_A: {"generated": {"sequence|md5|64": {"md5": "x"}}},
                SEG_B: {"generated": {"sequence|md5|64": {"md5": "y"}}},
            },
            "identifiers": {SEG_A: {}, SEG_B: {}},
        })
        ctx = _FakeContext(results, _cfg(parallel=True))

        # parallel path: run_with_thread_pool returns worker results —
        # one resolver error on segment A
        monkeypatch.setattr(
            "src_new.executor.parallel.run_with_thread_pool",
            lambda _w, _fn, items: [
                {
                    "fragment_name": fragment_name,
                    "results": {},
                    "partial": False,
                    "errors": [{
                        "resolver": "blast",
                        "generator": "sequence|md5|64",
                        "error": "HTTP 503 from NCBI",
                    }] if fragment_name == SEG_A else [],
                }
                for fragment_name, *_ in items
            ],
        )
        _identify_molecules(ctx)

        resolver_warnings = [w for w in ctx.warnings
                             if w[0] == "identifier_resolver_failed"]
        assert len(resolver_warnings) == 1
        _, message, details = resolver_warnings[0]
        assert details.get("segment") == SEG_A          # G4
        assert details.get("service") == "blast"        # G4
        assert details.get("generator") == "sequence|md5|64"  # parity
        # message format unchanged (legacy consumers parse it)
        assert message.startswith("blast (sequence|md5|64): ")
