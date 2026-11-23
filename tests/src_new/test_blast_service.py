"""BLAST services with an NVMe copy of one database, and worker routing (2026-11-19)."""
from __future__ import annotations

import json
import os
import shutil
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
    monkeypatch.setattr(s, "_run", lambda release, batch, members=None: [(504, {"error": "BLAST ran out of time"})] * len(batch))
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
            if not self.headers.get("Range") and self.command in ("GET", "HEAD"):
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


def test_a_restart_after_the_part_grew_does_not_count_it_done(tmp_path, range_bucket):
    """2026-11-19: a .part extended to full size, then the process restarted
    before a piece finished: the next start took it for a finished download."""
    from src_new import blastdb_fetch
    big, seen, _ = range_bucket
    dest = tmp_path / "nr-20261022-010501"
    dest.mkdir()
    url = f"{blastdb_fetch.BUCKET}/2026-10-22-01-05-01/nr.pdb"
    blastdb_fetch._Pieces(url, dest / "nr.pdb", len(big))  # grows the .part, then "dies"
    assert (dest / "nr.pdb.part").stat().st_size == len(big)
    blastdb_fetch.fetch("nr", "2026-10-22-01-05-01", dest, streams=2)
    assert (dest / "nr.pdb").read_bytes() == big
    assert sorted(seen) == [0, 2048, 4096, 6144, 8192]


def test_a_file_with_holes_is_removed_and_fetched_again(tmp_path, range_bucket, monkeypatch):
    from src_new import blastdb_fetch
    big, _, _ = range_bucket
    dest = tmp_path / "nr-20261022-010501"
    dest.mkdir()
    (dest / "nr.pdb").write_bytes(b"")  # "finished", but never written
    with open(dest / "nr.pdb", "r+b") as f:
        f.truncate(len(big))
    (dest / ".complete").write_text("{}")  # an old marker
    blastdb_fetch.fetch("nr", "2026-10-22-01-05-01", dest, streams=2, check="md5")
    assert (dest / "nr.pdb").read_bytes() == big
    assert json.loads((dest / ".complete").read_text())["checked"] == "md5"


def test_blocks_check_sees_a_sparse_file(tmp_path):
    from src_new import blastdb_fetch
    f = tmp_path / "x"
    with open(f, "wb") as out:
        out.truncate(100 << 20)
    assert blastdb_fetch._has_holes(f, "blocks", "")
    f.write_bytes(b"x" * (100 << 20))
    assert not blastdb_fetch._has_holes(f, "blocks", "")


def test_a_downloaded_copy_without_a_checked_marker_is_fetched_again(tmp_path, bucket):
    root = tmp_path / "dbs"
    db = _release(root, "nr-20261022-010501")
    s = blast_service.Service(db, str(tmp_path / "nvme"), snapshot="2026-10-22-01-05-01", streams=2)
    s.fetch_snapshot()
    marker = tmp_path / "nvme" / "nr-20261022-010501" / ".complete"
    assert json.loads(marker.read_text())["checked"] == "md5" and s._complete(s.prefetch)
    marker.write_text(json.dumps({"snapshot": "2026-10-22-01-05-01"}))  # before 2026-11-19
    assert not s._complete(s.prefetch)
    again = blast_service.Service(db, str(tmp_path / "nvme"), snapshot="2026-10-22-01-05-01")
    assert again.release is None


# -- 2026-11-23: batches of searches, clients that leave ---------------------------

FAKE_BATCH_BLAST = """#!{python}
import json, os, sys, time
a = sys.argv[1:]
if a == ["-version"]:
    print("blastp: 2.16.0+"); sys.exit(0)
text = sys.stdin.read()
qs = [l for l in text.split("\\n") if l and not l.startswith(">")] if text.startswith(">") else [text.strip()]
with open(os.environ["FAKE_BLAST_LOG"], "a") as f:
    f.write(json.dumps({{"pid": os.getpid(), "queries": qs, "args": a,
                        "batch_size": os.environ.get("BATCH_SIZE")}}) + "\\n")
if any(q.startswith("SLEEPY") for q in qs):
    time.sleep(float(os.environ.get("FAKE_BLAST_SLEEP", "30")))
if any("FAIL" in q for q in qs):
    sys.stderr.write("BLAST query error: bad query"); sys.exit(1)
out = a[a.index("-out") + 1]
mts = a[a.index("-max_target_seqs") + 1]
json.dump({{"BlastOutput2": [{{"report": {{"results": {{"search": {{
    "query_id": "Query_%d" % (i + 1), "query_len": len(q), "hits": [{{"q": q, "max": mts}}]}}}}}}}}
    for i, q in enumerate(qs)]}}, open(out, "w"))
"""


