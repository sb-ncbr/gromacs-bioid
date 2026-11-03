"""c13 fix F1a: UniProt sequence fetch = local BLAST DBs first, REST with
retry+backoff, pod-local persistent cache (successes only).

Local coverage measured on the 397-sample hit tables (b13 image):
6,975/6,975 distinct accessions resolve from /app/databases/swissprot —
REST becomes the fallback, not the primary source, and a 500 storm can no
longer zero similarity terms fleet-wide.
"""

from __future__ import annotations

import os
import subprocess
import sys
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pytest

from src_new.verification import base as vbase
from src_new.verification.fetchers import sequence_fetcher as sf


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setattr(sf, "_SEQ_CACHE", str(tmp_path / "seqcache"))
    vbase.clear_run_memo()
    yield
    vbase.clear_run_memo()


def _fetcher():
    return sf.SequenceSignatureFetcher()


def _fasta(seq):
    return f">sp|P06802.1|NAME\n{seq}\n"


def test_local_db_hit_skips_rest_and_caches():
    ok = subprocess.CompletedProcess([], 0, stdout="  MKTAYIAKQRQ\nISFVKSHFSRQ  \n", stderr="")
    with mock.patch.object(sf.subprocess, "run", return_value=ok) as m_run, \
         mock.patch.object(sf.requests, "get", side_effect=AssertionError("REST must not be called")):
        f = _fetcher()
        seq = f.fetch("P06802", "UNIPROT_ID")
    assert seq == "MKTAYIAKQRQISFVKSHFSRQ"
    assert m_run.call_count == 1
    assert os.path.exists(sf._seqcache_path("P06802")), "success must persist to the pod-local cache"
    # second fetch: cache hit, no subprocess at all
    with mock.patch.object(sf.subprocess, "run", side_effect=AssertionError("cache must serve")):
        assert _fetcher().fetch("P06802", "UNIPROT_ID") == seq


def test_local_miss_falls_back_to_rest_200():
    miss = subprocess.CompletedProcess([], 1, stdout="", stderr="no entries found")
    resp = mock.Mock(status_code=200, text=_fasta("MKTAY"))
    with mock.patch.object(sf.subprocess, "run", return_value=miss), \
         mock.patch.object(sf.requests, "get", return_value=resp) as m_get:
        assert _fetcher().fetch("P06802", "UNIPROT_ID") == "MKTAY"
    assert m_get.call_count == 1
    assert os.path.exists(sf._seqcache_path("P06802"))


def test_rest_404_is_definitive_none_and_memoized():
    miss = subprocess.CompletedProcess([], 1, stdout="", stderr="")
    resp = mock.Mock(status_code=404, text="")
    f = _fetcher()
    with mock.patch.object(sf.subprocess, "run", return_value=miss), \
         mock.patch.object(sf.requests, "get", return_value=resp) as m_get:
        assert f.fetch("P00000", "UNIPROT_ID") is None
        assert f.fetch("P00000", "UNIPROT_ID") is None
    assert m_get.call_count == 1, "definitive 404 must be memoizable"
    assert not os.path.exists(sf._seqcache_path("P00000")), "misses are never persisted"


def test_rest_500_retries_then_succeeds():
    miss = subprocess.CompletedProcess([], 1, stdout="", stderr="")
    bad = mock.Mock(status_code=500, text="")
    good = mock.Mock(status_code=200, text=_fasta("MKTAY"))
    with mock.patch.object(sf.subprocess, "run", return_value=miss), \
         mock.patch.object(sf.requests, "get", side_effect=[bad, bad, good]) as m_get, \
         mock.patch.object(sf.time, "sleep"):
        assert _fetcher().fetch("P06802", "UNIPROT_ID") == "MKTAY"
    assert m_get.call_count == 3


def test_rest_500_exhausted_raises_transient_and_is_never_memoized():
    import requests as real_requests
    miss = subprocess.CompletedProcess([], 1, stdout="", stderr="")
    bad = mock.Mock(status_code=500, text="")
    f = _fetcher()
    with mock.patch.object(sf.subprocess, "run", return_value=miss), \
         mock.patch.object(sf.requests, "get", side_effect=[bad, bad, bad]), \
         mock.patch.object(sf.time, "sleep"):
        with pytest.raises(vbase.TransientFetchError):
            f.fetch("P06802", "UNIPROT_ID")
        # nothing cached in the run memo for a transient outage
        key = ("SequenceSignatureFetcher", "UNIPROT_ID", "P06802")
        assert vbase.run_memo_get(key) is vbase._MEMO_MISS
        # timeout path also raises
        with mock.patch.object(sf.requests, "get",
                               side_effect=real_requests.Timeout("boom")):
            with pytest.raises(vbase.TransientFetchError):
                f.fetch("P06803", "UNIPROT_ID")
    assert not os.path.exists(sf._seqcache_path("P06802"))


def test_rest_504_is_transient_not_definitive():
    """Reviewer fix (c13 re-check): EVERY 5xx and 429 is transient — a 504
    (or any other 5xx) must never be memoized as a definitive None miss."""
    miss = subprocess.CompletedProcess([], 1, stdout="", stderr="")
    bad = mock.Mock(status_code=504, text="")
    f = _fetcher()
    with mock.patch.object(sf.subprocess, "run", return_value=miss), \
         mock.patch.object(sf.requests, "get", side_effect=[bad, bad, bad]), \
         mock.patch.object(sf.time, "sleep"):
        with pytest.raises(vbase.TransientFetchError):
            f.fetch("P06802", "UNIPROT_ID")
    key = ("SequenceSignatureFetcher", "UNIPROT_ID", "P06802")
    assert vbase.run_memo_get(key) is vbase._MEMO_MISS, \
        "a 504 must never enter the run memo as a definitive miss"


def test_seq_cache_write_is_atomic(monkeypatch, tmp_path):
    """Reviewer fix (c13 re-check): the persistent cache write is atomic
    (unique tmp + os.replace) — two threads in one pod can otherwise read a
    half-written file and score a truncated sequence."""
    import threading
    real_replace = os.replace
    replaces = []

    monkeypatch.setattr(sf, "_SEQ_CACHE", str(tmp_path))
    monkeypatch.setattr(os, "replace",
                        lambda a, b: (replaces.append((str(a), str(b))), real_replace(a, b))[1])

    errors = []

    def writer(name):
        try:
            for i in range(50):
                sf._seqcache_write("ACC", "M" * 100)
        except Exception as e:  # pragma: no cover
            errors.append(e)

    ts = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors
    assert replaces, "writes must go through os.replace"
    # every visible cache file is a COMPLETE write: never a .tmp leftover
    assert (tmp_path / "ACC.seq").read_text() == "M" * 100
    leftovers = [p for p in tmp_path.iterdir() if ".tmp." in p.name]
    assert not leftovers, f"stale tmp files: {leftovers}"
    # each thread wrote a UNIQUE tmp name (no clobbering each other's write)
    tmp_names = [a for a, _ in replaces]
    assert len(set(tmp_names)) >= 4
