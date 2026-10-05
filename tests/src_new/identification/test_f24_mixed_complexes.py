"""F-24 (2026-10-05): additive RCSB mixed-complex (Protein/NA) channel.

The base structure-similarity query filters
``rcsb_entry_info.selected_polymer_entity_types`` to either
``Protein (only)`` or ``Nucleic acid (only)``, so protein+NA complexes
(enum ``Protein/NA``) are invisible. With the flag ON, an EXTRA query for
``Protein/NA`` runs after the base query and unique hits are APPENDED —
base hits are never modified (additive-invariant). Flag default OFF =>
byte-identical legacy output. MmCif twin is n/a: its query carries no
entity filter, so mixed complexes were never excluded there.

Test doubles patch ``_fetch_pdb_similarity`` so no network is touched.
"""
from __future__ import annotations

import types

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.base import IdentifierResolutionError
from src_new.identification.resolvers.pdb_struct import (
    PDBStructResolverNucleotide,
    PDBStructResolverProtein,
)


def _config(flag: bool) -> RunConfig:
    cfg = RunConfig()
    cfg.pdb.use_deployment_file_access = True
    cfg.pdb.deployment_file_url = "https://example.test"
    cfg.pdb.curr_uuid = "uuid-1"
    cfg.pdb.rcsb_include_mixed_complexes = flag
    return cfg


def _res(payload):
    return {"result_set": [{"identifier": i, "score": s} for i, s in payload]}


BASE = [("1UBQ", 1.0), ("1AAA", 0.97), ("1BBB", 0.90)]
ADDON = [("1HLV", 0.999), ("1AAA", 0.55), ("1S72", 0.8)]  # 1AAA dupes a base hit


def _patch_fetch(resolver, calls: list):
    def fake(remote_path, entity_types):
        calls.append(list(entity_types))
        if entity_types == ["Protein/NA"]:
            return _res(ADDON)
        return _res(BASE)
    resolver._fetch_pdb_similarity = fake


def test_flag_off_does_not_query_mixed() -> None:
    r = PDBStructResolverProtein(_config(False))
    calls: list = []
    _patch_fetch(r, calls)
    out = r._pdb_fetch_similar_structures("/tmp/x.pdb", deployment_file_access=True)
    assert out == [("1UBQ", 100.0), ("1AAA", 97.0), ("1BBB", 90.0)]
    assert calls == [["Protein (only)"]]  # no addon call


def test_flag_on_appends_unique_mixed_hits() -> None:
    r = PDBStructResolverProtein(_config(True))
    calls: list = []
    _patch_fetch(r, calls)
    out = r._pdb_fetch_similar_structures("/tmp/x.pdb", deployment_file_access=True)
    assert out == [
        ("1UBQ", 100.0), ("1AAA", 97.0), ("1BBB", 90.0),  # base untouched, order kept
        ("1HLV", 99.9), ("1S72", 80.0),                  # mixed appended (1AAA deduped)
    ]
    assert calls == [["Protein (only)"], ["Protein/NA"]]


def test_flag_on_nucleotide_mode_also_appends() -> None:
    r = PDBStructResolverNucleotide(_config(True))
    calls: list = []
    _patch_fetch(r, calls)
    out = r._pdb_fetch_similar_structures("/tmp/x.pdb", deployment_file_access=True)
    assert out[:3] == [("1UBQ", 100.0), ("1AAA", 97.0), ("1BBB", 90.0)]
    assert ("1HLV", 99.9) in out and ("1S72", 80.0) in out
    assert calls == [["Nucleic acid (only)"], ["Protein/NA"]]


def test_flag_on_addon_failure_keeps_base_intact() -> None:
    r = PDBStructResolverProtein(_config(True))

    def fake(remote_path, entity_types):
        if entity_types == ["Protein/NA"]:
            raise IdentifierResolutionError("upstream exploded")
        return _res(BASE)

    r._fetch_pdb_similarity = fake
    out = r._pdb_fetch_similar_structures("/tmp/x.pdb", deployment_file_access=True)
    assert out == [("1UBQ", 100.0), ("1AAA", 97.0), ("1BBB", 90.0)]


def test_identity_path_inherits_addon() -> None:
    """Identical-structures phase reuses the merged similarity list and keeps
    its >=99.9 filter over base+addon."""
    r = PDBStructResolverProtein(_config(True))
    _patch_fetch(r, [])
    out = r._pdb_fetch_identical_structures("/tmp/x.pdb", deployment_file_access=True)
    assert "1UBQ" in out and "1HLV" in out  # 100.0 and 99.9 -> both pass >=99.9
    assert "1S72" not in out and "1BBB" not in out


def test_config_default_is_off() -> None:
    assert RunConfig().pdb.rcsb_include_mixed_complexes is False
