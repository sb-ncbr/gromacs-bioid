"""Corpus c13 item 2 (F2): mmCIF structure route is flag-gated (F-21 fields
mmcif_struct / mmcif_struct_similarity), and the D2 switch controls how
structure-search evidence may shape scores.

Reviewer evidence driving this: the mmCIF route returned 12,918 PDB rows
across 240/397 c13-sample entries vs 0 in d14 — because .b13pre disabled
pdb_struct_* but nobody knew mmcif_struct* gates the shared route. And a
structure match acted as a full corroborating source on an arbitrary one
among identical-sequence PDB entries while 2,241 structure-only rows
crowded the verification window.
"""

from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.mmcif import MmCifResolver
from src_new.identification.registry import IdentifierRegistry
from src_new.verification.dedup import RawHit, deduplicate_and_score


def _cfg(**kw) -> RunConfig:
    cfg = RunConfig()
    for k, v in kw.items():
        setattr(cfg.identifiers, k, v)
    return cfg


# --- F2a: the mmCIF route has a config flag ---------------------------------

def test_mmcif_flag_defaults_on():
    cfg = _cfg()
    assert cfg.identifiers.mmcif_struct is True
    assert cfg.identifiers.mmcif_struct_similarity is True
    r = MmCifResolver(cfg)
    assert r.enabled_identity is True
    assert r.enabled_similarity is True


def test_mmcif_flag_off_removes_resolver_from_registry():
    cfg = _cfg(mmcif_struct=False, mmcif_struct_similarity=False)
    r = MmCifResolver(cfg)
    registry = IdentifierRegistry([r])
    assert registry.get_applicable_resolvers("mmcif", as_similarity=True) == []
    assert registry.get_applicable_resolvers("mmcif", as_similarity=False) == []


def test_mmcif_similarity_flag_off_keeps_identity():
    cfg = _cfg(mmcif_struct=True, mmcif_struct_similarity=False)
    r = MmCifResolver(cfg)
    registry = IdentifierRegistry([r])
    assert registry.get_applicable_resolvers("mmcif", as_similarity=True) == []
    assert registry.get_applicable_resolvers("mmcif", as_similarity=False) != []


def test_struct_mode_defaults_full():
    assert _cfg().identifiers.mmcif_struct_mode == "full"


# --- D2: tiebreak scoring ---------------------------------------------------

def _hit(ident, resolver, score=90.0, hit_type="similarity"):
    return RawHit(identifier=ident, ident_type="PDB_ID",
                  resolver_name=resolver, resolver_score=score,
                  signature="SEQSEQSEQ", signature_type="fasta",
                  hit_type=hit_type)


def _score(meta):
    return meta["consensus_score"]


def test_full_mode_structure_source_raises_consensus():
    hits = [
        _hit("1AAA", "blast_swissprot_protein", 60.0, "identity"),
        _hit("1AAA", "mmcif_struct", 60.0, "identity"),
    ]
    res = deduplicate_and_score(hits, structure_mode="full")
    meta = res[("1AAA", "PDB_ID")]
    seq_only = deduplicate_and_score(hits[:1], structure_mode="full")
    assert _score(meta) > _score(seq_only[("1AAA", "PDB_ID")]), \
        "full mode: structure match counts as a corroborating source"
    assert meta["structure_corroborated"] is True


def test_tiebreak_mode_structure_source_never_raises_consensus():
    hits = [
        _hit("1AAA", "blast_swissprot_protein", 60.0, "identity"),
        _hit("1AAA", "mmcif_struct", 60.0, "identity"),
    ]
    res = deduplicate_and_score(hits, structure_mode="tiebreak")
    seq_only = deduplicate_and_score(hits[:1], structure_mode="tiebreak")
    assert _score(res[("1AAA", "PDB_ID")]) == _score(seq_only[("1AAA", "PDB_ID")])
    # attribution preserved even though scoring excluded the source
    assert "mmcif_struct" in res[("1AAA", "PDB_ID")]["source_resolvers"]


def test_tiebreak_structure_only_group_scores_zero():
    hits = [_hit("1BBB", "mmcif_struct", 95.0, "similarity")]
    res = deduplicate_and_score(hits, structure_mode="tiebreak")
    meta = res[("1BBB", "PDB_ID")]
    assert _score(meta) == 0.0
    assert meta["source_resolvers"] == ["mmcif_struct"]


def test_tiebreak_does_not_touch_pure_sequence_groups():
    hits = [
        _hit("1CCC", "blast_swissprot_protein", 60.0, "identity"),
        _hit("1CCC", "blast_pdb_protein", 60.0, "identity"),
    ]
    a = deduplicate_and_score(hits, structure_mode="tiebreak")[("1CCC", "PDB_ID")]
    b = deduplicate_and_score(hits, structure_mode="full")[("1CCC", "PDB_ID")]
    assert _score(a) == _score(b)
    assert a["structure_corroborated"] is False
