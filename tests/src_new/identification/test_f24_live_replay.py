"""F-24 replay: additive-invariance proven on LIVE-frozen RCSB data.

Fixture tests/src_new/identification/fixtures/f24/rcsb_live_2026-10-05.json
was captured from the production worker pod (v3.129) against
search.rcsb.org with the exact deployed payload shape (rows=10000):
  * 1ubq_base_protein : 464/464 rows ("Protein (only)" base channel)
  * 1ubq_addon_mixed  : 2 rows ("Protein/NA" neighbors of 1UBQ: 7P0V, 8ID2)
  * 1hlv_addon_mixed  : 2 rows (1HLV self + 1U78)
  * 1s72...           : upstream_failed=True (persistent HTTP 400 datapoint;
                        validates the addon-failure -> base-kept fallback)

Replays the resolver merge over the frozen responses; no network.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.pdb_struct import PDBStructResolverProtein

FIXTURE = Path(__file__).parent / "fixtures" / "f24" / "rcsb_live_2026-10-05.json"


@pytest.fixture(scope="module")
def gold() -> dict:
    return json.loads(FIXTURE.read_text())


def _config(flag: bool) -> RunConfig:
    cfg = RunConfig()
    cfg.pdb.use_deployment_file_access = True
    cfg.pdb.deployment_file_url = "https://example.test"
    cfg.pdb.curr_uuid = "uuid-gold"
    cfg.pdb.rcsb_include_mixed_complexes = flag
    return cfg


def _wire(resolver, gold: dict, addon_key: str | None = "1ubq_addon_mixed", calls: list | None = None):
    def fake(remote_path, entity_types):
        if calls is not None:
            calls.append(list(entity_types))
        if entity_types == ["Protein/NA"]:
            assert addon_key is not None
            return gold[addon_key]
        return gold["1ubq_base_protein"]
    resolver._fetch_pdb_similarity = fake


def _parse(resolver, payload: dict) -> list[tuple[str, float]]:
    return resolver._parse_pdb_response(payload)


def test_fixture_integrity(gold: dict) -> None:
    assert gold["1ubq_base_protein"]["rows"] == 464
    assert gold["1ubq_addon_mixed"]["rows"] == 2
    assert gold["1hlv_addon_mixed"]["rows"] == 2
    assert gold["1s72_addon_mixed_upstream400"]["upstream_failed"] is True


def test_replay_flag_off_byte_identical_base(gold: dict) -> None:
    r = PDBStructResolverProtein(_config(False))
    calls: list = []
    _wire(r, gold, calls=calls)
    out = r._pdb_fetch_similar_structures("/tmp/gold.pdb", deployment_file_access=True)
    expected = _parse(r, gold["1ubq_base_protein"])
    assert out == expected and len(out) == 464
    assert calls == [["Protein (only)"]]  # addon never queried


def test_replay_flag_on_additive_invariant(gold: dict) -> None:
    r = PDBStructResolverProtein(_config(True))
    _wire(r, gold)
    out = r._pdb_fetch_similar_structures("/tmp/gold.pdb", deployment_file_access=True)
    base = _parse(r, gold["1ubq_base_protein"])
    addon = _parse(r, gold["1ubq_addon_mixed"])
    # additive-invariant: base preserved as exact prefix, nothing dropped
    assert out[: len(base)] == base
    assert len(out) == len(base) + len([h for h in addon if h[0] not in {b[0] for b in base}])
    tail = {i for i, _ in out[len(base):]}
    assert tail == {"7P0V", "8ID2"}  # live mixed-complex neighbors appended


def test_replay_identity_phase_unchanged_by_addon(gold: dict) -> None:
    """Real-data proof the addon cannot pollute identity results: the live
    1UBQ addon hits (7P0V/8ID2 ~0.79/0.74) sit below the 99.9 identity bar,
    so identity output is the same with the flag on or off."""
    for flag in (False, True):
        r = PDBStructResolverProtein(_config(flag))
        _wire(r, gold)
        ids = r._pdb_fetch_identical_structures("/tmp/gold.pdb", deployment_file_access=True)
        assert ids == ["1UBQ"]  # only the 1.0 self-hit passes >= 99.9 in both modes


def test_replay_arbitrary_addon_shapes_merge_safely(gold: dict) -> None:
    """1HLV recorded payload replayed as the addon: dedupe + append ordering."""
    r = PDBStructResolverProtein(_config(True))
    _wire(r, gold, addon_key="1hlv_addon_mixed")
    out = r._pdb_fetch_similar_structures("/tmp/gold.pdb", deployment_file_access=True)
    base = _parse(r, gold["1ubq_base_protein"])
    assert out[: len(base)] == base
    assert {i for i, _ in out[len(base):]} == {"1HLV", "1U78"}
    assert len(out) == 466
