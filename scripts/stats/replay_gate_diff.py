"""Normalized A/B diff of two results.json trees for the replay regression gate.

Compares a baseline (old production code output) with a replay (new code) in
three tiers so that ONLY actionable differences fail the gate:

  STRICT   — must be byte-equal after normalization:
             pipeline.input_kind/status (when baseline was success),
             data.input decision+bundle file typing, data.loading
             (final_strategy, attempts sequence of strategy+status+error_code),
             data.universe parameters, data.signatures, data.molecules
             (count/unique_count/type_counts), data.fragments count,
             export artifact name set.
  INFO     — reported, never fails: external-drift surfaces (identifiers,
             verification status summaries).
  IGNORED  — timestamps, ids, absolute paths, events/logs, render paths,
             stage_errors, resolver-cache traces.

Usage:
  replay_gate_diff.py <baseline_results.json> <new_results.json>
  replay_gate_diff.py --batch <mapping.txt>   # lines: <baseline>\t<new>
Exit 0 = gate passes, 2 = strict diff found, 3 = usage/io error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ------------------------------------------------------------------ normalize
_IGNORED_KEY_PARTS = (
    "_at",           # created_at/started_at/finished_at + every *_at timestamp
    "run_id",
    "celery",
    "working_directory",
    "output_directory",
    "results_path",
    "events",
    "results_log",
)
_ALLOWED_DRIFT_DATA_KEYS = ("identifiers", "verification")


def _norm(value):
    """Recursively normalize for byte-comparison: drop volatile keys, scrub
    absolute paths, sort dict keys (lists keep order)."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if any(part in k for part in _IGNORED_KEY_PARTS):
                continue
            out[k] = _norm(v)
        return out
    if isinstance(value, list):
        return [_norm(v) for v in value]
    if isinstance(value, str) and (value.startswith("/app/") or value.startswith("/data/")):
        return "<path>"
    return value


# ------------------------------------------------------------------- compares
def _attempts_shape(attempts):
    """Attempts are volatile in used_files/timestamps; keep the decision chain."""
    return [
        {k: a.get(k) for k in ("strategy", "status", "error_code") if a.get(k) is not None}
        for a in (attempts or [])
    ]


def _export_names(data):
    exp = (data.get("exports") or {})
    if isinstance(exp, dict):
        return sorted(exp.keys())
    if isinstance(exp, list):
        return sorted(str(e) for e in exp)
    return []


def _verification_summary(data):
    ver = data.get("verification") or {}
    if not isinstance(ver, dict):
        return ver
    out = {}
    for seg, rec in ver.items():
        if isinstance(rec, dict):
            out[seg] = {k: v for k, v in rec.items()
                        if k in ("status", "verified", "confidence", "method")}
    return out


def _identifier_summary(data):
    ident = data.get("identifiers") or {}
    if not isinstance(ident, dict):
        return {}
    counts = {}
    for seg, gens in ident.items():
        if isinstance(gens, dict):
            counts[seg] = {
                g: len((rec or {}).get("candidates") or [])
                for g, rec in gens.items() if isinstance(rec, dict)
            }
    return counts


