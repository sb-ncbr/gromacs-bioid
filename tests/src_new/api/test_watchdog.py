"""Watchdog (src_new/api/watchdog.py): known-answers check and crash-loop alarms."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from src_new.api import alerts, watchdog

PRAGUE = ZoneInfo("Europe/Prague")


def results(status="success", uniprot="P00760", answered=("blast_swissprot_protein", "chembl_struct")):
    hits = [{"database": "uniprot", "identifier": uniprot, "ident_type": "UNIPROT_ID",
             "is_verified": True, "final_confidence": 90}] if uniprot else []
    return {"pipeline": {"status": status, "run_name": "Trypsin"}, "data": {
        "verification": {"seg_0_A": {"verified_hits": hits}},
        "identifiers": {"seg_0_A": {"fasta": {r: {"hits": ["x"]} for r in answered},
                                    "attempted": ["x"]}}}}


def write(runs: Path, rid: str, data: dict) -> None:
    (runs / rid).mkdir(parents=True, exist_ok=True)
    (runs / rid / "results.json").write_text(json.dumps(data))


class FakeRedis:
    def __init__(self):
        self.kv, self.lists = {}, {}

    def set(self, k, v, nx=False, ex=None, px=None):
        if nx and k in self.kv:
            return False
        self.kv[k] = v
        return True

    def lpush(self, k, v):
        self.lists.setdefault(k, []).insert(0, v)

    def ltrim(self, k, a, b):
        self.lists[k] = self.lists.get(k, [])[a:b + 1]

    def lrange(self, k, a, b):
        return self.lists.get(k, [])[a:b + 1]


@pytest.fixture
def env(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    sent = []
    monkeypatch.setenv("BAT3_ALERT_EMAIL", "someone@example.org")
    monkeypatch.setattr(alerts, "_send", lambda subject, body, to: sent.append((subject, body)))
    from src_new.api import security
    monkeypatch.setattr(security, "_redis", FakeRedis())
    reruns = iter(f"check-{i}" for i in range(100))
    created = []

    def fake_rerun(old_dir, creator_ip=None):
        rid = next(reruns)
        write(runs, rid, {"pipeline": {"status": "queued"}})
        created.append(rid)
        return rid, "token"
    monkeypatch.setattr("src_new.api.routes.runs._create_single_rerun", fake_rerun)
    write(runs, "case-1", results())
    watchdog.add_case(runs, "case-1", "Trypsin")
    return runs, sent, created


def test_add_case_records_answers_and_keeps_the_run(env):
    runs, _, _ = env
    case = watchdog.cases(runs)[0]
    assert case["expected"]["seg_0_A"] == {"state": "identified", "database": "UniProt", "identifier": "P00760",
                                           "answered_by": ["blast_swissprot_protein", "chembl_struct"]}
    assert json.loads((runs / "case-1/results.json").read_text())["pipeline"]["retention"] == {"policy": "preserve"}
    write(runs, "failed-run", results(status="failed"))
    with pytest.raises(ValueError):
        watchdog.add_case(runs, "failed-run")


def test_green_check_deletes_its_run(env):
    runs, sent, created = env
    watchdog.start_check(runs, now=1000.0)
    assert watchdog.progress_check(runs, now=1100.0)["status"] == "running"  # still queued
    write(runs, created[0], results())
    st = watchdog.progress_check(runs, now=1200.0)
    assert st["status"] == "green" and not (runs / created[0]).exists() and sent == []


def test_identity_change_is_red_and_mails(env):
    runs, sent, created = env
    watchdog.start_check(runs, now=1000.0)
    write(runs, created[0], results(uniprot="P00766"))
    st = watchdog.progress_check(runs, now=1200.0)
    assert st["status"] == "red"
    assert st["results"]["case-1"]["diffs"][0]["kind"] == "identity"
    assert (runs / created[0]).is_dir()  # kept for inspection, 7 days
    assert json.loads((runs / created[0] / "results.json").read_text())["pipeline"]["retention"]["days"] == 7
    assert len(sent) == 1 and "RED" in sent[0][0] and "P00766" in sent[0][1]


def test_a_missing_database_is_amber_once_red_twice(env):
    runs, sent, created = env
    for night, now in ((0, 1000.0), (1, 90000.0)):
        watchdog.start_check(runs, now=now)
        write(runs, created[night], results(answered=("blast_swissprot_protein",)))  # chembl silent
        st = watchdog.progress_check(runs, now=now + 100)
        diff = st["results"]["case-1"]["diffs"][0]
        assert diff == {**diff, "kind": "database", "resolver": "chembl_struct"}
        if night == 0:
            assert st["status"] == "amber" and sent == []
        else:
            assert st["status"] == "red" and diff["repeated"] and len(sent) == 1


def test_unfinished_run_times_out_amber(env):
    runs, sent, created = env
    watchdog.start_check(runs, now=1000.0)
    st = watchdog.progress_check(runs, now=1000.0 + watchdog.RUN_TIMEOUT_S + 1)
    assert st["status"] == "amber" and "did not finish" in st["results"]["case-1"]["diffs"][0]["observed"]


def test_accept_takes_the_observed_answer(env):
    runs, _, created = env
    watchdog.start_check(runs, now=1000.0)
    write(runs, created[0], results(uniprot="P00766"))
    watchdog.progress_check(runs, now=1200.0)
    assert watchdog.accept(runs, "case-1")["expected"]["seg_0_A"]["identifier"] == "P00766"


def test_schedule_is_daily_after_01_30_prague(env):
    runs, _, created = env
    at = lambda h, m, day=18: datetime(2026, 11, day, h, m, tzinfo=PRAGUE).timestamp()
    watchdog.tick(runs, now=at(1, 0))
    assert created == []  # too early
    watchdog.tick(runs, now=at(1, 35))
    assert created == ["check-0"]
    write(runs, "check-0", results())
    watchdog.tick(runs, now=at(1, 40))  # finishes the check
    watchdog.tick(runs, now=at(23, 0))
    assert created == ["check-0"]  # once a day
    watchdog.tick(runs, now=at(1, 31, day=19))
    assert created == ["check-0", "check-1"]


def test_crash_loops_mail_once(env, monkeypatch):
    _, sent, _ = env
    from src_new.api import admin
    monkeypatch.setattr(admin, "_deployments", lambda: [
        {"name": "bat3-ui-worker", "replicas": 10, "pods": [
            {"name": "p1", "waiting": "CrashLoopBackOff", "last_exit": "Error (1)"},
            {"name": "p2", "waiting": None}]},
        {"name": "bat3-ceitec-bat3-api", "replicas": 1, "pods": [{"name": "a", "waiting": None}]}])
    assert watchdog.crash_loops() == [{"deployment": "bat3-ui-worker", "pods": 1, "of": 10,
                                       "reason": "CrashLoopBackOff", "last_exit": "Error (1)"}]
    watchdog._check_crash_loops()
    watchdog._check_crash_loops()
    assert len(sent) == 1 and "bat3-ui-worker" in sent[0][0]
    assert alerts.recent()[0]["sent"] is True


def test_tick_never_raises(env, monkeypatch):
    runs, _, _ = env
    monkeypatch.setattr(watchdog, "_check_crash_loops", lambda: 1 / 0)
    monkeypatch.setattr(watchdog, "state", lambda r: 1 / 0)
    watchdog.tick(runs)


def test_no_recipient_means_logged_not_mailed(env, monkeypatch):
    _, sent, _ = env
    monkeypatch.delenv("BAT3_ALERT_EMAIL")
    assert alerts.alarm("k", "s", "b") is False and sent == []
