"""Resolver outcomes that mean "does not apply here", not "failed".

A resolver that declines its input (an RCSB structure search given a pure
nucleic acid, which RCSB cannot search; an mmCIF polymer search given a small
molecule) reports a reason
string through the same error channel as a real failure (HTTP error,
timeout, exception). Shown as `identifier_resolver_failed` warnings they
were most of all warnings and taught users to ignore warnings (2026-11-17).

New runs record them under identification/_meta/not_applicable/<segment>
instead of as warnings; readers of older runs drop the same entries with
is_not_applicable_warning(). The stage_errors record keeps everything.
"""
from __future__ import annotations

from typing import Any

#: Reason strings resolvers return when they decline the input (substring match).
NOT_APPLICABLE_REASONS = (
    "na_mode_unsupported",          # pdb_struct.py, mmcif.py: no RCSB structure search for pure nucleic acids
    "no_polymer_payload",           # mmcif.py: small molecule, no polymer to search
    "H-family not applicable",      # hfamily.py: formula without hydrogen
)


def is_not_applicable(reason: Any) -> bool:
    text = str(reason or "")
    return any(r in text for r in NOT_APPLICABLE_REASONS)


def is_not_applicable_warning(warning: Any) -> bool:
    """An identifier_resolver_failed warning (of an older run) that is really a skip."""
    return (isinstance(warning, dict)
            and warning.get("code") == "identifier_resolver_failed"
            and is_not_applicable(warning.get("message")))


def user_warnings(warnings: Any) -> list:
    """The run's warnings without not-applicable resolver outcomes."""
    return [w for w in (warnings or []) if not is_not_applicable_warning(w)]


# -- why a lookup failed (2026-11-18) ------------------------------------------
# One classification for the service measurements (service_stats.py), the
# "incomplete run" flag and automatic retries. Retryable = another attempt
# later can succeed: the remote service was down, busy or slow, or the stage
# ran out of time. A local BLAST/Foldseek timeout is not retryable (it would
# time out again), nor is a rejected query.

RETRYABLE = frozenset({"rate_limited", "server_error", "timeout", "connection", "budget"})

_LOCAL_TIMEOUT = ("BLAST timed out", "Foldseek local search timed out")
_RATE_LIMITED = ("429", "Too Many Requests", "PUGREST.ServerBusy", "ServerBusy")
_SERVER_ERROR = ("HTTP 5", "HTTP Error 5", "Internal Server Error", "Bad Gateway",
                 "Service Unavailable", "Gateway Time", "_unavailable: HTTP 5",
                 "PUGREST.Unknown", "PUGREST.Timeout")
_TIMEOUT = ("timed out", "Timeout", "timeout")
_CONNECTION = ("Connection", "connection", "reset by peer", "Name or service not known",
               "Temporary failure in name resolution", "Max retries exceeded",
               "RemoteDisconnected", "SSLError", "EOF occurred")


def failure_class(reason: Any) -> str:
    """not_applicable | local_timeout | budget | rate_limited | server_error |
    timeout | connection | other."""
    text = str(reason or "")
    if is_not_applicable(text):
        return "not_applicable"
    if any(s in text for s in _LOCAL_TIMEOUT):
        return "local_timeout"
    if "stage_time_budget" in text:
        return "budget"
    if any(s in text for s in _RATE_LIMITED):
        return "rate_limited"
    if any(s in text for s in _SERVER_ERROR):
        return "server_error"
    if any(s in text for s in _TIMEOUT):
        return "timeout"
    if any(s in text for s in _CONNECTION):
        return "connection"
    return "other"


def is_retryable(reason: Any) -> bool:
    return failure_class(reason) in RETRYABLE