@pytest.fixture
def fake_batch(tmp_path, monkeypatch):
    """A ready service on a fake blastp that takes multi-query FASTA, logs each
    run to FAKE_BLAST_LOG, sleeps on SLEEPY* queries and fails on *FAIL*."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "blastp"
    exe.write_text(FAKE_BATCH_BLAST.format(python=sys.executable))
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    runs = tmp_path / "runs.jsonl"
    monkeypatch.setenv("FAKE_BLAST_LOG", str(runs))
    monkeypatch.setattr(blast_service, "POLL_S", 0.2)
    db = _release(tmp_path / "dbs", "nr-1")

    def make(**kw):
        s = blast_service.Service(db, str(tmp_path / "nvme"), stage_mbps=1000, **kw)
        s.stage()
        return s

    def logged():
        return [json.loads(line) for line in runs.read_text().splitlines()] if runs.exists() else []
    return make, logged


def _req(query, **kw):
    return {"release": "nr-1", "query": query, "max_target_seqs": 500, "timeout_s": 60, **kw}


def _together(s, reqs):
    """Send the searches at the same moment; their answers in order."""
    out = [None] * len(reqs)

    def one(i):
        out[i] = s.search(reqs[i])
    threads = [threading.Thread(target=one, args=(i,)) for i in range(len(reqs))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    return out


def _wait_for(cond, timeout=10.0):
    import time
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_waiting_searches_run_as_one_batch_and_get_their_own_report(fake_batch):
    make, logged = fake_batch
    s = make(batch_max=16, batch_wait_s=1.0)
    queries = ["MKVLAAG", "MSTNPKPQRK", "MAAA", "MKVLAAG"]
    answers = _together(s, [_req(q) for q in queries])
    assert [code for code, _ in answers] == [200] * 4
    for q, (_, body) in zip(queries, answers):
        search = body["output"]["BlastOutput2"][0]["report"]["results"]["search"]
        assert search["query_id"] == "Query_1" and search["hits"][0]["q"] == q
        assert len(body["output"]["BlastOutput2"]) == 1 and body["release"] == "nr-1"
    runs = logged()
    # 2026-11-23: the repeated query is searched once, both callers get its report
    unique = sorted(set(queries))
    assert len(runs) == 1 and sorted(runs[0]["queries"]) == unique
    assert runs[0]["batch_size"] == str(sum(len(q) + 1 for q in unique))  # one pass over the database
    assert answers[0][1]["output"] == answers[3][1]["output"]
    h = s.health()
    assert h["batches"] == 1 and h["batched"] == 3 and h["batch_mean"] == 3.0 and h["deduplicated"] == 1
    assert h["searches"] == 4 and h["running"] == h["waiting"] == h["processes"] == 0


def test_identical_searches_run_once(fake_batch):
    make, logged = fake_batch
    s = make(batch_max=16, batch_wait_s=1.0)
    answers = _together(s, [_req("MKVLAAG") for _ in range(5)])
    assert [code for code, _ in answers] == [200] * 5
    runs = logged()
    assert len(runs) == 1 and runs[0]["queries"] == ["MKVLAAG"]
    assert s.health()["deduplicated"] == 4 and s.health()["searches"] == 5


def test_incompatible_searches_are_not_batched(fake_batch):
    make, logged = fake_batch
    s = make(batch_max=16, batch_wait_s=1.0)
    answers = _together(s, [_req("MKVL"), _req("MKVLA"), _req("MKVLAA", max_target_seqs=10),
                            _req("MKV", task="blastp-short"), _req("---")])
    assert [code for code, _ in answers] == [200] * 5
    groups = sorted((r["args"][r["args"].index("-max_target_seqs") + 1], "-task" in r["args"],
                     sorted(r["queries"])) for r in logged())
    assert groups == [("10", False, ["MKVLAA"]), ("500", False, ["---"]),  # no letters: alone
                      ("500", False, ["MKVL", "MKVLA"]), ("500", True, ["MKV"])]
    assert answers[2][1]["output"]["BlastOutput2"][0]["report"]["results"]["search"]["hits"][0]["max"] == "10"


def test_batch_size_is_capped_and_a_lone_search_is_not_delayed_beyond_the_window(fake_batch):
    import time
    make, logged = fake_batch
    s = make(batch_max=2, batch_wait_s=0.5)
    started = time.time()
    assert s.search(_req("MKVL"))[0] == 200
    assert time.time() - started < 0.5 + 1.0
    assert [code for code, _ in _together(s, [_req(q) for q in ("MA", "MC", "MD", "ME", "MF")])] == [200] * 5
    assert sorted(len(r["queries"]) for r in logged()) == [1, 1, 2, 2]


def test_spread_over_free_slots(fake_batch):
    make, logged = fake_batch
    s = make(slots=2, batch_max=16, batch_wait_s=1.0, batch_spread="1")
    _together(s, [_req(q) for q in ("MA", "MC", "MD", "ME")])
    assert sorted(len(r["queries"]) for r in logged()) == [2, 2]
    s = make(slots=2, batch_max=16, batch_wait_s=1.0, batch_spread="0")
    _together(s, [_req(q) for q in ("MG", "MH", "MI", "MK")])
    assert sorted(len(r["queries"]) for r in logged()) == [2, 2, 4]


def test_a_failed_batch_reports_the_error_to_every_member(fake_batch):
    make, _ = fake_batch
    s = make(batch_max=16, batch_wait_s=1.0)
    answers = _together(s, [_req("MKVL"), _req("MFAIL"), _req("MAAA")])
    assert [code for code, _ in answers] == [500] * 3
    assert all("bad query" in body["error"] for _, body in answers)
    h = s.health()
    assert h["failures"] == 3 and h["running"] == h["waiting"] == 0


def test_per_search_timeouts_hold_inside_a_batch(fake_batch, monkeypatch):
    make, logged = fake_batch
    monkeypatch.setenv("FAKE_BLAST_SLEEP", "2")
    s = make(batch_max=16, batch_wait_s=0.5)
    answers = _together(s, [_req("SLEEPYA", timeout_s=1), _req("SLEEPYB", timeout_s=30)])
    assert answers[0] == (504, {"error": "BLAST ran out of time"})
    assert answers[1][0] == 200
    assert len(logged()) == 1 and s.health()["timeouts"] == 1 and s.health()["killed"] == 0


@pytest.fixture
def fake_server(fake_batch):
    make, logged = fake_batch
    servers = []

    def start(**kw):
        s = make(**kw)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), blast_service.make_handler(s))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        servers.append(httpd)
        return s, httpd.server_address[1]
    yield start, logged
    for httpd in servers:
        httpd.shutdown()


def _post(port, req):
    """Send a search over a raw socket; the open socket (close it to leave)."""
    import socket
    body = json.dumps(req).encode()
    sock = socket.create_connection(("127.0.0.1", port))
    sock.sendall(b"POST /search HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
                 + f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    return sock


def _answer(sock):
    data = b""
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        data += chunk
        head, _, body = data.partition(b"\r\n\r\n")
        if body and b"Content-Length" in head:
            n = int(head.split(b"Content-Length: ")[1].split(b"\r\n")[0])
            if len(body) >= n:
                return int(head.split()[1]), json.loads(body[:n])
    return None


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_a_client_that_leaves_while_waiting_never_gets_a_slot(fake_server):
    start, logged = fake_server
    s, port = start(slots=1, batch_max=1)
    busy = _post(port, _req("SLEEPYA"))  # holds the only slot
    assert _wait_for(lambda: len(logged()) == 1)
    leaver = _post(port, _req("MKVL"))
    assert _wait_for(lambda: s.health()["waiting"] == 1)
    leaver.close()
    assert _wait_for(lambda: s.health()["abandoned"] == 1)
    assert s.health()["waiting"] == 0
    busy.close()  # the running search is abandoned and its BLAST killed
    assert _wait_for(lambda: s.health()["killed"] == 1)
    assert not _alive(logged()[0]["pid"])
    sock = _post(port, _req("MAAA"))  # the slot is free again
    code, body = _answer(sock)
    assert code == 200 and body["output"]["BlastOutput2"][0]["report"]["results"]["search"]["hits"][0]["q"] == "MAAA"
    assert [r["queries"] for r in logged()] == [["SLEEPYA"], ["MAAA"]]  # MKVL never ran
    h = s.health()
    assert h["abandoned"] == 2 and h["running"] == h["waiting"] == h["processes"] == 0


def test_a_client_gone_before_its_batch_starts_is_dropped_without_a_run(fake_server, monkeypatch):
    start, logged = fake_server
    monkeypatch.setenv("FAKE_BLAST_SLEEP", "1")
    s, port = start(slots=1, batch_max=16)
    busy = _post(port, _req("SLEEPYA"))
    assert _wait_for(lambda: len(logged()) == 1)
    monkeypatch.setattr(blast_service, "POLL_S", 30.0)  # its own handler does not look in time
    leaver = _post(port, _req("MKVL"))
    assert _wait_for(lambda: s.health()["waiting"] == 1)
    leaver.close()
    assert _answer(busy)[0] == 200
    assert _wait_for(lambda: s.health()["abandoned"] == 1, timeout=5)  # seen when the slot freed
    assert len(logged()) == 1 and s.health()["waiting"] == 0


def test_a_batch_member_that_leaves_does_not_stop_the_others(fake_server, monkeypatch):
    start, logged = fake_server
    monkeypatch.setenv("FAKE_BLAST_SLEEP", "1.5")
    s, port = start(batch_max=16, batch_wait_s=0.5)
    stays, leaves = _post(port, _req("SLEEPYA")), _post(port, _req("SLEEPYB"))
    assert _wait_for(lambda: len(logged()) == 1)
    leaves.close()
    code, body = _answer(stays)
    assert code == 200 and body["output"]["BlastOutput2"][0]["report"]["results"]["search"]["hits"][0]["q"] == "SLEEPYA"
    h = s.health()
    assert h["abandoned"] == 1 and h["killed"] == 0 and h["searches"] == 1 and h["batched"] == 2


# real BLAST+ on small databases: a batch answers exactly what single searches do

def _blast_db(root, name, dbtype, records):
    import subprocess
    rel = root / ".staging" / f"{name}-1"
    rel.mkdir(parents=True)
    fasta = root / f"{name}.fa"
    fasta.write_text("".join(f">s{i} member {i}\n{seq}\n" for i, seq in enumerate(records)))
    subprocess.run(["makeblastdb", "-in", str(fasta), "-dbtype", dbtype, "-out", str(rel / name)],
                   check=True, capture_output=True)
    (root / name).symlink_to(rel)
    return str(root / name / name)


def _families(alphabet, n_fam, per, length, rate, seed):
    import random
    rnd = random.Random(seed)

    def mutate(seq, r):
        return "".join(rnd.choice(alphabet) if rnd.random() < r else c for c in seq if rnd.random() > r / 10)
    bases = ["".join(rnd.choice(alphabet) for _ in range(rnd.randint(length // 2, length))) for _ in range(n_fam)]
    records = [mutate(b, rnd.random() * 0.5) for b in bases for _ in range(per)]
    queries = [mutate(bases[i], rate) for i in range(0, n_fam, 2)]
    return records, queries


@pytest.mark.skipif(not shutil.which("makeblastdb") or not shutil.which("blastp") or not shutil.which("blastn"),
                    reason="needs BLAST+")
@pytest.mark.parametrize("kind", ["protein", "nucleotide"])
def test_a_batch_on_real_blast_matches_single_searches(tmp_path, kind):
    if kind == "protein":
        records, queries = _families("ACDEFGHIKLMNPQRSTVWY", 12, 15, 300, 0.2, 1)
        db = _blast_db(tmp_path / "dbs", "nr", "prot", records)
        queries += ["MKVLAAGW", "XXXXXXXXXXXX", queries[0].lower()]  # no hits; cannot be scored
        variants = [(None, 500), (None, 3), ("blastp-short", 20)]
    else:
        records, queries = _families("ACGT", 12, 15, 1200, 0.05, 2)
        db = _blast_db(tmp_path / "dbs", "nt", "nucl", records)
        queries += [records[3][50:80], "N" * 30]
        variants = [(None, 500), (None, 2), ("blastn-short", 20)]
    nvme = str(tmp_path / "nvme")
    batched = blast_service.Service(db, nvme, threads=2, batch_max=32, batch_wait_s=1.0)
    batched.stage()
    single = blast_service.Service(db, nvme, threads=2)
    release = batched.release
    for task, mts in variants:
        reqs = [{"release": release, "query": q, "task": task, "max_target_seqs": mts, "timeout_s": 120}
                for q in queries]
        before = batched.health()["batches"]
        together = _together(batched, reqs)
        alone = [single.search(r) for r in reqs]
        assert [c for c, _ in together] == [c for c, _ in alone] == [200] * len(reqs)
        for (_, a), (_, b) in zip(together, alone):
            assert json.dumps(a["output"]) == json.dumps(b["output"])
        hits = [len(b["output"]["BlastOutput2"][0]["report"]["results"]["search"].get("hits", [])) for _, b in alone]
        assert sum(hits) > len(queries)  # real hits were compared
        # one batch for all, plus the query BLAST could not score, again on its own
        assert batched.health()["batches"] - before == 2
