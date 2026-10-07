#!/usr/bin/env python3
"""ghost_curation_list -- classify web-unresolvable pair keys into curation classes.

Input: warmup_ghosts.json produced by sigstage_warmup (A2). Each ghost pair
key is split into its two (kind, value) sides and every distinct identifier
is classified:

  cid_zero           -- CID not a positive integer ("0" lineage: upstream
                        emission of a null PubChem id; curation: strip/fix)
  inchikey_malformed -- fails InChIKey shape ^[A-Z]{14}-[A-Z]{10}-[A-Z]$
                        (curation: fix harvester mapping)
  unresolved_legacy  -- valid shape but unresolvable via mirror AND full web
                        chain (candidate deprecated/deleted PubChem record;
                        curation: review/withdraw GT or map successor CID)
  smiles_unparseable -- (from warmup "unparseable" list) resolved smiles but
                        skeleton FP failed (cross-ref S0-OQ-2; see A4)

Output: JSON (full identifier lists) + MD (curation tables) under
sigstage/casefiles/. Cross-references: S0-OQ-3 ghost GT census and the
2,143-cohort unresolved_GT list live in sibling casefiles artifacts.
"""
import argparse
import collections
import json
import os
import re

DATA = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")
GHOSTS_IN = os.path.join(DATA, "sigstage", "casefiles", "warmup_ghosts.json")
OUT_JSON = os.path.join(DATA, "sigstage", "casefiles", "ghost_curation.json")
OUT_MD = os.path.join(DATA, "sigstage", "casefiles", "ghost_curation.md")

IK_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


def classify_side(kind, value):
    """(kind, value) -> (class, normalized-identifier-string)."""
    if kind == "cid":
        if not value.isdigit() or int(value) <= 0:
            return "cid_zero", f"cid:{value}"
        return "unresolved_legacy", f"cid:{value}"
    if kind == "inchikey":
        v = value.strip().upper()
        if not IK_RE.match(v):
            return "inchikey_malformed", f"inchikey:{v}"
        return "unresolved_legacy", f"inchikey:{v}"
    return "unknown_kind", f"{kind}:{value}"


def split_key(key):
    """'skel-cid:123|skel-inchikey:ABC' -> [(kind, value), ...] ([] if bad)."""
    parts = key.split("|")
    out = []
    for p in parts:
        pref, _, val = p.partition(":")
        if pref == "skel-cid":
            out.append(("cid", val))
        elif pref == "skel-inchikey":
            out.append(("inchikey", val))
        else:
            return []
    return out if len(out) == 2 else []


def classify_keys(keys):
    """-> {"classes": {cls: {"identifiers": {ident: pair_count},
                            "pairs": int}},
           "bad_keys": [key]}  (deterministic ordering)."""
    classes = collections.defaultdict(
        lambda: {"identifiers": collections.Counter(), "pairs": 0})
    bad = []
    for key in keys:
        sides = split_key(key)
        if not sides:
            bad.append(key)
            continue
        seen_this_pair = set()
        for kind, value in sides:
            cls, ident = classify_side(kind, value)
            classes[cls]["identifiers"][ident] += 1
            seen_this_pair.add(cls)
        for cls in seen_this_pair:
            classes[cls]["pairs"] += 1
    out = {}
    for cls in sorted(classes):
        ids = classes[cls]["identifiers"]
        out[cls] = {
            "distinct_identifiers": len(ids),
            "pairs": classes[cls]["pairs"],
            "identifiers": sorted(ids.items()),
        }
    return {"classes": out, "bad_keys": sorted(bad)}


CURATION_GUIDANCE = {
    "cid_zero": "strip/fix upstream annotation emitters; CID 0 is not a PubChem record",
    "inchikey_malformed": "fix harvester value mapping (truncated/miscased keys)",
    "unresolved_legacy": "review in MDDBR: deprecated/deleted PubChem record or withdrawn GT; map successor CID where possible",
    "smiles_unparseable": "cross-ref S0-OQ-2 (generator normalization, A4)",
    "unknown_kind": " investigation: unexpected pair-key prefix",
}


def render_md(rep, source_desc):
    lines = ["# Ghost-GT curation list (A3)",
             f"- source: {source_desc}",
             f"- bad pair keys (unparseable shape): {len(rep['bad_keys'])}",
             ""]
    for cls, blk in rep["classes"].items():
        lines += [f"## {cls}",
                  f"- guidance: {CURATION_GUIDANCE.get(cls, 'review')}",
                  f"- distinct identifiers: {blk['distinct_identifiers']}",
                  f"- pair occurrences: {blk['pairs']}",
                  "",
                  "| identifier | pair count |", "|---|---|"]
        for ident, n in blk["identifiers"][:10]:
            lines.append(f"| `{ident}` | {n} |")
        if blk["distinct_identifiers"] > 10:
            lines.append(f"| ... ({blk['distinct_identifiers'] - 10} more in JSON) | |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ghosts", default=GHOSTS_IN)
    ap.add_argument("--out-json", default=OUT_JSON)
    ap.add_argument("--out-md", default=OUT_MD)
    args = ap.parse_args(argv)
    doc = json.load(open(args.ghosts))
    rep = classify_keys(doc.get("ghosts", []))
    unp = {}
    if doc.get("unparseable"):
        up = classify_keys(doc["unparseable"])
        cnt = collections.Counter()
        for key in doc["unparseable"]:
            for side in split_key(key):
                cnt[classify_side(*side)[1]] += 1
        unp = {
            "distinct_identifiers": len(cnt),
            "pairs": len(doc["unparseable"]),
            "identifiers": sorted(cnt.items()),
        }
        rep["classes"]["smiles_unparseable"] = unp
    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w") as fh:
        json.dump({"source": args.ghosts, "pair_keys": len(doc.get("ghosts", [])),
                   "report": rep}, fh, indent=1)
    with open(args.out_md, "w") as fh:
        fh.write(render_md(rep, args.ghosts))
    summary = {c: (b["distinct_identifiers"], b["pairs"])
               for c, b in rep["classes"].items()}
    print(json.dumps(summary, indent=1))
    return rep


if __name__ == "__main__":
    main()
