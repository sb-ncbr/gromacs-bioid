"""Uploaded archives are unpacked safely into the run's input (archives.py)."""
from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src_new.api import archives
from src_new.api.main import app

GRO = b"t\n1\n    1SOL     OW    1   0.126   1.624   1.679\n   1.0 1.0 1.0\n"
TOP = b"[ system ]\nx\n"


def zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def targz_bytes(members: dict[str, bytes], symlink: str | None = None) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        if symlink:
            link = tarfile.TarInfo(symlink)
            link.type = tarfile.SYMTYPE
            link.linkname = "/etc/passwd"
            tf.addfile(link)
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    c = TestClient(app)
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    monkeypatch.setattr("src_new.api.routes.runs.run_pipeline_task.apply_async", lambda **k: None)
    return c


def submit(client, name, data):
    return client.post("/api/v1/runs", files={"files": (name, data)})


def test_zip_with_folders_is_flattened_and_runs(client, tmp_path):
    r = submit(client, "deposit.zip", zip_bytes({
        "sim/run1/conf.gro": GRO, "sim/topol.top": TOP,
        "__MACOSX/sim/._conf.gro": b"junk", "sim/.hidden.pdb": b"x", "sim/notes.txt": b"x",
        "sim/inner.zip": b"PK"}))
    assert r.status_code == 200, r.text
    assert "Note" not in r.json()["message"]  # .gro + .top: a complete simulation
    names = {p.name for p in (tmp_path / r.json()["run_id"] / "input").iterdir()}
    assert names == {"deposit.zip", "conf.gro", "topol.top"}


def test_tar_gz_and_tgz(client, tmp_path):
    for name in ("deposit.tar.gz", "deposit.tgz"):
        r = submit(client, name, targz_bytes({"d/conf.gro": GRO, "d/topol.top": TOP}))
        assert r.status_code == 200, r.text


def test_no_path_escapes_and_no_links(client, tmp_path):
    r = submit(client, "evil.tar.gz", targz_bytes({"../../escaped.gro": GRO, "/abs/topol.top": TOP},
                                                 symlink="link.pdb"))
    assert r.status_code == 200, r.text
    inp = tmp_path / r.json()["run_id"] / "input"
    assert {p.name for p in inp.iterdir()} == {"evil.tar.gz", "escaped.gro", "topol.top"}
    assert not (tmp_path / "escaped.gro").exists() and not (tmp_path.parent / "escaped.gro").exists()


def test_duplicate_names_are_refused(client, tmp_path):
    r = submit(client, "dup.zip", zip_bytes({"a/conf.gro": GRO, "b/conf.gro": GRO}))
    assert r.status_code == 422 and "appears twice" in r.json()["detail"]
    assert not any(tmp_path.iterdir())


def test_size_is_capped_while_unpacking(client, tmp_path, monkeypatch):
    monkeypatch.setattr(archives, "MAX_MEMBER_BYTES", 1000)
    r = submit(client, "bomb.zip", zip_bytes({"conf.gro": b"0" * 5000}))
    assert r.status_code == 422 and "too large" in r.json()["detail"]
    assert not any(tmp_path.iterdir())


def test_archive_without_a_simulation_is_refused(client, tmp_path):
    r = submit(client, "empty.zip", zip_bytes({"readme.txt": b"x", "traj.xtc": b"x"}))
    assert r.status_code == 422 and "complete simulation" in r.json()["detail"]
