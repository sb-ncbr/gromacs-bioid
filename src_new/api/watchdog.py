"""Watchdog (2026-11-17): crash-loop alarms and the nightly known-answers check.

Called from the run reaper's leader loop every few minutes (tick()); never
raises into it.

Known answers: a few runs whose answers are known to be right ("cases").
Each night (01:30 Europe/Prague) every case is rerun through the normal
rerun path, and each molecule's answer is compared with the case's recorded
one: the identity (database + identifier + state) and the databases that
answered. Failures that degrade into "fewer hits" (a client missing, a
service changing, a database gone) show up here and nowhere else.

- identity changed                       -> red
- a database stopped answering            -> amber; red when the same
                                             database is missing two nights running
- a database not asked (PubChem breaker    -> amber, never red: the service was
  open, e.g. NCBI throttling us)              down, not the answer wrong
- a rerun did not finish (4 h)            -> amber
Red mails an alarm. Green check runs are deleted; others are kept 7 days.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .best_hit import molecule_result

log = logging.getLogger(__name__)

CASES = "_settings/known_answers.json"
STATE = "_settings/known_answers_state.json"
CHECK_AT = (1, 30)          # local time, Europe/Prague
RUN_TIMEOUT_S = 4 * 3600
CRASH_REASONS = {"CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull",
                 "CreateContainerConfigError", "CreateContainerError"}
TERMINAL = {"success", "failed", "cancelled", "timeout", "error"}


# -- storage -------------------------------------------------------------------

def _read(runs_dir: Path, rel: str, default):
    try:
        return json.loads((runs_dir / rel).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(runs_dir: Path, rel: str, value) -> None:
    path = runs_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.urandom(4).hex()}.tmp")
    tmp.write_text(json.dumps(value, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def cases(runs_dir: Path) -> list[dict[str, Any]]:
    return _read(runs_dir, CASES, [])


def state(runs_dir: Path) -> dict[str, Any]:
    return _read(runs_dir, STATE, {})


# -- answers -------------------------------------------------------------------

def answers(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per molecule: the answer the results page shows, and the databases that answered."""
    d = data.get("data") or {}
    out: dict[str, dict[str, Any]] = {}
    for seg, ver in (d.get("verification") or {}).items():
        if not isinstance(ver, dict) or seg.startswith("_"):
            continue
        r = molecule_result(ver.get("verified_hits") or [])
        idents = (d.get("identifiers") or {}).get(seg)
        out[seg] = {"state": r["state"], "database": r["database"], "identifier": r["identifier"],
                    "answered_by": sorted(_answered_by(idents)),
                    "not_asked": sorted(_not_asked(idents))}
    return out


def _answered_by(seg_idents: Any) -> set[str]:
    found: set[str] = set()
    if not isinstance(seg_idents, dict):
        return found
    for gen, by_resolver in seg_idents.items():
        if gen.startswith("_") or not isinstance(by_resolver, dict):
            continue
        for resolver, res in by_resolver.items():
            if isinstance(res, dict) and res.get("hits"):
                found.add(resolver)
    return found


def _not_asked(seg_idents: Any) -> set[str]:
    """Resolvers the PubChem circuit breaker skipped ('name:skipped:breaker'
    in attempted; the similarity phase records the same name)."""
    skipped: set[str] = set()
    if not isinstance(seg_idents, dict):
        return skipped
    for gen, by_resolver in seg_idents.items():
        if gen.startswith("_") or not isinstance(by_resolver, dict):
            continue
        for entry in by_resolver.get("attempted") or []:
            if isinstance(entry, str) and entry.endswith(":skipped:breaker"):
                skipped.add(entry.split(":", 1)[0])
    return skipped


