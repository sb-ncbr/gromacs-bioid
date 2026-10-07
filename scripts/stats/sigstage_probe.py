#!/usr/bin/env python3
"""sigstage_probe -- signature-stage ground-truth comparison (S0 analysis).

Scores MDDBR ground-truth annotations against BAT3 *signature-stage* outputs
(data.signatures[segment]["generated"][generator]) from per-entry results
JSON on NFS. Unlike campaign_stats S5/S7 (post-verification verified_hits),
this stage is pre-identification, pre-database, pre-ranking: one signature
per segment, nothing to rerank. The delta S0 - S7 attributes loss to
identification/verification vs input/annotation inconsistency.

Approved frame (2026-10-06): v13-era anchor campaign_stats_v13.json, whose
own full.pattern (results.json) is the scan pattern unless --pattern is
given explicitly; full GT-covered set.
  inchikey organic -> GT SMILES (PubChem mirror-first, web-cache fallback)
                      vs segment 'smiles' -> skeleton-FP Tanimoto >= 0.7
  inchikey ion     -> gt_rules.gt_class_for -> element presence
                      (_ion_elements_of channel, F19 metals union)
  uniprot          -> cached uniprot_seq vs segment 'fasta_map_protein'
                      -> local-align identity >= 0.9
  pdb              -> cached pdb_entity_seqs (max over entities) vs segment
                      'fasta_map_protein'/'fasta_map_nucleic' >= 0.9

Safety (replay protocol, scripts/stats/README.md): read-only on results,
writes ONLY under --out-dir (must be a dedicated subdir), STRICT anchor gate
against campaign_stats_v13.json denominators, deterministic shards, no DB
writes in v1.
"""
import argparse
import collections
import hashlib
import importlib.util
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")
MIRROR = os.environ.get(
    "PUBCHEM_MIRROR", "/app/databases/pubchem/current/pubchem.sqlite")
# Pattern resolution: explicit --pattern > anchor's own full.pattern > this
# fallback. (Evidence 2026-10-06: campaign_stats_v13.json anchors were
# generated with --pattern results.json; "v13" is the campaign version, NOT
# the results filename.)
DEFAULT_PATTERN = "results.json"
DEFAULT_ANCHOR = os.path.join(DATA, "campaign_stats_v13.json")
DEFAULT_OUT = os.path.join(DATA, "sigstage")
GUARD_RATIO = 10          # length-mismatch guard ratio (see GUARD_MIN_LEN)
GUARD_MIN_LEN = 20        # guard only when shorter seq < 20 aa: blocks peptide
                          # noise but does NOT fire on domain-vs-polyprotein
                          # (pilot finding: P0DTD1 ~7k-aa GT vs 300-aa segment
                          # must still score; ratio-only guard zeroed it)
CHEM_VALIDATED = 0.7      # == S7/F7 skeleton-FP gate
SEQ_VALIDATED = 0.9       # == S7 validated threshold for sequences

CHEM_GENERATORS = ("smiles",)
PROT_GENERATORS = ("fasta_map_protein",)
PDB_GENERATORS = ("fasta_map_protein", "fasta_map_nucleic")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------- helpers

