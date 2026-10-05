"""OQ-9 (2026-10-05): virtual-minority-segment generator routing.

Root cause: generators resolve segment properties via
``facade.get_segment_properties(fragment.segids[0])``. Virtual minority
segments (``SYSTEM__vN``) live under the PARENT segid ("SYSTEM"), so the
serial driver loop fed them the parent's classification (protein) and
protein-family generators produced nonsense (RNA letters as protein fasta).
The parallel worker mock-facade already pinned per-segment props; the fix
routes the same props through ``_PinnedPropsFacade`` in the serial path.

Guarantees pinned here:
  1. pinned facade answers virtual props when generators ask for the parent
     segid (the exact reported bug shape);
  2. flat (non-virtual) segments get byte-identical props (same object) ->
     zero behavior change on the flat cohort;
  3. passthrough of non-lookup attributes to the real facade;
  4. unknown/missing-props segments fall back to the unwrapped facade;
  5. parent-protein gating still works (no global suppression).
"""
from __future__ import annotations

import types

from src_new.config.loader import SignaturesConfig
from src_new.loader.universe_facade import SegmentProperties, SegmentProperty
from src_new.pipeline_steps import _PinnedPropsFacade, _pinned_props_facade
from src_new.signatures.generators.fasta import (
    MapFastaGeneratorProtein,
    MapFastaGeneratorNucleotide,
)


def _props(is_protein: bool, is_nucleic: bool) -> SegmentProperties:
    return SegmentProperties(
        atom_count_total=10,
        atom_count_fragment=10,
        residue_count=2,
        bond_count_total=1,
        bond_count_fragment=1,
        molecule_count=1,
        flags={
            SegmentProperty.IS_PROTEIN.value: is_protein,
            SegmentProperty.IS_NUCLEIC.value: is_nucleic,
            SegmentProperty.HAS_MULTI_ATOM_RESIDUES.value: True,
        },
    )


def _fragment():
    return types.SimpleNamespace(
        segids=["SYSTEM"],  # parent segid even for virtual fragments
        bonds=types.SimpleNamespace(indices=[(0, 1)]),
    )


def _facade_with_props(by_name: dict) -> types.SimpleNamespace:
    def get_segment_properties(name):
        return by_name[name]  # KeyError propagates like real facade
    return types.SimpleNamespace(
        get_segment_properties=get_segment_properties,
        sentinel="real-facade-attr",
    )


def test_pinned_facade_routes_virtual_props_by_segid_lookup() -> None:
    protein_props = _props(is_protein=True, is_nucleic=False)
    nucleic_props = _props(is_protein=False, is_nucleic=True)
    real = _facade_with_props({"SYSTEM": protein_props, "SYSTEM__v1": nucleic_props})

    wrapped = _pinned_props_facade(real, "SYSTEM__v1")
    cfg = SignaturesConfig()
    prot = MapFastaGeneratorProtein(cfg)
    nuc = MapFastaGeneratorNucleotide(cfg)
    inst = types.SimpleNamespace()

    # the bug scenario: generators ask for props by parent segid "SYSTEM"
    assert not prot.is_applicable(inst, _fragment(), wrapped)
    assert nuc.is_applicable(inst, _fragment(), wrapped)


def test_pinned_facade_flat_segment_props_are_identical_object() -> None:
    flat_props = _props(is_protein=True, is_nucleic=False)
    real = _facade_with_props({"CHAIN_A": flat_props})

    wrapped = _pinned_props_facade(real, "CHAIN_A")
    assert wrapped.get_segment_properties("CHAIN_A") is flat_props  # byte-invariant


def test_pinned_facade_protein_parent_still_protein_gated() -> None:
    protein_props = _props(is_protein=True, is_nucleic=False)
    nucleic_props = _props(is_protein=False, is_nucleic=True)
    real = _facade_with_props({"SYSTEM": protein_props, "SYSTEM__v1": nucleic_props})

    wrapped = _pinned_props_facade(real, "SYSTEM")
    cfg = SignaturesConfig()
    assert MapFastaGeneratorProtein(cfg).is_applicable(
        types.SimpleNamespace(), _fragment(), wrapped)
    assert not MapFastaGeneratorNucleotide(cfg).is_applicable(
        types.SimpleNamespace(), _fragment(), wrapped)


def test_pinned_facade_passthrough_and_fallback() -> None:
    real = _facade_with_props({"SYSTEM": _props(True, False)})

    wrapped = _pinned_props_facade(real, "SYSTEM")
    assert wrapped.sentinel == "real-facade-attr"  # __getattr__ passthrough

    # props missing for a segment -> unwrapped facade returned (legacy flow)
    assert _pinned_props_facade(real, "GHOST") is real


def test_pinned_props_facade_direct_construction() -> None:
    real = _facade_with_props({"X": _props(True, False)})
    props = _props(False, True)
    pinned = _PinnedPropsFacade(real, props)
    assert pinned.get_segment_properties("anything") is props
    assert pinned.sentinel == "real-facade-attr"
