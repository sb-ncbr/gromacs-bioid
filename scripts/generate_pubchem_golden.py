#!/usr/bin/env python3
"""Capture golden PUG-REST responses for PubChem mirror parity testing.

Run from a network location with clean PUG access (workstation; cluster egress
IPs are blacklisted). Writes tests/fixtures/pubchem_golden.jsonl: one JSON per
line ``{"kind": ..., "query": ..., "response": ...}``.

Kinds:
  formula   -> response is the full ascending CID list from cids/txt
  inchikey  -> response is the CID list from inchikey/{key}/cids/txt (may be [])
  cid       -> response is the CanonicalSMILES text

Politeness: ~0.45s between requests, honors Retry-After, single retry.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
UA = "bat3-parity-fixture/1.0 (mirror parity testing)"

# Campaign-relevant coverage: tiny/common, drugs, cofactors, nucleotide-like,
# lipids, heme, sugars, salts, and one huge class (C6H12O6) + one absurd one.
FORMULAS = [
    "H2O", "CH4", "C2H6O", "C2H6O2", "C3H8O3", "C6H12O6", "C9H8O4", "C8H9NO2",
    "C10H16O", "C10H16N5O13P3", "C10H15N5O11P2", "C21H36N7O16P3S",
    "C34H32FeN4O4", "C27H46O", "C16H32O2", "C8H10N4O2", "C6H8O6",
    "C5H14NO", "C2H3O2", "C7H6O2", "C6H5NO2", "C4H10O", "C5H12O",
    "C3H6O3", "C4H6O5", "C5H5N5O", "C9H13N5O4", "C20H25N3O",
    "C17H19NO3", "C21H23ClFNO2", "C22H30Cl2N10", "C29H31N7O",
    "C51H98O6", "C43H83NO8P", "C17H21NO4", "C47H73NO17", "C62H111N11O12",
    "C10H14N2", "C21H28O5", "C20H24O2", "C8H11N", "C7H8N4O2",
    "C36H72O8", "C13H10O2", "C12H17N4OS", "C18H24O2",
    "C6H15N3", "C99H99N99O99", "NaCl",
]
INCHIKEYS = [
    "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",  # ethanol 702
    "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",  # aspirin 2244
    "KDXKERNSBIXSRK-UHFFFAOYSA-N",  # lidocaine?
    "XLYOFNOQVPJJNP-UHFFFAOYSA-N",  # water 962
    "RYYVLZVUVIJVGH-UHFFFAOYSA-N",  # caffeine
    "AAOVKJBEBIDNHE-UHFFFAOYSA-N",  # ?
    "UTIBUFBNLEZVBZ-UHFFFAOYSA-O",  # ?
    "BQJCRHHNABKAKU-KBQPJGBKSA-N",  # ?
    "HMFHFAOOGCDWPA-UHFFFAOYSA-N",  # ?
    "FINQKMXHCWMVSA-UHFFFAOYSA-N",
    "AAAAAAAAAAAAAAAAAAAAAA-AAAA-A",  # malformed
    "ZZZZZZZZZZZZZZ-ZZZZZZZZZZ-Z",  # well-formed, should be absent
]
CIDS = [
    702, 2244, 962, 5957, 5793, 5460162, 5234, 3121, 4056, 2112,
    6520, 6757, 1049, 4128, 10138, 6257, 3672, 297, 444734, 5460163,
]


def _get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return 404, ""
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            if exc.code in (429, 503) and attempt == 0:
                time.sleep(float(retry_after or 30))
                continue
            return exc.code, ""
    return 0, ""


def main() -> int:
    out_path = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/pubchem_golden.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(out_path, "w") as fh:
        for kind, queries, urlf in [
            ("formula", FORMULAS, lambda q: f"{BASE}/fastformula/{q}/cids/txt"),
            ("inchikey", INCHIKEYS, lambda q: f"{BASE}/inchikey/{q}/cids/txt"),
            ("cid", (str(c) for c in CIDS), lambda q: f"{BASE}/cid/{q}/property/CanonicalSMILES/TXT"),
        ]:
            for q in queries:
                status, text = _get(urlf(q))
                if kind == "cid":
                    response: object = text.strip() or None
                else:
                    response = [int(x) for x in text.split() if x.strip().isdigit()]
                fh.write(json.dumps({"kind": kind, "query": q, "status": status, "response": response}) + "\n")
                n += 1
                if n % 10 == 0:
                    print(f"{n} captured...", file=sys.stderr)
                time.sleep(0.45)
    print(f"captured {n} entries -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
