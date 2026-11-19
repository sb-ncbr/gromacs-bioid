"""BLAST services with an NVMe copy of one database, and worker routing (2026-11-19)."""
from __future__ import annotations

import json
import os
import sys
import threading
from http.server import ThreadingHTTPServer

import pytest

from src_new import blast_service
from src_new.config.loader import RunConfig
from src_new.identification.resolvers import blast_service_client as svc
from src_new.identification.resolvers.blast import BLASTResolverNR, BLASTResolverUNIREF50

FAKE_BLAST = """#!{python}
import json, sys
a = sys.argv[1:]
if a == ["-version"]:
    print("blastp: 2.16.0+"); sys.exit(0)
q = sys.stdin.read().strip()
out = a[a.index("-out") + 1]
db = a[a.index("-db") + 1]
json.dump({{"BlastOutput2": [{{"report": {{"db": db, "query": q, "task": "-task" in a,
          "threads": a[a.index("-num_threads") + 1]}}}}]}}, open(out, "w"))
"""


@pytest.fixture
def blastp(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "blastp"
    exe.write_text(FAKE_BLAST.format(python=sys.executable))
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    svc._versions.clear()
    svc._health.clear()
    svc.routes.clear()
    return str(exe)


def _release(root, name, files=None):
    rel = root / ".staging" / name
    rel.mkdir(parents=True)
    for fname, data in (files or {"nr.pal": b"alias", "nr.00.psq": b"x" * 5000}).items():
        (rel / fname).write_bytes(data)
    link = root / "nr"
    if link.is_symlink():
        link.unlink()
    link.symlink_to(rel)
    return str(link / "nr")


def test_stages_once_then_ready_on_restart(tmp_path, blastp):
    db = _release(tmp_path / "dbs", "nr-20260729")
    s = blast_service.Service(db, str(tmp_path / "nvme"), stage_mbps=1000)
    assert s.state() == "staging" and s.program == "blastp"
    s.stage()
    h = s.health()
    assert h["state"] == "ready" and h["release"] == "nr-20260729" == svc.release_of(db)
    assert h["staging"]["done_bytes"] == h["staging"]["total_bytes"] == 5005
    assert (tmp_path / "nvme/nr-20260729/nr.00.psq").read_bytes() == b"x" * 5000
    again = blast_service.Service(db, str(tmp_path / "nvme"))
    assert again.state() == "ready" and again.release == "nr-20260729"


def test_new_release_replaces_the_old_copy(tmp_path, blastp):
    root = tmp_path / "dbs"
    db = _release(root, "nr-1")
    s = blast_service.Service(db, str(tmp_path / "nvme"), stage_mbps=1000)
    s.stage()
    _release(root, "nr-2", {"nr.pal": b"alias2", "nr.00.psq": b"y" * 10})
    assert s.release == "nr-1" and s.source_release() == "nr-2"  # old copy serves meanwhile
    s.stage()
    assert s.release == "nr-2"
    assert sorted(p.name for p in (tmp_path / "nvme").iterdir()) == ["nr-2"]


def test_search_checks_the_request(tmp_path, blastp):
    db = _release(tmp_path / "dbs", "nr-1")
    s = blast_service.Service(db, str(tmp_path / "nvme"), stage_mbps=1000)
    ok = {"release": "nr-1", "query": "MKVLA", "max_target_seqs": 500, "timeout_s": 60}
    assert s.search(ok)[0] == 409  # not copied yet
    s.stage()
    assert s.search({**ok, "release": "nr-0"})[0] == 409
    assert s.search({**ok, "query": "MKV\n>x\nLA"})[0] == 422
    assert s.search({**ok, "task": "blastn-short"})[0] == 422
    assert s.search({**ok, "timeout_s": 0})[0] == 422
    code, body = s.search({**ok, "task": "blastp-short"})
    assert code == 200
    report = body["output"]["BlastOutput2"][0]["report"]
    assert report["db"] == str(tmp_path / "nvme/nr-1/nr") and report["query"] == "MKVLA" and report["task"]
    assert s.health()["searches"] == 1


@pytest.fixture
def server(tmp_path, blastp):
    db = _release(tmp_path / "dbs", "nr-1")
    s = blast_service.Service(db, str(tmp_path / "nvme"), stage_mbps=1000)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), blast_service.make_handler(s))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield s, f"http://127.0.0.1:{httpd.server_address[1]}", db
    httpd.shutdown()