def _load_module_from(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CAMPAIGN_MOD = None


def load_campaign_module():
    """Import campaign_stats (NFS live copy first, repo provenance copy second).

    Used for _ion_elements_of (F19 metals-union channel) per approved spec.
    """
    global _CAMPAIGN_MOD
    if _CAMPAIGN_MOD is not None:
        return _CAMPAIGN_MOD
    for path in (os.path.join(DATA, "campaign_stats.py"),
                 os.path.join(_REPO_ROOT, "scripts", "campaign_stats.py")):
        if os.path.isfile(path):
            try:
                _CAMPAIGN_MOD = _load_module_from(path, "sigstage_campaign")
                return _CAMPAIGN_MOD
            except Exception:
                continue
    raise RuntimeError("campaign_stats.py not importable from NFS or repo")


_GT_RULES = None


def load_gt_rules():
    global _GT_RULES
    if _GT_RULES is not None:
        return _GT_RULES
    for path in (os.path.join(DATA, "gt_rules.py"),
                 os.path.join(_REPO_ROOT, "scripts", "gt_rules.py")):
        if os.path.isfile(path):
            try:
                _GT_RULES = _load_module_from(path, "sigstage_gt_rules")
                return _GT_RULES
            except Exception:
                continue
    raise RuntimeError("gt_rules.py not importable from NFS or repo")


_SKEL = None


def load_skeletize():
    """Import src_new.signatures.skeletize (repo or /app)."""
    global _SKEL
    if _SKEL is not None:
        return _SKEL
    for base in (_REPO_ROOT, "/app"):
        pkg = os.path.join(base, "src_new", "signatures", "skeletize.py")
        if os.path.isfile(pkg):
            if base not in sys.path:
                sys.path.insert(0, base)
            from src_new.signatures import skeletize
            _SKEL = skeletize
            return _SKEL
    raise RuntimeError("src_new.signatures.skeletize not importable")


def skelfp_tanimoto(smiles_a, smiles_b):
    """Skeleton-FP Tanimoto between two SMILES (F7/S7 currency).

    Returns None when either SMILES fails to parse/fingerprint.
    """
    if not smiles_a or not smiles_b:
        return None
    fp_a = _skelfp(smiles_a)
    fp_b = _skelfp(smiles_b)
    if fp_a is None or fp_b is None:
        return None
    return float(load_skeletize().tanimoto(fp_a, fp_b))


_ALIGNER = None


def align_identity_local(s1, s2):
    """Local-alignment identity, faithful replica of SimEngine._align_identity.

    Same scoring (match=1, mismatch=0, open=-0.5, extend=-0.1, mode=local),
    same denominator (counts.aligned, fallback max length). Drift-guarded by
    test_seq_identity_matches_simengine when SimEngine is importable.
    """
    global _ALIGNER
    s1, s2 = (s1 or ""), (s2 or "")
    if not s1 or not s2:
        return 0.0
    if _ALIGNER is None:
        from Bio.Align import PairwiseAligner
        a = PairwiseAligner()
        a.substitution_matrix = None
        a.match_score = 1.0
        a.mismatch_score = 0.0
        a.open_gap_score = -0.5
        a.extend_gap_score = -0.1
        a.mode = "local"
        _ALIGNER = a
    p = _ALIGNER.align(s1, s2)[0]
    counted = p.counts()
    aligned = getattr(counted, "aligned", 0)
    denom = aligned if aligned else max(len(s1), len(s2), 1)
    return max(0.0, min(1.0, counted.identities / denom))


def clean_fasta(value):
    """Strip FASTA headers/whitespace, keep sequence letters and '*'."""
    if not isinstance(value, str):
        value = str(value or "")
    lines = [ln.strip() for ln in value.splitlines() if not ln.startswith(">")]
    joined = "".join(lines)
    return "".join(c for c in joined if c.isalpha() or c == "*")


def norm_gt_value(gt_type, value):
    v = (value or "").strip()
    if gt_type == "pdb":
        return v.upper()[:4]
    return v.upper()


# ---------------------------------------------------------------- resolvers

class ProdResolver:
    """Production resolver: PubChem mirror-first, cached web fallback.

    Budget semantics: --budget caps NEW web-chain escalations for
    inchikey->SMILES (mirror misses). Cached fetchers (uniprot_seq /
    pdb_entity_seqs) are NFS-cached and NOT budget-counted.
    """

    def __init__(self, budget=200):
        self.budget = budget
        self.network_uses = 0
        self._pubchem = None
        self._vsim = None

    # -- chemistry ------------------------------------------------------
    def _pubchem_db(self):
        if self._pubchem is None:
            for base in (_REPO_ROOT, "/app"):
                if os.path.isfile(os.path.join(base, "src_new", "molecules", "pubchem_db.py")):
                    if base not in sys.path:
                        sys.path.insert(0, base)
                    from src_new.molecules.pubchem_db import PubChemDB
                    self._pubchem = PubChemDB(MIRROR)
                    break
        if self._pubchem is None:
            raise RuntimeError("PubChemDB unavailable (no src_new.molecules)")
        return self._pubchem

    def _vsim_mod(self):
        if self._vsim is None:
            for path in (os.path.join(DATA, "validation_similarity.py"),
                         os.path.join(_REPO_ROOT, "scripts", "validation_similarity.py")):
                if os.path.isfile(path):
                    try:
                        self._vsim = _load_module_from(path, "sigstage_vsim")
                        break
                    except Exception:
                        continue
        if self._vsim is None:
            raise RuntimeError("validation_similarity.py not importable")
        return self._vsim

    def smiles_for_inchikey(self, ik):
        """-> (smiles|None, source in mirror|webcache|budget_exceeded|fail)."""
        ik = (ik or "").strip().upper()
        if not ik:
            return None, "fail"
        try:
            row = self._pubchem_db().by_inchikey(ik)
            smi = getattr(row, "smiles", None) if row else None
            if smi:
                return smi, "mirror"
        except Exception:
            pass
        if self.network_uses >= self.budget:
            return None, "budget_exceeded"
        self.network_uses += 1
        try:
            smi = self._vsim_mod()._inchikey_smiles(ik)
            return (smi or None), ("webcache" if smi else "fail")
        except Exception:
            return None, "fail"

    def gt_class(self, ik):
        return load_gt_rules().gt_class_for(ik)

    def ion_element(self, ik):
        return load_gt_rules().ion_element(ik)

    # -- sequences --------------------------------------------------------
    def uniprot_seq(self, acc):
        return self._vsim_mod().uniprot_seq(acc)

    def pdb_entity_seqs(self, pdb):
        return self._vsim_mod().pdb_entity_seqs(pdb)

    def align_identity(self, s1, s2):
        return align_identity_local(s1, s2)


# ---------------------------------------------------------------- scoring

def extract_sig_pool(doc):
    """Segment signature pool from a results JSON doc.

    Returns (pool, stats): pool = {generator: [(segment, value), ...]} with
    identical values deduped across SYSTEM/__vN variants (first segment kept);
    stats = {n_segments, n_unique_sigs}.
    """
    sigs = ((doc.get("data") or {}).get("signatures")) or {}
    pool = collections.defaultdict(list)
    seen = collections.defaultdict(set)   # generator -> set(values)
    n_segments = 0
    for seg, payload in sigs.items():
        gen = (payload or {}).get("generated") or {}
        if not gen:
            continue
        n_segments += 1
        for generator, value in gen.items():
            if value is None:
                continue
            value = str(value)
            if value in seen[generator]:
                continue
            seen[generator].add(value)
            pool[generator].append((seg, value))
    stats = {
        "n_segments": n_segments,
        "n_unique_sigs": sum(len(v) for v in pool.values()),
    }
    return dict(pool), stats


def _skelfp(smiles):
    """skeleton fingerprint or None (unparseable). Separated so GT-side and
    segment-side failures can be attributed per row (pilot finding)."""
    if not smiles:
        return None
    sk = load_skeletize()
    mol = sk.from_smiles(str(smiles).strip())
    if mol is None:
        return None
    return sk.skeleton_fp(mol)


def _best_chem(gt_fp, candidates, resolver):
    """Returns (best, seg_parse_fail): best against segment fingerprints.

    seg_parse_fail counts candidate signature SMILES that failed to parse,
    so sim==0.0 rows can be told apart: true skeleton divergence vs
    unparseable segment signatures (RDKit valence warnings in pilot)."""
    best = {"sim": 0.0, "segment": None, "generator": None}
    seg_parse_fail = 0
    for gen in CHEM_GENERATORS:
        for seg, value in candidates.get(gen, []):
            seg_fp = _skelfp(value)
            if seg_fp is None:
                seg_parse_fail += 1
                continue
            sim = float(load_skeletize().tanimoto(gt_fp, seg_fp))
            if sim > best["sim"]:
                best = {"sim": sim, "segment": seg, "generator": gen}
    return best, seg_parse_fail


def _best_seq(gt_seqs, generators, pool, resolver, guard_ratio=GUARD_RATIO):
    best = {"sim": 0.0, "segment": None, "generator": None}
    pairs, guard_skipped = 0, 0
    for gen in generators:
        for seg, value in pool.get(gen, []):
            seg_seq = clean_fasta(value)
            if not seg_seq:
                continue
            for gt_seq in gt_seqs:
                gt_seq = clean_fasta(gt_seq)
                if not gt_seq:
                    continue
                hi, lo = max(len(gt_seq), len(seg_seq)), min(len(gt_seq), len(seg_seq))
                if 0 < lo < GUARD_MIN_LEN and hi > guard_ratio * lo:
                    guard_skipped += 1
                    continue
                sim = resolver.align_identity(gt_seq, seg_seq)
                pairs += 1
                if sim > best["sim"]:
                    best = {"sim": sim, "segment": seg, "generator": gen}
    return best, pairs, guard_skipped


def score_annotation(gt_type, gt_value, pool, ion_elements, resolver):
    """Score one GT annotation against the signature pool. Returns row dict."""
    gt_type = (gt_type or "").strip().lower()
    gt_value = norm_gt_value(gt_type, gt_value)
    row = {
        "gt_type": gt_type,
        "gt_value": gt_value,
        "gt_class": None,
        "sim": 0.0,
        "threshold": None,
        "validated": False,
        "attempted": False,
        "best_segment": None,
        "best_generator": None,
        "smiles_source": None,
        "bucket": None,
        "details": {},
    }

    if gt_type == "inchikey":
        cls = resolver.gt_class(gt_value)
        row["gt_class"] = cls
        if cls == "ion":
            row["threshold"] = None  # boolean presence channel
            el = resolver.ion_element(gt_value)
            att = bool(ion_elements)
            row["attempted"] = att
            if not att:
                row["bucket"] = "no_matching_generator"  # no ion channel data in doc
            elif not el:
                row["bucket"] = "unresolved_gt"
            else:
                present = el in ion_elements
                row["sim"] = 1.0 if present else 0.0
                row["validated"] = present
                row["best_generator"] = "ion_elements"
                row["bucket"] = "validated" if present else "below_gate"
                row["details"]["element"] = el
            return row
        # organic (or unresolved class: still try skelfp if smiles resolvable)
        gt_smiles, source = resolver.smiles_for_inchikey(gt_value)
        row["smiles_source"] = source
        row["threshold"] = CHEM_VALIDATED
        if not gt_smiles:
            row["bucket"] = "unresolved_gt"
            return row
        candidates = {g: pool.get(g, []) for g in CHEM_GENERATORS}
        if not any(candidates.values()):
            row["bucket"] = "no_matching_generator"
            return row
        gt_fp = _skelfp(gt_smiles)
        if gt_fp is None:
            row["details"]["note"] = "gt_smiles_unparseable"
            row["bucket"] = "unresolved_gt"
            return row
        row["attempted"] = True
        best, seg_parse_fail = _best_chem(gt_fp, candidates, resolver)
        row["sim"] = round(best["sim"], 6)
        row["validated"] = best["sim"] >= CHEM_VALIDATED
        row["best_segment"] = best["segment"]
        row["best_generator"] = best["generator"]
        row["bucket"] = "validated" if row["validated"] else "below_gate"
        row["details"]["n_candidates"] = sum(len(v) for v in candidates.values())
        if seg_parse_fail:
            row["details"]["chem_parse_fail"] = seg_parse_fail
        return row

    if gt_type == "uniprot":
        generators = PROT_GENERATORS
        try:
            gt_seqs = [resolver.uniprot_seq(gt_value)]
        except Exception:
            gt_seqs = []
    elif gt_type == "pdb":
        generators = PDB_GENERATORS
        try:
            gt_seqs = list(resolver.pdb_entity_seqs(gt_value) or [])
        except Exception:
            gt_seqs = []
    else:
        row["bucket"] = "unmapped_type"
        return row

    row["threshold"] = SEQ_VALIDATED
    if not any(gt_seqs):
        row["bucket"] = "unresolved_gt"
        return row
    if not any(pool.get(g) for g in generators):
        row["bucket"] = "no_matching_generator"
        return row
    row["attempted"] = True
    best, pairs, guard_skipped = _best_seq(gt_seqs, generators, pool, resolver)
    row["sim"] = round(best["sim"], 6)
    row["validated"] = best["sim"] >= SEQ_VALIDATED
    row["best_segment"] = best["segment"]
    row["best_generator"] = best["generator"]
    row["bucket"] = "validated" if row["validated"] else "below_gate"
    row["details"]["pairs"] = pairs
    row["details"]["guard_skipped"] = guard_skipped
    return row


def score_entry_doc(eid, doc, gt_map_entry, resolver):
    """Score all GT annotations of one entry. Returns list of row dicts."""
    pool, stats = extract_sig_pool(doc)
    needs_ion = any((t or "").strip().lower() == "inchikey" for t in gt_map_entry)
    ion_elements = set()
    if needs_ion and pool:
        try:
            ion_elements = load_campaign_module()._ion_elements_of(doc) or set()
        except Exception:
            ion_elements = set()

    rows = []
    stage_errors = ((doc.get("data") or {}).get("stage_errors")) or {}
    stage_errors_present = any(stage_errors.get(cat) for cat in stage_errors)
    annotations = sorted(
        (t.strip().lower(), v) for t, vals in gt_map_entry.items() for v in vals)
    for gt_type, gt_value in annotations:
        if not pool:
            row = {
                "gt_type": gt_type, "gt_value": norm_gt_value(gt_type, gt_value),
                "gt_class": None, "sim": 0.0, "threshold": None,
                "validated": False, "attempted": False,
                "best_segment": None, "best_generator": None,
                "smiles_source": None, "bucket": "no_sig_data", "details": {},
            }
        else:
            row = score_annotation(gt_type, gt_value, pool, ion_elements, resolver)
        row["entry_id"] = eid
        row["stage_errors_present"] = stage_errors_present
        row.update(stats)
        rows.append(row)
    return rows


# ---------------------------------------------------------------- aggregation

def aggregate(rows, scan_stats):
    """Deterministic aggregate: absolute + percentage + denominator, never pct-only."""
    out = {"generated_by": "sigstage_probe.py v1",
           "scan": scan_stats,
           "rows": len(rows)}
    per_type = collections.defaultdict(list)
    buckets = collections.Counter()
    entries_any = collections.defaultdict(bool)
    entries_seen = set()
    for r in rows:
        # ion split (S7-comparable): campaign S7 reports ions separately
        key = "ion" if (r["gt_type"] == "inchikey" and r["gt_class"] == "ion") \
            else r["gt_type"]
        per_type[key].append(r)
        buckets[r["bucket"]] += 1
        entries_seen.add(r["entry_id"])
        if r["validated"]:
            entries_any[r["entry_id"]] = True
    types_block = {}
    for t in sorted(per_type):
        rs = per_type[t]
        n = len(rs)
        att = [r for r in rs if r["attempted"]]
        n_val = sum(1 for r in rs if r["validated"])
        types_block[t] = {
            "annotations": n,
            "attempted": len(att),
            "attempted_pct": round(100.0 * len(att) / n, 1) if n else None,
            "validated": n_val,
            "pct_validated": round(100.0 * n_val / n, 1) if n else None,
            "mean_sim_attempted": (
                round(sum(r["sim"] for r in att) / len(att), 4) if att else None),
            "buckets": dict(sorted(
                collections.Counter(r["bucket"] for r in rs).items())),
        }
    out["per_type"] = types_block
    out["buckets"] = dict(sorted(buckets.items()))
    n_ent = len(entries_seen)
    n_any = sum(1 for e in entries_seen if entries_any.get(e))
    out["entries"] = {"seen": n_ent, "any_validated": n_any,
                      "any_validated_pct": round(100.0 * n_any / n_ent, 1) if n_ent else None}
    return out


def serialize_rows(rows):
    """Byte-deterministic JSONL: sorted, fixed key order via sort_keys."""
    ordered = sorted(rows, key=lambda r: (r["entry_id"], r["gt_type"], r["gt_value"]))
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in ordered)


