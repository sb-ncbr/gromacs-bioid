"""PubChem annotation quality scorer."""

from __future__ import annotations

import os
import threading
import time

import requests

from ..base import AnnotationQualityScorer, fetch_failure_reason
from ..models import AnnotationQuality

import logging

logger = logging.getLogger("annotation")

_LOCAL_DB = None
_LOCAL_DB_READY = False

# v3.142 (1c): single source of truth for the PubChem signal schema (total 100).
_PUBCHEM_SIGNAL_POINTS = {
    "base": 20.0,            # record exists (base points)
    "canonical_smiles": 20.0,
    "isomeric_smiles": 15.0,
    "molecular_formula": 15.0,
    "iupac_name": 15.0,
    "synonyms": 15.0,
}


def _pubchem_schema_score(signals: list[str]) -> float:
    """Score = base + sum of achieved signal points (uniform denominator)."""
    return _PUBCHEM_SIGNAL_POINTS["base"] + sum(
        _PUBCHEM_SIGNAL_POINTS[s] for s in set(signals))


def _pug_props_url(identifier: str, is_inchikey: bool) -> str:
    kind = "inchikey" if is_inchikey else "cid"
    # D-07: current PUG property names (legacy CanonicalSMILES/
    # IsomericSMILES requests now return renamed columns — see
    # _extract_pug_signals).
    return (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/{kind}/"
            f"{identifier}/property/ConnectivitySMILES,SMILES,IUPACName,MolecularFormula/JSON")


def _pug_synonyms_url(identifier: str, is_inchikey: bool) -> str:
    kind = "inchikey" if is_inchikey else "cid"
    return (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/{kind}/"
            f"{identifier}/synonyms/JSON")


def _pug_smiles_signals(props: dict) -> tuple[bool, bool]:
    """(has_connectivity_smiles, has_isomeric_smiles) from a PUG Properties
    record. Live-verified 2026-10-23 on CID 702: current responses carry
    'ConnectivitySMILES' and 'SMILES'; the historic 'CanonicalSMILES' and
    'IsomericSMILES' keys are read as fallbacks only."""
    has_canonical = bool(props.get("ConnectivitySMILES")
                         or props.get("CanonicalSMILES"))
    has_isomeric = bool(props.get("SMILES") or props.get("IsomericSMILES"))
    return has_canonical, has_isomeric


# Item-4 correction (user ruling 11-03): NCBI throttling (503 PUGREST
# ServerBusy, 429) is the binding constraint on annotation A-coverage at
# fleet scale, not budget. Robust live calls instead of disabling fetch:
_PUG_RETRIES = 3                 # total tries per call on 503/429
_PUG_RETRY_AFTER_CAP_S = 10.0   # Retry-After honoured but bounded
_PUG_MIN_INTERVAL_S_DEFAULT = 1.0  # <=1 req/s/pod default


class _RateLimiter:
    """Per-process PUG rate limiter (thread-safe). NCBI's published
    guidance is <=5 req/s; a pod-local 1 req/s default (config knob
    annotation_live_min_interval_s) keeps the fleet far below the shared
    throttle ceiling. Interval 0 disables."""

    def __init__(self) -> None:
        self._min_interval_s = _PUG_MIN_INTERVAL_S_DEFAULT
        self._lock = threading.Lock()
        self._next_ok = 0.0

    def set_interval(self, min_interval_s: float) -> None:
        with self._lock:
            self._min_interval_s = max(0.0, float(min_interval_s))

    def wait(self) -> None:
        with self._lock:
            interval = self._min_interval_s
            if interval <= 0:
                return
            now = time.monotonic()
            delay = max(0.0, self._next_ok - now)
            self._next_ok = max(now, self._next_ok) + interval
        if delay > 0:
            time.sleep(delay)


_PUG_LIMITER = _RateLimiter()


def _retry_after_s(response) -> float:
    """Backoff for a throttled attempt: honour the Retry-After header when
    present, else exponential (2^attempt); capped so the worst case stays
    bounded (3 tries x cap + limiter intervals per call)."""
    try:
        v = float(response.headers.get("Retry-After", ""))
    except (TypeError, ValueError):
        v = 0.0
    return min(max(v, 1.0), _PUG_RETRY_AFTER_CAP_S)


