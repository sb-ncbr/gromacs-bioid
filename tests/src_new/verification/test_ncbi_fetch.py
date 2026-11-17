"""NCBI efetch: API key, shared rate budget, 429 handling (sequence_fetcher)."""
from __future__ import annotations

import pytest

from src_new.verification.base import TransientFetchError
from src_new.verification.fetchers import sequence_fetcher as sf


class Resp:
    def __init__(self, status, text="", headers=None):
        self.status_code, self.text, self.headers = status, text, headers or {}


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr(sf.time, "sleep", lambda s: None)
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.setattr(sf, "_ncbi_redis", None)


def test_key_and_fasta(monkeypatch):
    seen = []
    monkeypatch.setenv("NCBI_API_KEY", "k123")
    monkeypatch.setattr(sf.requests, "get", lambda url, params, timeout: seen.append(params) or
                        Resp(200, ">HMW90543 hypothetical\nMKT\nAYI\n"))
    assert sf._ncbi_fasta("protein", "HMW90543") == "MKTAYI"
    assert seen[0]["api_key"] == "k123" and seen[0]["db"] == "protein" and seen[0]["tool"] == "bioid"
    assert sf._ncbi_rate() == 9


def test_429_is_retried_then_transient(monkeypatch):
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    answers = iter([Resp(429, headers={"Retry-After": "1"}), Resp(200, ">x\nMKT\n")])
    monkeypatch.setattr(sf.requests, "get", lambda url, params, timeout: next(answers))
    assert sf._ncbi_fasta("protein", "A1") == "MKT"
    monkeypatch.setattr(sf.requests, "get", lambda url, params, timeout: Resp(429))
    with pytest.raises(TransientFetchError):
        sf._ncbi_fasta("protein", "A1")
    monkeypatch.setattr(sf.requests, "get", lambda url, params, timeout: Resp(400))
    assert sf._ncbi_fasta("protein", "bad id") is None  # a definitive miss, not transient


def test_shared_budget_per_second(monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.n = {}

        def incr(self, k):
            self.n[k] = self.n.get(k, 0) + 1
            return self.n[k]

        def expire(self, k, s):
            pass

    fake = FakeRedis()
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://x")
    monkeypatch.setattr(sf, "_ncbi_redis", fake)
    clock = {"t": 1000.0}
    monkeypatch.setattr(sf.time, "time", lambda: clock["t"])
    monkeypatch.setattr(sf.time, "sleep", lambda s: clock.__setitem__("t", clock["t"] + s))
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    for _ in range(7):
        sf._ncbi_wait_turn()
    # 3 per second without a key: 7 requests need 3 seconds' budget
    assert fake.n == {"bioid:ncbi:1000": 4, "bioid:ncbi:1001": 4, "bioid:ncbi:1002": 1}
