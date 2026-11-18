"""Service measurements (src_new/service_stats.py): counting never changes calls."""
from __future__ import annotations

import fnmatch
import time

import pytest

from src_new import service_stats as ss


class FakeRedis:
    """The few commands service_stats uses."""

    def __init__(self):
        self.h: dict[str, dict[str, int]] = {}
        self.kv: dict[str, str] = {}
        self.ops: list = []

    def pipeline(self, transaction=False):
        return self

    def hincrby(self, key, field, n):
        self.ops.append(lambda: self.h.setdefault(key, {}).__setitem__(
            field, self.h.get(key, {}).get(field, 0) + n))

    def expire(self, key, s):
        self.ops.append(lambda: None)

    def set(self, key, value, ex=None):
        self.ops.append(lambda: self.kv.__setitem__(key, value))

    def delete(self, key):
        self.ops.append(lambda: self.kv.pop(key, None))

    def hgetall(self, key):
        self.ops.append(lambda: {k.encode(): str(v).encode() for k, v in self.h.get(key, {}).items()})

    def execute(self):
        out = [op() for op in self.ops]
        self.ops = []
        return out

    def scan_iter(self, match, count=None):
        return [k for k in list(self.kv) if fnmatch.fnmatch(k, match)]

    def get(self, key):
        return self.kv.get(key)


class Broken(FakeRedis):
    def execute(self):
        raise ConnectionError("down")


@pytest.fixture
def fake(monkeypatch):
    r = FakeRedis()
    ss._after_fork()
    monkeypatch.setattr(ss, "_off_until", 0.0)
    monkeypatch.setattr(ss, "_redis", lambda: r)
    monkeypatch.setattr(ss, "_ensure_flusher", lambda: None)
    ss.set_stage("identify_molecules")
    yield r
    ss._after_fork()
    ss.set_stage("other")


def test_counts_reach_redis_and_summarize(fake):
    for _ in range(3):
        ss.record("db:chembl_struct@sim", "hit", 0.2)
    ss.record("db:chembl_struct@sim", "error:server_error", 31.0)
    ss.record("db:chembl_struct@sim", "cache_shared")
    ss.flush()
    rows = ss.summarize(ss.window(fake, 600))
    (row,) = rows
    assert row["service"] == "db:chembl_struct@sim" and row["stage"] == "identify_molecules"
    assert row["calls"] == 4 and row["cached"] == 1 and row["errors"] == 1
    assert row["error_share"] == 0.25
    assert row["p50_s"] == 0.3 and row["p95_s"] == 100.0
    assert ss.run_summary()["db:chembl_struct@sim|identify_molecules|hit"] == 3


def test_stage_separates_verification(fake):
    ss.record("http:www.ebi.ac.uk", "ok", 0.1)
    ss.set_stage("verify_results")
    ss.record("http:www.ebi.ac.uk", "http_5xx", 0.1)
    ss.flush()
    rows = {r["stage"]: r for r in ss.summarize(ss.window(fake, 600))}
    assert rows["identify_molecules"]["errors"] == 0
    assert rows["verify_results"]["errors"] == 1


def test_in_flight_is_published_and_cleared(fake):
    with ss.in_flight("db:blast_nr_protein"):
        ss.flush()
        running = ss.running_now(fake)
        assert [r["service"] for r in running] == ["db:blast_nr_protein"]
    ss.flush()
    assert ss.running_now(fake) == []


def test_redis_errors_never_raise_and_trip(monkeypatch):
    ss._after_fork()
    monkeypatch.setattr(ss, "_off_until", 0.0)
    monkeypatch.setattr(ss, "_redis", lambda: Broken())
    monkeypatch.setattr(ss, "_ensure_flusher", lambda: None)
    ss.record("db:x", "hit", 0.1)
    ss.flush()  # must not raise
    assert ss._off_until > time.time()
    ss._after_fork()