def _resolver(db, url, exe):
    cfg = RunConfig()
    cfg.blast.nr_aa_db = db
    cfg.blast.blastp_exec = exe
    cfg.blast.nr_service_url = url
    return BLASTResolverNR(cfg)


def test_worker_searches_on_the_service_when_ready(server, blastp, tmp_path):
    s, url, db = server
    r = _resolver(db, url, blastp)
    assert svc.unusable_reason(url, db, blastp) == "state staging"
    s.stage()
    svc._health.clear()
    assert svc.unusable_reason(url, db, blastp) is None
    report = r._run_blast_local("MKVLAAGIVGLLLA", str(tmp_path))[0]["BlastOutput2"][0]["report"]
    assert report["db"].startswith(str(tmp_path / "nvme"))
    assert svc.routes["blast_nr_protein"]["route"] == "service"
    assert svc.routes["blast_nr_protein"]["release"] == "nr-1"


def test_worker_searches_nfs_when_the_service_is_not_ready(server, blastp, tmp_path):
    s, url, db = server
    r = _resolver(db, url, blastp)
    report = r._run_blast_local("MKVLAAGIVGLLLA", str(tmp_path))[0]["BlastOutput2"][0]["report"]
    assert report["db"] == db  # the NFS path
    assert svc.routes["blast_nr_protein"] == {"route": "local", "release": "nr-1",
                                              "reason": "state staging"}


def test_worker_searches_nfs_on_another_release(server, blastp, tmp_path):
    s, url, db = server
    s.stage()
    _release(tmp_path / "dbs", "nr-2")  # NFS moved on, the service has not copied it yet
    r = _resolver(db, url, blastp)
    assert r._run_blast_local("MKVLAAGIVGLLLA", str(tmp_path))[0]["BlastOutput2"][0]["report"]["db"] == db
    assert svc.routes["blast_nr_protein"]["reason"] == "release nr-1 != nr-2"


def test_no_service_no_change(blastp, tmp_path):
    db = _release(tmp_path / "dbs", "nr-1")
    r = _resolver(db, "", blastp)
    assert r._run_blast_local("MKVLAAGIVGLLLA", str(tmp_path))[0]["BlastOutput2"][0]["report"]["db"] == db
    assert svc.routes == {}
    r = _resolver(db, "http://127.0.0.1:9", blastp)  # nothing listens
    assert r._run_blast_local("MKVLAAGIVGLLLA", str(tmp_path))[0]["BlastOutput2"][0]["report"]["db"] == db
    assert svc.routes["blast_nr_protein"]["reason"] == "no answer"


def test_service_timeout_is_a_blast_timeout(server, blastp, tmp_path, monkeypatch):
    from src_new.identification.base import IdentifierResolutionError
    s, url, db = server
    s.stage()
    monkeypatch.setattr(s, "_run", lambda *a: (504, {"error": "BLAST ran out of time"}))
    r = _resolver(db, url, blastp)
    with pytest.raises(IdentifierResolutionError, match="BLAST timed out"):
        r._run_blast_local("MKVLAAGIVGLLLA", str(tmp_path))
    assert svc.routes["blast_nr_protein"]["reason"] == "timeout"


def test_service_keys_and_default_urls():
    cfg = RunConfig.from_default_ini()
    assert BLASTResolverNR(cfg)._service_key == "nr"
    assert BLASTResolverUNIREF50(cfg)._service_key == "uniref50"
    assert cfg.blast.nr_service_url == "http://bioid-blast-nr:8080"
    assert cfg.blast.uniref50_service_url == "http://bioid-blast-uniref50:8080"


