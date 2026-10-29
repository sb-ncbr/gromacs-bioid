"""W3.1 item 4 (A9 follow-up): adhoc file serving, loud unavailability,
and reaper retention.

Defects pinned here (real inputs — real FastAPI app, real files, real
reaper functions, real RunConfig):

1. ``Path("")`` bug: with ``BAT3_ADHOC_DIR`` unset, ``Path("")`` is ``.``
   (truthy), so the 404 guard in ``serve_adhoc_file`` was dead and the
   route served sha-named files from the container CWD.
2. Silent skip: when the adhoc dir is unset/unwritable and the run has no
   registry uuid (Celery-dispatched), every RCSB similarity query was
   skipped with only a log line ("curr_uuid is empty") — the results
   payload never said structure search was off.
3. Reaper: the adhoc staging dir under the runs dir must never be
   treated as a run, and staged adhoc mmCIFs need age-based retention.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src_new.api.main import app
from src_new.config.loader import RunConfig

_SHA = hashlib.sha256(b"w31-item4 adhoc probe content").hexdigest()
_PROBE = "w31-item4 adhoc probe content"
_CIF = f"data_\n# probe for {_PROBE}\n"
_SHA = hashlib.sha256(_CIF.encode()).hexdigest()  # resolver hashes file CONTENT


def _write_staged(adhoc_dir: Path, sha: str = _SHA, content: str = _CIF) -> Path:
    adhoc_dir.mkdir(parents=True, exist_ok=True)
    target = adhoc_dir / f"{sha}.cif"
    target.write_text(content)
    return target


class TestAdhocRouteGuard:
    """Route must serve ONLY from a configured BAT3_ADHOC_DIR."""

    def test_unset_dir_refuses_even_when_file_exists_in_cwd(
            self, tmp_path, monkeypatch):
        # RED at HEAD: Path("") == "." is truthy, the guard passed, and
        # the route happily served <sha>.cif from the process CWD.
        monkeypatch.delenv("BAT3_ADHOC_DIR", raising=False)
        # a sha-named .cif in the CWD (exact trap of the Path("") bug)
        monkeypatch.chdir(tmp_path)
        (tmp_path / f"{_SHA}.cif").write_text(_CIF)
        with TestClient(app) as client:
            r = client.get(f"/files/adhoc/{_SHA}.cif")
        assert r.status_code == 404, (
            "unset BAT3_ADHOC_DIR must refuse to serve; the old Path('') "
            "guard served files from the container CWD")

    def test_configured_dir_serves_staged_file_by_sha(
            self, tmp_path, monkeypatch):
        adhoc = tmp_path / "adhoc"
        _write_staged(adhoc)
        monkeypatch.setenv("BAT3_ADHOC_DIR", str(adhoc))
        with TestClient(app) as client:
            r = client.get(f"/files/adhoc/{_SHA}.cif")
        assert r.status_code == 200
        assert r.text == _CIF

    def test_configured_dir_404_on_missing_sha(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BAT3_ADHOC_DIR", str(tmp_path / "adhoc"))
        missing = "a" * 64
        with TestClient(app) as client:
            r = client.get(f"/files/adhoc/{missing}.cif")
        assert r.status_code == 404

    def test_name_regex_blocks_traversal(self, tmp_path, monkeypatch):
        adhoc = tmp_path / "adhoc"
        outside = tmp_path / "secret.txt"
        outside.write_text("nope")
        # a copy masquerading under a traversal-ish name
        (adhoc).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("BAT3_ADHOC_DIR", str(adhoc))
        with TestClient(app) as client:
            for bad in ("..%2fsecret.txt", f"{_SHA}.cif%00",
                        f"{_SHA}.CIF", "short.cif"):
                r = client.get(f"/files/adhoc/{bad}")
                assert r.status_code == 404, bad


class TestWorkerStaging:
    """The mmCIF resolver's adhoc staging (real resolver, real files)."""

    def _resolver(self, adhoc_dir: Path):
        from src_new.identification.resolvers.mmcif import MmCifResolver
        cfg = RunConfig()
        cfg.pdb.adhoc_files_dir = str(adhoc_dir)
        return MmCifResolver(cfg)

    def test_stages_file_as_sha_cif_and_returns_url(self, tmp_path):
        adhoc = tmp_path / "adhoc"
        cif = tmp_path / "seg.cif"
        cif.write_text(_CIF)
        url = self._resolver(adhoc)._stage_adhoc_url(str(cif))
        assert url is not None
        assert url.endswith(f"/files/adhoc/{_SHA}.cif")
        assert (adhoc / f"{_SHA}.cif").read_text() == _CIF

    def test_unwritable_dir_returns_none_without_raising(self, tmp_path):
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("file where a dir should be")
        cif = tmp_path / "seg.cif"
        cif.write_text(_CIF)
        url = self._resolver(blocker / "sub")._stage_adhoc_url(str(cif))
        assert url is None


