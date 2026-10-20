"""Foldseek resolver mode tests (v3.138: local subprocess + REST remote).

The resolver consumes ca_only_pdb STRUCTURE text (not 3Di letter strings):
foldseek's createdb rejects FASTA input outright ("No structures found in
given input"; empirically established 2026-10-20 on the 9-427df8a static
build). Local mode is createdb(pdb) -> search -> convertalis(--format-
output query,target,fident); remote POSTs the structure with mode=3diaa.
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

# Minimal CA-only structure text (matches the ca_only_pdb signature shape).
CRAMBIN_CA_PDB = (
    "ATOM      2  CA  THR A   1      16.967  12.784   4.338  1.00 10.80           C\n"
    "ATOM      9  CA  THR A   2      13.856  11.469   6.066  1.00  8.31           C\n"
    "END\n"
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
    """Stub foldseek binary: createdb/search/convertalis exits + canned M8.

    Arg layout the resolver relies on (pinned here):
      createdb <query.pdb> <query_db>
      search   <query_db> <target_db> <result_db> <tmpdir>
      convertalis <query_db> <target_db> <result_db> <m8> --format-output ...
    """
    script = tmp_path / "foldseek"
    lines = ["#!/bin/sh"]
    lines.append(f'if [ "$1" = "createdb" ]; then exit {1 if fail_createdb else 0}; fi')
    lines.append(f'if [ "$1" = "search" ]; then exit {1 if fail_search else 0}; fi')
    for row in m8_rows:
        lines.append(f'if [ "$1" = "convertalis" ]; then printf "%s\\n" \'{row}\' >> "$5"; fi')
    lines.append('if [ "$1" = "convertalis" ]; then exit 0; fi')
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
            assert resolver._resolve_similarity(CRAMBIN_CA_PDB, str(tmp_path)) == []
        loc.assert_not_called()
        rem.assert_not_called()

    def test_remote_mode_skips_local(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="remote")
        with patch.object(resolver, "_local_search") as loc, \
             patch.object(resolver, "_remote_search", return_value=[("P01542", 97.8)]) as rem:
            assert resolver._resolve_similarity(CRAMBIN_CA_PDB, str(tmp_path)) == [("P01542", 97.8)]
        loc.assert_not_called()
        rem.assert_called_once()

    def test_missing_binary_falls_back_to_remote(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="local", exec_ok=False)
        assert resolver._binary_available is False
        with patch.object(resolver, "_remote_search", return_value=[("P01542", 97.8)]) as rem:
            assert resolver._resolve_similarity(CRAMBIN_CA_PDB, str(tmp_path)) == [("P01542", 97.8)]
        rem.assert_called_once()

    def test_missing_db_falls_back_to_remote(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="local", db_exists=False, exec_ok=False)
        resolver._binary_available = True  # pretend binary exists; DB does not
        with patch.object(resolver, "_remote_search", return_value=[]) as rem:
            assert resolver._resolve_similarity(CRAMBIN_CA_PDB, str(tmp_path)) == []
        rem.assert_called_once()

    def test_resolver_accepts_ca_only_pdb_signature(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="off")
        assert resolver.accepted_signatures == ["ca_only_pdb"]
        assert resolver._is_applicable(CRAMBIN_CA_PDB) is True
        assert resolver._is_applicable("ieancmrjrr") is False  # 3Di letters: not structure text
        assert resolver._is_applicable("") is False


class TestLocalSearch:
    def test_happy_path_normalizes_targets(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="local")
        resolver.config.foldseek.foldseek_exec = _write_fake_foldseek(
            tmp_path,
            m8_rows=[
                "query\tAF-P01542-F1-model_v6 Crambin\t1.0",
                "query\tAF-Q9XYZ1-F1-model_v4\t0.978",
            ],
        )
        resolver._binary_available = True
        results = resolver._resolve_similarity(CRAMBIN_CA_PDB, str(tmp_path))
        assert results == [("P01542", 100.0), ("Q9XYZ1", pytest.approx(97.8))]

    def test_max_hits_cap(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="local")
        resolver.config.foldseek.max_target_hits = 2
        rows = [f"query\tP{i:05d}\t0.9" for i in range(1000, 1005)]
        resolver.config.foldseek.foldseek_exec = _write_fake_foldseek(tmp_path, m8_rows=rows)
        resolver._binary_available = True
        assert len(resolver._resolve_similarity(CRAMBIN_CA_PDB, str(tmp_path))) == 2

    def test_unnormalizable_and_unparseable_rows_skipped(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="local")
        resolver.config.foldseek.foldseek_exec = _write_fake_foldseek(
            tmp_path,
            m8_rows=[
                "query\t6VXX\t0.9",                       # raw PDB id -> dropped
                "query\tAF-P01542-F1-model_v4\tjunk",     # bad fident -> dropped
                "query\tP01542\t0.991",
            ],
        )
        resolver._binary_available = True
        assert resolver._resolve_similarity(CRAMBIN_CA_PDB, str(tmp_path)) == [("P01542", pytest.approx(99.1))]

    def test_createdb_failure_triggers_remote_fallback(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="local")
        resolver.config.foldseek.foldseek_exec = _write_fake_foldseek(tmp_path, fail_createdb=True)
        resolver._binary_available = True
        with patch.object(resolver, "_remote_search", return_value=[("P01542", 97.8)]) as rem:
            assert resolver._resolve_similarity(CRAMBIN_CA_PDB, str(tmp_path)) == [("P01542", 97.8)]
        rem.assert_called_once()

    def test_search_failure_triggers_remote_fallback(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="local")
        resolver.config.foldseek.foldseek_exec = _write_fake_foldseek(tmp_path, fail_search=True)
        resolver._binary_available = True
        with patch.object(resolver, "_remote_search", return_value=[]):
            assert resolver._resolve_similarity(CRAMBIN_CA_PDB, str(tmp_path)) == []


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
        """Live payload shape (2026-10-20): alignments nested per query,
        seqId on a PERCENT scale (97.8, not 0.978)."""
        resolver = _make_resolver(tmp_path, mode="remote")
        payload = {
            "results": [{
                "db": "afdb-swissprot",
                "alignments": [[
                    {"target": "AF-P01542-F1-model_v6 Crambin", "seqId": 97.8, "alnLength": 46},
                    {"target": "AF-P01541-F1-model_v6", "seqId": 50.0, "alnLength": 46},
                    {"target": "6VXX", "seqId": 0.9},  # dropped: not UniProt-space
                ]],
            }]
        }
        post_resp, get_side = self._patch_http(payload=payload)
        with patch("src_new.identification.resolvers.foldseek.requests.post", return_value=post_resp), \
             patch("src_new.identification.resolvers.foldseek.requests.get", side_effect=get_side):
            results = resolver._resolve_similarity(CRAMBIN_CA_PDB, str(tmp_path))
        assert results == [("P01542", 97.8), ("P01541", 50.0)]

    def test_remote_fraction_seqid_variant_normalized(self, tmp_path):
        """Older shape: flat alignments + fraction seqId -> still 0-100."""
        resolver = _make_resolver(tmp_path, mode="remote")
        payload = {
            "results": [{
                "alignments": [
                    {"target": "AF-P01542-F1-model_v6 Crambin", "seqId": 0.978},
                ],
            }]
        }
        post_resp, get_side = self._patch_http(payload=payload)
        with patch("src_new.identification.resolvers.foldseek.requests.post", return_value=post_resp), \
             patch("src_new.identification.resolvers.foldseek.requests.get", side_effect=get_side):
            results = resolver._resolve_similarity(CRAMBIN_CA_PDB, str(tmp_path))
        assert results == [("P01542", pytest.approx(97.8))]

    def test_remote_posts_structure_with_3diaa_mode(self, tmp_path):
        """Wire format pinned: pdb structure upload (computed-3Di server-side)
        + 'database[]' field (rejected names: Database/databases), mode 3diaa."""
        resolver = _make_resolver(tmp_path, mode="remote")
        resolver.config.foldseek.remote_database = "afdb-swissprot"
        post_resp, get_side = self._patch_http()
        with patch("src_new.identification.resolvers.foldseek.requests.post", return_value=post_resp) as post, \
             patch("src_new.identification.resolvers.foldseek.requests.get", side_effect=get_side):
            resolver._resolve_similarity(CRAMBIN_CA_PDB, str(tmp_path))
        kwargs = post.call_args.kwargs
        assert kwargs["data"]["database[]"] == "afdb-swissprot"
        assert kwargs["data"]["mode"] == "3diaa"
        fname, body = kwargs["files"]["q"]
        assert fname.endswith(".pdb")
        assert "ATOM" in body

    def test_error_status_returns_none(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="remote")
        post_resp, get_side = self._patch_http(status="ERROR")
        with patch("src_new.identification.resolvers.foldseek.requests.post", return_value=post_resp), \
             patch("src_new.identification.resolvers.foldseek.requests.get", side_effect=get_side):
            assert resolver._remote_search(CRAMBIN_CA_PDB) is None

    def test_pending_past_budget_returns_none(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="remote")
        resolver.config.foldseek.remote_polls = 2
        resolver.config.foldseek.remote_poll_interval_s = 0.01
        post_resp, _ = self._patch_http(status="PENDING")
        pending = MagicMock(status_code=200)
        pending.json.return_value = {"id": "t1", "status": "PENDING"}
        with patch("src_new.identification.resolvers.foldseek.requests.post", return_value=post_resp), \
             patch("src_new.identification.resolvers.foldseek.requests.get", return_value=pending):
            assert resolver._remote_search(CRAMBIN_CA_PDB) is None

    def test_network_failure_returns_none(self, tmp_path):
        resolver = _make_resolver(tmp_path, mode="remote")
        with patch("src_new.identification.resolvers.foldseek.requests.post", side_effect=OSError("boom")):
            assert resolver._remote_search(CRAMBIN_CA_PDB) is None