def compare(base: dict, new: dict) -> dict:
    """Return {'ok': bool, 'strict': [...], 'info': [...]} verdict dict."""
    strict: list[str] = []
    info: list[str] = []

    b_data, n_data = base.get("data", {}) or {}, new.get("data", {}) or {}

    # --- tier STRICT: pipeline level
    b_pipe, n_pipe = base.get("pipeline", {}) or {}, new.get("pipeline", {}) or {}
    if b_pipe.get("input_kind") != n_pipe.get("input_kind"):
        strict.append(f"pipeline.input_kind: {b_pipe.get('input_kind')} -> {n_pipe.get('input_kind')}")
    if (b_pipe.get("status") == "success") != (n_pipe.get("status") == "success"):
        strict.append(f"pipeline.status: {b_pipe.get('status')} -> {n_pipe.get('status')}")

    # --- tier STRICT: input decision + bundle typing
    b_in, n_in = _norm(b_data.get("input") or {}), _norm(n_data.get("input") or {})
    if b_in != n_in:
        strict.append("data.input differs (decision or bundle file typing)")

    # --- tier STRICT: loading
    b_lo, n_lo = b_data.get("loading") or {}, n_data.get("loading") or {}
    for key in ("final_strategy",):
        if b_lo.get(key) != n_lo.get(key):
            strict.append(f"loading.{key}: {b_lo.get(key)!r} -> {n_lo.get(key)!r}")
    b_att, n_att = _attempts_shape(b_lo.get("attempts")), _attempts_shape(n_lo.get("attempts"))
    if b_att != n_att:
        strict.append(f"loading.attempts: {json.dumps(b_att)[:160]} -> {json.dumps(n_att)[:160]}")
    if b_pipe.get("status") == "success" and not n_lo.get("success"):
        strict.append("loading.success: True -> False")

    # --- tier STRICT: universe parameters
    b_un, n_un = _norm(b_data.get("universe") or {}), _norm(n_data.get("universe") or {})
    if b_un != n_un:
        strict.append("data.universe parameters differ")

    # --- tier STRICT: signatures / molecules / fragments / exports
    for key in ("signatures", "fragments"):
        if _norm(b_data.get(key) or {}) != _norm(n_data.get(key) or {}):
            strict.append(f"data.{key} differs")
    for key in ("count", "unique_count", "type_counts"):
        b_mol, n_mol = (b_data.get("molecules") or {}), (n_data.get("molecules") or {})
        if _norm(b_mol.get(key)) != _norm(n_mol.get(key)):
            strict.append(f"molecules.{key}: {b_mol.get(key)!r} -> {n_mol.get(key)!r}")
    if _export_names(b_data) != _export_names(n_data):
        strict.append(f"export artifacts: {_export_names(b_data)} -> {_export_names(n_data)}")

    # --- tier INFO: external-drift surfaces
    b_ver, n_ver = _verification_summary(b_data), _verification_summary(n_data)
    if b_ver != n_ver:
        info.append(f"verification drift: {json.dumps(b_ver)[:140]} -> {json.dumps(n_ver)[:140]}")
    b_id, n_id = _identifier_summary(b_data), _identifier_summary(n_data)
    if b_id != n_id:
        info.append("identifier candidate counts drift")

    return {"ok": len(strict) == 0, "strict": strict, "info": info}


def _load_json(path: Path) -> dict:
    with open(path) as fh:
        return json.load(fh)


def _report(label: str, verdict: dict) -> None:
    head = "PASS" if verdict["ok"] else "DIFF"
    print(f"[{head}] {label}")
    for s in verdict["strict"]:
        print(f"  STRICT {s}")
    for i in verdict["info"]:
        print(f"  info   {i}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline", nargs="?", help="baseline results.json")
    ap.add_argument("new", nargs="?", help="replay results.json")
    ap.add_argument("--batch", help="mapping file: '<baseline>\\t<new>' per line")
    args = ap.parse_args()

    pairs: list[tuple[Path, Path]] = []
    if args.batch:
        for line in Path(args.batch).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            b, n = line.split("\t")
            pairs.append((Path(b), Path(n)))
    elif args.baseline and args.new:
        pairs.append((Path(args.baseline), Path(args.new)))
    else:
        ap.error("give two files or --batch")

    rc = 0
    for b_path, n_path in pairs:
        try:
            verdict = compare(_load_json(b_path), _load_json(n_path))
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {b_path} vs {n_path}: {type(exc).__name__}: {exc}")
            rc = 3
            continue
        _report(f"{b_path.parent.name} vs {n_path.parent.name}", verdict)
        if not verdict["ok"]:
            rc = max(rc, 2)
    return 0 if rc == 0 else rc


if __name__ == "__main__":
    sys.exit(main())
