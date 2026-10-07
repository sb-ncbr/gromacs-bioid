#!/usr/bin/env python3
"""sigstage_heal -- measure + repair stale-negative pairs in the sim pair cache.

Evidence (2026-10-07, case file F-7): SimEngine._entity_sim converts
LookupError/exception during identifier resolution into sim=0.0 and durably
appends it to sim_cache/pairs.jsonl. Transient web failures (cactus outages,
PUG 429s, idsm timeouts) become IMMORTAL zeros; every later metric (S7,
audit, chemrerank) trusts them. Fresh recompute of the 2,143-row
S0-pass/S7@1-lost organic cohort heals 89.6% at rank 1.

Modes:
  --measure   (default) recompute top-5 family hits for each cohort row
              mirror-first, classify healed@1/@5, write heal summary.
  --purge     scan pairs.jsonl for skel-* pairs scored exactly 0.0, recompute
              mirror-first; rewrite pairs file with healed values
              (BACKUP original first). Budget-capped.

Reads chemrerank cohort rows (casefiles/chemrerank.jsonl) for --measure.
Pod execution (needs NFS sim cache + /app mirror + src_new). Read-only on
results; writes ONLY under sigstage/casefiles (+ pairs backup/rewrite on
--purge, never in-place without backup).
"""
import argparse
import collections
import importlib.util
import json
import os
import shutil
import sys
import tempfile

DATA = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")
COHORT = os.path.join(DATA, "sigstage", "casefiles", "chemrerank.jsonl")
OUT_DIR = os.path.join(DATA, "sigstage", "casefiles")
MIRROR = os.environ.get("PUBCHEM_MIRROR",
                        "/app/databases/pubchem/current/pubchem.sqlite")
PAIR_FILE = os.path.join(os.environ.get("SIM_CACHE_ROOT",
                                        os.path.join(DATA, "sim_cache")),
                         "pairs.jsonl")
GATE = 0.7
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------- loaders