# -- database updates: AWS snapshots downloaded ahead of the NFS switch ------------

def test_release_names_match_the_nfs_naming():
    from src_new.blastdb_fetch import release_name
    assert release_name("nr", "2026-10-22-01-05-01") == "nr-20261022-010501"
    assert release_name("core_nt", "2026-10-22-01-05-01") == "core_nt-20261022-010501"


@pytest.fixture
def bucket(tmp_path, monkeypatch, blastp):
    """A fake NCBI bucket served from tmp_path/bucket, and a fake blastdbcmd."""
    from src_new import blastdb_fetch
    snap = tmp_path / "bucket" / "2026-10-22-01-05-01"
    snap.mkdir(parents=True)
    vols = {"nr.pal": b"alias", "nr.000.psq": b"q" * 3000, "nr.000.pin": b"i" * 10}
    for n, data in vols.items():
        (snap / n).write_bytes(data)
    for n in blastdb_fetch.EXTRA:
        (snap / n).write_bytes(b"tax")
    (snap / "nr-prot-metadata.json").write_text(json.dumps(
        {"dbname": "nr", "bytes-total": 3015, "files": [f"s3://x/2026-10-22-01-05-01/{n}" for n in vols]}))
    bindir = tmp_path / "bin"
    (bindir / "blastdbcmd").write_text(f"#!{sys.executable}\nprint('Database: fake nr')\n")
    (bindir / "blastdbcmd").chmod(0o755)
    monkeypatch.setattr(blastdb_fetch, "BUCKET", (tmp_path / "bucket").as_uri())
    return snap


def test_fetch_downloads_resumes_and_marks_complete(tmp_path, bucket):
    from src_new import blastdb_fetch
    dest = tmp_path / "nfs" / ".staging" / "nr-20261022-010501"
    dest.mkdir(parents=True)
    (dest / "nr.000.psq").write_bytes(b"q" * 3000)          # already there: kept
    (dest / "nr.pal.part").write_bytes(b"half")              # interrupted: fetched again
    status = {}
    blastdb_fetch.fetch("nr", "2026-10-22-01-05-01", dest, streams=2, status=status)
    assert (dest / "nr.pal").read_bytes() == b"alias" and not (dest / "nr.pal.part").exists()
    assert (dest / "taxdb.btd").exists() and (dest / "nr-prot-metadata.json").exists()
    assert json.loads((dest / ".complete").read_text())["snapshot"] == "2026-10-22-01-05-01"
    assert status["files_done"] == status["files_total"] == 6


def test_service_prefetches_and_serves_after_the_switch(tmp_path, bucket):
    root = tmp_path / "dbs"
    db = _release(root, "nr-20260729-070107")                   # NFS: the July copy
    s = blast_service.Service(db, str(tmp_path / "nvme"), snapshot="2026-10-22-01-05-01", streams=2)
    (tmp_path / "nvme" / "nr-20260729-070107").mkdir(parents=True)  # a partial July copy
    s.fetch_snapshot()
    s._drop(keep={s.release, s.prefetch})
    assert s.release is None and s.state() == "staging"         # NFS still on July: workers use NFS
    assert sorted(p.name for p in (tmp_path / "nvme").iterdir()) == ["nr-20261022-010501"]
    _release(root, "nr-20261022-010501")                         # the switch
    assert s._complete(s.source_release())
    s.release = s.source_release()                               # what keep_current does next
    h = s.health()
    assert h["state"] == "ready" and h["release"] == h["source_release"] == "nr-20261022-010501"


