"""W3.3 item 1: mmCIF structure search must route OUR minimal generated
mmCIF through a PDB conversion (RCSB 500s on the minimal content; live
probe 2026-11-01: identical staging route with a PDB export -> 200, hits),
and RCSB POSTs must tolerate the api-pod NFS negative-cache race (P01's
404: RCSB fetched /files/adhoc/<sha>.cif seconds after publish and got a
cached 404; later fetches 200) with ONE settle-retry on HTTP 4xx/5xx.

Genuine full mmCIF (declares _entity_poly.type) stays on format "cif".

Tests mock RCSB / staging — no live network.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest import mock

import pytest

pytest.importorskip("MDAnalysis")
requests = pytest.importorskip("requests")

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.mmcif import (
    MmCifResolver,
    IdentifierResolutionError,
    _mmcif_text_to_pdb,
)


MINIMAL_CIF = (
    "data_mock\n"
    "loop_\n"
    "_atom_site.group_PDB\n"
    "_atom_site.id\n"
    "_atom_site.label_atom_id\n"
    "_atom_site.label_comp_id\n"
    "_atom_site.label_asym_id\n"
    "_atom_site.label_seq_id\n"
    "_atom_site.Cartn_x\n"
    "_atom_site.Cartn_y\n"
    "_atom_site.Cartn_z\n"
    "_atom_site.type_symbol\n"
    "ATOM 1 N ALA A 1 10.000 20.000 30.000 N\n"
    "ATOM 2 CA ALA A 1 11.000 21.000 31.000 C\n"
    "ATOM 3 CB GLY B 2 12.500 22.500 32.500 C\n"
    "#\n"
)

# Genuine full mmCIF (declares polymer types) — must stay on the cif path.
FULL_CIF = (
    "data_1UBQ\n"
    "_entity_poly.type 'polypeptide(L)'\n"
    "loop_\n"
    "_atom_site.group_PDB\n"
    "_atom_site.id\n"
    "_atom_site.label_atom_id\n"
    "_atom_site.label_comp_id\n"
    "_atom_site.label_asym_id\n"
    "_atom_site.label_seq_id\n"
    "_atom_site.Cartn_x\n"
    "_atom_site.Cartn_y\n"
    "_atom_site.Cartn_z\n"
    "_atom_site.type_symbol\n"
    "ATOM 1 N MET A 1 27.340 24.430 10.457 N\n"
    "#\n"
)


def _config(tmp: Path, **pdb_kw) -> RunConfig:
    cfg = RunConfig()
    cfg.pdb.use_deployment_file_access = True
    cfg.pdb.deployment_file_url = "https://bioid.example"
    cfg.pdb.curr_uuid = "celery-run-not-in-api"
    for k, v in pdb_kw.items():
        setattr(cfg.pdb, k, v)
    return cfg


def _fake_rcsb_hit(post_mock, ident="4HHB", score=0.98):
    resp = mock.Mock()
    resp.status_code = 200
    resp.json.return_value = {
        "result_set": [{"identifier": ident, "score": score}]}
    resp.raise_for_status = lambda: None
    post_mock.return_value = resp


def _http_error(status: int) -> "requests.exceptions.HTTPError":
    resp = mock.Mock()
    resp.status_code = status
    err = requests.exceptions.HTTPError(f"HTTP {status}")
    err.response = resp
    return err


class TestMinimalToPdbConversion:
    def test_minimal_generated_loop_converts(self):
        pdb = _mmcif_text_to_pdb(MINIMAL_CIF)
        assert pdb is not None
        atom_lines = [l for l in pdb.splitlines() if l.startswith("ATOM")]
        assert len(atom_lines) == 3
        # chain B row keeps its chain; coordinates round-trip
        assert atom_lines[2][21] == "B"
        assert "12.500" in atom_lines[2]
        # resname + resseq mapped
        assert "ALA" in atom_lines[0]
        assert "GLY" in atom_lines[2]

    def test_full_cif_not_converted(self):
        assert _mmcif_text_to_pdb(FULL_CIF) is None

    def test_non_mmcif_text_not_converted(self):
        assert _mmcif_text_to_pdb("") is None
        assert _mmcif_text_to_pdb("ATOM      1  N   ALA A   1\n") is None


class TestQueryRouting:
    def test_minimal_signature_queries_as_pdb(self, tmp_path):
        resolver = MmCifResolver(_config(tmp_path))
        with mock.patch(
            "src_new.identification.resolvers._rcsb_search.requests.post"
        ) as post_mock:
            _fake_rcsb_hit(post_mock)
            results = resolver._resolve_similarity(MINIMAL_CIF, str(tmp_path))
        assert results == [("4HHB", 98.0)]
        payload = post_mock.call_args[1]["json"]
        params = payload["query"]["nodes"][0]["parameters"]
        assert params["value"]["format"] == "pdb"
        assert params["value"]["url"].endswith(".pdb")

    def test_full_cif_signature_stays_cif(self, tmp_path):
        resolver = MmCifResolver(_config(tmp_path))
        with mock.patch(
            "src_new.identification.resolvers._rcsb_search.requests.post"
        ) as post_mock:
            _fake_rcsb_hit(post_mock)
            results = resolver._resolve_similarity(FULL_CIF, str(tmp_path))
        assert results == [("4HHB", 98.0)]
        payload = post_mock.call_args[1]["json"]
        params = payload["query"]["nodes"][0]["parameters"]
        assert params["value"]["format"] == "cif"
        assert params["value"]["url"].endswith(".cif")


def _minimal_cif(rows):
    head = ("data_mock\nloop_\n_atom_site.group_PDB\n_atom_site.id\n"
            "_atom_site.label_atom_id\n_atom_site.label_comp_id\n"
            "_atom_site.label_asym_id\n_atom_site.label_seq_id\n"
            "_atom_site.Cartn_x\n_atom_site.Cartn_y\n_atom_site.Cartn_z\n"
            "_atom_site.type_symbol\n")
    body = "".join(f"ATOM {i} {a} {comp} A {seq} {i}.000 0.000 0.000 {a[0]}\n"
                   for i, (a, comp, seq) in enumerate(rows, start=1))
    return head + body + "#\n"


class TestNoPolymerSkip:
    """c13 S4: RCSB answers a small-molecule-only query with HTTP 400 (live
    probe 2026-11-04, T02's 39-atom ligand); the 397 sample logged it 66-294
    times per arm as structure_search_unavailable after a 10 s retry."""

    def test_ligand_only_payload_skipped_without_post(self, tmp_path):
        resolver = MmCifResolver(_config(tmp_path))
        ligand = _minimal_cif([("O1", "BDD", 101), ("C1", "BDD", 101), ("C2", "BDD", 101)])
        with mock.patch(
            "src_new.identification.resolvers._rcsb_search.requests.post"
        ) as post_mock:
            results = resolver._resolve_similarity(ligand, str(tmp_path))
        assert results == []
        assert post_mock.call_count == 0
        assert resolver._last_error == "no_polymer_payload"

    def test_force_field_named_protein_still_queried(self, tmp_path):
        resolver = MmCifResolver(_config(tmp_path))
        protein = _minimal_cif([("CA", "HIE", 1), ("CA", "CYX", 2), ("CA", "ASH", 3)])
        with mock.patch(
            "src_new.identification.resolvers._rcsb_search.requests.post"
        ) as post_mock:
            _fake_rcsb_hit(post_mock)
            results = resolver._resolve_similarity(protein, str(tmp_path))
        assert results == [("4HHB", 98.0)]
        assert post_mock.call_count == 1


class TestTransientRetry:
    def test_single_retry_after_http_404_race(self, tmp_path):
        """RCSB reports its fetch of the freshly staged URL as 404 (api-pod
        NFS negative cache). One settle-retry must mask the race."""
        resolver = MmCifResolver(_config(tmp_path))
        with mock.patch(
            "src_new.identification.resolvers._rcsb_search.requests.post"
        ) as post_mock, mock.patch(
            "src_new.identification.resolvers._rcsb_search.time.sleep"
        ) as sleep_mock:
            fail = mock.Mock()
            fail.status_code = 404
            fail.raise_for_status.side_effect = _http_error(404)
            ok = mock.Mock()
            ok.status_code = 200
            ok.json.return_value = {
                "result_set": [{"identifier": "4HHB", "score": 0.5}]}
            ok.raise_for_status = lambda: None
            post_mock.side_effect = [fail, ok]
            results = resolver._resolve_similarity(FULL_CIF, str(tmp_path))
        assert results == [("4HHB", 50.0)]
        assert post_mock.call_count == 2
        sleep_mock.assert_called_once()

    def test_permanent_5xx_stays_countable_error(self, tmp_path):
        resolver = MmCifResolver(_config(tmp_path))
        with mock.patch(
            "src_new.identification.resolvers._rcsb_search.requests.post"
        ) as post_mock, mock.patch(
            "src_new.identification.resolvers._rcsb_search.time.sleep"
        ):
            fail = mock.Mock()
            fail.status_code = 500
            fail.raise_for_status.side_effect = _http_error(500)
            post_mock.side_effect = [fail, fail]
            results = resolver._resolve_similarity(FULL_CIF, str(tmp_path))
        assert results == []
        assert "structure_search_unavailable" in (resolver._last_error or "")
        assert "HTTP 500" in resolver._last_error
        assert post_mock.call_count == 2  # one retry, then give up

    def test_http_204_is_empty_result_not_outage(self, tmp_path):
        """c13 S2: RCSB answers a valid no-match query with 204 + empty body.
        That is 0 hits — no settle-retry, no structure_search_unavailable."""
        resolver = MmCifResolver(_config(tmp_path))
        with mock.patch(
            "src_new.identification.resolvers._rcsb_search.requests.post"
        ) as post_mock, mock.patch(
            "src_new.identification.resolvers._rcsb_search.time.sleep"
        ) as sleep_mock:
            empty = mock.Mock()
            empty.status_code = 204
            empty.raise_for_status = lambda: None
            empty.json.side_effect = requests.exceptions.JSONDecodeError(
                "Expecting value", "", 0)
            post_mock.return_value = empty
            results = resolver._resolve_similarity(FULL_CIF, str(tmp_path))
        assert results == []
        assert "structure_search_unavailable" not in (resolver._last_error or "")
        assert post_mock.call_count == 1
        sleep_mock.assert_not_called()

    def test_timeout_not_retried(self, tmp_path):
        resolver = MmCifResolver(_config(tmp_path))
        with mock.patch(
            "src_new.identification.resolvers._rcsb_search.requests.post"
        ) as post_mock:
            post_mock.side_effect = requests.exceptions.Timeout("slow")
            results = resolver._resolve_similarity(FULL_CIF, str(tmp_path))
        assert results == []
        assert "timed out" in (resolver._last_error or "")
        assert post_mock.call_count == 1
