"""Validation-runs file serving resolution (N1 wave, F-N1a).

RCSB structure-search resolvers build public URLs like
`/files/validation-<eid>-<timestamp>/input/<name>` (see config.pdb.curr_uuid
for validation runs). Normal runs are served by the /files StaticFiles mount
over runs_dir; validation runs live on the validation NFS instead. This module
pure-resolves those URLs to files under VALIDATION_FILES_ROOT with strict
guards; when the root is absent (validation un-deployed) resolution yields None
and the endpoint returns 404 — exactly today's behavior for unknown uuids.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

# validation-4653-20260924075449/input/sub/dir/file.pdb -> ("4653", "input/sub/dir/file.pdb")
_UUID_PATH_RE = re.compile(r"^(?P<eid>\d+)-(?P<ts>\d{10,16})/(?P<rel>.+)$")


def resolve_validation_file(path_after_uuid_prefix: str, root: Path) -> Optional[Path]:
    """Resolve the part of the URL after '/files/validation-' to a file under root.

    Args:
        path_after_uuid_prefix: e.g. '4653-20260924075449/input/foo.pdb'
        root: validation data root (e.g. /data/validation)

    Returns:
        Resolved Path if it exists as a file AND stays strictly inside
        root/<eid>/input; None otherwise (caller maps to 404).
    """
    if not isinstance(path_after_uuid_prefix, str):
        return None
    m = _UUID_PATH_RE.match(path_after_uuid_prefix)
    if not m:
        return None
    eid, rel = m.group("eid"), m.group("rel")
    # URL layout mirrors production runs: /files/{uuid}/input/{name}; on disk
    # validation inputs live at root/<eid>/input/<name>. The literal leading
    # "input/" in the URL is the mount layout, NOT part of the relative name.
    if not rel.startswith("input/"):
        return None
    rel = rel[len("input/"):]
    if not rel or rel.endswith("/"):
        return None  # no directory listings
    if "\x00" in rel:
        return None
    rel_path = Path(rel)
    if rel_path.is_absolute() or any(part == ".." for part in rel_path.parts):
        return None
    eid_root = (root / eid / "input").resolve()
    if not eid_root.is_dir():
        return None  # validation NFS not mounted (durable 404)
    target = (eid_root / rel_path).resolve()
    if not str(target).startswith(str(eid_root) + "/"):
        return None
    if not target.is_file():
        return None
    return target