def _load_module_from(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CAMPAIGN = None


def load_campaign():
    global _CAMPAIGN
    if _CAMPAIGN is not None:
        return _CAMPAIGN
    for path in (os.path.join(DATA, "campaign_stats.py"),
                 os.path.join(_REPO_ROOT, "scripts", "campaign_stats.py")):
        if os.path.isfile(path):
            try:
                _CAMPAIGN = _load_module_from(path, "heal_campaign")
                return _CAMPAIGN
            except Exception:
                continue
    raise RuntimeError("campaign_stats.py not importable")


_VSIM = None


def load_vsim():
    global _VSIM
    if _VSIM is not None:
        return _VSIM
    for path in (os.path.join(DATA, "validation_similarity.py"),
                 os.path.join(_REPO_ROOT, "scripts", "validation_similarity.py")):
        if os.path.isfile(path):
            try:
                _VSIM = _load_module_from(path, "heal_vsim")
                return _VSIM
            except Exception:
                continue
    raise RuntimeError("validation_similarity.py not importable")


_SK = None


def load_skeletize():
    global _SK
    if _SK is not None:
        return _SK
    for base in (_REPO_ROOT, "/app"):
        if os.path.isfile(os.path.join(base, "src_new", "signatures", "skeletize.py")):
            if base not in sys.path:
                sys.path.insert(0, base)
            from src_new.signatures import skeletize
            _SK = skeletize
            return _SK
    raise RuntimeError("skeletize not importable")


_PUBCHEM = None


def load_pubchem():
    global _PUBCHEM
    if _PUBCHEM is not None:
        return _PUBCHEM
    for base in (_REPO_ROOT, "/app"):
        if os.path.isfile(os.path.join(base, "src_new", "molecules", "pubchem_db.py")):
            if base not in sys.path:
                sys.path.insert(0, base)
            from src_new.molecules.pubchem_db import PubChemDB
            _PUBCHEM = PubChemDB(MIRROR)
            return _PUBCHEM
    raise RuntimeError("PubChemDB not importable")


# ---------------------------------------------------------------- fresh sim

def smiles_for(kind, value, allow_web=False):
    """Mirror-first. kind: 'inchikey' | 'cid'. None when unresolvable."""
    db = load_pubchem()
    try:
        if kind == "inchikey":
            row = db.by_inchikey(value)
        else:
            row = db.by_cid(int(value)) if str(value).isdigit() else None
        if row and getattr(row, "smiles", None):
            return row.smiles
    except Exception:
        pass
    if not allow_web:
        return None
    vsim = load_vsim()
    try:
        return vsim._inchikey_smiles(value) if kind == "inchikey" \
            else vsim._cid_smiles(value)
    except Exception:
        return None


def fresh_tanimoto(smiles_a, smiles_b):
    """Direct skel tanimoto or None (no pair cache, no tolerance caching)."""
    if not smiles_a or not smiles_b:
        return None
    sk = load_skeletize()
    fp_a = sk.skeleton_fp(sk.from_smiles(str(smiles_a).strip()))
    fp_b = sk.skeleton_fp(sk.from_smiles(str(smiles_b).strip()))
    if fp_a is None or fp_b is None:
        return None
    return float(sk.tanimoto(fp_a, fp_b))


def pair_key_sides(key):
    """'skel-cid:123|skel-inchikey:ABC' -> (('cid','123'), ('inchikey','ABC'))."""
    parts = key.split("|")
    if len(parts) != 2:
        return None
    out = []
    for p in parts:
        if ":" not in p:
            return None
        pref, val = p.split(":", 1)
        if pref == "skel-cid":
            out.append(("cid", val))
        elif pref == "skel-inchikey":
            out.append(("inchikey", val))
        else:
            return None
    return out[0], out[1]


# ---------------------------------------------------------------- measure

def measure(args):
    campaign = load_campaign()
    fam = campaign.GT_FAMILIES["inchikey"]
    cohort = [json.loads(l) for l in open(COHORT)]
    if args.limit:
        cohort = cohort[: args.limit]
    heals = collections.Counter()
    by_cls = collections.defaultdict(collections.Counter)
    unresolved_gt = 0
    for r in cohort:
        try:
            with open(os.path.join(args.root, str(r["entry_id"]), args.pattern)) as fh:
                doc = json.load(fh)
        except Exception:
            continue
        g_smi = smiles_for("inchikey", r["gt_value"], allow_web=False)
        if not g_smi:
            unresolved_gt += 1
            continue
        hits = campaign.verified_hits(doc)
        fam_hits = [h for h in hits
                    if any(f in (h[0] or "").upper() for f in fam)][:5]
        fresh = []
        for h in fam_hits:
            t = (h[0] or "").upper()
            kind = "cid" if "PUBCHEM" in t and str(h[1]).isdigit() else \
                   ("inchikey" if "INCHI" in t else None)
            h_smi = smiles_for(kind, h[1]) if kind else None
            fresh.append(fresh_tanimoto(g_smi, h_smi))
        if fresh and fresh[0] is not None and fresh[0] >= GATE:
            heals["healed@1"] += 1
            by_cls[r["cls"]]["healed@1"] += 1
        if any(s is not None and s >= GATE for s in fresh):
            heals["healed@5"] += 1
            by_cls[r["cls"]]["healed@5"] += 1
        by_cls[r["cls"]]["n"] += 1
    out = {"cohort": len(cohort), "unresolved_gt": unresolved_gt,
           "heals": dict(heals),
           "by_class": {c: dict(v) for c, v in by_cls.items()},
           "heal1_pct": round(100.0 * heals.get("healed@1", 0) / max(1, len(cohort)), 1),
           "heal5_pct": round(100.0 * heals.get("healed@5", 0) / max(1, len(cohort)), 1)}
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "heal_summary.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


# ---------------------------------------------------------------- purge

def purge(args):
    if not os.path.isfile(PAIR_FILE):
        print(f"pair file missing: {PAIR_FILE}", file=sys.stderr)
        return
    entries = []
    with open(PAIR_FILE) as fh:
        for ln in fh:
            parts = ln.rstrip("\n").split("\t")
            if len(parts) == 2:
                entries.append((parts[0], parts[1]))
    zeros = [(k, v) for k, v in entries
             if v.startswith("0.00000") and pair_key_sides(k)]
    print(f"pairs: {len(entries)}; skel zeros: {len(zeros)}", file=sys.stderr)
    healed, still_zero, unresolved = 0, 0, 0
    new_values = {}
    budget = args.budget
    for key, _v in zeros[: args.limit or None]:
        (ka, a), (kb, b) = pair_key_sides(key)
        if budget <= 0:
            new_values[key] = None  # drop stale zero, unseen
            continue
        sa = smiles_for(*ka, allow_web=False)
        sb = smiles_for(*kb, allow_web=False)
        sim = fresh_tanimoto(sa, sb)
        if sim is None:
            unresolved += 1
            new_values[key] = None
        elif sim >= GATE:
            healed += 1
            new_values[key] = f"{sim:.6f}"
        else:
            still_zero += 1
            new_values[key] = _v
        budget -= 1
    if args.dry_run:
        out = {"candidates": len(zeros[: args.limit or None]),
               "healed": healed, "still_zero": still_zero,
               "dropped_unresolved": unresolved}
        print(json.dumps(out, indent=1))
        return
    backup = PAIR_FILE + f".bak-pre-heal-{args.stamp}"
    shutil.copy2(PAIR_FILE, backup)
    kept = 0
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(PAIR_FILE), suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for key, v in entries:
            if key in new_values:
                nv = new_values[key]
                if nv is None:
                    continue
                fh.write(f"{key}\t{nv}\n")
            else:
                fh.write(f"{key}\t{v}\n")
            kept += 1
    os.replace(tmp, PAIR_FILE)
    out = {"backup": backup, "healed": healed, "still_zero": still_zero,
           "dropped_unresolved": unresolved, "pairs_after": kept}
    print(json.dumps(out, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=DATA)
    ap.add_argument("--pattern", default="results.json")
    ap.add_argument("--budget", type=int, default=500)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--purge", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stamp", default="20261007")
    args = ap.parse_args(argv)
    if args.purge:
        purge(args)
    else:
        measure(args)


if __name__ == "__main__":
    main()