# ---------------------------------------------------------------- anchor gate

class AnchorMismatch(Exception):
    pass


def anchor_check(counts, anchor, pattern, lax=False):
    """Replay-protocol gate: reproduced denominators must equal anchors.

    counts = {"scanned": int, "gt_covered": int} computed with campaign-stats
    gating (load_simulation==success AND verify_results==success).

    STRICT (default): any denominator mismatch aborts. Only meaningful for
    unscaffolded full-set runs. lax=True (narrowed runs: --sample/--limit/
    shard>1, or pilot): mismatches become stderr ANCHOR WARNINGs, run
    proceeds, and the warning content is returned for the record.
    """
    full = (anchor or {}).get("full") or {}
    anchor_pattern = full.get("pattern")
    warnings = []
    if anchor_pattern and anchor_pattern != pattern:
        msg = f"pattern mismatch: probe={pattern} anchor={anchor_pattern}"
        if not lax:
            raise AnchorMismatch(msg + " (use --anchor-lax to override)")
        warnings.append(msg)
    problems = []
    for key, ours, theirs in (
            ("scanned_entries", counts.get("scanned"), full.get("scanned_entries")),
            ("gt_covered_scanned", counts.get("gt_covered"), full.get("gt_covered_scanned"))):
        if theirs is None:
            continue
        if ours != theirs:
            problems.append(f"{key}: probe={ours} anchor={theirs}")
    if problems:
        msg = "; ".join(problems)
        if not lax:
            raise AnchorMismatch(msg)
        warnings.append(msg)
    for w in warnings:
        print(f"ANCHOR WARNING: {w}", file=sys.stderr)
    return {"pattern": anchor_pattern, "checked": True, "warnings": warnings}


