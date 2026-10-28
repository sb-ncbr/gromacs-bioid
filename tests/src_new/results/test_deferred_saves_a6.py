"""W3 A6 (BH-047): O(N^2) results.json persistence.

F14 evidence (logs/final_wo/f14/rootcause_f14.md): ~41.6k set_data calls
(38,635 in the signatures merge loop), each deep-copying + rewriting the
whole 3.5->10 MB payload (103-212 ms per save) => 6,146 s of wall time
for 4.2 s of real chemistry. These tests pin the fix contract:

- deferred/batched save mode: <= 1 save per 10 s inside a stage window
  plus one flush at the end (test_stage_saves_bounded);
- immediate saves outside deferred windows (control-plane semantics kept);
- compact JSON (the deepcopy+dump amplification is dropped);
- per-unique signature generation: heavy generators run ONCE per unique
  fragment group and results are copied to the copies; only mmcif,
  name_chain and name_segment are recomputed per copy
  (test_unique_group_generation_counts);
- the stage budget is checked inside the merge loop, not only during
  generation (test_merge_loop_budget_check).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src_new.results.results_manager import ResultsManager


def _count_writes(manager: ResultsManager) -> list:
    """Wrap atomic_write_json to count real writes."""
    import src_new.results.results_manager as rm_mod
    calls = []
    orig = rm_mod.atomic_write_json

    def spy(path, data, **kw):
        calls.append(path)
        return orig(path, data, **kw)
    rm_mod.atomic_write_json = spy
    return calls


def _restore(manager):
    import src_new.results.results_manager as rm_mod
    # re-bind the real function (tests must not leak the spy)
    from src_new.utils.file_utils import atomic_write_json as real
    rm_mod.atomic_write_json = real


class TestDeferredSaves:
    def test_stage_saves_bounded(self, tmp_path, monkeypatch):
        rm = ResultsManager(str(tmp_path / "r" / "results.json"), pipeline_name="t")
        rm.start_run()
        writes = _count_writes(rm)
        writes.clear()

        clock = {"t": 1000.0}
        monkeypatch.setattr(
            "src_new.results.results_manager.time.monotonic",
            lambda: clock["t"])

        with rm.deferred_saves():
            for i in range(3000):
                clock["t"] += 0.05          # 150 s simulated
                rm.set_data(f"signatures/seg_{i}/generated/smiles", "CC")
        _restore(rm)
        # <= 150 s / 10 s interval + 1 end-flush = 16
        assert len(writes) <= 17, f"{len(writes)} saves in a 150 s window (unbounded O(N^2) regression)"
        # final state fully persisted despite the throttling
        data = json.loads((tmp_path / "r" / "results.json").read_text())
        assert data["data"]["signatures"]["seg_2999"]["generated"]["smiles"] == "CC"

    def test_deferred_flush_on_exit(self, tmp_path):
        rm = ResultsManager(str(tmp_path / "r" / "results.json"), pipeline_name="t")
        rm.start_run()
        with rm.deferred_saves():
            rm.set_data("x1", "first")
            rm.set_data("x2", "second")
        data = json.loads((tmp_path / "r" / "results.json").read_text())["data"]
        assert data["x2"] == "second", "window exit must flush pending writes"

    def test_outside_deferred_saves_immediately(self, tmp_path):
        rm = ResultsManager(str(tmp_path / "r" / "results.json"), pipeline_name="t")
        rm.start_run()
        rm.set_data("plain", {"v": 1})
        data = json.loads((tmp_path / "r" / "results.json").read_text())["data"]
        assert data["plain"] == {"v": 1}, (
            "saves outside deferred windows stay synchronous "
            "(API/UI reads rely on quick visibility of events)")

    def test_events_rate_limited_inside_window(self, tmp_path, monkeypatch):
        rm = ResultsManager(str(tmp_path / "r" / "results.json"), pipeline_name="t")
        rm.start_run()
        writes = _count_writes(rm)
        writes.clear()
        clock = {"t": 500.0}
        monkeypatch.setattr(
            "src_new.results.results_manager.time.monotonic",
            lambda: clock["t"])
        with rm.deferred_saves():
            for i in range(200):
                clock["t"] += 0.1           # 20 s simulated
                rm.add_event("w", message=f"m{i}")
        _restore(rm)
        assert len(writes) <= 4, f"{len(writes)} event-driven saves in a 20 s window"

    def test_compact_json_output(self, tmp_path):
        rm = ResultsManager(str(tmp_path / "r" / "results.json"), pipeline_name="t")
        rm.start_run()
        rm.set_data("nested", {"a": {"b": list(range(100))}})
        text = (tmp_path / "r" / "results.json").read_text()
        assert "\n    " not in text, (
            "results.json must be written compact (indent=4 rewrite of a "
            "10 MB payload was half of the BH-047 O(N^2) cost)")


def _fake_ctx(tmp_path):
    """Minimal pipeline context for _generate_signatures (serial branch)."""
    from src_new.pipeline_steps import _STAGE_BUDGET_STATE_KEY
    rm = ResultsManager(str(tmp_path / "r" / "results.json"), pipeline_name="t")
    rm.start_run()
    ctx = MagicMock()
    state = {"deadline": None}
    cfg = SimpleNamespace(
        executor=SimpleNamespace(signatures_parallel=False, n_threads=1),
        signatures=SimpleNamespace(smiles_maximum_number_of_atoms=250),
        to_dict=lambda: {},
    )
    ctx.config = cfg
    ctx.results = rm
    store = SimpleNamespace()
    ctx.get_value.side_effect = lambda k: {"stage_deadline_epoch": state["deadline"]}.get(k)
    ctx._test_state = state
    ctx._test_store = store
    return ctx, rm


def _mk_inst(seg):
    return SimpleNamespace(segment_ids=[seg], instance_id=f"inst_{seg}",
                           molecule_type=SimpleNamespace(value="small_molecule"),
                           atom_count=4, chain_ids=[seg], copy_number=1)


def _mk_snapshot(seg, names=("C1", "C2", "O1", "O2")):
    return SimpleNamespace(
        segment_name=seg, molecule_type="small_molecule", atom_count=4,
        residue_count=1, names=names, elements=tuple(n.rstrip("0123456789") for n in names),
        bonds=[(0, 1), (2, 3)], resnames=("LIG",),
        __dict__={})


class _FakeGen:
    def __init__(self, name, log):
        self.name = name
        self._log = log

    def is_applicable(self, instance, fragment, facade):
        return True

    def generate(self, instance, fragment, facade):
        self._log.append((self.name, instance.segment_ids[0]))
        if self.name == "mmcif":
            return f"mmcif-of-{instance.segment_ids[0]}"
        if self.name == "name_chain":
            return f"chain-{instance.segment_ids[0]}"
        if self.name == "name_segment":
            return f"seg-{instance.segment_ids[0]}"
        return f"{self.name}-shared-value"


def _run_sigs(tmp_path, monkeypatch, segment_groups, gens_log, pre_run=None):
    """Drive _generate_signatures with a synthetic facade/store.

    segment_groups: member lists; the first member groups share one
    uniqueness key, the second member group another key.
    pre_run: optional hook(ctx, rm) invoked right before the stage runs.
    """
    import src_new.pipeline_steps as ps
    import src_new.signatures.snapshot as snap_mod
    import src_new.signatures.registry as reg_mod

    all_segs = [s for grp in segment_groups for s in grp]
    facade = MagicMock()
    facade.get_segments.return_value = list(all_segs)
    facade.get_fragment.side_effect = lambda s: SimpleNamespace(seg=s)
    facade.get_segment_properties.side_effect = lambda s: SimpleNamespace(flags={})

    instances = {s: _mk_inst(s) for s in all_segs}
    store = MagicMock()
    store.get_all_instances.return_value = list(instances.values())

    ctx, rm = _fake_ctx(tmp_path)
    ctx.get_value.side_effect = lambda k: {
        "facade": facade, "fragment_store": store,
        "stage_deadline_epoch": ctx._test_state["deadline"],
    }.get(k)

    key_by_seg = {}
    for gi, grp in enumerate(segment_groups):
        for s in grp:
            key_by_seg[s] = gi

    monkeypatch.setattr(
        snap_mod, "build_signature_snapshot",
        lambda seg, frag, inst, fac: _mk_snapshot(
            seg, names=("C1", "C2", "O1", "O2") if key_by_seg[seg] == 0 else ("N1", "N2", "CL1", "O9")))
    monkeypatch.setattr(ps, "_pinned_props_facade", lambda fac, seg: fac)
    monkeypatch.setattr(ps, "_segment_flags", lambda frag: {})
    monkeypatch.setattr(
        reg_mod, "get_default_generators",
        lambda cfg: [_FakeGen("molecular_formula", gens_log),
                     _FakeGen("smiles", gens_log),
                     _FakeGen("mmcif", gens_log),
                     _FakeGen("name_chain", gens_log),
                     _FakeGen("name_segment", gens_log)])
    if pre_run is not None:
        pre_run(ctx, rm)
    ps._generate_signatures(ctx)
    return ctx, rm


class TestPerUniqueSignatureGeneration:
    def test_unique_group_generation_counts(self, tmp_path, monkeypatch):
        """Two identical copies + one distinct: heavy generators run once
        per UNIQUE group; every member still gets full generated data with
        shared chemistry and per-copy mmcif/name_chain/name_segment."""
        log = []
        ctx, rm = _run_sigs(
            tmp_path, monkeypatch,
            segment_groups=[["A", "B"], ["C"]], gens_log=log)

        heavy = [seg for name, seg in log if name in ("molecular_formula", "smiles")]
        assert sorted(heavy) == ["A", "A", "C", "C"], (
            f"heavy generators must run once per unique segment, got {log}")
        per_copy = [seg for name, seg in log if name in ("mmcif", "name_chain", "name_segment")]
        assert sorted(per_copy) == ["A", "A", "A", "B", "B", "B", "C", "C", "C"], (
            "per-copy generators (mmcif/name_chain/name_segment) run for every segment")

        data = json.loads((tmp_path / "r" / "results.json").read_text())["data"]
        sa, sb, sc = (data["signatures"][s]["generated"] for s in ("A", "B", "C"))
        assert sa["smiles"] == sb["smiles"] == "smiles-shared-value"
        assert sa["molecular_formula"] == sb["molecular_formula"]
        assert sa["mmcif"] == "mmcif-of-A" and sb["mmcif"] == "mmcif-of-B"
        assert sa["name_chain"] == "chain-A" and sb["name_chain"] == "chain-B"
        assert sc["smiles"] == "smiles-shared-value"

    def test_stage_saves_bounded_on_many_copies(self, tmp_path, monkeypatch):
        """F14 shape (one unique, 500 copies): merge-time saves are
        deferred to <= 1 per 10 s + final flush."""
        log = []
        ctx, rm = _run_sigs(
            tmp_path, monkeypatch,
            segment_groups=[["A"] + [f"C{i}" for i in range(500)]], gens_log=log)
        heavy = [seg for name, seg in log if name in ("molecular_formula", "smiles")]
        assert sorted(set(heavy)) == ["A"], "one unique group -> one heavy generation"
        data = json.loads((tmp_path / "r" / "results.json").read_text())["data"]
        assert len(data["signatures"]) == 501

    def test_merge_loop_budget_check(self, tmp_path, monkeypatch):
        """Generation completes fully, budget trips only once results are
        BEING MERGED -> the merge loop must stop promptly (pre-fix: no
        check existed there; F14 wrote for 2h48m after generation ended
        at ~25 s)."""
        import src_new.pipeline_steps as ps

        log = []
        state = {"exceeded": False}

        def pre_run(ctx, rm):
            orig_set_data = rm.set_data

            def flip_on_first_write(*a, **k):
                state["exceeded"] = True   # first merge write: budget exceeded
                return orig_set_data(*a, **k)
            rm.set_data = flip_on_first_write

        monkeypatch.setattr(ps, "_budget_exceeded", lambda ctx: state["exceeded"])
        ctx, rm = _run_sigs(
            tmp_path, monkeypatch,
            segment_groups=[["A", "B", "C"]], gens_log=log, pre_run=pre_run)
        data = json.loads((tmp_path / "r" / "results.json").read_text())["data"]
        assert len(data["signatures"]) < 3, (
            "merge loop must stop at the stage budget "
            f"(merged {sorted(data['signatures'])})")
