#!/usr/bin/env python3
"""sigstage_warmup -- async warm-up for cache pairs dropped by sigstage_heal.

Context (A2, 2026-10-07): the heal purge dropped 9,504 mirror-unresolvable
skel-zero pairs (stale zeros whose sides even the local PubChem mirror cannot
resolve). A campaign S7 rerun that re-discovers them lazily stalls the
32-thread ordered scan on web chains (~26h projection, empirically observed
as 0 scan progress + 71 open sockets over 10 min). This tool resolves the
dropped keys AHEAD of the rerun, out-of-band:

  - resolution uses the DEPLOYED validation_similarity resolvers (the A1
    engine's exact web chain: cactus -> pug -> ChemSpider -> IDSM), so
    successes are identical in provenance to engine-computed pairs;
  - computed values (including genuine zeros) are appended to pairs.jsonl
    in engine-identical format (drift-guarded by test);
  - keys that stay unresolvable after the full web chain are TRUE ghosts
    (deprecated/deleted records) -- written to warmup_ghosts.json as the
    input list for A3 (ghost-GT curation / mirror refresh);
  - failures persist nothing (A1 semantics); the tool is re-runnable.

Writes: appends to PAIR_FILE (resolved only) + warmup_ghosts.json under
sigstage/casefiles. Read-only otherwise.
"""
import argparse
import importlib.util
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

DATA = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")
PAIR_FILE = os.path.join(os.environ.get("SIM_CACHE_ROOT",
                                        os.path.join(DATA, "sim_cache")),
                         "pairs.jsonl")
GHOST_OUT = os.path.join(DATA, "sigstage", "casefiles", "warmup_ghosts.json")
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(name, *candidates):
    for path in candidates:
        if os.path.isfile(path):
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise RuntimeError(f"{name} not importable from {candidates}")


def load_vsim():
    return _load("warmup_vsim",
                 os.path.join(DATA, "validation_similarity.py"),
                 os.path.join(_REPO_ROOT, "scripts", "validation_similarity.py"))


def load_heal():
    return _load("warmup_heal",
                 os.path.join(DATA, "sigstage_heal.py"),
                 os.path.join(_REPO_ROOT, "scripts", "stats", "sigstage_heal.py"))


def pair_line(key, sim):
    """MUST byte-match SimEngine._save_pair's f"{key}\\t{sim:.6f}\\n"
    (drift-guarded by test)."""
    return f"{key}\t{sim:.6f}\n"


def resolve_pair(key, vsim, heal):
    """(key, sim|None, class): resolved | ghost | unparseable | bad_key.
    ghost = full web chain exhausted (A3 curation input);
    unparseable = resolved smiles but skeleton FP failed."""
    sides = heal.pair_key_sides(key)
    if sides is None:
        return key, None, "bad_key"
    (ka, a), (kb, b) = sides
    try:
        sa = (vsim._inchikey_smiles(a) if ka == "inchikey"
              else vsim._cid_smiles(a))
        sb = (vsim._inchikey_smiles(b) if kb == "inchikey"
              else vsim._cid_smiles(b))
    except Exception:
        return key, None, "ghost"
    sim = heal.fresh_tanimoto(sa, sb)
    if sim is None:
        return key, None, "unparseable"
    return key, sim, "resolved"


def warmup(args):
    vsim = load_vsim()
    heal = load_heal()
    keys = [l.strip() for l in open(args.keys_file) if l.strip()]
    if args.limit:
        keys = keys[: args.limit]
    results = []
    with ThreadPoolExecutor(max_workers=args.threads) as ex:
        for i, res in enumerate(ex.map(
                lambda k: resolve_pair(k, vsim, heal), keys)):
            results.append(res)
            if (i + 1) % args.progress_every == 0:
                print(f"  ...resolved-pass {i + 1}/{len(keys)}", file=sys.stderr)
    resolved = {k: s for k, s, c in results if c == "resolved"}
    ghosts = sorted(k for k, s, c in results if c == "ghost")
    unparseable = sorted(k for k, s, c in results if c == "unparseable")
    bad = sorted(k for k, s, c in results if c == "bad_key")
    if not args.dry_run and resolved:
        with open(PAIR_FILE, "a") as fh:
            for k in sorted(resolved):
                fh.write(pair_line(k, resolved[k]))
    os.makedirs(os.path.dirname(GHOST_OUT), exist_ok=True)
    with open(GHOST_OUT, "w") as fh:
        json.dump({"dropped_input": len(keys),
                   "ghosts": ghosts, "unparseable": unparseable,
                   "bad_keys": bad}, fh, indent=1)
    out = {"input_keys": len(keys), "resolved": len(resolved),
           "ghost": len(ghosts), "unparseable": len(unparseable),
           "bad_key": len(bad),
           "appended": 0 if args.dry_run else len(resolved),
           "ghost_out": GHOST_OUT, "dry_run": bool(args.dry_run)}
    print(json.dumps(out, indent=1))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("keys_file")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--progress-every", type=int, default=500)
    ap.add_argument("--dry-run", action="store_true",
                    help="resolve but do not append to pairs.jsonl")
    warmup(ap.parse_args(argv))


if __name__ == "__main__":
    main()