def _local_db():
    """Lazy per-process handle to the local PubChem mirror (None when absent).

    Same pattern as verification/fetchers/compound_fetcher._local_db:
    path override via PUBCHEM_LOCAL_DB env var (tests, staging).

    2026-09-25 spin-class: per-candidate PUG HTTP calls (2x timeout=10s each)
    were the verify-stage wall-stall driver after the cluster egress got
    rate-limited by NCBI; the local mirror answers in ~1ms instead.
    """
    global _LOCAL_DB, _LOCAL_DB_READY
    if not _LOCAL_DB_READY:
        path = os.environ.get(
            "PUBCHEM_LOCAL_DB", "/app/databases/pubchem/current/pubchem.sqlite"
        )
        try:
            from ...molecules.pubchem_db import PubChemDB

            db = PubChemDB(path)
            if db.exists():
                _LOCAL_DB = db
        except Exception:
            _LOCAL_DB = None
        _LOCAL_DB_READY = True
    return _LOCAL_DB


class PubChemAnnotationScorer(AnnotationQualityScorer):
    """Scores annotation quality for PubChem-compound identifiers.

    (v3.142 1c) Uniform signal schema — total 100 — applied identically
    regardless of store: base 20 + canonical_smiles 20 + isomeric_smiles 15
    + molecular_formula 15 + iupac_name 15 + synonyms 15. The local mirror
    structurally supplies the first four; the item-4 extension (11-03,
    CID-IUPAC.gz + CID-Synonym-filtered.gz) additionally supplies
    iupac_name/synonyms locally on extended mirrors — legacy mirrors
    live-fill those two as before.

    (W3.3 item 2, user directive 2026-11-01 — supersedes the "floor is not
    a cap" note) Determinism contract for the same identifier across runs:
      * live fetch ON (default, config verification.annotation_live_fetch)
        + budget remaining: missing signals are filled from PUG. A NEEDED
        call that cannot complete (network failure / rate limit / budget
        exhausted) makes the schema unprovable -> None (annotation UNKNOWN,
        confidence blend re-weights). Never a silently degraded 70/85.
      * a SUCCEEDED live call whose record genuinely lacks the signal is a
        legitimately absent signal and keeps the real (lower) score.
      * live fetch OFF: the mirror floor (70) is the deterministic policy
        answer.
    Successful scores are cached per (ident_type, identifier) (D-07); Nones
    are never cached so a transient failure re-attempts on a later segment.
    Supports PUBCHEM_CID and (via the mirror's inchikey column / PUG inchikey
    endpoints) INCHIKEY.
    """

    def __init__(self) -> None:
        self._live_fetch = True
        self._timeout_s = 3.0
        self._remaining = 0
        # Red-team batch-4 (D-07 position-independence): records are
        # immutable, so a successful score is cached per (ident_type,
        # identifier) and served verbatim on repeats — identical records can
        # no longer decay with window position / budget consumption. The
        # cache deliberately survives begin_segment (cross-segment repeats
        # are the same record); transient None failures are never cached.
        self._score_cache: dict[tuple[str, str], AnnotationQuality] = {}

    def configure(self, *, live_fetch: bool, timeout_s: float,
                  min_interval_s: float = _PUG_MIN_INTERVAL_S_DEFAULT) -> None:
        """Per-manager wiring (v3.142): live-fetch policy from config.
        Item-4 correction (11-03): min_interval_s is the per-process PUG
        rate limit (config knob annotation_live_min_interval_s, default
        1 req/s/pod)."""
        self._live_fetch = bool(live_fetch)
        self._timeout_s = float(timeout_s)
        _PUG_LIMITER.set_interval(min_interval_s)

    def begin_segment(self, budget: int) -> None:
        """Re-arm the per-segment live-call budget (manager calls once per
        segment)."""
        self._remaining = int(budget)

    def _live_get_json(self, url: str) -> dict | None:
        """One budgeted live call with throttle-resilient retry (item-4
        correction, user ruling 11-03). Returns parsed JSON or None (never
        raises: budget exhaustion / network failure are silent fallbacks,
        but W3.3 A.3 tags every incomplete attempt for the per-run health
        record). Semantics:

        * 503/429: retried up to _PUG_RETRIES tries with backoff
          honouring Retry-After (capped). A THROTTLED attempt does NOT
          consume the per-segment budget — only a non-throttle outcome
          (success / definitive HTTP failure / network exception) spends
          one unit.
        * Every attempt passes the per-process rate limiter (<=1 req/s
          per pod default; config knob annotation_live_min_interval_s).
        * W3.3-2 contract unchanged: still failing after retries -> None
          (annotation UNKNOWN, never a silently degraded score)."""
        if not self._live_fetch or self._remaining <= 0:
            logger.info("ann_fetch_failed service=pubchem reason=budget_exhausted url=%s",
                        url.rsplit("/", 3)[-3] if "/" in url else url)
            return None
        short_url = url.rsplit("/", 3)[-3] if "/" in url else url
        for attempt in range(1, _PUG_RETRIES + 1):
            _PUG_LIMITER.wait()
            try:
                r = requests.get(url, timeout=self._timeout_s)
            except Exception as exc:
                self._remaining -= 1
                logger.warning("ann_fetch_failed service=pubchem reason=%s url=%s",
                               fetch_failure_reason(exc), short_url)
                return None
            if r.status_code == 429 or r.status_code >= 500:
                if attempt < _PUG_RETRIES:
                    # intermediate throttle: retried, not a failure record
                    logger.info("ann_fetch_throttled service=pubchem "
                                "reason=HTTP %d attempt=%d/%d retrying url=%s",
                                r.status_code, attempt, _PUG_RETRIES,
                                short_url)
                    time.sleep(_retry_after_s(r))
                    continue
                # retries exhausted while throttled: budget NOT consumed
                # (the attempt never got a fair shot at a real response)
                logger.warning("ann_fetch_failed service=pubchem "
                               "reason=HTTP %d throttled tries=%d url=%s",
                               r.status_code, _PUG_RETRIES, short_url)
                return None
            self._remaining -= 1
            if r.status_code != 200:
                logger.warning("ann_fetch_failed service=pubchem "
                               "reason=HTTP %d url=%s",
                               r.status_code, short_url)
                return None
            try:
                return r.json()
            except Exception as exc:
                logger.warning("ann_fetch_failed service=pubchem reason=%s url=%s",
                               fetch_failure_reason(exc), short_url)
                return None
        return None

    def supports(self, ident_type: str) -> bool:
        """Check if this scorer supports the given identifier type."""
        return ident_type in ("PUBCHEM_CID", "INCHIKEY", "INCHI_KEY")

    def score(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
        """Score the annotation quality for a PubChem CID.

        Caching wrapper around _score_uncached (red-team batch-4, D-07): a
        record scores once and repeats verbatim — identical records can no
        longer decay with window position. Transient None failures are not
        cached (a retry recomputes them).
        """
        if not self.supports(ident_type):
            return None
        key = (ident_type, str(identifier))
        cached = self._score_cache.get(key)
        if cached is not None:
            return cached
        result = self._score_uncached(identifier, ident_type)
        if result is not None:
            self._score_cache[key] = result
        return result

    def _score_uncached(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
        """Score the annotation quality for a PubChem CID (fetch path).
        
        Args:
            identifier: PubChem CID (e.g., "962").
            ident_type: Should be "PUBCHEM_CID".
            
        Returns:
            AnnotationQuality with score 0-100 and signals found.
            Returns low score (0.0) on any failure without raising.

        Scoring note (v3.142 1c, supersedes the 2026-09-25 cap note): the
        local-mirror path yields base 20 + canonical_smiles 20 +
        isomeric_smiles 15 + molecular_formula 15 = 70 (mirror stores no
        IUPAC/synonyms by design). With live-fetch enabled and budget left,
        the two missing signals are filled from PUG, so the store floor is
        not a cap: both stores can reach the full 100-signal schema.
        """
        if not self.supports(ident_type):
            return None

        is_inchikey = ident_type in ("INCHIKEY", "INCHI_KEY")
        cid = identifier

        # Local PubChem mirror first: ~1ms, immune to PUG rate-limiting.
        db = _local_db()
        if db is not None:
            try:
                row = (db.by_inchikey(identifier) if is_inchikey
                       else db.by_cid(cid))
            except Exception:
                row = None
            if row is not None:
                signals = []
                if row.smiles:
                    # Mirror stores isomeric SMILES (connectivity superset of
                    # PUG CanonicalSMILES) -> both structure signals apply.
                    signals.append("canonical_smiles")
                    signals.append("isomeric_smiles")
                if row.formula_hill:
                    signals.append("molecular_formula")
                # Item-4 correction (user ruling 11-03): the extended mirror
                # (CID-IUPAC.gz + CID-Synonym-filtered.gz) supplies the two
                # signals live fetch existed for — locally, ~1ms, immune to
                # NCBI throttling. Legacy mirrors return None/False here and
                # the live fill below runs as before. getattr keeps duck-typed
                # row stubs (and any pre-extension row object) working.
                if getattr(row, "iupac_name", None):
                    signals.append("iupac_name")
                if getattr(row, "has_synonyms", False):
                    signals.append("synonyms")
                # W3.3 item 2 (determinism): with live fetch enabled the
                # reachable score is the FULL schema — an incomplete fill
                # (network failure / rate limit / budget exhausted) is
                # annotation UNKNOWN (None, re-weighted by the blend), never
                # a silently degraded 70/85 that re-orders top-1 for the
                # same identifier across runs (T02a/b/c CID 137895 evidence).
                # With live fetch disabled the mirror floor is the documented
                # deterministic policy answer.
                if self._live_fetch:
                    incomplete = self._live_fill(identifier, is_inchikey, signals,
                                                 "iupac_name" not in signals,
                                                 "synonyms" not in signals)
                    if incomplete:
                        return None
                # re-sum from achieved signals (single source of truth)
                return AnnotationQuality(
                    database="pubchem",
                    score=min(_pubchem_schema_score(signals), 100.0),
                    signals=signals,
                )

        # Mirror miss or mirror absent: full PUG path (budgeted live calls).
        props_data = self._live_get_json(
            _pug_props_url(identifier, is_inchikey))
        if props_data is None:
            # Live fetch disabled / budget exhausted / network failure:
            # nothing provable locally about this record.
            return None
        
        # v3.143 (D-17): the signal extraction below used to appear
        # twice in a row; the first copy was overwritten before use
        # (dead code, removed).
        signals = []
        score = 20.0  # Base points for having the entry
        
        # Extract properties from response
        prop_list = props_data.get("PropertyTable", {}).get("Properties", [])
        if prop_list and len(prop_list) > 0:
            props = prop_list[0]
            
            # Check canonical_smiles / isomeric_smiles (D-07: PUG renamed
            # the keys; read via the shared extractor)
            has_canonical, has_isomeric = _pug_smiles_signals(props)
            if has_canonical:
                signals.append("canonical_smiles")
                score += 20.0
            if has_isomeric:
                signals.append("isomeric_smiles")
                score += 15.0
            
            # Check iupac_name
            iupac_name = props.get("IUPACName", "")
            if iupac_name:
                signals.append("iupac_name")
                score += 15.0
            
            # Check molecular_formula
            mol_formula = props.get("MolecularFormula", "")
            if mol_formula:
                signals.append("molecular_formula")
                score += 15.0
        
        # Fetch synonyms (budgeted live call). W3.3 item 2: a FAILED call
        # (timeout/rate limit/budget) makes the schema unprovable -> None;
        # a SUCCEEDED call with an empty synonym list is a legitimately
        # absent signal and keeps the real (lower) score.
        synonyms_data = self._live_get_json(_pug_synonyms_url(identifier, is_inchikey))
        if synonyms_data is None:
            return None
        info_list = synonyms_data.get("InformationList", {}).get("Information", [])
        if info_list and len(info_list) > 0:
            synonyms = info_list[0].get("Synonym", [])
            if synonyms and len(synonyms) > 0:
                signals.append("synonyms")
                score += 15.0
        
        return AnnotationQuality(
            database="pubchem",
            score=min(score, 100.0),
            signals=signals,
        )

    def _live_fill(self, identifier: str, is_inchikey: bool, signals: list,
                   missing_iupac: bool, missing_syn: bool) -> bool:
        """Fill mirror-missing signals from PUG (bounded live calls).

        Mutates `signals` in place with whatever PUG proves.

        Returns True when a NEEDED live call could not complete (network
        failure, rate limit, or budget exhausted) — the caller then treats
        the score as UNKNOWN (None). A succeeded call whose payload lacks
        the signal is a legitimately absent signal, not an incompleteness.
        """
        incomplete = False
        if missing_iupac:
            props_data = self._live_get_json(_pug_props_url(identifier, is_inchikey))
            if props_data is None:
                incomplete = True
            else:
                prop_list = props_data.get("PropertyTable", {}).get("Properties", [])
                if prop_list:
                    props = prop_list[0]
                    if props.get("IUPACName"):
                        signals.append("iupac_name")
                    # free bonus fill (PUG carries these anyway); mirror rows
                    # already hold them, so guard against duplication.
                    has_canonical, has_isomeric = _pug_smiles_signals(props)
                    if has_canonical and "canonical_smiles" not in signals:
                        signals.append("canonical_smiles")
                    if has_isomeric and "isomeric_smiles" not in signals:
                        signals.append("isomeric_smiles")
                    if props.get("MolecularFormula") and "molecular_formula" not in signals:
                        signals.append("molecular_formula")
        if missing_syn:
            synonyms_data = self._live_get_json(_pug_synonyms_url(identifier, is_inchikey))
            if synonyms_data is None:
                incomplete = True
            else:
                info_list = synonyms_data.get("InformationList", {}).get("Information", [])
                if info_list and info_list[0].get("Synonym"):
                    signals.append("synonyms")
        return incomplete
