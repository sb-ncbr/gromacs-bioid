#!/usr/bin/env python3
"""Check the local PubChem mirror against captured golden PUG responses.

Compares tests/fixtures/pubchem_golden.jsonl (produced on a clean-IP host by
scripts/generate_pubchem_golden.py) against a built mirror DB.

Rules:
  formula:  set equality between mirror formula_hill index and PUG cids/txt list
  inchikey: mirror has a row whose cid matches the PUG answer (per key)
  cid:      SMILES equal after RDKit canonicalization (PUG returns
            CanonicalSMILES; mirror stores the published isomeric SMILES)

On mismatch it prints the first diffs and a pattern hint (e.g. isotope-labeled
compounds), and exits 1 when any systematic difference exists.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src_new.molecules.pubchem_db import normalize_formula  # noqa: E402


def _canon(smiles: str) -> str | None:
    from rdkit import Chem

    mol = Chem.MolFromSmiles(smiles) if smiles else None
    return Chem.MolToSmiles(mol) if mol is not None else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--fixture", required=True)
    args = ap.parse_args()

    try:
        from rdkit import RDLogger

        RDLogger.DisableLog("rdApp.*")
    except Exception:
        pass

    conn = sqlite3.connect(f"file:{args.db}?mode=ro&immutable=1", uri=True)
    entries = [json.loads(l) for l in open(args.fixture)]
    bad = 0
    pattern_notes: dict[str, int] = {}

    for e in entries:
        kind, query, response = e["kind"], e["query"], e["response"]
        if kind == "formula":
            try:
                hill = normalize_formula(query)
            except ValueError:
                continue  # non-formula queries (e.g. 'NaCl' names) skipped
            local = {r[0] for r in conn.execute(
                "SELECT cid FROM compounds WHERE formula_hill=?", (hill,))}
            pug = set(response or [])
            missing = sorted(pug - local)[:3]
            extra = sorted(local - pug)[:3]
            if missing or extra:
                bad += 1
                print(f"FORMULA DIFF {query}: missing={len(pug - local)} extra={len(local - pug)} "
                      f"e.g. missing{missing} extra{extra}")
                for cid in (pug - local):
                    row = conn.execute("SELECT smiles, formula_hill FROM compounds WHERE cid=?", (cid,)).fetchone()
                    hint = "isotope" if row and "[" in row[0] else ("local-formula:" + row[1] if row else "cid-absent-entirely")
                    pattern_notes[hint] = pattern_notes.get(hint, 0) + 1
        elif kind == "inchikey":
            pug = set(response or [])
            row = conn.execute(
                "SELECT cid FROM compounds WHERE inchikey=?", (query.upper(),)).fetchone()
            local = {row[0]} if row else set()
            if local != pug and not (not pug and not local):
                bad += 1
                print(f"INCHIKEY DIFF {query}: local={sorted(local)[:3]} pug={sorted(pug)[:3]}")
        else:  # cid
            row = conn.execute(
                "SELECT smiles FROM compounds WHERE cid=?", (int(query),)).fetchone()
            if row is None:
                bad += 1
                print(f"CID DIFF {query}: absent locally")
                continue
            if response is None:
                continue  # PUG had nothing either (rare)
            if _canon(row[0]) != _canon(response):
                bad += 1
                print(f"CID DIFF {query}: smiles differ local={row[0][:60]!r} pug={response[:60]!r}")

    if pattern_notes:
        print("pattern hints:", pattern_notes)
    print(f"parity: {'FAIL' if bad else 'PASS'} ({bad} diffs / {len(entries)} checks)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
