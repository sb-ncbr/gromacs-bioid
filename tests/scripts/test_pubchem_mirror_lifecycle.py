"""Lifecycle tests for scripts/populate_pubchem_mirror.py (A3).

Production reality on the NFS database volume (2026-10-07): `current` is a
REAL DIRECTORY (legacy layout), while the script's activation expects the
symlink pattern -- the original `_activate` would complete a multi-hour build
and then crash on `os.replace(symlink, nonempty_dir)`. The A3 patch makes
activation dir-safe (archive the legacy dir under a dated v-label) and adds
--defer-activate / --activate-only so activation can be gated on a consumer
liveness check on the shared volume.
"""
import importlib.util
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "populate_pubchem_mirror", os.path.join(REPO, "scripts", "populate_pubchem_mirror.py"))
pm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pm)


def _mk_version(target, name, payload="sqlite-bytes"):
    d = target / name
    d.mkdir(parents=True)
    (d / "pubchem.sqlite").write_text(payload)
    return d


def test_creates_symlink_when_no_current(tmp_path):
    v = _mk_version(tmp_path, "v2099-01-01")
    pm._activate(tmp_path, v)
    cur = tmp_path / "current"
    assert cur.is_symlink() and os.readlink(cur) == "v2099-01-01"
    assert (cur / "pubchem.sqlite").read_text() == "sqlite-bytes"


def test_replaces_existing_symlink_atomically(tmp_path):
    _mk_version(tmp_path, "v2098-01-01", payload="old")
    v2 = _mk_version(tmp_path, "v2099-01-01", payload="new")
    (tmp_path / "current").symlink_to("v2098-01-01")
    pm._activate(tmp_path, v2)
    cur = tmp_path / "current"
    assert os.readlink(cur) == "v2099-01-01"
    assert (cur / "pubchem.sqlite").read_text() == "new"
    assert (tmp_path / "v2098-01-01" / "pubchem.sqlite").exists()  # old kept


def test_real_dir_current_is_archived_then_activated(tmp_path):
    """The live layout case: current is a non-symlink directory."""
    legacy = _mk_version(tmp_path / "current", "", payload="legacy-sqlite")
    os.utime(legacy, (1200000000, 1200000000))  # 2008-01-10 -> deterministic label
    v2 = _mk_version(tmp_path, "v2099-01-01", payload="new")
    backup = pm._activate(tmp_path, v2)
    assert backup is not None and backup.name == "v2008-01-10"
    assert (tmp_path / "current").is_symlink()
    assert os.readlink(tmp_path / "current") == "v2099-01-01"
    assert (tmp_path / "v2008-01-10" / "pubchem.sqlite").read_text() == "legacy-sqlite"
    assert not (tmp_path / "current" / "pubchem.sqlite").read_text() == "legacy-sqlite"


def test_real_dir_current_refuses_to_overwrite_existing_backup(tmp_path):
    legacy = _mk_version(tmp_path / "current", "")
    os.utime(legacy, (1200000000, 1200000000))
    _mk_version(tmp_path, "v2008-01-10")  # collision with the archive label
    v2 = _mk_version(tmp_path, "v2099-01-01")
    with pytest.raises(FileExistsError):
        pm._activate(tmp_path, v2)
    assert (tmp_path / "current").is_dir()          # nothing moved
def test_prune_keeps_two_newest_and_never_current(tmp_path):
    for n in ("v2096-01-01", "v2097-01-01", "v2098-01-01", "v2099-01-01"):
        _mk_version(tmp_path, n)
    (tmp_path / "current").symlink_to("v2099-01-01")
    pm._prune_old_versions(tmp_path, keep=2)
    remaining = sorted(p.name for p in tmp_path.glob("v*"))
    assert remaining == ["v2098-01-01", "v2099-01-01"]


def test_prune_never_prunes_current_target(tmp_path):
    for n in ("v2096-01-01", "v2097-01-01", "v2098-01-01"):
        _mk_version(tmp_path, n)
    (tmp_path / "current").symlink_to("v2096-01-01")  # oldest, but ACTIVE
    pm._prune_old_versions(tmp_path, keep=1)
    remaining = sorted(p.name for p in tmp_path.glob("v*"))
    assert "v2096-01-01" in remaining


def test_main_activate_only_end_to_end(tmp_path, capsys):
    """Choreography gate used for the shared volume: build deferred, then an
    explicit activate-only step after a consumer check."""
    legacy = _mk_version(tmp_path / "current", "", payload="legacy")
    os.utime(legacy, (1200000000, 1200000000))
    _mk_version(tmp_path, "v2099-01-01", payload="new")
    rc = pm.main(["--target-dir", str(tmp_path), "--activate-only",
                  "--version-label", "v2099-01-01"])
    assert rc == 0
    assert os.readlink(tmp_path / "current") == "v2099-01-01"
    assert (tmp_path / "v2008-01-10" / "pubchem.sqlite").read_text() == "legacy"


def test_main_activate_only_missing_version_errors(tmp_path):
    rc = pm.main(["--target-dir", str(tmp_path), "--activate-only",
                  "--version-label", "v2099-01-01"])
    assert rc != 0
