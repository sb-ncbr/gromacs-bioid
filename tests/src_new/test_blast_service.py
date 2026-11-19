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
