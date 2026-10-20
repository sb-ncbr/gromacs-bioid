"""Foldseek resolver mode tests (v3.138 rewrite: local subprocess + REST remote).

The pre-v3.138 resolver was fully dead: a duplicated `_run_foldseek_search`
method definition (the workflow wrapper shadowed the executor) made every
call raise TypeError, and the fallback DB name "afdb" never existed. These
tests pin the new contract: mode dispatch, remote fallback, shared target
normalization, and REST payload parsing.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.foldseek import (
    Foldseek3DiResolver,
    normalize_foldseek_target,
)


def _make_resolver(tmp_path: Path, *, mode="local", db_exists=True, exec_ok=True) -> Foldseek3DiResolver:
    config = RunConfig()
    config.foldseek.mode = mode
    db_prefix = tmp_path / "swissprot"
    if db_exists:
        db_prefix.touch()
        (tmp_path / "swissprot.index").touch()
    config.foldseek.db_path = str(db_prefix)
    if not exec_ok:
        config.foldseek.foldseek_exec = str(tmp_path / "no-such-binary")
    resolver = Foldseek3DiResolver(config)
    return resolver


def _write_fake_foldseek(tmp_path: Path, *, m8_rows=(), fail_createdb=False, fail_search=False) -> str:
    """Stub foldseek binary: createdb/search exit codes + canned M8 output."""
    script = tmp_path / "foldseek"
    lines = ["#!/bin/sh"]
    if fail_createdb:
        lines.append('if [ "$1" = "createdb" ]; then exit 1; fi')
    else:
        lines.append('if [ "$1" = "createdb" ]; then exit 0; fi')
    if fail_search:
        lines.append('if [ "$1" = "search" ]; then exit 1; fi')
    else:
        for row in m8_rows:
            lines.append(f'if [ "$1" = "search" ]; then printf "%s\\n" \'{row}\' >> "$4"; fi')
        lines.append('if [ "$1" = "search" ]; then exit 0; fi')
    script.write_text("\n".join(lines) + "\n")
    script.chmod(0o755)
    return str(script)


class TestNormalizeTarget:
    def test_wrapped_af_v6_with_description_tail(self):
        assert normalize_foldseek_target("AF-P01542-F1-model_v6 Crambin") == "P01542"

    def test_wrapped_af_v4(self):
        assert normalize_foldseek_target("AF-Q9XYZ1-F1-model_v4") == "Q9XYZ1"

    def test_bare_accession(self):
        assert normalize_foldseek_target("P01542") == "P01542"

    def test_pdb_id_rejected(self):
        assert normalize_foldseek_target("6VXX") is None

    def test_empty_and_garbage(self):
        assert normalize_foldseek_target("") is None
        assert normalize_foldseek_target("???") is None


class TestBinaryCheck:
    def test_version_subcommand_not_dashdash(self, tmp_path):
        """foldseek has no --version flag; availability probe must use the
        `version` subcommand (empirically verified on build 9-427df8a)."""
        config = RunConfig()
        config.foldseek.db_path = str(tmp_path / "swissprot")
        with patch("src_new.identification.resolvers.foldseek.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            resolver = Foldseek3DiResolver(config)
        assert resolver._binary_available is True
        assert run.call_args.args[0][1] == "version"

    def test_nonzero_rc_marks_unavailable(self, tmp_path):
        config = RunConfig()
        config.foldseek.db_path = str(tmp_path / "swissprot")
        with patch("src_new.identification.resolvers.foldseek.subprocess.run") as run:
            run.return_value = MagicMock(returncode=1)
            resolver = Foldseek3DiResolver(config)
        assert resolver._binary_available is False


class TestModeDispatch:
    def test_off_mode_returns_empty_without_work(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="off")
        with patch.object(resolver, "_local_search") as loc, \
             patch.object(resolver, "_remote_search") as rem:
            assert resolver._resolve_similarity("dddddddd", str(tmp_path)) == []
        loc.assert_not_called()
        rem.assert_not_called()

    def test_remote_mode_skips_local(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="remote")
        with patch.object(resolver, "_local_search") as loc, \
             patch.object(resolver, "_remote_search", return_value=[("P01542", 97.8)]) as rem:
            assert resolver._resolve_similarity("dddddddd", str(tmp_path)) == [("P01542", 97.8)]
        loc.assert_not_called()
        rem.assert_called_once()

    def test_missing_binary_falls_back_to_remote(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="local", exec_ok=False)
        assert resolver._binary_available is False
        with patch.object(resolver, "_remote_search", return_value=[("P01542", 97.8)]) as rem:
            assert resolver._resolve_similarity("dddddddd", str(tmp_path)) == [("P01542", 97.8)]
        rem.assert_called_once()

    def test_missing_db_falls_back_to_remote(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="local", db_exists=False, exec_ok=False)
        resolver._binary_available = True  # pretend binary exists; DB does not
        with patch.object(resolver, "_remote_search", return_value=[]) as rem:
            assert resolver._resolve_similarity("dddddddd", str(tmp_path)) == []
        rem.assert_called_once()


class TestLocalSearch:
    def test_happy_path_normalizes_targets(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="local")
        resolver.config.foldseek.foldseek_exec = _write_fake_foldseek(
            tmp_path,
            m8_rows=[
                "query\tAF-P01542-F1-model_v4 Crambin\t0.978\t1.0\t1e-20",
                "query\tAF-Q9XYZ1-F1-model_v4\t1.0\t1.0\t0.0",
            ],
        )
        resolver._binary_available = True
        results = resolver._resolve_similarity("dddddddd", str(tmp_path))
        assert results == [("P01542", pytest.approx(97.8)), ("Q9XYZ1", 100.0)]

    def test_max_hits_cap(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="local")
        resolver.config.foldseek.max_target_hits = 2
        rows = [f"query\tP{i:05d}\t0.9\t1.0\t1e-9" for i in range(1000, 1005)]
        # P01000 etc are valid UniProt-shaped accessions
        resolver.config.foldseek.foldseek_exec = _write_fake_foldseek(tmp_path, m8_rows=rows)
        resolver._binary_available = True
        assert len(resolver._resolve_similarity("dddddddd", str(tmp_path))) == 2

    def test_unparseable_and_unnormalizable_rows_skipped(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="local")
        resolver.config.foldseek.foldseek_exec = _write_fake_foldseek(
            tmp_path,
            m8_rows=[
                "query\t6VXX\t0.9\t1.0\t1e-9",        # raw PDB id -> dropped
                "query\tAF-P01542-F1-model_v4\tjunk\t1.0\t1e-9",  # bad fident -> dropped
                "query\tP01542\t0.991\t1.0\t1e-15",
            ],
        )
        resolver._binary_available = True
        assert resolver._resolve_similarity("dddddddd", str(tmp_path)) == [("P01542", pytest.approx(99.1))]

    def test_createdb_failure_triggers_remote_fallback(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="local")
        resolver.config.foldseek.foldseek_exec = _write_fake_foldseek(tmp_path, fail_createdb=True)
        resolver._binary_available = True
        with patch.object(resolver, "_remote_search", return_value=[("P01542", 97.8)]) as rem:
            assert resolver._resolve_similarity("dddddddd", str(tmp_path)) == [("P01542", 97.8)]
        rem.assert_called_once()

    def test_search_failure_triggers_remote_fallback(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="local")
        resolver.config.foldseek.foldseek_exec = _write_fake_foldseek(tmp_path, fail_search=True)
        resolver._binary_available = True
        with patch.object(resolver, "_remote_search", return_value=[]):
            assert resolver._resolve_similarity("dddddddd", str(tmp_path)) == []


class TestRemoteSearch:
    def _patch_http(self, *, ticket_id="t1", status="COMPLETE", payload=None):
        post_resp = MagicMock(status_code=200)
        post_resp.json.return_value = {"id": ticket_id, "status": status}
        post_resp.raise_for_status = MagicMock()

        status_resp = MagicMock(status_code=200)
        status_resp.json.return_value = {"id": ticket_id, "status": status}

        result_resp = MagicMock(status_code=200)
        result_resp.json.return_value = payload or {}
        result_resp.raise_for_status = MagicMock()

        get_side = [status_resp, result_resp]
        if status == "ERROR":
            get_side = [status_resp]
        return post_resp, get_side

    def test_remote_happy_path(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="remote")
        payload = {
            "results": [{
                "alignments": [
                    {"target": "AF-P01542-F1-model_v6 Crambin", "seqId": 0.978, "eval": 1e-20},
                    {"target": "6VXX", "seqId": 0.9},  # dropped: not UniProt-space
                ]
            }]
        }
        post_resp, get_side = self._patch_http(payload=payload)
        with patch("src_new.identification.resolvers.foldseek.requests.post", return_value=post_resp), \
             patch("src_new.identification.resolvers.foldseek.requests.get", side_effect=get_side):
            results = resolver._resolve_similarity("dddddddd", str(tmp_path))
        assert results == [("P01542", pytest.approx(97.8))]

    def test_database_field_name_is_database_bracket(self, tmp_path):
        """Wire format pinned: server rejects 'Database'/'databases' (2026-10-19 probe)."""
        resolver = _make_resolver(tmp_path, mode="remote")
        resolver.config.foldseek.remote_database = "afdb-swissprot"
        post_resp, get_side = self._patch_http()
        with patch("src_new.identification.resolvers.foldseek.requests.post", return_value=post_resp) as post, \
             patch("src_new.identification.resolvers.foldseek.requests.get", side_effect=get_side):
            resolver._resolve_similarity("dddddddd", str(tmp_path))
        assert post.call_args.kwargs["data"]["database[]"] == "afdb-swissprot"
        assert post.call_args.kwargs["data"]["mode"] == "3diaa"

    def test_error_status_returns_none(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="remote")
        post_resp, get_side = self._patch_http(status="ERROR")
        with patch("src_new.identification.resolvers.foldseek.requests.post", return_value=post_resp), \
             patch("src_new.identification.resolvers.foldseek.requests.get", side_effect=get_side):
            assert resolver._remote_search("dddddddd") is None

    def test_pending_past_budget_returns_none(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="remote")
        resolver.config.foldseek.remote_polls = 2
        resolver.config.foldseek.remote_poll_interval_s = 0.01
        post_resp, _ = self._patch_http(status="PENDING")
        pending = MagicMock(status_code=200)
        pending.json.return_value = {"id": "t1", "status": "PENDING"}
        with patch("src_new.identification.resolvers.foldseek.requests.post", return_value=post_resp), \
             patch("src_new.identification.resolvers.foldseek.requests.get", return_value=pending):
            assert resolver._remote_search("dddddddd") is None

    def test_network_failure_returns_none(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="remote")
        with patch("src_new.identification.resolvers.foldseek.requests.post", side_effect=OSError("no route")):
            assert resolver._remote_search("dddddddd") is None
