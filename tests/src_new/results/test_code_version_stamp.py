"""bughunt verify §5: pipeline.code_version in every results.json.

New results.json files carry pipeline.code_version (BAT3_CODE_VERSION env >
git commit of the checkout > 'unknown'). Existing files are NEVER
retro-modified (old-run doctrine).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src_new.results.results_manager import ResultsManager


class TestCodeVersionStamp:
    def test_new_results_json_carries_code_version(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BAT3_CODE_VERSION", "git-abc1234")
        p = tmp_path / "results.json"
        ResultsManager(str(p))
        payload = json.loads(p.read_text())
        assert payload["pipeline"]["code_version"] == "git-abc1234"

    def test_git_fallback(self, tmp_path, monkeypatch):
        monkeypatch.delenv("BAT3_CODE_VERSION", raising=False)
        p = tmp_path / "results.json"
        ResultsManager(str(p))
        payload = json.loads(p.read_text())
        # in the repo checkout this resolves to git-<short>; keep it lenient
        assert payload["pipeline"]["code_version"]

    def test_existing_results_not_retro_modified(self, tmp_path):
        p = tmp_path / "results.json"
        old = {
            "schema_version": "0.1.0", "created_at": "2026-10-01T00:00:00",
            "updated_at": "2026-10-01T00:00:00",
            "pipeline": {"name": "BAT3", "status": "success", "metadata": {}},
            "tasks": {}, "artifacts": {}, "warnings": [],
            "critical_errors": [], "events": [], "data": {},
        }
        p.write_text(json.dumps(old))
        ResultsManager(str(p))
        payload = json.loads(p.read_text())
        assert "code_version" not in payload["pipeline"]