def test_blast_answers_are_cached_per_release(tmp_path, blastp):
    from src_new.identification import shared_cache
    root = tmp_path / "dbs"
    db = _release(root, "nr-1")
    r = _resolver(db, "", blastp)
    assert r.cache_name() == "blast_nr_protein@nr-1"
    before = shared_cache._key(r, "MKV", False)
    _release(root, "nr-2")
    assert r.cache_name() == "blast_nr_protein@nr-2" and shared_cache._key(r, "MKV", False) != before


@pytest.fixture
def range_bucket(tmp_path, monkeypatch, blastp):
    """A fake NCBI bucket over HTTP with Range support, and a fake blastdbcmd."""
    import functools
    from http.server import SimpleHTTPRequestHandler
    from src_new import blastdb_fetch
    root = tmp_path / "bucket"
    snap = root / "2026-10-22-01-05-01"
    snap.mkdir(parents=True)
    big = bytes(range(256)) * 40  # 10240 bytes: 5 pieces of 2048 + 0
    vols = {"nr.pal": b"alias", "nr.pdb": big}
    for n, data in vols.items():
        (snap / n).write_bytes(data)
    for n in blastdb_fetch.EXTRA:
        (snap / n).write_bytes(b"tax")
    (snap / "nr-prot-metadata.json").write_text(json.dumps(
        {"dbname": "nr", "bytes-total": len(big) + 5, "files": [f"s3://x/s/{n}" for n in vols]}))
    requests_seen = []

    class Ranged(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        bad_md5 = False

        def end_headers(self):
            # Google's x-goog-hash on whole-file answers
            import base64, hashlib
            if not self.headers.get("Range") and self.command == "GET":
                data = (root / self.path.lstrip("/")).read_bytes() + (b"x" if Ranged.bad_md5 else b"")
                self.send_header("x-goog-hash", "crc32c=AAAA==, md5="
                                 + base64.b64encode(hashlib.md5(data).digest()).decode())
            super().end_headers()

        def do_GET(self):
            rng = self.headers.get("Range")
            if not rng:
                return super().do_GET()
            data = (root / self.path.lstrip("/")).read_bytes()
            lo, hi = (int(x) for x in rng.split("=")[1].split("-"))
            requests_seen.append(lo)
            body = data[lo:hi + 1]
            self.send_response(206)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Ranged, directory=str(root)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    bindir = tmp_path / "bin"
    (bindir / "blastdbcmd").write_text(f"#!{sys.executable}\nprint('Database: fake nr')\n")
    (bindir / "blastdbcmd").chmod(0o755)
    monkeypatch.setattr(blastdb_fetch, "BUCKET", f"http://127.0.0.1:{httpd.server_address[1]}")
    monkeypatch.setattr(blastdb_fetch, "PIECE_BYTES", 2048)
    yield big, requests_seen, Ranged
    httpd.shutdown()


def test_large_files_come_in_pieces_and_resume(tmp_path, range_bucket):
    from src_new import blastdb_fetch
    big, seen, _ = range_bucket
    dest = tmp_path / "nfs" / "nr-20261022-010501"
    dest.mkdir(parents=True)
    (dest / "nr.pdb.part").write_bytes(big[:5000])  # an old front-to-back .part: 2 whole pieces valid
    status = {}
    blastdb_fetch.fetch("nr", "2026-10-22-01-05-01", dest, streams=3, status=status)
    assert (dest / "nr.pdb").read_bytes() == big
    assert not (dest / "nr.pdb.part").exists() and not (dest / "nr.pdb.part.json").exists()
    assert sorted(seen) == [4096, 6144, 8192]  # the first two pieces were kept
    assert status["files_done"] == status["files_total"] == 5


def test_a_file_whose_md5_differs_is_refused(tmp_path, range_bucket, monkeypatch):
    from src_new import blastdb_fetch
    _, _, handler = range_bucket
    handler.bad_md5 = True
    monkeypatch.setattr(blastdb_fetch, "ATTEMPTS", 1)
    with pytest.raises(RuntimeError, match="MD5"):
        blastdb_fetch.fetch("nr", "2026-10-22-01-05-01", tmp_path / "d", streams=1)
