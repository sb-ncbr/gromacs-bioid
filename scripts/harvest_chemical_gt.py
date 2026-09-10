#!/usr/bin/env python3
"""Harvest chemical GT (INCHIKEYS) from MDDBR project metadata into
ground_truth_signatures. Metadata cached on NFS; idempotent; resumable."""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import psycopg2
import requests

DATABASE_URL = os.environ["DATABASE_URL"]
CACHE = "/data/validation/mddbr_meta_cache"
API = "https://mdposit.mddbr.eu/api/rest/v1"
os.makedirs(CACHE, exist_ok=True)


def get_meta(acc):
    path = os.path.join(CACHE, acc + ".json")
    try:
        return json.load(open(path)), True
    except Exception:
        pass
    try:
        r = requests.get(f"{API}/projects/{acc}", timeout=30)
        if r.status_code == 404:
            payload = {"_missing": True}
        else:
            r.raise_for_status()
            payload = r.json()
    except Exception as e:
        return {"_error": str(e)}, False
    try:
        json.dump(payload, open(path, "w"))
    except OSError:
        pass
    return payload, False


def main():
    con = psycopg2.connect(DATABASE_URL)
    con.autocommit = True
    cur = con.cursor()
    cur.execute("SELECT id, local_accession FROM mddb_entries ORDER BY id")
    entries = cur.fetchall()
    cur.execute("SELECT entry_id, signature_value FROM ground_truth_signatures WHERE signature_type='inchikey'")
    existing = set(cur.fetchall())

    to_fetch = [e for e in entries
                if not os.path.exists(os.path.join(CACHE, e[1] + ".json"))]
    print(f"{len(entries)} entries; {len(entries)-len(to_fetch)} cached; fetching {len(to_fetch)}")

    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(get_meta, acc): acc for _, acc in to_fetch}
        for fut in as_completed(futs):
            done += 1
            if done % 500 == 0:
                print(f"  {done}/{len(to_fetch)} fetched ({time.time()-t0:.0f}s)", flush=True)
            fut.result()

    inserted = 0
    scanned = 0
    for eid, acc in entries:
        try:
            md = json.load(open(os.path.join(CACHE, acc + ".json")))
        except Exception:
            continue
        scanned += 1
        iks = (md.get("metadata") or {}).get("INCHIKEYS") or []
        for ik in iks:
            if not isinstance(ik, str) or not ik.strip():
                continue
            ik = ik.strip().upper()
            if (eid, ik) in existing:
                continue
            cur.execute(
                "INSERT INTO ground_truth_signatures (entry_id, signature_type, signature_value, raw_data, created_at) "
                "VALUES (%s,'inchikey',%s,%s,now())", (eid, ik, "mddbr:INCHIKEYS"))
            existing.add((eid, ik))
            inserted += 1
    print(f"scanned {scanned} metas; inserted {inserted} inchikey GT rows; total existing now {len(existing)}")


if __name__ == "__main__":
    main()
