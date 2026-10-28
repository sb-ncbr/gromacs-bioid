"""W3 A7 (BH-046): identify_molecules groups identical segments and
resolves each group ONCE; budget cuts drop whole groups, never parts.

Production evidence (g0a2091-1028): P23's 7 identical GroES chains got
NO answer (budget ran out per-segment part-way) while identical GroEL
chains got three DIFFERENT assignments; F14 resolved 9 of 2952 segments
in 187 s resolving all 8 chloride copies separately. BH-048: the
resolver cache died in production ("[Cache] disabled ... unable to open
database file") because directory "" resolved into the unwritable
container cwd.

Fix contract pinned here:
1. Group key per segment from its signatures: polymer ->
   ("polymer", canonical fasta sequence); small molecule ->
   ("small", inchi_key), else ("small_formula", heavy formula +
   fingerprint); ion -> ("ion", atom signature); water -> skipped.
2. Only the group's representative is resolved; members copy the rep's
   identifiers payload with an ``_shared_with`` marker (resolver call
   count == group count).
3. Group ordering: polymers by length desc, then small molecules, then
   ions (waters ungrouped-skipped).
4. Budget checks apply per GROUP: a cut leaves whole groups unresolved
   and records them in identification/unresolved_groups.
5. An empty identifiers_cache.directory falls back to a writable
   run-local directory instead of dying in the container cwd.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("MDAnalysis")
pytest.importorskip("rdkit")


def _ctx(tmp_path: Path, signatures: dict, budget_past: bool = False):
    """Minimal executor-context double for identify_molecules."""
    from src_new.config.loader import RunConfig
    from src_new.results.results_manager import ResultsManager

    cfg = RunConfig()
    cfg.executor.identifiers_parallel = False  # exercise the serial loop
    results = ResultsManager(str(tmp_path / "results.json"),
                             pipeline_name="a7")
    results.set_data("signatures", signatures)
    ctx = MagicMock()
    ctx.config = cfg
    ctx.results = results
    ctx.working_directory = tmp_path
    ctx.get_value.side_effect = lambda k, *a, **kw: (
        object() if k == "facade" else
        (0.0 if budget_past else None)
        if k == "stage_deadline_epoch" else None)
    ctx.fail.side_effect = Exception("context.fail called")
    warnings_: list = []
    ctx.add_warning.side_effect = lambda code, msg, details=None: (
        warnings_.append((code, msg)))
    return ctx, results, warnings_


def _poly_sigs(seq: str) -> dict:
    return {"generated": {"fasta_map_protein": seq, "atom_count": "42"}}


def _small_sigs(inchi_key: str) -> dict:
    return {"generated": {"inchi_key": inchi_key,
                          "molecular_formula": "C2H4O2"}}


def _formula_only_sigs(formula: str) -> dict:
    return {"generated": {"molecular_formula_heavy": formula,
                          "fingerprint": "fp" + formula}}


def _ion_sigs(elem: str) -> dict:
    return {"generated": {"atom": elem}}


_MGR_PATCHES = [
    "src_new.identification.resolution_manager.IdentifierResolutionManager",
]


class _Mgr:
    """Resolution manager double: records resolved segments, writes one
    identity hit per resolution call."""

    instances: list = []

    def __init__(self, *a, **k):
        self.calls: list = []
        _Mgr.instances.append(self)

    def resolve(self, results, segment, signature_generator_name, signature,
                cache, working_directory, errors, deadline_epoch=None):
        self.calls.append(segment)
        results.set_data(
            f"identifiers/{segment}/{signature_generator_name}",
            {"identity": {"ident_type": "UNIPROT_ID", "hits": [
                {"ident_value": "P0A6F9", "confidence": 99.0}]}})


def _run_identify(ctx):
    _Mgr.instances.clear()
    with patch(
            "src_new.identification.resolution_manager"
            ".IdentifierResolutionManager", _Mgr):
        from src_new.pipeline_steps import _identify_molecules as identify_molecules
        identify_molecules(ctx)
    return _Mgr.instances


class TestGrouping:
    def test_identical_segments_resolved_once(self, tmp_path):
        """7 identical polymer chains + 1 ligand + 2 identical ions:
        three resolution units, reps alphabetical-first."""
        sigs = {s: _poly_sigs("KDKAAAA")
                for s in ("A", "B", "C", "D", "E", "F", "G")}
        sigs["LIG"] = _small_sigs("DOAKLVKFURWEDJ-HOASTROESA-K")
        sigs["CL1"] = _ion_sigs("Cl")
        sigs["CL2"] = _ion_sigs("Cl")
        ctx, results, _ = _ctx(tmp_path, sigs)
        instances = _run_identify(ctx)
        resolved = sorted({c for inst in instances for c in inst.calls})
        assert resolved == ["A", "CL1", "LIG"], resolved
        for seg in ("B", "C", "D", "E", "F", "G", "CL2"):
            payload = results.get_data(f"identifiers/{seg}")
            assert payload, f"{seg} must inherit group identifiers"
            assert "_shared_with" in str(payload), str(payload)[:200]

    def test_identical_segments_get_identical_top1(self, tmp_path):
        sigs = {s: _poly_sigs("AAKDKAAA") for s in ("H", "I", "J", "K", "L")}
        ctx, results, _ = _ctx(tmp_path, sigs)
        _run_identify(ctx)
        top1 = {}
        for seg in ("H", "I", "J", "K", "L"):
            payload = results.get_data(f"identifiers/{seg}")
            hit = payload["fasta_map_protein"]["identity"]["hits"][0]
            top1[seg] = (hit["ident_value"], hit["confidence"])
        assert len(set(top1.values())) == 1, top1

    def test_grouping_uses_formula_when_no_inchi(self, tmp_path):
        """Small molecules without an InChIKey group by heavy formula +
        fingerprint."""
        sigs = {s: _formula_only_sigs("C4H6O2") for s in ("X1", "X2", "X3")}
        ctx, results, _ = _ctx(tmp_path, sigs)
        instances = _run_identify(ctx)
        resolved = sorted({c for inst in instances for c in inst.calls})
        assert resolved == ["X1"], resolved

    def test_budget_cut_reports_unresolved_groups(self, tmp_path):
        """Budget already past: whole (not per-segment) groups go
        unresolved and get reported."""
        sigs = {s: _poly_sigs("AAAAAA") for s in ("A", "B", "C")}
        sigs["L1"] = _small_sigs("DOAKLVKFURWEDJ-HOASTROESA-K")
        sigs["L2"] = _small_sigs("DOAKLVKFURWEDJ-HOASTROESA-K")
        sigs["CL1"] = _ion_sigs("Cl")
        ctx, results, warnings_ = _ctx(tmp_path, sigs, budget_past=True)

        class _Boom:
            def __init__(self, *a, **k):
                pass

            def resolve(self, *a, **k):
                raise AssertionError(
                    "resolve must not run under spent budget")

        with patch(
                "src_new.identification.resolution_manager"
                ".IdentifierResolutionManager", _Boom):
            from src_new.pipeline_steps import _identify_molecules as identify_molecules
            identify_molecules(ctx)
        unresolved = results.get_data("identification/unresolved_groups")
        assert unresolved, "the budget cut must record unresolved GROUPS"
        assert any("budget" in w[1] for w in warnings_), warnings_


class TestCacheDirectoryDefault:
    def test_empty_directory_falls_back_to_writable_default(self, tmp_path,
                                                            monkeypatch):
        """BH-048: directory '' must not resolve into the unwritable
        container cwd — fall back to a writable run-local/tmp path."""
        monkeypatch.delenv("BAT3_IDENTIFIERS_CACHE_DIR", raising=False)
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        from src_new.config.loader import RunConfig
        cfg = RunConfig()
        cfg.identifiers_cache.directory = ""  # the production failure
        from src_new.identification.cache_manager import ResolverCache
        cache = ResolverCache(cfg)
        conn = cache._get_connection()
        assert conn is not None, "cache must open with a writable default"
        assert os.path.isabs(cache._cache_path)
        assert not cache._cache_path.startswith("/app")
