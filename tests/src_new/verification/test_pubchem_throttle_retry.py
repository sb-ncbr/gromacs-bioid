"""Item-4 correction (user ruling 11-03): robust PubChem live calls.

NCBI throttling (503 PUGREST ServerBusy / 429) is the binding constraint
on annotation A-coverage at fleet scale — c13 evidence: 6,776 HTTP 503 +
561 HTTP 429 vs 8,393 budget_exhausted across 40 subset logs, scaling
with fleet size. The fix keeps annotation_live_fetch TRUE and makes the
live call layer throttle-resilient:

* 503/429 retried up to _PUG_RETRIES (3) tries with backoff honouring
  Retry-After (capped at _PUG_RETRY_AFTER_CAP_S);
* a THROTTLED attempt does NOT consume the per-segment budget — only a
  non-throttle outcome (success / definitive failure) spends one unit;
* every attempt passes the per-process rate limiter (<=1 req/s/pod
  default; config knob annotation_live_min_interval_s);
* W3.3-2 contract unchanged: still failing after retries -> None
  (annotation UNKNOWN), never a silently degraded score.

The shared conftest autouse fixture zeroes the PUG limiter interval for
these tests (no real rate-limit sleeps); backoff sleeps are patched.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from src_new.verification.scorers.pubchem_scorer import (
    _PUG_MIN_INTERVAL_S_DEFAULT,
    _PUG_RETRIES,
    _PUG_RETRY_AFTER_CAP_S,
    _RateLimiter,
    PubChemAnnotationScorer,
)


def _resp(status_code: int, payload: dict | None = None,
          retry_after: str | None = None):
    r = Mock()
    r.status_code = status_code
    r.json.return_value = payload or {}
    r.headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return r


class TestThrottleRetry:
    def test_503_then_success_consumes_one_budget_unit(self) -> None:
        """A throttled-then-successful call retries and spends exactly one
        budget unit (the intermediate 503 is free)."""
        s = PubChemAnnotationScorer()
        s.configure(live_fetch=True, timeout_s=3.0, min_interval_s=0.0)
        s.begin_segment(5)
        ok = _resp(200, {"PropertyTable": {"Properties": [
            {"CanonicalSMILES": "O", "MolecularFormula": "H2O"}]}})
        with patch("src_new.verification.scorers.pubchem_scorer.requests.get",
                   side_effect=[_resp(503), _resp(503), ok]) as get, \
             patch("src_new.verification.scorers.pubchem_scorer.time.sleep") \
                as sleep:
            data = s._live_get_json("https://pubchem.example/x")
        assert data is not None
        assert get.call_count == 3  # 2 throttled tries + success
        assert sleep.call_count == 2  # backoff between tries
        assert s._remaining == 4  # exactly ONE unit consumed

    def test_429_all_tries_throttled_is_free(self) -> None:
        """All 3 tries throttled -> None with the budget untouched (a
        throttled attempt never got a fair shot at a real response)."""
        s = PubChemAnnotationScorer()
        s.configure(live_fetch=True, timeout_s=3.0, min_interval_s=0.0)
        s.begin_segment(5)
        with patch("src_new.verification.scorers.pubchem_scorer.requests.get",
                   side_effect=[_resp(429, retry_after="1")] * _PUG_RETRIES), \
             patch("src_new.verification.scorers.pubchem_scorer.time.sleep"):
            data = s._live_get_json("https://pubchem.example/x")
        assert data is None
        assert s._remaining == 5  # nothing consumed

    def test_retry_after_honoured_and_capped(self) -> None:
        """Backoff = Retry-After header when present, capped at
        _PUG_RETRY_AFTER_CAP_S."""
        s = PubChemAnnotationScorer()
        s.configure(live_fetch=True, timeout_s=3.0, min_interval_s=0.0)
        s.begin_segment(5)
        with patch("src_new.verification.scorers.pubchem_scorer.requests.get",
                   side_effect=[_resp(503, retry_after="3600"),
                               _resp(429),
                               _resp(200, {})]), \
             patch("src_new.verification.scorers.pubchem_scorer.time.sleep") \
                as sleep:
            s._live_get_json("https://pubchem.example/x")
        delays = [c.args[0] for c in sleep.call_args_list]
        assert delays[0] == _PUG_RETRY_AFTER_CAP_S  # 3600 capped to 10
        assert 1.0 <= delays[1] <= _PUG_RETRY_AFTER_CAP_S  # no header: >= 1

    def test_non_throttle_failure_consumes_budget(self) -> None:
        """A definitive network failure spends one unit (only throttled
        attempts are free)."""
        s = PubChemAnnotationScorer()
        s.configure(live_fetch=True, timeout_s=3.0, min_interval_s=0.0)
        s.begin_segment(5)
        with patch("src_new.verification.scorers.pubchem_scorer.requests.get",
                   side_effect=OSError("refused")):
            data = s._live_get_json("https://pubchem.example/x")
        assert data is None
        assert s._remaining == 4

    def test_503_not_retried_beyond_three_tries(self) -> None:
        """Exactly _PUG_RETRIES tries total, then the W3.3-2 contract:
        None."""
        s = PubChemAnnotationScorer()
        s.configure(live_fetch=True, timeout_s=3.0, min_interval_s=0.0)
        s.begin_segment(5)
        with patch("src_new.verification.scorers.pubchem_scorer.requests.get",
                   side_effect=[_resp(503)] * 10) as get, \
             patch("src_new.verification.scorers.pubchem_scorer.time.sleep"):
            data = s._live_get_json("https://pubchem.example/x")
        assert data is None
        assert get.call_count == _PUG_RETRIES

    def test_score_returns_none_when_all_retries_throttled(self) -> None:
        """End-to-end W3.3-2: mirror hit + needed fill throttled to death
        -> UNKNOWN (None), never the mirror floor 70."""
        from src_new.verification.scorers import pubchem_scorer as mod

        class _Row:
            smiles = "O"
            inchikey = "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
            molecular_formula = "H2O"
            formula_hill = "H2O"

        class _DB:
            def by_cid(self, cid):
                return _Row()

            def by_inchikey(self, ik):
                return _Row()

        with patch.object(mod, "_local_db", lambda: _DB()), \
             patch.object(mod.requests, "get",
                          side_effect=[_resp(503)] * 2 * _PUG_RETRIES), \
             patch.object(mod.time, "sleep"):
            s = PubChemAnnotationScorer()
            s.begin_segment(25)
            quality = s.score("962", "PUBCHEM_CID")
        assert quality is None


class TestRateLimiter:
    def test_limiter_spaces_requests(self) -> None:
        """Two waits inside the interval -> the second sleeps ~interval."""
        import time as _time
        lim = _RateLimiter()
        lim.set_interval(0.05)
        lim.wait()  # first is free
        t0 = _time.monotonic()
        lim.wait()  # second must sleep ~0.05
        assert _time.monotonic() - t0 >= 0.04

    def test_limiter_zero_disables(self) -> None:
        lim = _RateLimiter()
        lim.set_interval(0)
        lim.wait()
        lim.wait()  # no sleep, no raise

    def test_default_interval_is_one_per_second(self) -> None:
        assert _PUG_MIN_INTERVAL_S_DEFAULT == 1.0

    def test_configure_sets_limiter_interval(self) -> None:
        s = PubChemAnnotationScorer()
        s.configure(live_fetch=True, timeout_s=3.0, min_interval_s=0.25)
        import src_new.verification.scorers.pubchem_scorer as mod
        # module-level limiter carries the configured interval
        assert mod._PUG_LIMITER._min_interval_s == 0.25
