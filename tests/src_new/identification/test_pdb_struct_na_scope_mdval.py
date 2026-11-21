"""2026-11-21 (mdval audit item 2): which RCSB structure search takes which input.

pdb_struct_nucleotide accepted topology_less_pdb, a signature of every
polymer segment, and declined it (na_mode_unsupported) for every protein,
which read as "nucleic acid not searched" in the audit. The protein mode
now takes topology_less_pdb alone and declines pure nucleic acids itself.
"""
from __future__ import annotations

from src_new.config.loader import RunConfig
from src_new.identification.registry import IdentifierRegistry, get_default_resolvers
from src_new.identification.resolvers.pdb_struct import (
    PDBStructResolverNucleotide,
    PDBStructResolverProtein,
    _na_only_pdb_payload,
)


def _atom(serial, name, resname, resid, chain="A"):
    return (f"ATOM  {serial:5d} {name:<4} {resname:>3} {chain}{resid:4d}    "
            f"{0.0:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00  0.00           C  ")


PROTEIN = "\n".join(_atom(i + 1, "CA", rn, i + 1) for i, rn in enumerate(["ALA", "GLY", "HIE", "CYX"]))
DNA = "\n".join(_atom(i + 1, "P", rn, i + 1) for i, rn in enumerate(["DA5", "DC", "DG", "DT3"]))
RNA = "\n".join(_atom(i + 1, "P", rn, i + 1) for i, rn in enumerate(["RA5", "U", "G", "C3"]))
COMPLEX = PROTEIN + "\n" + DNA


def test_payload_classification():
    assert _na_only_pdb_payload(DNA)
    assert _na_only_pdb_payload(RNA)
    assert not _na_only_pdb_payload(PROTEIN)
    assert not _na_only_pdb_payload(COMPLEX)  # the protein part is searchable
    assert not _na_only_pdb_payload("HEADER    export\n")


def test_topology_less_pdb_goes_to_the_protein_search_only():
    reg = IdentifierRegistry(get_default_resolvers(RunConfig()))
    names = {r.name for r in reg.get_applicable_resolvers("topology_less_pdb", as_similarity=True)}
    assert "pdb_struct_protein" in names
    assert "pdb_struct_nucleotide" not in names
    names = {r.name for r in reg.get_applicable_resolvers("pdb_nucleic", as_similarity=True)}
    assert "pdb_struct_nucleotide" in names


def test_nucleotide_mode_keeps_its_declared_skip():
    r = PDBStructResolverNucleotide(RunConfig())
    assert r.accepted_signatures == ["pdb_nucleic"]
    assert r._resolve_similarity(DNA, "/tmp") == []
    assert r.get_last_error() == "na_mode_unsupported"


def test_protein_mode_declines_a_pure_nucleic_acid(monkeypatch):
    r = PDBStructResolverProtein(RunConfig())
    calls = []
    monkeypatch.setattr(r, "_similarity_one", lambda q, wd: calls.append(q) or [("1ABC", 90.0)])
    assert r._resolve_similarity(DNA, "/tmp") == []
    assert r.get_last_error() == "na_mode_unsupported"
    assert calls == []
    r._last_error = None
    assert r._resolve_similarity(COMPLEX, "/tmp") == [("1ABC", 90.0)]
    assert r._resolve_similarity(PROTEIN, "/tmp") == [("1ABC", 90.0)]
    assert r.get_last_error() is None
