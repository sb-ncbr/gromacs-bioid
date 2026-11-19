"""Switch nr, nt and core_nt to the NCBI snapshot 2026-10-22, unattended (2026-11-19).

Runs in the cluster (deploy/blastdb-switch.yaml: a Job with the databases
volume and the shared cache), so the switch does not wait for anyone:

1. wait until the downloaded copies on NFS are complete and checked
   (.complete with "checked"; core_nt's copy is older, its files are checked
   here for never-written regions)
2. per database: blastdbcmd -info on the new copy, then point the symlink
   /app/databases/<db> at it (atomic rename; the July copy stays for rollback:
   ln -sfn .staging/<old> <db>.new && mv -T <db>.new <db>)
3. wait for the BLAST services to serve the new release, and search trypsin
   on the nr service
4. purge the shared cache's BLAST answers that cannot be used any more:
   untagged ones (written before answers carried the database release) and
   those of the July nr/nt/core_nt releases
5. write a report to /app/databases/.staging/switch-20261022.json

Running searches keep the files they opened; new searches use the new
release. Workers need no restart: they compare releases per search.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path("/app/databases")
NEW = {"nr": "nr-20261022-010501", "nt": "nt-20261022-010501", "core_nt": "core_nt-20261022-010501"}
SERVICES = {"nr": "http://bioid-blast-nr:8080", "nt": "http://bioid-blast-nt:8080",
            "core_nt": "http://bioid-blast-core-nt:8080"}
#: the July copies the symlinks pointed to (kept for rollback)
OLD = {"nr-20260729-070107", "nt-20260729-142734", "core_nt-20260729-123803"}
REPORT = ROOT / ".staging" / "switch-20261022.json"
TRYPSIN = ("IVGGYTCGANTVPYQVSLNSGYHFCGGSLINSQWVVSAAHCYKSGIQVRLGEDNINVVEGNEQFISASKSIVHPSYNSNTLNNDIMLIKL"
           "KSAASLNSRVASISLPTSCASAGTQCLISGWGNTKSSGTSYPDVLKCLKAPILSDSSCKSAYPGQITSNMFCAGYLEGGKDSCQGDSGGPV"
           "VCSGKLQGIVSWGSGCAQKNKPGVYTKVCNYVSWIKQTIASN")
WAIT_DOWNLOADS_S = 12 * 3600
WAIT_SERVICES_S = 6 * 3600

report: dict = {"started": time.strftime("%FT%T"), "steps": []}


def log(msg: str, **kw) -> None:
    print(time.strftime("%H:%M:%S"), msg, json.dumps(kw) if kw else "", flush=True)
    report["steps"].append({"at": time.strftime("%FT%T"), "msg": msg, **kw})
    REPORT.write_text(json.dumps(report, indent=1))


def holes(d: Path) -> list[str]:
    return [p.name for p in d.iterdir() if p.is_file() and p.stat().st_size > 64 << 20
            and p.stat().st_blocks * 512 < 0.97 * p.stat().st_size]


def ready(db: str) -> str:
    """'' when the new copy can be switched to, else why not."""
    d = ROOT / ".staging" / NEW[db]
    marker = d / ".complete"
    if not marker.exists():
        return "downloading"
    if json.loads(marker.read_text()).get("checked") not in ("blocks", "md5"):
        bad = holes(d)  # core_nt: downloaded before the check existed
        if bad:
            return f"{len(bad)} files with holes: {bad[:5]}"
    if any(p.name.endswith(".part") for p in d.iterdir()):
        return "unfinished .part files"
    return ""


def info(path: Path) -> str:
    r = subprocess.run(["blastdbcmd", "-db", str(path), "-info"], capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise RuntimeError(f"blastdbcmd -info {path}: {r.stderr.strip()[:300]}")
    return r.stdout.strip().splitlines()[0]


def health(url: str) -> dict:
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=10) as r:
            return json.load(r)
    except Exception as exc:
        return {"state": f"no answer ({exc})"}


def main() -> int:
    # 1. downloads
    deadline = time.time() + WAIT_DOWNLOADS_S
    last = None
    while True:
        why = {db: ready(db) for db in NEW}
        if why != last:
            log("waiting for the downloads" if any(why.values()) else "all downloads complete", **why)
            last = why
        if not any(why.values()):
            break
        if time.time() > deadline:
            log("GAVE UP: downloads not complete in time; nothing switched", **why)
            return 1
        time.sleep(60)

    # 2. switch
    for db, rel in NEW.items():
        link = ROOT / db
        old = os.readlink(link)
        if old == f".staging/{rel}":
            log(f"{db}: already switched")
            continue
        new_info = info(ROOT / ".staging" / rel / db)
        tmp = ROOT / f"{db}.new"
        if tmp.is_symlink():
            tmp.unlink()
        os.symlink(f".staging/{rel}", tmp)
        os.replace(tmp, link)
        log(f"{db}: switched", old=old, new=f".staging/{rel}", info=new_info,
            rollback=f"cd /app/databases && ln -sfn {old} {db}.new && mv -T {db}.new {db}")
        log(f"{db}: reads through the symlink", info=info(ROOT / db / db))

    # 3. services
    deadline = time.time() + WAIT_SERVICES_S
    pending = dict(SERVICES)
    while pending and time.time() < deadline:
        for db, url in list(pending.items()):
            h = health(url)
            if h.get("state") == "ready" and h.get("release") == NEW[db]:
                log(f"{db} service serves the new release", release=h["release"])
                del pending[db]
        if pending:
            time.sleep(60)
    if pending:
        log("services not serving the new release in time (workers use NFS meanwhile)",
            **{db: health(url).get("state") for db, url in pending.items()})
    if "nr" not in pending:
        t = time.time()
        body = json.dumps({"release": NEW["nr"], "query": TRYPSIN, "task": None,
                           "max_target_seqs": 50, "timeout_s": 3600}).encode()
        req = urllib.request.Request(f"{SERVICES['nr']}/search", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=4000) as r:
                out = json.load(r)["output"]
            hits = out["BlastOutput2"][0]["report"]["results"]["search"]["hits"]
            top = hits[0]["description"][0] if hits else {}
            log("nr service: trypsin search", seconds=round(time.time() - t), hits=len(hits),
                top=f"{top.get('accession')} {top.get('title', '')[:80]}")
        except Exception as exc:
            log("nr service: trypsin search FAILED", error=str(exc)[:300])

    # 4. cache purge
    import redis
    r = redis.Redis.from_url(os.environ["BAT3_SHARED_CACHE_URL"])
    old_releases = OLD | {Path(s["old"]).name for s in report["steps"] if s.get("old")}
    deleted = kept = 0
    batch = []
    for key in r.scan_iter(match="bioid:rc:v1:*:blast_*", count=2000):
        name = key.decode().split(":")[4]
        resolver, _, release = name.partition("@")
        if not resolver.startswith("blast_"):
            continue
        if not release or release in old_releases:
            batch.append(key)
        else:
            kept += 1
        if len(batch) >= 500:
            deleted += r.delete(*batch)
            batch = []
    if batch:
        deleted += r.delete(*batch)
    log("shared cache: old BLAST answers purged", deleted=deleted, kept=kept,
        old_releases=sorted(old_releases))
    report["finished"] = time.strftime("%FT%T")
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
