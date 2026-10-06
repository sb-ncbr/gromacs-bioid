"""F-26 (2026-10-06): freeze guard for the legacy dispatch machinery.

Legacy dispatch (schedule_validation wrapper + old validate/batch/retry
endpoints) diverges from the canonical queue_processor machinery: ts-less /
short run ids fail the /files/validation-<eid>-<ts> serving regex, no Bat3Run
bookkeeping is created (settle/sweeper blind), and per-run layout can split
from the served tree. Empirical census 2026-10-06: legacy paths unused since
2026-08-06 (66 uuid8 runs; 3 unlinked queue rows ever) - armed but dead code.

Default posture is FROZEN: legacy dispatch paths refuse fast (HTTP 410 on the
endpoints, sentinel string from the wrapper task). Operators can re-enable for
forensics with VALIDATION_LEGACY_DISPATCH=allow on a scratch deployment only.

Canonical dispatch remains untouched (queue_processor.process_validation_queue
-> _process_single_item, and src_new.api.tasks.run_pipeline_task by name;
F-04 registration import in root tasks.py stays load-bearing regardless).
"""

from __future__ import annotations

import os

FROZEN_MESSAGE = (
    "legacy dispatch frozen (F-26): use the canonical queue API "
    "(/validation/queue/*). See .tmp/F26_DESIGN.md / docs/CHEMISTRY_FIX_TODO.md."
)

_ALLOW_VALUES = {"allow", "true", "1", "yes"}


def legacy_dispatch_allowed() -> bool:
    """True only when VALIDATION_LEGACY_DISPATCH explicitly unfreezes legacy paths."""
    return os.environ.get("VALIDATION_LEGACY_DISPATCH", "").strip().lower() in _ALLOW_VALUES