def gating_counts(docs_gate):
    """counts for anchor: docs_gate = list of (has_gt, load_ok, verify_ok)."""
    scanned = sum(1 for _has_gt, lo, vo in docs_gate if lo and vo)
    gt_covered = sum(1 for has_gt, lo, vo in docs_gate if lo and vo and has_gt)
    return {"scanned": scanned, "gt_covered": gt_covered}


def task_success(doc, name):
    return ((doc.get("tasks") or {}).get(name) or {}).get("status") == "success"


# ---------------------------------------------------------------- main scan

def entry_ids(root, pattern, since_ts=0.0):
    ids = []
    try:
        it = os.scandir(root)
    except FileNotFoundError:
        return ids
    with it:
        for d in it:
            if not (d.is_dir() and d.name.isdigit()):
                continue
            p = os.path.join(d.path, pattern)
            try:
                if os.path.isfile(p) and os.path.getmtime(p) >= since_ts:
                    ids.append(int(d.name))
            except OSError:
                continue
    ids.sort()
    return ids


def load_gt_postgres():
    import psycopg2
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://validation:validation-password-change-me@validation-postgres:5432/bat3_validation")
    con = psycopg2.connect(db_url)
    cur = con.cursor()
    cur.execute("SELECT entry_id, signature_type, signature_value FROM ground_truth_signatures")
    gt = collections.defaultdict(lambda: collections.defaultdict(set))
    for eid, t, v in cur.fetchall():
        if v and t:
            gt[eid][t.strip().lower()].add(v.strip())
    con.close()
    return gt


