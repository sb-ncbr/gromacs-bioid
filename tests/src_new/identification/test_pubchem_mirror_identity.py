"""pubchem_struct exact matches from the local mirror; InChIKey hits merged
into their CID (2026-11-20). No network."""

from __future__ import annotations

import gzip
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import src_new.identification.resolution_manager as rm
import src_new.identification.resolvers.pubchem as pubchem_mod
from src_new.identification.base import IdentifierResolutionError
from src_new.identification.resolvers.pubchem import PubChemResolver
from src_new.molecules.pubchem_db import PubChemDB, build
from src_new.verification.dedup import RawHit, deduplicate_and_score, merge_inchikey_hits

ETHANOL_IK = "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
ASPIRIN_IK = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
WATER_IK = "XLYOFNOQVPJJNP-UHFFFAOYSA-N"
# cid, smiles, InChIKey: 702 and 9999 share ethanol's key and are the same
# structure (undecidable offline); water 962 shares its key with
# '[H+].[OH-]' 22247451 as in the real mirror
ROWS = [(702, "CCO", ETHANOL_IK), (2244, "CC(=O)OC1=CC=CC=C1C(=O)O", ASPIRIN_IK),
        (9999, "OCC", ETHANOL_IK), (962, "O", WATER_IK), (22247451, "[H+].[OH-]", WATER_IK)]


@pytest.fixture()
def mirror(tmp_path: Path) -> PubChemDB:
    # the builder streams both files in ascending CID order, like PubChem's
    smiles_gz, ik_gz = tmp_path / "CID-SMILES.gz", tmp_path / "CID-InChI-Key.gz"
    with gzip.open(smiles_gz, "wt") as fh:
        fh.write("".join(f"{c}\t{s}\n" for c, s, _ in sorted(ROWS)))
    with gzip.open(ik_gz, "wt") as fh:
        fh.write("".join(f"{c}\tInChI=1S/fake\t{k}\n" for c, _, k in sorted(ROWS)))
    build(tmp_path / "pubchem.sqlite", smiles_gz, ik_gz, workers=1)
    return PubChemDB(str(tmp_path / "pubchem.sqlite"))


def test_cids_by_inchikey(mirror):
    assert mirror.cids_by_inchikey(ETHANOL_IK) == [702, 9999]
    assert mirror.cids_by_inchikey(ASPIRIN_IK.lower()) == [2244]
    assert mirror.cids_by_inchikey("ZZZZZZZZZZZZZZ-ZZZZZZZZZZ-N") == []


def _resolver(db, monkeypatch, pug_up=True):
    r = PubChemResolver.__new__(PubChemResolver)
    r.config = SimpleNamespace(pubchem=SimpleNamespace(retry_attempts=1, retry_delay_s=0))
    r._session = None
    r._local_db = db
    online = MagicMock(return_value=["online"])
    monkeypatch.setattr(pubchem_mod, "pubchem_fetch_identity_match", online)
    probe = MagicMock(return_value=pug_up)
    monkeypatch.setattr(rm, "_pubchem_healthy", probe)
    return r, online, probe


def test_single_cid_comes_from_the_mirror(mirror, monkeypatch):
    r, online, probe = _resolver(mirror, monkeypatch)
    assert r._resolve_identity("CC(=O)OC1=CC=CC=C1C(=O)O", "") == ["2244"]
    online.assert_not_called()
    probe.assert_not_called()


def test_selfies_signature_uses_the_mirror(mirror, monkeypatch):
    r, online, _ = _resolver(mirror, monkeypatch)
    assert r._resolve_identity("[C][C][=Branch1][C][=O][O][C][=C][C][=C][C][=C][Ring1][=Branch1]"
                               "[C][=Branch1][C][=O][O]", "") == ["2244"]
    online.assert_not_called()


def test_shared_key_resolved_by_structure(mirror, monkeypatch):
    r, online, probe = _resolver(mirror, monkeypatch, pug_up=False)
    assert mirror.cids_by_inchikey(WATER_IK) == [962, 22247451]
    assert r._resolve_identity("O", "") == ["962"]
    online.assert_not_called()
    probe.assert_not_called()


