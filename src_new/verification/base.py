"""Base classes for the verification pipeline."""

from __future__ import annotations

import functools
import threading
from abc import ABC, abstractmethod

from .models import VerificationScore, AnnotationQuality


# ---------------------------------------------------------------------------
# W3.2 A7: run-scoped fetch memo.
#
# Production evidence (W3 package, P23 results.log at b954adc33): the same
# InChIKey (XUVWGNKSYIFPIN-UHFFFAOYSA-N) was fetched over the network 3
# times, ~5 min per attempt on the firewalled workstation — once per segment
# that mentioned it, because each segment's verify worker builds a fresh
# VerificationManager over fresh fetcher instances. Memoize fetch results
# per (fetcher class, ident type, identifier) for the lifetime of one run;
# clear_run_memo() is called at each verify_results stage start.
#
# c13 corpus fix (F1b): the memo is THREAD-LOCAL, not a module global. Celery
# runs one task per worker thread and the verify stage spawns a fresh pool
# per run (executor.parallel.run_with_thread_pool), so a thread-local dict
# is per-run by construction: concurrent runs in one process neither read
# each other's memo nor wipe it via clear(). Negative results ARE cached,
# but only definitive ones: callers raise TransientFetchError for 5xx/
# timeouts, which propagates past run_memo_put below (never cached).
# ---------------------------------------------------------------------------

_RUN_MEMO_LOCAL = threading.local()


def _run_memo_dict() -> dict:
    d = getattr(_RUN_MEMO_LOCAL, "d", None)
    if d is None:
        d = {}
        _RUN_MEMO_LOCAL.d = d
    return d


def run_memo_get(key: tuple) -> object:
    return _run_memo_dict().get(key, _MEMO_MISS)


def run_memo_put(key: tuple, value: str | None) -> None:
    _run_memo_dict()[key] = value


def clear_run_memo() -> None:
    _run_memo_dict().clear()


class TransientFetchError(Exception):
    """A fetch failed transiently (5xx, timeout, connection error) after
    retries. Unlike a definitive miss (404), this must NEVER be memoized or
    treated as "no sequence": callers propagate it so the result is left
    unmeasured rather than silently zeroed (corpus c13 finding: a UniProt
    500 memoized as None zeroed the similarity term for the whole run)."""


_MEMO_MISS = object()


def memoized_fetch(fetch_method):
    """Decorate a SignatureFetcher.fetch implementation with the run memo."""

    @functools.wraps(fetch_method)
    def wrapper(self, identifier, ident_type):
        key = (type(self).__name__, (ident_type or "").upper(),
               str(identifier).strip())
        hit = run_memo_get(key)
        if hit is not _MEMO_MISS:
            return hit
        value = fetch_method(self, identifier, ident_type)
        run_memo_put(key, value)
        return value

    return wrapper


class VerificationWorker(ABC):
    """Abstract base class for verification workers.
    
    Each worker implements verification for a specific signature/identifier type pair.
    """
    
    @abstractmethod
    def is_applicable(self, signature_type: str, ident_type: str) -> bool:
        """Check if this worker can verify the given signature and identifier types."""
        pass
    
    @abstractmethod
    def verify(
        self,
        signature: str,
        identifier: str,
        ident_type: str,
        canonical_signature: str | None = None,
        signature_type: str | None = None,
    ) -> VerificationScore | None:
        """Verify a hit by comparing simulation signature against canonical signature.

        Args:
            signature: The signature extracted from simulation.
            identifier: The identifier (e.g., database ID).
            ident_type: The type of identifier (e.g., "PUBCHEM_CID").
            canonical_signature: Optional pre-fetched canonical signature for comparison.
            signature_type: Optional canonical signature type (e.g.,
                "residue_sequence_nucleotide"); only the sequence worker
                uses it (wave-7 orientation handling). Others ignore it.

        Returns:
            VerificationScore if verification was performed, None if not applicable.
            Non-verification is a normal outcome, not an error.
        """
        pass


class SignatureFetcher(ABC):
    """Abstract base class for fetching canonical signatures from databases."""
    
    @abstractmethod
    def supports(self, ident_type: str) -> bool:
        """Check if this fetcher supports the given identifier type."""
        pass
    
    @abstractmethod
    def fetch(self, identifier: str, ident_type: str) -> str | None:
        """Fetch the canonical signature for an identifier.
        
        Returns:
            The canonical signature string, or None if not found.
            None is a normal outcome, not an error.
        """
        pass


def fetch_failure_reason(exc: Exception) -> str:
    """Status-bearing failure tag for the annotation health record (W3.3 A.3)."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return f"HTTP {status}" if status is not None else type(exc).__name__


class AnnotationQualityScorer(ABC):
    """Abstract base class for scoring annotation quality."""
    
    @abstractmethod
    def supports(self, ident_type: str) -> bool:
        """Check if this scorer supports the given identifier type."""
        pass
    
    @abstractmethod
    def score(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
        """Score the annotation quality for an identifier.
        
        Returns:
            AnnotationQuality if scoring was performed, None if not applicable.
            None is a normal outcome, not an error.
        """
        pass
