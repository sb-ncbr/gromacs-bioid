"""Shared cache on the admin page (src_new/api/cache_admin.py). No Redis."""
from __future__ import annotations

import fnmatch
import time

import pytest

from src_new import service_stats as ss
from src_new.api import cache_admin


class FakeRedis:
    def __init__(self):
        self.kv: dict[str, object] = {}

    def info(self, section):
        return {"memory": {"used_memory": 900, "maxmemory": 1000, "maxmemory_policy": "volatile-lru"},
                "stats": {"evicted_keys": 7, "expired_keys": 2, "keyspace_hits": 30, "keyspace_misses": 10},
                "server": {"uptime_in_seconds": 3600}}[section]

    def dbsize(self):
        return len(self.kv)

    def scan_iter(self, match="*", count=None):
        return [k.encode() for k in list(self.kv) if fnmatch.fnmatchcase(k, match)]

    def memory_usage(self, key):
        return 100 if key.startswith("bioid:rc") else 10

    def hgetall(self, key):
        return {f.encode(): str(v).encode() for f, v in (self.kv.get(key) or {}).items()}

    def unlink(self, *keys):
        n = 0
        for k in keys:
            n += self.kv.pop(k.decode() if isinstance(k, bytes) else k, None) is not None
        return n

    def pipeline(self, transaction=False):
        outer, calls = self, []

        class Pipe:
            def __getattr__(self, name):
                return lambda *a: calls.append((name, a))

            def execute(self):
                return [getattr(outer, name)(*a) for name, a in calls]
        return Pipe()


@pytest.fixture
def r():
    fake = FakeRedis()
    for i in range(3):
        fake.kv[f"bioid:rc:v1:fp1:blast_nr_protein@2026-10-22:id:{i}"] = "x"
    fake.kv["bioid:rc:v1:fp1:blast_nr_protein@2026-07-29:sim:0"] = "x"
    fake.kv["bioid:rc:v1:fp2:chembl_struct:id:0"] = "x"
    fake.kv["bioid:rc:v1:fp2:chembl_struct:sim:0"] = "x"
    for i in range(4):
        fake.kv[f"bioid:ann:v1:live:PUBCHEM_CID:{i}"] = "1"
    fake.kv["someone:else"] = "1"
    return fake


def test_redis_info(r):
    info = cache_admin.redis_info(r)
    assert info["used_bytes"] == 900 and info["max_bytes"] == 1000 and info["evicted"] == 7
    assert info["hit_share"] == 0.75 and info["keys"] == len(r.kv)


def test_keys_summary_per_kind_and_database(r):
    s = cache_admin.keys_summary(r)
    kinds = {k["kind"]: k for k in s["kinds"]}
    assert kinds["results"]["keys"] == 6 and kinds["results"]["est_bytes"] == 600
    assert kinds["annotations"]["keys"] == 4 and kinds["annotations"]["purgeable"]
    assert not kinds["measurements"]["purgeable"] and s["other_keys"] == 1
    dbs = {d["cache_name"]: d for d in s["databases"]}
    assert dbs["blast_nr_protein@2026-10-22"] == {"cache_name": "blast_nr_protein@2026-10-22",
                                                  "resolver": "blast_nr_protein", "release": "2026-10-22",
                                                  "identity": 3, "similarity": 0, "keys": 3}
    assert dbs["chembl_struct"]["release"] is None and dbs["chembl_struct"]["keys"] == 2


def test_usage_counts_cache_answers(r):
    now = 1_800_000_000.0
    bucket = f"{ss.PREFIX}:b:{int(now // ss.BUCKET_S)}"
    r.kv[bucket] = {"db:chembl_struct|identify|cache_shared": 6, "db:chembl_struct|identify|cache_local": 2,
                    "db:chembl_struct|identify|ok": 1, "db:chembl_struct|identify|error:Timeout": 1,
                    "db:chembl_struct|identify|ms": 999, "db:chembl_struct|identify|lat:1": 2,
                    "http:www.ebi.ac.uk|verify|ok": 5}
    u = cache_admin.usage(r, now)
    (row,) = u["last_24h"]
    assert row == {"service": "chembl_struct", "shared": 6, "local": 2, "live": 2, "answered_share": 0.8}
    assert len(u["hourly"]) == cache_admin.HOURS
    assert u["hourly"][-1]["shared"] == 6 and u["hourly"][0]["shared"] == 0
    assert u["total_24h"]["answered_share"] == 0.8


def _wait_purge():
    for _ in range(200):
        st = cache_admin.purge_state()
        if not st.get("running"):
            return st
        time.sleep(0.01)
    raise AssertionError("purge did not finish")


def test_purge_one_database_leaves_the_rest(r):
    cache_admin.start_purge(r, "results", "blast_nr_protein@2026-07-29")
    st = _wait_purge()
    assert st["deleted"] == 1 and st["error"] is None
    assert sum(k.startswith("bioid:rc:v1:") for k in r.kv) == 5


def test_purge_all_results_keeps_annotations(r):
    cache_admin.start_purge(r, "results")
    assert _wait_purge()["deleted"] == 6
    assert not any(k.startswith("bioid:rc:v1:") for k in r.kv)
    assert sum(k.startswith("bioid:ann:v1:") for k in r.kv) == 4 and "someone:else" in r.kv


def test_purge_annotations(r):
    cache_admin.start_purge(r, "annotations")
    assert _wait_purge()["deleted"] == 4


@pytest.mark.parametrize("kind,name", [("measurements", None), ("annotations", "x"), ("results", "*"),
                                       ("results", "id"), ("results", "a:b")])
def test_purge_refuses(r, kind, name):
    with pytest.raises(ValueError):
        cache_admin.start_purge(r, kind, name)
