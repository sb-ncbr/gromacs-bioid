"""F-26 (2026-10-06): dispatch unification - freeze guard + canonical reroute.

Empirical basis (design .tmp/F26_DESIGN.md): legacy dispatch unused since
2026-08-06 (66 uuid8 runs; 3 unlinked queue rows ever). UI "Start" endpoints
(now rerouted) were the only live landmine.

Under test:
1. legacy_guard default posture is FROZEN; env allow-list unfreezes.
2. The four legacy endpoints refuse 410 without touching the DB.
3. schedule_validation refuses fast under freeze (no download/dispatch).
4. Both start-processing endpoints delegate to the CANONICAL
   queue_processor.process_validation_queue (no inline legacy loop left).
"""
from __future__ import annotations

import asyncio
import os
import sys
from unittest import mock

import pytest

# Root main.py pulls apscheduler at import time (scheduler bootstrap, line
# ~2214). The package is absent from the dev .venv (known env-parity class,
# same as the api suite's 2 env-fails) and irrelevant to dispatch logic ->
# stub it so the module imports. setdefault keeps a real install winning.
for _mod in (
    "apscheduler",
    "apscheduler.schedulers",
    "apscheduler.schedulers.background",
    "apscheduler.triggers",
    "apscheduler.triggers.interval",
):
    sys.modules.setdefault(_mod, mock.MagicMock())

from src_new.api.legacy_guard import FROZEN_MESSAGE, legacy_dispatch_allowed


def test_freeze_default_and_allow_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VALIDATION_LEGACY_DISPATCH", raising=False)
    assert legacy_dispatch_allowed() is False
    monkeypatch.setenv("VALIDATION_LEGACY_DISPATCH", "allow")
    assert legacy_dispatch_allowed() is True
    monkeypatch.setenv("VALIDATION_LEGACY_DISPATCH", "no")
    assert legacy_dispatch_allowed() is False


class TestLegacyEndpoints410:
    """Guard fires before any DB access - pass db=None and expect 410 raise."""

    def test_validate_entry(self) -> None:
        import main as root_main
        with pytest.raises(Exception) as excinfo:
            root_main.validate_entry(entry_id=1, request=None, db=None)
        assert getattr(excinfo.value, "status_code", None) == 410
        assert "F-26" in str(excinfo.value.detail)

    def test_batch_validate(self) -> None:
        import main as root_main
        with pytest.raises(Exception) as excinfo:
            root_main.batch_validate(request=None, db=None)
        assert getattr(excinfo.value, "status_code", None) == 410

    def test_retry_run(self) -> None:
        import main as root_main
        with pytest.raises(Exception) as excinfo:
            asyncio.run(
                root_main.retry_validation_run(run_id=1, db=None)
            )
        assert getattr(excinfo.value, "status_code", None) == 410

    def test_retry_entry(self) -> None:
        import main as root_main
        with pytest.raises(Exception) as excinfo:
            asyncio.run(
                root_main.retry_entry_validation(entry_id=1, db=None)
            )
        assert getattr(excinfo.value, "status_code", None) == 410


def test_schedule_validation_refuses_under_freeze(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VALIDATION_LEGACY_DISPATCH", raising=False)
    import tasks as root_tasks
    # Direct function call (no broker): must refuse BEFORE any download/dispatch.
    out = root_tasks.schedule_validation.run(
        entry_id=42,
        input_dir="/tmp/nope",
        results_path="/tmp/nope/results.json",
        config_path="/tmp/nope/config.ini",
    )
    assert out == "frozen-legacy-dispatch-42"


def _fake_db_session():
    class _Q:
        def __getattr__(self, _):
            return self
        def filter(self, *a, **k):
            return self
        def all(self):
            return []
        def scalar(self):
            return 0
        def count(self):
            return 0
    class _DB:
        def query(self, *a, **k):
            return _Q()
        def commit(self):
            pass
        def rollback(self):
            pass
        def close(self):
            pass
    return _DB()


class TestStartProcessingCanonicalReroute:
    def test_root_main_reroutes_to_canonical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import main as root_main
        import queue_processor

        calls: list = []
        def fake_dispatch(db, concurrency=5, batch_id=None):
            calls.append({"concurrency": concurrency, "batch_id": batch_id})
            return 3
        monkeypatch.setattr(queue_processor, "process_validation_queue", fake_dispatch)
        monkeypatch.setattr(root_main, "get_db", lambda: iter([_fake_db_session()]))

        out = asyncio.run(root_main.start_queue_processing())
        assert out["dispatched"] == 3
        assert out["path"].startswith("canonical")
        assert calls and calls[0]["concurrency"] == 100

    def test_src_new_reroutes_to_canonical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import queue_processor
        from src_new.api import main as api_main

        calls: list = []
        def fake_dispatch(db, concurrency=5, batch_id=None):
            calls.append({"concurrency": concurrency})
            return 7
        monkeypatch.setattr(queue_processor, "process_validation_queue", fake_dispatch)
        monkeypatch.setattr(api_main, "SessionLocal", lambda: _fake_db_session())

        out = asyncio.run(api_main.start_processing())
        assert out["success"] is True
        assert out["dispatched"] == 7
        assert calls and calls[0]["concurrency"] == 20

    def test_concurrency_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import main as root_main
        import queue_processor

        seen: list = []
        monkeypatch.setattr(
            queue_processor, "process_validation_queue",
            lambda db, concurrency=5, batch_id=None: seen.append(concurrency) or 0,
        )
        monkeypatch.setattr(root_main, "get_db", lambda: iter([_fake_db_session()]))
        monkeypatch.setenv("VALIDATION_MANUAL_DISPATCH_CONCURRENCY", "5")
        asyncio.run(root_main.start_queue_processing())
        assert seen == [5]