def load_gt_json(path):
    raw = json.load(open(path))
    gt = collections.defaultdict(lambda: collections.defaultdict(set))
    for eid, m in raw.items():
        for t, vals in m.items():
            for v in vals:
                gt[int(eid)][t.strip().lower()].add(v)
    return gt


def main(argv=None, resolver_factory=None):
    """Entry point. resolver_factory(budget)->resolver injectable for tests."""
    resolver_factory = resolver_factory or (lambda budget: ProdResolver(budget=budget))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=DATA)
    ap.add_argument("--pattern", default=None,
                    help="results filename to scan; default: anchor's "
                         "full.pattern, else results.json")
    ap.add_argument("--threads", type=int, default=32)
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", default="0/1", help="i/n: process ids where idx%%n==i")
    ap.add_argument("--budget", type=int, default=200,
                    help="max NEW web-chain inchikey->SMILES escalations per worker")
    ap.add_argument("--anchor", default=DEFAULT_ANCHOR)
    ap.add_argument("--no-anchor", action="store_true")
    ap.add_argument("--anchor-lax", action="store_true")
    ap.add_argument("--out-dir", default=DEFAULT_OUT)
    ap.add_argument("--gt-json", default="", help="offline GT override (no Postgres)")
    ap.add_argument("--since", default=os.environ.get("CAMPAIGN_STATS_SINCE",
                                                      "2026-09-10T11:00:00"))
    args = ap.parse_args(argv)

    out_dir = os.path.abspath(args.out_dir)
    if os.path.abspath(args.root) == out_dir or not os.path.basename(out_dir):
        ap.error("--out-dir must be a dedicated subdirectory (replay protocol)")

    # Pattern resolution: explicit flag > anchor's own pattern > default.
    anchor_doc = None
    if not args.no_anchor and os.path.isfile(args.anchor):
        with open(args.anchor) as fh:
            anchor_doc = json.load(fh)
    anchor_pattern = ((anchor_doc or {}).get("full") or {}).get("pattern")
    args.pattern = args.pattern or anchor_pattern or DEFAULT_PATTERN

    from datetime import datetime
    try:
        since_ts = datetime.fromisoformat(args.since).timestamp()
    except Exception:
        since_ts = 0.0

    gt = load_gt_json(args.gt_json) if args.gt_json else load_gt_postgres()
    print(f"GT entries: {len(gt)}", file=sys.stderr)

    ids = entry_ids(args.root, args.pattern, since_ts)
    if args.sample:
        ids = ids[:: max(1, len(ids) // args.sample)][:args.sample]
    if args.limit:
        ids = ids[: args.limit]
    try:
        shard_i, shard_n = (int(x) for x in args.shard.split("/"))
    except Exception:
        ap.error("--shard must be i/n")
    if shard_n > 1:
        ids = [e for j, e in enumerate(ids) if j % shard_n == shard_i]
    print(f"entries to scan: {len(ids)} (shard {args.shard})", file=sys.stderr)

    docs_gate, results, gate_meta = [], [], {}
    import time
    t0 = time.time()

    def _work(eid):
        """Read + score inside the worker thread (IO and CPU both parallel)."""
        path = os.path.join(args.root, str(eid), args.pattern)
        with open(path) as fh:
            doc = json.load(fh)
        if not task_success(doc, "load_simulation"):
            return eid, None, None, 0
        verify_ok = task_success(doc, "verify_results")
        resolver = resolver_factory(args.budget)
        rows = score_entry_doc(eid, doc, gt.get(eid) or {}, resolver)
        return eid, rows, (eid in gt, True, verify_ok), resolver.network_uses

    with ThreadPoolExecutor(max_workers=args.threads) as ex:
        futs = {ex.submit(_work, e): e for e in ids}
        for i, fut in enumerate(as_completed(futs), 1):
            eid, rows, gate, esc = fut.result()
            if gate is None:
                continue
            docs_gate.append(gate)
            results.extend(rows)
            gate_meta[eid] = esc
            if i % 500 == 0:
                print(f"  ...{i}/{len(ids)} ({time.time()-t0:.0f}s)", file=sys.stderr)

    if anchor_doc is not None:
        check = anchor_check(gating_counts(docs_gate), anchor_doc, args.pattern,
                             lax=args.anchor_lax)
        print(f"anchor gate OK: {check}", file=sys.stderr)
    elif not args.no_anchor:
        print(f"anchor file missing ({args.anchor}); STRICT gate skipped", file=sys.stderr)

    scan_stats = {
        "pattern": args.pattern, "root": args.root, "shard": args.shard,
        "ids": len(ids), "rows": len(results),
        "load_ok": len(docs_gate),
        "budget_escalations": sum(gate_meta.values()),
        "scan_seconds": round(time.time() - t0, 1),
        "anchor": None if args.no_anchor else args.anchor,
    }
    os.makedirs(os.path.join(out_dir, "shards"), exist_ok=True)
    shard_path = os.path.join(out_dir, "shards", f"shard_{shard_i:03d}.jsonl")
    payload = serialize_rows(results)
    with open(shard_path, "w") as fh:
        fh.write(payload)
    agg = aggregate(results, scan_stats)
    agg_path = os.path.join(out_dir, f"sigstage_v1_shard{shard_i:03d}.json")
    with open(agg_path, "w") as fh:
        json.dump(agg, fh, indent=2, sort_keys=True)
    sha = hashlib.sha1(payload.encode()).hexdigest()[:12]
    print(f"rows={len(results)} shard={shard_path} sha1={sha}", file=sys.stderr)
    print(f"aggregate={agg_path}", file=sys.stderr)
    print(json.dumps(agg["per_type"], indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