def test_without_url_nothing_is_written(monkeypatch):
    monkeypatch.delenv("BAT3_SHARED_CACHE_URL", raising=False)
    ss._client = None
    assert ss._redis() is None
    ss.flush()  # no-op


def test_http_hook_counts_and_passes_through(fake, monkeypatch):
    import requests

    class Resp:
        status_code = 503
        raw = type("Raw", (), {"retries": type("R", (), {"history": (1, 2)})()})()

    sent = []

    def original(self, request, **kw):
        sent.append(request.url)
        return Resp()

    monkeypatch.setattr(requests.Session, "send", original)
    assert ss.install_http_hook()
    assert ss.install_http_hook()  # idempotent
    req = requests.Request("GET", "https://pubchem.ncbi.nlm.nih.gov/rest/x").prepare()
    resp = requests.Session().send(req)
    assert resp.status_code == 503 and sent == [req.url]

    def failing(self, request, **kw):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(requests.Session, "send", failing)
    ss.install_http_hook()
    with pytest.raises(requests.ConnectionError):
        requests.Session().send(req)
    ss.flush()
    (row,) = ss.summarize(ss.window(fake, 600))
    assert row["service"] == "http:pubchem.ncbi.nlm.nih.gov"
    assert row["outcomes"] == {"http_5xx": 1, "error:ConnectionError": 1}
    assert row["retries"] == 2


def test_resolver_lookups_are_counted(fake):
    from src_new.config.loader import RunConfig
    from src_new.identification.base import IdentifierResolutionError, IdentifierResolver

    class R(IdentifierResolver):
        name = "fake_db"
        accepted_signatures = ["smiles"]

        def _is_applicable(self, s):
            return True

        def _resolve_identity(self, s, wd):
            if s == "bad":
                raise IdentifierResolutionError("HTTP Error 500: Internal Server Error")
            if s == "na":
                raise IdentifierResolutionError("no_polymer_payload")
            return ["X1"] if s == "C" else []

        def _resolve_similarity(self, s, wd):
            return []

    r = R(RunConfig())
    assert r.resolve("C") == ["X1"]
    assert r.resolve("CC") == []
    assert r.resolve("bad") is None
    assert r.resolve("na") is None
    ss.flush()
    (row,) = ss.summarize(ss.window(fake, 600))
    assert row["outcomes"] == {"hit": 1, "empty": 1, "error:server_error": 1, "not_applicable": 1}


def test_watchdog_alarms_on_failing_service_and_ncbi_crowd(fake, monkeypatch):
    from src_new.api import alerts, watchdog
    sent = []
    monkeypatch.setattr(alerts, "alarm", lambda key, subject, body, every_s=0: sent.append(key) or True)
    monkeypatch.setattr(ss, "reader", lambda: fake)
    for _ in range(8):
        ss.record("db:chembl_struct@sim", "error:server_error", 1.0)
    for _ in range(4):
        ss.record("db:chembl_struct@sim", "hit", 1.0)
    for _ in range(20):
        ss.record("db:pubchem_struct", "hit", 1.0)
    monkeypatch.setenv("BAT3_NCBI_RUNNING_ALARM", "2")
    with ss.in_flight("db:blast_nr_protein"), ss.in_flight("db:blast_nt@sim"):
        ss.flush()
        watchdog._check_services()
    assert sorted(sent) == ["ncbi-running", "service:db:chembl_struct@sim"]


def test_watchdog_quiet_when_healthy(fake, monkeypatch):
    from src_new.api import alerts, watchdog
    sent = []
    monkeypatch.setattr(alerts, "alarm", lambda *a, **k: sent.append(a) or True)
    monkeypatch.setattr(ss, "reader", lambda: fake)
    for _ in range(5):  # failing, but too few calls to judge
        ss.record("db:chembl_struct@sim", "error:timeout", 1.0)
    with ss.in_flight("db:blast_nr_protein"):
        ss.flush()
        watchdog._check_services()
    assert sent == []