class TestStructureSearchUnavailableWarning:
    """Loud once-per-run warning instead of the silent curr_uuid skip."""

    def _reason(self, **pdb_overrides):
        cfg = RunConfig()
        for k, v in pdb_overrides.items():
            setattr(cfg.pdb, k, v)
        from src_new.pipeline_steps import structure_search_unavailable_reason
        return structure_search_unavailable_reason(cfg)

    def test_unset_dir_and_no_uuid_gives_reason(self):
        reason = self._reason(adhoc_files_dir="", curr_uuid="")
        assert reason, "unset adhoc dir + Celery run must give a reason"
        assert "structure search" in reason.lower()

    def test_unwritable_dir_gives_reason(self, tmp_path):
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("x")
        reason = self._reason(
            adhoc_files_dir=str(blocker / "adhoc"), curr_uuid="")
        assert reason and "writ" in reason.lower()

    def test_writable_dir_no_reason(self, tmp_path):
        assert self._reason(
            adhoc_files_dir=str(tmp_path / "adhoc"), curr_uuid="") is None

    def test_registry_uuid_no_reason_legacy_path_works(self):
        # API-registry runs fall back to /files/{uuid}/input/ — fine.
        assert self._reason(adhoc_files_dir="", curr_uuid="run-42") is None

    def test_upload_mode_no_reason(self):
        assert self._reason(
            use_deployment_file_access=False, adhoc_files_dir="",
            curr_uuid="") is None

    def test_warning_emitted_once_via_context(self, tmp_path):
        from src_new.pipeline_steps import _maybe_warn_structure_search
        cfg = RunConfig()
        cfg.pdb.adhoc_files_dir = ""
        cfg.pdb.curr_uuid = ""

        class _Results:
            def __init__(self):
                self._d = {}

            def get_data(self, k):
                return self._d.get(k)

            def set_data(self, k, v):
                self._d[k] = v

        class _Ctx:
            def __init__(self):
                self.warnings = []
                self.results = _Results()

            def add_warning(self, code, message, **kw):
                self.warnings.append((code, message))

        ctx = _Ctx()
        _maybe_warn_structure_search(ctx, cfg)
        _maybe_warn_structure_search(ctx, cfg)  # second call: once per run
        codes = [w[0] for w in ctx.warnings]
        assert codes.count("structure_search_unavailable") == 1, codes


class TestReaperAdhocRetention:
    """Reaper skips _adhoc as a run; adhoc files get age-based retention."""

    def _runs_dir(self, tmp_path: Path) -> Path:
        runs = tmp_path / "runs"
        runs.mkdir()
        return runs

    def test_sweep_never_treats_adhoc_dir_as_a_run(self, tmp_path):
        from src_new.api.run_reaper import sweep
        runs = self._runs_dir(tmp_path)
        _write_staged(runs / "_adhoc")
        summary = sweep(runs, live_task_ids=set(), misses={})
        assert summary["scanned"] == 0, summary
        assert (runs / "_adhoc" / f"{_SHA}.cif").is_file()

    def test_sweep_adhoc_deletes_only_stale_files(self, tmp_path):
        from src_new.api.run_reaper import sweep_adhoc
        adhoc = tmp_path / "adhoc"
        fresh = _write_staged(adhoc, sha="b" * 64)
        stale = _write_staged(adhoc, sha="c" * 64)
        stale_tmp = adhoc / ("." + "d" * 64 + ".tmp")
        stale_tmp.write_text("abandoned staging file")
        old = time.time() - 30 * 86400
        os.utime(stale, (old, old))
        os.utime(stale_tmp, (old, old))
        summary = sweep_adhoc(adhoc, retention_s=7 * 86400)
        assert summary["adhoc_deleted"] == 2, summary
        assert fresh.is_file(), "fresh staging file must survive"
        assert not stale.exists()
        assert not stale_tmp.exists()

    def test_sweep_adhoc_missing_dir_is_noop(self, tmp_path):
        from src_new.api.run_reaper import sweep_adhoc
        summary = sweep_adhoc(tmp_path / "nope", retention_s=60.0)
        assert summary["adhoc_deleted"] == 0