def test_several_cids_ask_pubchem(mirror, monkeypatch):
    r, online, _ = _resolver(mirror, monkeypatch, pug_up=True)
    assert r._resolve_identity("CCO", "") == ["online"]


def test_several_cids_while_pubchem_down_returns_all(mirror, monkeypatch):
    r, online, _ = _resolver(mirror, monkeypatch, pug_up=False)
    assert r._resolve_identity("CCO", "") == ["702", "9999"]
    online.assert_not_called()


def test_mirror_miss_goes_online(mirror, monkeypatch):
    r, online, _ = _resolver(mirror, monkeypatch, pug_up=True)
    assert r._resolve_identity("c1ccncc1", "") == ["online"]


def test_mirror_miss_while_pubchem_down_is_an_error(mirror, monkeypatch):
    r, online, _ = _resolver(mirror, monkeypatch, pug_up=False)
    with pytest.raises(IdentifierResolutionError, match="unreachable"):
        r._resolve_identity("c1ccncc1", "")
    online.assert_not_called()


def test_without_mirror_unchanged(monkeypatch):
    r, online, probe = _resolver(None, monkeypatch, pug_up=False)
    assert r._resolve_identity("CCO", "") == ["online"]
    probe.assert_not_called()


def test_breaker_exempts_mirror_identity_only(mirror):
    r = PubChemResolver.__new__(PubChemResolver)
    r._local_db = mirror
    assert rm._breaker_blocked(r, False) is False
    assert rm._breaker_blocked(r, False, as_similarity=True) is True
    r._local_db = None
    assert rm._breaker_blocked(r, False) is True


def test_breaker_ignores_mock_truthiness():
    r = MagicMock()
    r.name = "pubchem_struct"
    del r.offline_capable
    assert rm._breaker_blocked(r, False) is True


def _hit(identifier, ident_type, resolver):
    return RawHit(identifier=identifier, ident_type=ident_type, resolver_name=resolver,
                  resolver_score=100.0, signature="sig", signature_type="inchikey",
                  hit_type="identity")


def test_inchikey_hits_join_their_cid():
    hits = [_hit("5497103", "PUBCHEM_CID", "inchikey_pubchem"),
            _hit("WTJKGGKOPKCXLL-VYOBOKEXSA-N", "INCHIKEY", "inchikey_self"),
            _hit("WTJKGGKOPKCXLL-VYOBOKEXSA-N", "INCHIKEY", "name_maps")]
    lookup = MagicMock(return_value=[5497103])
    merged = merge_inchikey_hits(hits, lookup)
    assert {(h.identifier, h.ident_type) for h in merged} == {("5497103", "PUBCHEM_CID")}
    assert lookup.call_count == 1
    groups = deduplicate_and_score(merged)
    assert list(groups) == [("5497103", "PUBCHEM_CID")]
    assert set(groups[("5497103", "PUBCHEM_CID")]["source_resolvers"]) == {
        "inchikey_pubchem", "inchikey_self", "name_maps"}


def test_merge_prefers_a_cid_already_found():
    hits = [_hit("9999", "PUBCHEM_CID", "pubchem_struct"),
            _hit(ETHANOL_IK, "INCHIKEY", "inchikey_self")]
    merged = merge_inchikey_hits(hits, lambda k: [702, 9999])
    assert merged[1].identifier == "9999"


def test_no_cid_found_keeps_the_inchikey_hit():
    # benzamidine (trypsin case): named by the CCD only; as CID 2332 it would
    # be scored against a misread structure
    hits = [_hit("17943838", "PUBCHEM_CID", "pubchem_struct"),
            _hit("PXXJHWLDUBFPOL-UHFFFAOYSA-N", "INCHIKEY", "name_ccd")]
    assert merge_inchikey_hits(hits, lambda k: [2332]) == hits


def test_merge_keeps_unknown_keys_and_lookup_failures():
    hits = [_hit("AAAAAAAAAAAAAA-BBBBBBBBBB-N", "INCHIKEY", "inchikey_self"),
            _hit("CHEMBL25", "CHEMBL_ID", "idsm_chembl")]
    assert merge_inchikey_hits(hits, lambda k: []) == hits

    def boom(_key):
        raise RuntimeError("mirror gone")
    assert merge_inchikey_hits(hits, boom) == hits
