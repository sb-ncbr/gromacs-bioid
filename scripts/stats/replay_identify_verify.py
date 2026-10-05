"""Offline IDENTIFY+VERIFY replay: rebuild identifier candidates AND verification
blocks of stored results using the CURRENT pipeline code.

Scope/discipline:
  - Results' own signatures are read (never rewritten). identifiers + verification
    blocks are REBUILT (legacy-era entries have resolver 'attempted' stubs with no
    candidates - verification alone cannot invent them).
  - ResolutionManager.resolve_all() regenerates identifiers/{seg}/{gen}/{resolver}.
  - VerificationManager.verify_all() recomputes verification per entry.
  - Results file atomically replaced only when output actually differs.
  - --dry-run: report what would change, write nothing.
  - Honors VALIDATION_SKIP_PUG=1 (cluster-IP to PUG is blocked).

Usage:
  replay_identify_verify.py [--dry-run] [--entry ID] [--entries-file F] [--threads N]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import time

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src_new.config.loader import RunConfig, load_config_from_path


def _production_config() -> RunConfig:
    """Load the production config (/data/validation/config_shared.ini) when present:
    without it the tool would run with repo defaults (blast_nt timeouts 300s each,
    config-tuned resolver disables/housekeeping ignored)."""
    for cand in ("/data/validation/config_shared.ini",):
        try:
            if os.path.exists(cand):
                return load_config_from_path(cand)
        except Exception:
            break
    return RunConfig()
from src_new.results.results_manager import ResultsManager
from src_new.verification.manager import VerificationManager
from src_new.identification.registry import IdentifierRegistry, get_default_resolvers
from src_new.identification.resolution_manager import IdentifierResolutionManager

ROOT = "/data/validation"
CHEM = ("PUBCHEM_CID", "PUBCHEM_ID", "PUBCHEM", "INCHIKEY", "INCHI_KEY",
        "CHEMBL_ID", "CHEBI_ID", "SMILES", "SELFIES")


def _chem_verified_count(ver: dict) -> int:
    n = 0
    for seg in (ver or {}).values():
        for h in ((seg or {}).get("verified_hits") or []):
            if h.get("is_verified") and (h.get("ident_type") or "").upper() in CHEM:
                n += 1
    return n


def _chem_candidate_count(ids: dict) -> int:
    n = 0
    for seg in (ids or {}).values():
        if not isinstance(seg, dict):
            continue
        for per_res in seg.values():
            if isinstance(per_res, dict):
                hits = per_res.get("hits") or per_res.get("results") or []
                for h in (hits if isinstance(hits, list) else []):
                    t = (h.get("identifier_type") or h.get("type") or h.get("ident_type") or "").upper()
                    if t in CHEM:
                        n += 1
    return n


def _rebuild_for(eid: int, doc: dict) -> tuple[dict, dict]:
    # Name/CCD + BLAST resolvers resolve their databases relative to CWD
    # (config.names.*_db = "databases/<name>.json"). The image ships them at
    # /app/databases; without this chdir the entire name->InChIKey channel
    # silently no-ops (exactly the legacy-era zero-candidates failure shape).
    if os.path.isdir("/app/databases") and not os.getcwd().startswith("/app"):
        os.chdir("/app")
    payload = json.loads(json.dumps(doc))
    rm = ResultsManager.__new__(ResultsManager)
    rm._payload = payload
    rm._save = lambda: None
    config = _production_config()
    registry = IdentifierRegistry(get_default_resolvers(config))
    mgr = IdentifierResolutionManager(registry, config)
    workdir = os.path.join(ROOT, str(eid))
    try:
        mgr.resolve_all(rm, working_directory=workdir)
    except Exception as exc:
        raise RuntimeError(f"resolve_all: {type(exc).__name__}: {exc}") from exc
    new_ids = rm.get_data("identifiers") or {}
    per = VerificationManager(config).verify_all(rm)
    out_ver = {}
    for seg, hits in per.items():
        out_ver[seg] = {"verified_hits": [dataclasses.asdict(h) for h in hits]}
    return new_ids, out_ver


def _process_one(eid):
    path = os.path.join(ROOT, str(eid), "results.json")
    try:
        doc = json.load(open(path))
    except Exception:
        return None
    old_ids = (doc.get("data") or {}).get("identifiers") or {}
    old_ver = (doc.get("data") or {}).get("verification") or {}
    try:
        new_ids, new_ver = _rebuild_for(eid, doc)
    except Exception as exc:
        return ("err", eid, exc)
    return (eid, doc, old_ids, old_ver, new_ids, new_ver)


def run(entries, dry_run: bool, threads: int = 4):
    changed = chem_cand_delta = chem_ver_delta = 0
    examples = []
    from concurrent.futures import ThreadPoolExecutor, as_completed
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = {ex.submit(_process_one, eid): eid for eid in entries}
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if done % 5 == 0:
                print(f"[{done}/{len(entries)}] {time.time()-t0:.0f}s", flush=True)
            if r is None:
                continue
            if r and r[0] == "err":
                print(f"  {r[1]}: replay error {type(r[2]).__name__}: {str(r[2])[:200]}", flush=True)
                continue
            eid, doc, old_ids, old_ver, new_ids, new_ver = r
            if new_ids != old_ids or new_ver != old_ver:
                changed += 1
                oc, nc = _chem_candidate_count(old_ids), _chem_candidate_count(new_ids)
                ov, nv = _chem_verified_count(old_ver), _chem_verified_count(new_ver)
                chem_cand_delta += max(0, nc - oc)
                chem_ver_delta += max(0, nv - ov)
                if len(examples) < 12:
                    examples.append((eid, oc, nc, ov, nv))
                if not dry_run:
                    data = dict(doc)
                    data.setdefault("data", {})["identifiers"] = new_ids
                    data.setdefault("data", {})["verification"] = new_ver
                    path = os.path.join(ROOT, str(eid), "results.json")
                    tmp = path + ".tmp"
                    with open(tmp, "w") as fh:
                        json.dump(data, fh)
                    os.replace(tmp, path)
    print(f"processed={len(entries)} changed={changed} chemCandidates+={chem_cand_delta} chemVerified+={chem_ver_delta} dry={dry_run}", flush=True)
    print("  (eid, chemCandBefore, chemCandAfter, chemVerBefore, chemVerAfter)")
    for t in examples:
        print("   ", t, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry", type=int, default=0)
    ap.add_argument("--entries-file", type=str, default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    if a.entries_file:
        with open(a.entries_file) as fh:
            entries = [int(x) for x in fh if x.strip()]
    elif a.entry:
        entries = [a.entry]
    else:
        raise SystemExit("provide --entry or --entries-file")
    run(entries, a.dry_run, threads=a.threads)


if __name__ == "__main__":
    main()
