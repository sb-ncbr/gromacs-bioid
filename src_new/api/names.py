"""Server-side display-name helpers for segment metadata.

BACKEND_GAPS G3: mirrors the UI's client-side derivation EXACTLY
(ui/src/features/results/viewmodel/derive.ts — stripSeg / chainOf /
baseName), so the redesigned page can flip from client-side munging to
the additive `display_name` / `chain` keys without any visible change.
Keep the two implementations in sync.
"""

from __future__ import annotations

import re
from typing import Optional

_SEG_PREFIX = re.compile(r"^seg_\d+_")
_V_SUFFIX = re.compile(r"__v\d+$")
_CHAIN_SUFFIX = re.compile(r"(?:^|_)chain_([A-Za-z0-9]+)$")


def strip_seg(segment: str) -> str:
    """Segment id → source string: strip `seg_N_` prefix and `__vN` suffix."""
    return _V_SUFFIX.sub("", _SEG_PREFIX.sub("", segment))


def chain_of(source: str) -> Optional[str]:
    """Chain letter from a stripped segment source
    ("Protein_chain_A" → "A"), None when no `_chain_X` suffix."""
    m = _CHAIN_SUFFIX.search(source)
    return m.group(1) if m else None


def segment_display_name(segment: str) -> str:
    """Base display name for one segment (before the UI's duplicate
    disambiguation): chains → "Chain X"; otherwise the stripped source."""
    source = strip_seg(segment)
    chain = chain_of(source)
    return f"Chain {chain}" if chain else source
