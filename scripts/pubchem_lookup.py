#!/usr/bin/env python3
"""ops CLI for the local PubChem mirror DB.

Examples:
  python scripts/pubchem_lookup.py --formula C2H6O [--limit 10]
  python scripts/pubchem_lookup.py --cid 702
  python scripts/pubchem_lookup.py --inchikey LFQSCWFLJHTTHZ-UHFFFAOYSA-N
  python scripts/pubchem_lookup.py --stats
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src_new.molecules.pubchem_db import PubChemDB  # noqa: E402

DEFAULT_DB = "/app/databases/pubchem/current/pubchem.sqlite"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DEFAULT_DB)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--formula")
    g.add_argument("--cid", type=int)
    g.add_argument("--inchikey")
    g.add_argument("--stats", action="store_true")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    db = PubChemDB(args.db)
    if not db.exists():
        print(f"mirror DB not found: {args.db}", file=sys.stderr)
        return 2

    if args.stats:
        meta_path = Path(args.db).parent / "build_metadata.json"
        print("rows:", db.count())
        if meta_path.exists():
            print(json.dumps(json.loads(meta_path.read_text()), indent=2))
        else:
            print("(no build_metadata.json beside the DB)")
        return 0

    if args.formula:
        for cid in db.by_formula(args.formula, limit=args.limit):
            row = db.by_cid(cid)
            print(f"{cid}\t{row.smiles if row else '?'}")
        return 0

    if args.cid:
        row = db.by_cid(args.cid)
        print(row if row else "not found")
        return 0 if row else 1

    row = db.by_inchikey(args.inchikey)
    print(row if row else "not found")
    return 0 if row else 1


if __name__ == "__main__":
    sys.exit(main())
