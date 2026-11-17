"""Shared resolver cache between worker pods (shared_cache.py)."""
from __future__ import annotations

import pytest

from src_new.config.loader import RunConfig
from src_new.identification import shared_cache
from src_new.identification.base import IdentifierResolver


class FakeRedis:
    def __init__(self):
        self.kv = {}
        self.fail = False

    def get(self, k):
        if self.fail:
            raise ConnectionError("down")
        return self.kv.get(k)

    def set(self, k, v, ex=None):
        if self.fail:
            raise ConnectionError("down")
        self.kv[k] = v


class Counting(IdentifierResolver):
    """Answers with metadata; counts live resolutions."""

    def __init__(self, config, answer=("P00760",), error=None):
        super().__init__(config)
        self.name = "blast_swissprot_protein"
        self.calls = 0
        self.answer, self.error = list(answer), error

    def _is_applicable(self, signature):
        return True

    def _resolve_identity(self, signature, working_directory):
        self.calls += 1
        self._last_resolution_metadata = {"P00760": {"identity_p": 100.0, "coverage_p": 100.0}}
        self._last_error = self.error
        return list(self.answer)

    def _resolve_similarity(self, signature, working_directory):
        self.calls += 1
        return [("P00760", 99.5)]


class NoCache:
    """A local cache that always misses (the shared layer alone)."""

    def fetch_identity_identifiers(self, *a):
        return []

    fetch_similarity_identifiers = fetch_identity_identifiers

    def save_identity_identifiers(self, *a):
        pass

    save_similarity_identifiers = save_identity_identifiers


@pytest.fixture
def redis(monkeypatch):
    r = FakeRedis()
    monkeypatch.setenv("BAT3_SHARED_CACHE_URL", "redis://cache:6379/0")
    monkeypatch.setattr(shared_cache, "_client", r)
    monkeypatch.setattr(shared_cache, "_off_until", 0.0)
    return r


def test_second_pod_gets_the_answer_with_its_metadata(redis):
    pod1, pod2 = Counting(RunConfig()), Counting(RunConfig())
    assert pod1.resolve("MKT", cache=NoCache()) == ["P00760"]
    assert pod2.resolve("MKT", cache=NoCache()) == ["P00760"]
    assert (pod1.calls, pod2.calls) == (1, 0)
    assert pod2.get_last_resolution_metadata() == {"P00760": {"identity_p": 100.0, "coverage_p": 100.0}}
    assert pod2.resolve("MKT", as_similarity=True, cache=NoCache()) == [("P00760", 99.5)]
    assert pod2.resolve("MKT", as_similarity=True, cache=NoCache()) == [("P00760", 99.5)]
    assert pod2.calls == 1  # similarity cached separately, tuples restored


def test_different_answer_settings_do_not_share(redis):
    a, b, c = RunConfig(), RunConfig(), RunConfig()
    b.pubchem.similarity_threshold = 80          # shapes answers: separate entries
    c.blast.blastp_num_threads = 8               # does not: shared
    c.timeouts.global_timeout_s = 1
    assert shared_cache.fingerprint(a) != shared_cache.fingerprint(b)
    assert shared_cache.fingerprint(a) == shared_cache.fingerprint(c)


def test_failures_and_empty_results_are_not_shared(redis):
    Counting(RunConfig(), error="HTTP 500").resolve("MKT", cache=NoCache())
    Counting(RunConfig(), answer=()).resolve("MKT", cache=NoCache())
    assert redis.kv == {}


def test_off_without_url_or_local_cache(redis, monkeypatch):
    Counting(RunConfig()).resolve("MKT", cache=None)  # no local caching: no sharing either
    assert redis.kv == {}
    monkeypatch.delenv("BAT3_SHARED_CACHE_URL")
    Counting(RunConfig()).resolve("MKT", cache=NoCache())
    assert redis.kv == {}


def test_redis_down_costs_nothing(redis):
    redis.fail = True
    r = Counting(RunConfig())
    assert r.resolve("MKT", cache=NoCache()) == ["P00760"] and r.calls == 1
    assert shared_cache._off_until > 0  # switched off for a minute, no retries per call
