import sys
import types

import pytest

if "MDAnalysis" not in sys.modules:
    mdanalysis = types.ModuleType("MDAnalysis")
    mdanalysis.Universe = type("Universe", (), {})
    mdanalysis.AtomGroup = type("AtomGroup", (), {})
    sys.modules["MDAnalysis"] = mdanalysis

if "periodictable" not in sys.modules:
    periodictable = types.ModuleType("periodictable")
    periodictable.elements = []
    sys.modules["periodictable"] = periodictable

if "rdkit" not in sys.modules:
    rdkit = types.ModuleType("rdkit")
    chem = types.ModuleType("rdkit.Chem")
    determine_bonds = types.ModuleType("rdkit.Chem.rdDetermineBonds")
    chem.rdDetermineBonds = determine_bonds
    rdkit.Chem = chem
    sys.modules["rdkit"] = rdkit
    sys.modules["rdkit.Chem"] = chem
    sys.modules["rdkit.Chem.rdDetermineBonds"] = determine_bonds

from ...src.identifiers.identifier_resolvers import identifier_resolver as resolver_module
from ...src.identifiers.identifier_resolvers import pdb_struct as pdb_struct_module
from ...src.identifiers.identifier_resolvers.blast import (
    BlastHit,
    _filter_blast_results,
    _process_blast_results,
)
from ...src.identifiers.identifier_resolvers.identifier_resolver import (
    IdentifierResolutionError,
    IdentifierResolver,
)
from ...src.identifiers.identifier_resolvers.pdb_struct import (
    _fetch_pdb_similarity,
    _parse_pdb_response,
    _replace_placeholders,
)


class FakeCache:
    def fetch_identity_identifiers(self, resolver_name, signature):
        return []

    def fetch_similarity_identifiers(self, resolver_name, signature):
        return []

    def save_identity_identifiers(self, resolver_name, signature, identifiers):
        self.saved_identity = (resolver_name, signature, identifiers)

    def save_similarity_identifiers(self, resolver_name, signature, identifiers):
        self.saved_similarity = (resolver_name, signature, identifiers)


class FailingResolver(IdentifierResolver):
    def __init__(self):
        super().__init__("test_resolver", "TEST_ID", ["smiles"])
        self.allowed_identity = True
        self.allowed_similarity = True

    def _is_applicable(self, signature):
        return True

    def _resolve_identity(self, signature, working_directory):
        raise IdentifierResolutionError("mock identity failure")

    def _resolve_similarity(self, signature, working_directory):
        raise RuntimeError("mock similarity failure")


def test_identifier_resolver_converts_resolution_errors_to_none(monkeypatch):
    monkeypatch.setattr(resolver_module, "ResolverCache", FakeCache)
    resolver = FailingResolver()

    assert resolver.resolve_signature("CCO", as_similarity=False, working_directory=".") is None
    assert resolver.resolve_signature("CCO", as_similarity=True, working_directory=".") is None


def test_process_blast_results_normalizes_hits():
    payload = {
        "BlastOutput2": {
            "report": {
                "results": {
                    "search": {
                        "query_len": 10,
                        "hits": [
                            {
                                "description": [{"accession": "1ABC_A"}],
                                "hsps": [
                                    {
                                        "bit_score": 50.0,
                                        "evalue": 1e-12,
                                        "align_len": 8,
                                        "identity": 6,
                                    }
                                ],
                            }
                        ],
                    }
                }
            }
        }
    }

    hits = _process_blast_results([payload])

    assert hits == [BlastHit(["1ABC_A"], 1e-12, 50.0, 0.75, 0.8)]


def test_process_blast_results_treats_malformed_payload_as_empty():
    assert _process_blast_results([{"unexpected": "shape"}]) == []


def test_filter_blast_results_is_deterministic():
    hits = [
        BlastHit(["low"], 1e-3, 10.0, 0.2, 0.5),
        BlastHit(["high"], 1e-20, 100.0, 1.0, 1.0),
    ]

    filtered = _filter_blast_results(hits, lambda hit: hit.identity_p >= 0.9)

    assert filtered == [hits[1]]


def test_parse_pdb_response_normalizes_scores_to_percent():
    response = {
        "result_set": [
            {"identifier": "1ABC", "score": 0.95},
            {"identifier": "2XYZ", "score": 1.0},
        ]
    }

    assert _parse_pdb_response(response) == [("1ABC", 95.0), ("2XYZ", 100.0)]


def test_parse_pdb_response_treats_missing_result_set_as_empty():
    assert _parse_pdb_response({"status": 204}) == []


def test_replace_placeholders_requires_all_placeholders_to_be_used():
    command = ["scp", "{FILEPATH}", "host:{FILENAME}"]

    _replace_placeholders(command, {"{FILEPATH}": "/tmp/a.pdb", "{FILENAME}": "a.pdb"})

    assert command == ["scp", "/tmp/a.pdb", "host:a.pdb"]

    with pytest.raises(KeyError):
        _replace_placeholders(["echo", "nothing"], {"{FILEPATH}": "/tmp/a.pdb"})


def test_fetch_pdb_similarity_uses_post_without_live_network(monkeypatch):
    class FakeResponse:
        text = '{"result_set": []}'

        def close(self):
            self.closed = True

    calls = []

    def fake_post(url, json):
        calls.append((url, json))
        return FakeResponse()

    monkeypatch.setattr(pdb_struct_module.requests, "post", fake_post)

    response = _fetch_pdb_similarity(
        pdb_name="input.pdb",
        deployment_file_access=False,
        as_protein=True,
        as_nucleic=False,
    )

    assert response == {"result_set": []}
    assert calls[0][0] == "https://search.rcsb.org/rcsbsearch/v2/query"
    assert calls[0][1]["return_type"] == "entry"
