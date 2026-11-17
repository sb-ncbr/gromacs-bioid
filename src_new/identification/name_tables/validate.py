"""Validate the force-field name table against PubChem (network required).

For every entry of maps.json:
  * the key has exactly one provenance record with the same InChIKey;
  * PubChem PUG REST resolves the InChIKey;
  * the provenance CID is among the CIDs PubChem returns for that key;
  * the PubChem molecular formula equals the provenance formula.

Requests are rate-limited to <= 4 per second (PubChem allows 5).

Usage:
    python src_new/identification/name_tables/validate.py [--only NAME ...]
Exit status 0 when every entry passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
MAPS = HERE / "maps.json"
PROVENANCE = HERE / "maps_provenance.json"
PUG = ("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/{}/property/"
       "MolecularFormula,IUPACName/JSON")
MIN_INTERVAL_S = 0.25  # <= 4 requests per second


class _RateLimiter:
    def __init__(self, interval: float) -> None:
        self.interval = interval
        self.last = 0.0

    def wait(self) -> None:
        delay = self.interval - (time.monotonic() - self.last)
        if delay > 0:
            time.sleep(delay)
        self.last = time.monotonic()


def query(session: requests.Session, limiter: _RateLimiter, inchikey: str) -> list[dict] | None:
    """Return PubChem property rows for an InChIKey, [] when not found, None on failure."""
    for attempt in range(6):
        limiter.wait()
        try:
            resp = session.get(PUG.format(inchikey), timeout=30)
        except requests.RequestException:
            time.sleep(2 + 3 * attempt)
            continue
        if resp.status_code == 404:
            return []
        if resp.status_code == 200:
            return resp.json().get("PropertyTable", {}).get("Properties", [])
        # 503 ServerBusy / throttling: back off and retry
        time.sleep(2 + 3 * attempt)
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", nargs="*", help="validate only these names")
    args = ap.parse_args(argv)

    maps = json.loads(MAPS.read_text())
    prov_list = json.loads(PROVENANCE.read_text())
    prov = {p["name"]: p for p in prov_list}
    failures: list[str] = []

    if len(prov) != len(prov_list):
        failures.append("duplicate names in maps_provenance.json")
    for name in sorted(set(maps) ^ set(prov)):
        failures.append(f"{name}: present in only one of maps.json / maps_provenance.json")

    names = sorted(maps) if not args.only else [n for n in args.only if n in maps]
    session = requests.Session()
    limiter = _RateLimiter(MIN_INTERVAL_S)
    cache: dict[str, list[dict] | None] = {}
    for i, name in enumerate(names, 1):
        key = maps[name]
        p = prov.get(name)
        if p is None:
            continue
        if p["inchikey"] != key:
            failures.append(f"{name}: provenance InChIKey {p['inchikey']} != maps.json {key}")
            continue
        if not p.get("source_urls"):
            failures.append(f"{name}: no source_urls")
        if key not in cache:
            cache[key] = query(session, limiter, key)
        rows = cache[key]
        if rows is None:
            failures.append(f"{name}: PubChem request failed for {key}")
        elif not rows:
            failures.append(f"{name}: {key} does not resolve on PubChem")
        else:
            cids = {r.get("CID") for r in rows}
            if p["pubchem_cid"] not in cids:
                failures.append(f"{name}: CID {p['pubchem_cid']} not in PubChem CIDs {sorted(cids)}")
            row = next((r for r in rows if r.get("CID") == p["pubchem_cid"]), rows[0])
            if row.get("MolecularFormula") != p["formula"]:
                failures.append(f"{name}: formula {row.get('MolecularFormula')} != provenance {p['formula']}")
        if i % 50 == 0:
            print(f"... {i}/{len(names)} checked", file=sys.stderr)

    if failures:
        print(f"FAIL: {len(failures)} problem(s) in {len(names)} entries")
        for f in failures:
            print("  " + f)
        return 1
    print(f"OK: {len(names)} entries resolve on PubChem with matching CID and formula")
    return 0


if __name__ == "__main__":
    sys.exit(main())
