"""PDB hits are named after the matched polymer entity (UI pass 2026-11-07).

An antibody light chain was shown as "The mechanism of GM-CSF inhibition by
human GM-CSF auto-antibodies" (the best hit's entry title). The matched
entity's pdbx_description is used instead; anything unsure keeps the name.
"""

from types import SimpleNamespace

from src_new.verification.models import ref_seq_sha1
from src_new.verification.pdb_entity_names import entity_name, matched_entity, name_pdb_hits

LIGHT = {"entity_id": "1", "sequence": "DIVLTQSPAS", "description": "IgG2a kappa light chain",
         "auth_asym_ids": ["A", "C"], "asym_ids": ["A", "C"], "organism": "Mus musculus"}
HEAVY = {"entity_id": "2", "sequence": "EVKLVESGGG", "description": "IgG2a heavy chain",
         "auth_asym_ids": ["B", "D"], "asym_ids": ["B", "D"], "organism": "Mus musculus"}


def test_structure_path_maps_chain_to_entity():
    assert entity_name([LIGHT, HEAVY], {"tm_chain_ref": "D"}) == ("IgG2a heavy chain", "Mus musculus")


def test_sequence_path_maps_reference_hash_to_entity():
    details = {"ref_seq_sha1": ref_seq_sha1(LIGHT["sequence"])}
    assert matched_entity([LIGHT, HEAVY], details) is LIGHT


def test_unsure_or_missing_keeps_the_old_name():
    # most hits: no details, several entities -> no guess
    assert entity_name([LIGHT, HEAVY], None) == (None, None)
    assert entity_name([LIGHT, HEAVY], {"tm_chain_ref": "Z"}) == (None, None)
    assert entity_name([], {"tm_chain_ref": "A"}) == (None, None)
    no_desc = dict(LIGHT, description=None)
    assert entity_name([no_desc], None) == (None, None)


def test_single_entity_needs_no_details():
    assert entity_name([LIGHT], None)[0] == "IgG2a kappa light chain"


def test_renames_verified_pdb_hits_and_never_raises():
    hits = [SimpleNamespace(is_verified=True, ident_type="UNIPROT_ID", identifier="P01837",
                            name="Ig kappa chain C region", organism=None, similarity_details=None),
            SimpleNamespace(is_verified=True, ident_type="PDB_ID", identifier="1IGT",
                            name="STRUCTURE OF IMMUNOGLOBULIN", organism=None,
                            similarity_details={"tm_chain_ref": "A"}),
            SimpleNamespace(is_verified=True, ident_type="PDB_ID", identifier="6BFS",
                            name="The mechanism of GM-CSF inhibition", organism=None,
                            similarity_details={"tm_chain_ref": "A"})]

    def fetch(pdb_id):
        if pdb_id == "6BFS":
            raise RuntimeError("RCSB down")
        return [LIGHT, HEAVY]

    assert name_pdb_hits(hits, fetch) == 1
    assert hits[0].name == "Ig kappa chain C region"          # not a PDB hit
    assert hits[1].name == "IgG2a kappa light chain"
    assert hits[2].name == "The mechanism of GM-CSF inhibition"  # failure keeps it


def _pdb_hits(n):
    return [SimpleNamespace(is_verified=True, ident_type="PDB_ID", identifier=f"{i}ABC",
                            name=f"ENTRY TITLE {i}", organism=None, similarity_details=None)
            for i in range(n)]


def test_names_beyond_the_top_three():
    # 2026-11-09: only the top 3 were named; the matches table showed titles.
    hits = _pdb_hits(10)
    assert name_pdb_hits(hits, lambda pid: [LIGHT]) == 10
    assert {h.name for h in hits} == {"IgG2a kappa light chain"}


def test_stops_after_consecutive_failures():
    calls = []

    def down(pid):
        calls.append(pid)
        return []  # fetch failure -> empty

    hits = _pdb_hits(10)
    assert name_pdb_hits(hits, down, max_failures=3) == 0
    assert len(calls) == 3
    assert hits[5].name == "ENTRY TITLE 5"


def test_respects_the_wall_budget():
    t = [0.0]

    def slow(pid):
        t[0] += 10.0  # each lookup "takes" 10 s
        return [LIGHT]

    hits = _pdb_hits(10)
    assert name_pdb_hits(hits, slow, budget_s=25.0, clock=lambda: t[0]) == 3
    assert hits[3].name == "ENTRY TITLE 3"
