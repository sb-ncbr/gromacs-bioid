"""W3.2 item 3 (A9): pdb_struct similarity queries through adhoc staging.

URL trace at b954adc33 (why this is needed):

- PDBStructResolver._pdb_fetch_similar_structures builds
  ``{deployment_file_url}/files/{curr_uuid}/input/{filename}`` where
  curr_uuid = run_id (api/tasks.py:112) and filename is a tmp .pdb the
  resolver wrote via safe_tmp_dir(working_directory).
- (a) corpus/Celery-direct runs: the run directory is NOT under the
  API's BAT3_RUNS_DIR, so the /files StaticFiles mount over
  get_runs_dir() (routes/runs.py:88) cannot serve it — the URL 404s for
  every corpus run, exactly the mmCIF BH-044 class. Additionally,
  safe_tmp_dir falls back to the worker pod's local /tmp whenever the
  run's input dir is owned by another uid, so the file is often not on
  the served path at all.
- (b) bughunt re-eval runs (POST /runs): run_dir = runs_dir/run_id, so
  the static mount WOULD serve the tmp pdb — but only when the worker
  could write it into the input dir (uid/NFS-dependent).

Fix (same shape as mmCIF BH-044): stage the query pdb content-addressed
into BAT3_ADHOC_DIR and point RCSB at /files/adhoc/<sha256>.pdb, with
the legacy per-run URL as fallback. The API adhoc route
(main.py _ADHOC_NAME_RE) must accept the .pdb suffix — pinned in
tests/src_new/api/test_adhoc_serving_w31.py.
"""

from __future__ import annotations

import hashlib
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pytest

from src_new.config.loader import RunConfig


_PDB = "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N\n"
_SHA = hashlib.sha256(_PDB.encode()).hexdigest()


def _resolver(tmp_path, adhoc_dir=None):
    from src_new.identification.resolvers.pdb_struct import PDBStructResolverProtein
    cfg = RunConfig()
    cfg.pdb.use_deployment_file_access = True
    cfg.pdb.deployment_file_url = "https://api.example"
    cfg.pdb.curr_uuid = "corpus-run-123"
    if adhoc_dir is not None:
        cfg.pdb.adhoc_files_dir = str(adhoc_dir)
    else:
        cfg.pdb.adhoc_files_dir = ""  # unset -> no adhoc staging
    return PDBStructResolverProtein(cfg)


def _run_similarity(resolver, tmp_path, monkeypatch):
    """Call _pdb_fetch_similar_structures with the network mocked out;
    return the remote_path RCSB would be pointed at."""
    captured = {}

    def fake_fetch(remote_path, base_types):
        captured["url"] = remote_path
        return None  # no response -> empty parse, no network

    monkeypatch.setattr(resolver, "_fetch_pdb_similarity", fake_fetch)
    monkeypatch.setattr(resolver, "_parse_pdb_response", lambda r: [])
    pdb = tmp_path / "query.pdb"
    pdb.write_text(_PDB)
    resolver._pdb_fetch_similar_structures(str(pdb), True)
    return captured.get("url")


def test_similarity_prefers_adhoc_url(tmp_path, monkeypatch):
    adhoc = tmp_path / "adhoc"
    r = _resolver(tmp_path, adhoc_dir=adhoc)
    url = _run_similarity(r, tmp_path, monkeypatch)
    assert url == f"https://api.example/files/adhoc/{_SHA}.pdb", (
        f"pdb_struct must prefer the run-independent adhoc URL, got {url!r}")
    assert (adhoc / f"{_SHA}.pdb").read_text() == _PDB, (
        "query pdb not staged content-addressed into BAT3_ADHOC_DIR")


def test_adhoc_disabled_falls_back_to_legacy_run_url(tmp_path, monkeypatch):
    monkeypatch.delenv("BAT3_ADHOC_DIR", raising=False)
    r = _resolver(tmp_path, adhoc_dir=None)
    url = _run_similarity(r, tmp_path, monkeypatch)
    assert url is not None and "/files/adhoc/" not in url
    assert url.startswith("https://api.example/files/corpus-run-123/input/")


def test_unwritable_adhoc_dir_falls_back_without_raising(tmp_path, monkeypatch):
    monkeypatch.delenv("BAT3_ADHOC_DIR", raising=False)
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("file where a dir should be")
    r = _resolver(tmp_path, adhoc_dir=blocker / "sub")
    url = _run_similarity(r, tmp_path, monkeypatch)
    assert url is not None and "/files/adhoc/" not in url, (
        "staging failure must fall back to the legacy URL, never raise")
