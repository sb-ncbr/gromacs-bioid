"""Resolver outcomes that mean "does not apply here", not "failed".

A resolver that declines its input (a nucleotide structure search given a
protein, an mmCIF polymer search given a small molecule) reports a reason
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
    "na_mode_unsupported",          # pdb_struct.py, mmcif.py: nucleic-acid search mode not supported
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
