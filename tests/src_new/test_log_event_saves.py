"""dm1 audit (I3): log events no longer rewrite results.json one by one
(28k warnings x 11 MB kept identify_molecules running for 2.5 h); the next
status change and finish_run still persist every event."""
import json

from src_new.results import results_manager as rm


def test_log_events_are_throttled_and_flushed(tmp_path, monkeypatch):
    writes = []
    real = rm.atomic_write_json
    monkeypatch.setattr(rm, "atomic_write_json", lambda p, d: (writes.append(1), real(p, d)))
    path = tmp_path / "results.json"
    m = rm.ResultsManager(path)
    m.start_run()
    before = len(writes)
    for i in range(2000):
        m.add_event("log", level="WARNING", logger="base", message=f"w{i}")
    assert len(writes) - before <= 2
    m.finish_run("success")
    events = [e for e in json.loads(path.read_text())["events"] if e["kind"] == "log"]
    assert len(events) == 2000


def test_other_events_still_save_at_once(tmp_path, monkeypatch):
    writes = []
    real = rm.atomic_write_json
    monkeypatch.setattr(rm, "atomic_write_json", lambda p, d: (writes.append(1), real(p, d)))
    m = rm.ResultsManager(tmp_path / "results.json")
    m.start_run()
    before = len(writes)
    for i in range(3):
        m.add_event("stage", message=f"s{i}")
    assert len(writes) - before == 3
