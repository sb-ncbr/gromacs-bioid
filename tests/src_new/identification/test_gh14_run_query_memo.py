"""GitHub #14/#18: smiles / smiles_not_sanitized / selfies of one molecule
send ONE query per SMILES resolver per run (same query string after the
selfies decoder's '[C@H1]'/'[O-1]' token normalization)."""
import pytest

pytest.importorskip("selfies")
import selfies

from src_new.config.loader import RunConfig
from src_new.identification.base import (
    IdentifierResolver, clear_run_query_memo, end_run_query_memo)

POPC = "CCCCCCCCCCCCCCCC(=O)OC[C@H](COP(=O)([O-])OCC[N+](C)(C)C)OC(=O)CCCCCCC/C=C\\CCCCCCCC"


class _Smiles(IdentifierResolver):
    name = "fake_smiles"
    identifier_type = "PUBCHEM_CID"
    accepted_signatures = ["smiles", "selfies"]

    def __init__(self):
        super().__init__(RunConfig())
        self.queries = []

    def _is_applicable(self, signature):
        return True

    def _resolve_identity(self, signature, wd):
        from src_new.identification.resolvers._smiles_query import query_smiles
        self.queries.append(query_smiles(signature, self._signature_type))
        self._last_resolution_metadata = {"5497103": {"note": "x"}}
        return ["5497103"]

    def _resolve_similarity(self, signature, wd):
        self.queries.append(signature)
        return [("5497103", 95.0)]


@pytest.fixture(autouse=True)
def _fresh_memo():
    clear_run_query_memo()
    yield
    end_run_query_memo()


def test_smiles_and_selfies_of_one_molecule_query_once():
    r = _Smiles()
    a = r.resolve(POPC, signature_type="smiles")
    b = r.resolve(POPC, signature_type="smiles")              # smiles_not_sanitized twin
    c = r.resolve(selfies.encoder(POPC), signature_type="selfies")
    assert a == b == c == ["5497103"]
    assert len(r.queries) == 1
    assert r.get_last_resolution_metadata() == {"5497103": {"note": "x"}}


def test_different_query_strings_still_run():
    r = _Smiles()
    r.resolve("CC(=O)Oc1ccccc1C(=O)O", signature_type="smiles")
    r.resolve(selfies.encoder("CC(=O)Oc1ccccc1C(=O)O"), signature_type="selfies")  # kekulized
    assert len(r.queries) == 2


def test_identity_and_similarity_kept_apart_and_memo_cleared_per_run():
    r = _Smiles()
    r.resolve(POPC, signature_type="smiles")
    r.resolve(POPC, as_similarity=True, signature_type="smiles")
    assert len(r.queries) == 2
    clear_run_query_memo()
    r.resolve(POPC, signature_type="smiles")
    assert len(r.queries) == 3


def test_no_memo_outside_a_run():
    end_run_query_memo()
    r = _Smiles()
    r.resolve(POPC, signature_type="smiles")
    r.resolve(POPC, signature_type="smiles")
    assert len(r.queries) == 2
