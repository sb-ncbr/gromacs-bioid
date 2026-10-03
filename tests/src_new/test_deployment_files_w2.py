"""W2/F-N1a unit tests: DEPLOYMENT_FILE_URL env override + validation file resolution."""
from __future__ import annotations

import os
import pytest

from src_new.config.loader import RunConfig
from src_new.api.validation_files import resolve_validation_file


class TestDeploymentFileUrlOverride:
    PROD = "https://bioid.dyn.cloud.e-infra.cz"
    CEITEC = "https://bioid-ceitec.dyn.cloud.e-infra.cz"

    def test_default_untouched_when_env_unset(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DEPLOYMENT_FILE_URL", raising=False)
        ini = tmp_path / "config.ini"
        ini.write_text("[pdb]\ndeployment_file_url: https://example.org/base\n")
        cfg = RunConfig.from_ini_path(str(ini))
        assert cfg.pdb.deployment_file_url == "https://example.org/base"

    def test_env_wins_over_ini(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DEPLOYMENT_FILE_URL", self.CEITEC + "/")
        ini = tmp_path / "config.ini"
        ini.write_text("[pdb]\ndeployment_file_url: https://bioid.dyn.cloud.e-infra.cz\n")
        cfg = RunConfig.from_ini_path(str(ini))
        assert cfg.pdb.deployment_file_url == self.CEITEC  # trailing slash stripped

    def test_env_applies_to_default_fallback(self, monkeypatch, tmp_path, cwd=None):
        monkeypatch.setenv("DEPLOYMENT_FILE_URL", self.CEITEC)
        # from_default_ini falls back to cls() when config.ini absent in repo root;
        # env override must apply there too (loader.change-independent).
        cfg = RunConfig()
        from src_new.config.loader import _apply_deployment_env_overrides
        _apply_deployment_env_overrides(cfg)
        assert cfg.pdb.deployment_file_url == self.CEITEC

    def test_code_default_is_main_prod(self, monkeypatch):
        monkeypatch.delenv("DEPLOYMENT_FILE_URL", raising=False)
        assert RunConfig().pdb.deployment_file_url == self.PROD


class TestResolveValidationFile:
    UUID = "4653-20260924075449/input/topology.prmtop"

    def _mk(self, tmp_path):
        d = tmp_path / "4653" / "input"
        d.mkdir(parents=True)
        (d / "topology.prmtop").write_text("top")
        return tmp_path

    def test_happy_path(self, tmp_path):
        self._mk(tmp_path)
        t = resolve_validation_file(self.UUID, tmp_path)
        assert t is not None and t.is_file() and t.read_text() == "top"

    def test_missing_file_404(self, tmp_path):
        self._mk(tmp_path)
        assert resolve_validation_file("4653-20260924075449/input/nope.pdb", tmp_path) is None

    def test_missing_root_gives_none_not_error(self, tmp_path):
        assert resolve_validation_file(self.UUID, tmp_path / "no_such_root") is None

    def test_traversal_rejected(self, tmp_path):
        self._mk(tmp_path)
        for bad in ["4653-20260924075449/input/../config.ini",
                    "4653-20260924075449//abs",
                    "4653-20260924075449/input/"]:
            assert resolve_validation_file(bad, tmp_path) is None

    def test_uuid_shape_rejected(self, tmp_path):
        self._mk(tmp_path)
        for bad in ["abc-2026/input/x", "4653/input/x", "4653-xyz/input/x", "4653-20260924075449input/x"]:
            assert resolve_validation_file(bad, tmp_path) is None

    def test_stays_within_eid_root(self, tmp_path):
        # a second entry's file must not be reachable through a crafted rel path
        (tmp_path / "4513" / "input").mkdir(parents=True)
        (tmp_path / "4653" / "input").mkdir(parents=True)
        (tmp_path / "4513" / "input" / "a.txt").write_text("a")
        (tmp_path / "4653" / "input" / "b.txt").write_text("b")
        assert resolve_validation_file("4653-20260924075449/input/b.txt", tmp_path) is not None
        assert resolve_validation_file("4513-20260924075449/input/b.txt", tmp_path) is None