def compare(expected: dict[str, dict], observed: dict[str, dict]) -> list[dict[str, Any]]:
    """Differences: kind 'identity' (red), 'database' (amber) or 'not_asked'
    (amber; the breaker skipped it, so it neither counts nor repeats)."""
    diffs = []
    for seg, exp in expected.items():
        obs = observed.get(seg)
        if obs is None:
            diffs.append({"segment": seg, "kind": "identity", "expected": _label(exp), "observed": "molecule missing"})
            continue
        if (exp["identifier"], exp["database"], exp["state"]) != (obs["identifier"], obs["database"], obs["state"]):
            diffs.append({"segment": seg, "kind": "identity", "expected": _label(exp), "observed": _label(obs)})
        not_asked = set(obs.get("not_asked") or [])
        for resolver in sorted(set(exp.get("answered_by") or []) - set(obs.get("answered_by") or [])):
            if resolver.split("@", 1)[0] in not_asked:
                diffs.append({"segment": seg, "kind": "not_asked", "resolver": resolver,
                              "expected": "answered", "observed": "not asked (PubChem unreachable)"})
                continue
            diffs.append({"segment": seg, "kind": "database", "resolver": resolver,
                          "expected": "answered", "observed": "no answer"})
    return diffs


def _label(a: dict) -> str:
    return f"{a['database']} {a['identifier']} ({a['state']})" if a.get("identifier") else f"not identified ({a['state']})"


# -- cases (admin) ---------------------------------------------------------------

def add_case(runs_dir: Path, run_id: str, label: str = "") -> dict[str, Any]:
    """Record a finished run's current answers as the known answers; keep the run forever."""
    from . import retention
    data = json.loads((runs_dir / run_id / "results.json").read_text(encoding="utf-8"))
    if (data.get("pipeline") or {}).get("status") != "success":
        raise ValueError("Only a successful run can be a known-answers case.")
    expected = answers(data)
    if not expected:
        raise ValueError("This run has no identified molecules to check.")
    retention.set_policy(runs_dir / run_id, {"policy": "preserve"})
    items = [c for c in cases(runs_dir) if c["run_id"] != run_id]
    case = {"run_id": run_id, "label": label or (data.get("pipeline") or {}).get("run_name") or run_id,
            "expected": expected, "added_at": datetime.now(timezone.utc).isoformat()}
    _write(runs_dir, CASES, items + [case])
    return case


def remove_case(runs_dir: Path, run_id: str) -> None:
    _write(runs_dir, CASES, [c for c in cases(runs_dir) if c["run_id"] != run_id])


def accept(runs_dir: Path, run_id: str) -> dict[str, Any]:
    """Take the last check's observed answers as the case's known answers."""
    obs = (state(runs_dir).get("results") or {}).get(run_id, {}).get("observed")
    if not obs:
        raise ValueError("No observed answers for this case in the last check.")
    items = cases(runs_dir)
    for c in items:
        if c["run_id"] == run_id:
            c["expected"] = obs
            c["accepted_at"] = datetime.now(timezone.utc).isoformat()
    _write(runs_dir, CASES, items)
    return next(c for c in items if c["run_id"] == run_id)


# -- the check -------------------------------------------------------------------

def start_check(runs_dir: Path, now: Optional[float] = None) -> dict[str, Any]:
    from .routes.runs import _create_single_rerun
    now = now or time.time()
    runs: dict[str, Optional[str]] = {}
    for c in cases(runs_dir):
        try:
            created = _create_single_rerun(runs_dir / c["run_id"], creator_ip=None)
            runs[c["run_id"]] = created[0] if created else None
        except Exception as exc:
            log.error("known answers: rerun of %s failed: %s", c["run_id"], exc)
            runs[c["run_id"]] = None
    prev = state(runs_dir)
    st = {"started_at": now, "finished_at": None, "runs": runs, "status": "running",
          "previous": {k: v.get("diffs", []) for k, v in (prev.get("results") or {}).items()},
          "last_completed": _summary(prev) if prev.get("finished_at") else prev.get("last_completed")}
    _write(runs_dir, STATE, st)
    return st


