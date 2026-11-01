"""W3.3 A.3 health record: additive per-run diagnostics.

Corpus-run requirement (user 2026-11-01): every results.json is
self-describing — resolver cache hits/misses per resolver, annotation
fetch failures tagged per service, per-stage wall seconds, pod name.
Additive only: no behavioral change to resolution, scoring, or the
executor beyond these counters/metadata.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest import mock

import pytest

requests = pytest.importorskip("requests")
MDAnalysis = pytest.importorskip("MDAnalysis")

from src_new.executor.executor import PipelineExecutor
from src_new.executor.task import PipelineStep, StepResult
from src_new.identification.base import IdentifierResolver
from src_new.identification.cache_manager import (
    cache_stats_snapshot,
    record_cache_event,
    reset_cache_stats,
)
from src_new.results.results_manager import ResultsManager
from src_new.verification.scorers.uniprot_scorer import UniProtAnnotationScorer


class TestCacheStatsCounters:
    def setup_method(self):
        reset_cache_stats()

    def test_hit_miss_error_roundtrip(self):
        record_cache_event("pdb_struct", True)
        record_cache_event("pdb_struct", True)
        record_cache_event("pdb_struct", False)
        record_cache_event("uniprot", False, error=True)
        snap = cache_stats_snapshot()
        assert snap["pdb_struct"] == {"hit": 2, "miss": 1, "error": 0}
        assert snap["uniprot"] == {"hit": 0, "miss": 0, "error": 1}

    def test_reset_clears(self):
        record_cache_event("x", True)
        reset_cache_stats()
        assert cache_stats_snapshot() == {}

    def test_resolve_path_counts_hit_and_miss(self, tmp_path):
        """The resolver's cache seam counts one event per lookup."""
        from src_new.config.loader import RunConfig

        store = {"sig-hit": ["4HHB"]}

        class _StubCache:
            def fetch_similarity_identifiers(self, name, signature):
                return []
            def fetch_identity_identifiers(self, name, signature):
                return list(store.get(signature, []))
            def save_identity_identifiers(self, name, signature, ids):
                pass
            def save_similarity_identifiers(self, name, signature, ids):
                pass

        class _StubResolver(IdentifierResolver):
            name = "stub"

            def __init__(self):
                super().__init__(RunConfig())
                self.name = "stub"
                self.identifier_type = "PDB_ID"

            def _is_applicable(self, signature):
                return True

            def _resolve_identity(self, signature, working_directory):
                return ["9ZZZ"]

            def _resolve_similarity(self, signature, working_directory):
                return []

        r = _StubResolver()
        assert r.resolve("sig-hit", working_directory=str(tmp_path),
                         cache=_StubCache()) == ["4HHB"]
        assert r.resolve("sig-miss", working_directory=str(tmp_path),
                         cache=_StubCache()) == ["9ZZZ"]
        snap = cache_stats_snapshot()
        assert snap["stub"] == {"hit": 1, "miss": 1, "error": 0}


class TestStageWallsAndPod:
    def test_walls_and_pod_persisted(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOSTNAME", "bat3-worker-7")
        results_path = tmp_path / "results.json"
        manager = ResultsManager(results_path)

        def ok(context):
            return StepResult(summary={})

        steps = [PipelineStep(step_id="load", name="Load", handler=ok),
                 PipelineStep(step_id="identify", name="Id", handler=ok)]
        PipelineExecutor(steps=steps, results_manager=manager).run(
            output_directory=tmp_path / "outputs")

        payload = json.loads(results_path.read_text(encoding="utf-8"))
        health = payload["data"]["run_health"]
        walls = health["stage_walls"]
        assert set(walls) >= {"load", "identify"}
        assert all(isinstance(v, float) and v >= 0 for v in walls.values())
        assert health["pod"] == "bat3-worker-7"

    def test_wall_recorded_for_failed_step(self, tmp_path):
        results_path = tmp_path / "results.json"
        manager = ResultsManager(results_path)

        def boom(context):
            raise RuntimeError("kaput")

        steps = [PipelineStep(step_id="load", name="Load", handler=boom)]
        with pytest.raises(Exception):
            PipelineExecutor(steps=steps, results_manager=manager).run(
                output_directory=tmp_path / "outputs")
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        assert "load" in payload["data"]["run_health"]["stage_walls"]


class TestAnnotationFailureTags:
    def test_uniprot_failure_logs_tagged_line(self, caplog):
        scorer = UniProtAnnotationScorer()
        with mock.patch(
            "src_new.verification.scorers.uniprot_scorer.requests.get",
            side_effect=requests.exceptions.ConnectionError("boom"),
        ), caplog.at_level(logging.WARNING, logger="annotation"):
            assert scorer.score("P00698", "UNIPROT_ID") is None
        tagged = [r for r in caplog.records if "ann_fetch_failed" in r.getMessage()]
        assert len(tagged) == 1
        assert "service=uniprot" in tagged[0].getMessage()
        assert "reason=" in tagged[0].getMessage()
