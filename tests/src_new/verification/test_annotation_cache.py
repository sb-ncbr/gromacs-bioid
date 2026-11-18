"""Shared annotation scores and counted annotation fetch failures (2026-11-18)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src_new import completeness
from src_new.verification import annotation_cache, base
from src_new.verification.models import AnnotationQuality


class FakeRedis:
    def __init__(self):
        self.kv = {}

    def get(self, key):
        return self.kv.get(key)

    def set(self, key, value, ex=None):
        assert ex is None, "annotation scores are kept with no expiry"
        self.kv[key] = value


@pytest.fixture
def redis(monkeypatch):
    r = FakeRedis()
    monkeypatch.setattr(annotation_cache, "_redis", lambda: r)
    return r


def test_scores_round_trip_per_mode_without_expiry(redis):
    q = AnnotationQuality(database="ChEBI", score=75.0, signals=["name", "smiles"], name="water")
    annotation_cache.put("CHEBI_ID", "15377", True, q)
    assert annotation_cache.get("CHEBI_ID", "15377", True) == q
    assert annotation_cache.get("CHEBI_ID", "15377", False) is None  # offline scores are kept apart
    annotation_cache.put("CHEBI_ID", "16234", True, None)  # failures are never stored
    assert len(redis.kv) == 1


def test_redis_errors_switch_the_cache_off(monkeypatch):
    class Broken:
        def get(self, key):
            raise ConnectionError("down")

    monkeypatch.setattr(annotation_cache, "_off_until", 0.0)
    monkeypatch.setattr(annotation_cache, "_client", Broken())
    monkeypatch.setenv("BAT3_SHARED_CACHE_URL", "redis://x")
    assert annotation_cache.get("CHEBI_ID", "1", True) is None
    assert annotation_cache._off_until > 0
    monkeypatch.setattr(annotation_cache, "_client", None)


def test_failures_are_counted_but_unknown_entries_are_not():
    base.reset_fetch_failures()
    base.note_fetch_failure("chebi", "ReadTimeout")
    base.note_fetch_failure("chebi", "ReadTimeout")
    base.note_fetch_failure("chebi", "HTTP 503")
    base.note_fetch_failure("chebi", "HTTP 404")   # the entry does not exist: an answer
    base.note_fetch_failure("pubchem", "HTTP 429")
    assert base.fetch_failures() == {("chebi", "ReadTimeout"): 2, ("chebi", "HTTP 503"): 1,
                                     ("pubchem", "HTTP 429"): 1}
    base.reset_fetch_failures()
    assert base.fetch_failures() == {}


def test_verify_step_records_a_warning_that_makes_the_run_incomplete():
    from src_new.pipeline_steps import _record_annotation_fetch_failures
    base.reset_fetch_failures()
    for _ in range(28):
        base.note_fetch_failure("chebi", "ReadTimeout")
    ctx = MagicMock()
    _record_annotation_fetch_failures(ctx)
    code, message = ctx.add_warning.call_args[0]
    details = ctx.add_warning.call_args[1]["details"]
    assert code == "annotation_fetch_failed" and details["count"] == 28
    assert message.startswith("ChEBI: 28 annotation records could not be fetched (ReadTimeout ×28)")
    gaps = completeness.gaps({"warnings": [{"code": code, "message": message, "details": details}]})
    assert [(g["service"], g["reason"], g["count"]) for g in gaps] == [("chebi_annotation", "timeout", 28)]
    base.reset_fetch_failures()


def test_no_failures_no_warning():
    from src_new.pipeline_steps import _record_annotation_fetch_failures
    base.reset_fetch_failures()
    ctx = MagicMock()
    _record_annotation_fetch_failures(ctx)
    ctx.add_warning.assert_not_called()
