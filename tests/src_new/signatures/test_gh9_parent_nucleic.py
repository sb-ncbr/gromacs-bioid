"""GitHub #9: fasta_parent_nucleic — an ADDITIONAL nucleic sequence with
modified nucleotides as their parent base; the existing fasta_map_nucleic /
fasta_resname_nucleic signatures keep 'X' unchanged."""
from __future__ import annotations

import pytest

pytest.importorskip("MDAnalysis")

from src_new.config.loader import SignaturesConfig
from src_new.signatures.canonical import CANONICAL_SIGNATURE_TYPES
from src_new.signatures.generators.fasta import (
    MapFastaGeneratorNucleotide, ParentBaseFastaGeneratorNucleotide,
    ResnameFastaGeneratorNucleotide)
from src_new.signatures.registry import get_default_generators
from tests.src_new.signatures.test_fasta_nucleic_enhancements import (
    _chain_bonds, _mk_facade, _mk_universe)

ATOMS = [["P", "O5'", "C5'", "C4'", "C3'", "O3'"]]
BONDS = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]


def _run(resnames, bonded=True):
    n = len(resnames)
    bonds = _chain_bonds(n, 6, BONDS, (0, 5)) if bonded else None
    facade, fragment, inst = _mk_facade(_mk_universe(resnames, ATOMS * n, bonds=bonds))
    cfg = SignaturesConfig()
    plain_gen = (MapFastaGeneratorNucleotide(cfg) if bonded
                 else ResnameFastaGeneratorNucleotide(cfg))
    plain = (plain_gen._generate(inst, fragment, facade)
             if plain_gen._is_applicable(inst, fragment, facade) else None)
    gen = ParentBaseFastaGeneratorNucleotide(cfg)
    applicable = gen._is_applicable(inst, fragment, facade)
    parent = gen._generate(inst, fragment, facade) if applicable else None
    return plain, applicable, parent


@pytest.mark.parametrize("bonded", [True, False])
def test_ccd_modified_bases_get_parent_letters(bonded):
    plain, applicable, parent = _run(["G", "PSU", "C", "OMG", "5MC", "A"], bonded)
    assert plain == "GXCXXA"          # existing signature untouched
    assert applicable and parent == "GUCGCA"


def test_unmodified_rna_gets_no_extra_signature():
    _plain, applicable, _parent = _run(["G", "U", "C", "A"])
    assert not applicable


def test_amber_mra_bonded_into_chain_becomes_a():
    plain, applicable, parent = _run(["U", "C", "C", "C", "MRA", "G"])
    assert plain == "UCCCXG" and applicable and parent == "UCCCAG"


def test_amber_rap_without_bonds_is_not_mapped():
    # bondless: no proof RAP is a nucleotide (CCD RAP = rapamycin)
    _plain, applicable, _parent = _run(["U", "RAP", "G"], bonded=False)
    assert not applicable


def test_wiring():
    assert CANONICAL_SIGNATURE_TYPES["fasta_parent_nucleic"] == "residue_sequence_nucleotide"
    names = [g.name for g in get_default_generators(SignaturesConfig())]
    assert "fasta_parent_nucleic" in names
