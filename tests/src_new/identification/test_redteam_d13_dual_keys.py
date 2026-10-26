"""Red-team D-13 (subtask 2) — dual persistence keys for identity/similarity.

The manager historically wrote BOTH phases to identifiers/…/{resolver}, so
one listing always clobbered the other (with overwrite_existing=yes — the
ga1 campaign config — every protein identity listing was lost to the
similarity phase). D-13 (2a/2c): the similarity phase writes to its own
"{resolver}@sim" key with its own skip check; the identity key is
untouched so existing readers keep working.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.base import IdentifierResolver
from src_new.identification.registry import IdentifierRegistry
from src_new.identification.resolution_manager import IdentifierResolutionManager
from src_new.results.results_manager import ResultsManager
from src_new.verification.dedup import collect_hits, deduplicate_and_score, resolver_belief


class DualMockResolver(IdentifierResolver):
    """Stub dual-mode resolver: one identity hit + one similarity hit."""

    name = "mock_blast"
    identifier_type = "MOCK_ID"
    accepted_signatures = ["smiles"]

    def __init__(self, config: RunConfig) -> None:
        super().__init__(config)
        self.identity_calls = 0
        self.similarity_calls = 0

    def _is_applicable(self, signature: str) -> bool:
        return bool(signature)

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        self.identity_calls += 1
        return ["MOCK_EXACT"]

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        self.similarity_calls += 1
        return [("MOCK_EXACT", 98.5), ("MOCKHOMOLOG", 60.0)]


def _setup(tmp_path: Path, overwrite: bool):
    config = RunConfig()
    config.identifiers_cache.directory = str(tmp_path / "cache")
    config.identifiers_cache.file = "test_cache.sqlite3"
    config.identifiers.overwrite_existing = overwrite

    resolver = DualMockResolver(config)
    manager = IdentifierResolutionManager(
        IdentifierRegistry([resolver]), config,
        signature_type_map={"smiles": "smiles"},
    )

    results = ResultsManager(tmp_path / "results.json")
    results.start_run(
        step_definitions=[{"step_id": "signatures", "name": "Signatures"}],
        input_kind="pdb",
        input_files={"structure": str(tmp_path / "input.pdb")},
    )
    results.set_data("signatures/frag1/generated/smiles", "CCO")
    return resolver, manager, results


class TestDualPersistenceKeys:
    @pytest.mark.parametrize("overwrite", [True, False],
                             ids=["overwrite_yes_ga1", "overwrite_no"])
    def test_identity_and_similarity_both_persist(self, tmp_path: Path, overwrite: bool):
        """Both listings survive regardless of overwrite_existing — the
        identity key must never be clobbered by the similarity phase."""
        resolver, manager, results = _setup(tmp_path, overwrite)
        manager.resolve_all(results)

        ident = results.get_data("identifiers/frag1/smiles/mock_blast")
        sim = results.get_data("identifiers/frag1/smiles/mock_blast@sim")

        assert ident is not None and ident["hit_type"] == "identity"
        assert ident["hits"] == ["MOCK_EXACT"]
        assert sim is not None and sim["hit_type"] == "similarity"
        assert ("MOCK_EXACT", 98.5) in [tuple(h) for h in sim["hits"]]

    def test_attempted_distinguishes_tiers(self, tmp_path: Path):
        resolver, manager, results = _setup(tmp_path, True)
        manager.resolve_all(results)
        attempted = results.get_data("identifiers/frag1/smiles/attempted")
        assert "mock_blast" in attempted
        assert "mock_blast@sim" in attempted

    def test_belief_end_to_end_through_collect_hits(self, tmp_path: Path):
        """Subtask 1+2 integration: dual-persisted listings for one
        accession yield belief 50.00 (strongest tier), not 60.3."""
        resolver, manager, results = _setup(tmp_path, True)
        manager.resolve_all(results)

        hits = collect_hits(results, "frag1")
        out = deduplicate_and_score(hits)
        meta = out[("MOCK_EXACT", "MOCK_ID")]
        assert meta["hit_type"] == "identity"
        assert meta["n_identity_sources"] == 1
        assert meta["n_similarity_sources"] == 0
        assert meta["belief"] == pytest.approx(50.0)