def _summary(st: dict[str, Any]) -> dict[str, Any]:
    return {k: st.get(k) for k in ("started_at", "finished_at", "status")}


def progress_check(runs_dir: Path, now: Optional[float] = None) -> dict[str, Any]:
    """Compare finished check runs; finish the check when all are done or timed out."""
    now = now or time.time()
    st = state(runs_dir)
    if st.get("status") != "running":
        return st
    by_case = {c["run_id"]: c for c in cases(runs_dir)}
    results: dict[str, Any] = {}
    pending = False
    for case_id, check_id in (st.get("runs") or {}).items():
        case = by_case.get(case_id)
        if case is None:
            continue
        if not check_id:
            results[case_id] = {"status": "amber", "diffs": [{"kind": "run", "observed": "rerun could not be created"}]}
            continue
        try:
            data = json.loads((runs_dir / check_id / "results.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        status = (data.get("pipeline") or {}).get("status")
        if status not in TERMINAL:
            if now - st["started_at"] < RUN_TIMEOUT_S:
                pending = True
                continue
            results[case_id] = {"status": "amber", "check_run": check_id,
                                "diffs": [{"kind": "run", "observed": f"did not finish in {RUN_TIMEOUT_S // 3600} h"}]}
            continue
        observed = answers(data)
        diffs = compare(case["expected"], observed)
        if status != "success":
            diffs.insert(0, {"kind": "run", "observed": f"run {status}"})
        previous = {(d.get("segment"), d.get("resolver")) for d in (st.get("previous") or {}).get(case_id, [])
                    if d.get("kind") == "database"}
        for d in diffs:
            if d["kind"] == "database" and (d["segment"], d["resolver"]) in previous:
                d["repeated"] = True
        red = any(d["kind"] in ("identity", "run") or d.get("repeated") for d in diffs)
        results[case_id] = {"status": "red" if red else ("amber" if diffs else "green"),
                            "check_run": check_id, "diffs": diffs, "observed": observed}
    if pending:
        st["results"] = results
        _write(runs_dir, STATE, st)
        return st
    order = {"green": 0, "amber": 1, "red": 2}
    st.update(results=results, finished_at=now,
              status=max((r["status"] for r in results.values()), key=order.get, default="green"))
    _write(runs_dir, STATE, st)
    _clean_up(runs_dir, results)
    if st["status"] == "red":
        _alarm_red(st, by_case)
    return st


def _clean_up(runs_dir: Path, results: dict[str, Any]) -> None:
    from . import retention
    for r in results.values():
        check_id = r.get("check_run")
        if not check_id or not (runs_dir / check_id).is_dir():
            continue
        try:
            if r["status"] == "green":
                shutil.rmtree(runs_dir / check_id)
            else:
                retention.set_policy(runs_dir / check_id, {"policy": "days", "days": 7})
        except Exception as exc:
            log.warning("known answers: cleanup of %s failed: %s", check_id, exc)


def _alarm_red(st: dict[str, Any], by_case: dict[str, dict]) -> None:
    from . import alerts
    lines = []
    for case_id, r in st["results"].items():
        if r["status"] == "green":
            continue
        lines.append(f"{by_case.get(case_id, {}).get('label', case_id)} [{r['status']}]"
                     f"  check run: {r.get('check_run') or '-'}")
        for d in r["diffs"]:
            what = d.get("resolver") or d.get("segment") or ""
            lines.append(f"  - {d['kind']} {what}: expected {d.get('expected', '-')}, got {d['observed']}"
                         + (" (second night)" if d.get("repeated") else ""))
    day = datetime.fromtimestamp(st["started_at"], timezone.utc).date().isoformat()
    alerts.alarm(f"nightly:{day}", "Nightly known-answers check is RED",
                 "BioID's nightly check found answers that changed:\n\n" + "\n".join(lines)
                 + "\n\nDetails and 'accept as new answer' on the admin page (/admin).", every_s=20 * 3600)


def _due(st: dict[str, Any], now: float) -> bool:
    from zoneinfo import ZoneInfo
    local = datetime.fromtimestamp(now, ZoneInfo("Europe/Prague"))
    if (local.hour, local.minute) < CHECK_AT:
        return False
    started = st.get("started_at")
    if started is None:
        return True
    return datetime.fromtimestamp(started, ZoneInfo("Europe/Prague")).date() < local.date()


# -- crash loops ---------------------------------------------------------------

def crash_loops() -> list[dict[str, Any]]:
    from . import admin
    broken = []
    for d in admin._deployments():
        bad = [p for p in d.get("pods") or [] if p.get("waiting") in CRASH_REASONS]
        if bad:
            broken.append({"deployment": d["name"], "pods": len(bad), "of": d.get("replicas"),
                           "reason": bad[0]["waiting"], "last_exit": bad[0].get("last_exit")})
    return broken


def _check_crash_loops() -> None:
    from . import alerts
    for b in crash_loops():
        alerts.alarm(
            f"crashloop:{b['deployment']}", f"{b['deployment']}: {b['pods']} pod(s) in {b['reason']}",
            f"Deployment {b['deployment']}: {b['pods']} of {b['of']} pods are in {b['reason']}"
            f" (last exit: {b['last_exit'] or 'n/a'}).\n\nCheck the admin page (/admin) or"
            f" `kubectl -n ceitec-biodata-ns get pods`.")


def _check_services() -> None:
    """Alarms from the service measurements (service_stats.py): a service
    failing most calls for 30 min, and too many NCBI searches at once (they
    share the database volume's ~50 MB/s; no lock, only this alarm)."""
    from src_new import service_stats as ss
    from . import alerts
    client = ss.reader()
    if client is None:
        return
    for f in ss.failing(ss.summarize(ss.window(client, 1800))):
        alerts.alarm(
            f"service:{f['service']}", f"{f['service']} failing: {f['errors']} of {f['calls']} calls in 30 min",
            f"{f['service']} failed {f['errors']} of {f['calls']} calls in the last 30 minutes.\n"
            f"Outcomes: {json.dumps(f['outcomes'], sort_keys=True)}\n\n"
            "Runs searching it in this time are incomplete. See Services on the admin page (/admin).")
    ncbi = [r for r in ss.running_now(client) if r.get("service") in ss.NCBI_SERVICES]
    if len(ncbi) >= ss.ncbi_alarm_at():
        alerts.alarm(
            "ncbi-running", f"{len(ncbi)} NCBI nr/nt searches running at once",
            f"{len(ncbi)} NCBI nr/nt/core_nt searches are running at once (alarm at "
            f"{ss.ncbi_alarm_at()}). They share the database volume's ~50 MB/s: at 3 an nr "
            "search needs about 6.6 h, at 6 none fits the 12 h limit.\n\n"
            + "\n".join(f"- {r['service']} on {r.get('pod', '?')} since "
                         f"{time.strftime('%H:%M', time.localtime(r.get('started', 0)))}" for r in ncbi))


# -- reaper hook ---------------------------------------------------------------

def tick(runs_dir: Path, now: Optional[float] = None) -> None:
    """One watchdog step; never raises."""
    now = now or time.time()
    try:
        _check_crash_loops()
    except Exception as exc:
        log.warning("watchdog: crash-loop check failed: %s", exc)
    try:
        _check_services()
    except Exception as exc:
        log.warning("watchdog: service check failed: %s", exc)
    try:
        st = state(runs_dir)
        if st.get("status") == "running":
            progress_check(runs_dir, now)
        elif cases(runs_dir) and _due(st, now):
            start_check(runs_dir, now)
    except Exception as exc:
        log.warning("watchdog: known-answers check failed: %s", exc)
