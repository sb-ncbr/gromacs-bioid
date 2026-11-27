"""GitHub #39: a failed structure search is an error (get_last_error), not
'zero structural matches'."""
from src_new.config.loader import RunConfig
from src_new.identification.base import IdentifierResolutionError
from src_new.identification.resolvers import pdb_struct
from src_new.identification.resolvers.foldseek import Foldseek3DiResolver

PDB = ("ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\n"
       "ATOM      2  CA  GLY A   2       3.800   0.000   0.000  1.00  0.00           C\nEND\n")


def test_pdb_struct_persistent_error_is_reported(monkeypatch, tmp_path):
    r = pdb_struct.PDBStructResolverProtein(RunConfig())
    monkeypatch.setattr(pdb_struct, "split_oversized_query", lambda s: [s])

    def boom(*a, **k):
        raise IdentifierResolutionError("structure_search_unavailable: HTTP 503")
    monkeypatch.setattr(r, "_pdb_fetch_similar_structures", boom)
    assert r.resolve(PDB, as_similarity=True, working_directory=str(tmp_path)) == []
    assert "HTTP 503" in (r.get_last_error() or "")


def test_foldseek_remote_failure_is_reported(monkeypatch):
    r = Foldseek3DiResolver(RunConfig())
    r.foldseek_config.mode = "remote"
    monkeypatch.setattr(r, "_remote_search", lambda s: None)
    monkeypatch.setattr(r, "_is_applicable", lambda s: True)
    assert r.resolve("x", as_similarity=True) == []
    assert r.get_last_error() == "foldseek_remote_failed"


def test_foldseek_genuine_empty_is_not_an_error(monkeypatch):
    r = Foldseek3DiResolver(RunConfig())
    r.foldseek_config.mode = "remote"
    monkeypatch.setattr(r, "_remote_search", lambda s: [])
    monkeypatch.setattr(r, "_is_applicable", lambda s: True)
    assert r.resolve("x", as_similarity=True) == []
    assert r.get_last_error() is None
