from __future__ import annotations

import pytest

mdanalysis = pytest.importorskip("MDAnalysis")

from pathlib import Path
from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.loader.strategies import load_simulation
from src_new.loader.repair import TopologyRepair
from src_new.loader.universe_facade import LoadedUniverse
from src_new.loader.fragment_store import FragmentStore
from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager


def _build_store(data_dir: str, tmp_path: Path):
    root = Path(data_dir)
    bundle = inspect_directory(root)
    decision = select_best_file_combination(bundle)
    
    results = ResultsManager(tmp_path / "results.json")
    config = RunConfig()
    config.loader.guess_missing_elements = True
    config.loader.guess_missing_masses = True
    config.loader.guess_missing_bonds = True
    
    load_result = load_simulation(decision, bundle, config, results)
    assert load_result.success
    
    repair = TopologyRepair(load_result.universe, config)
    repair_report = repair.run()
    
    facade = LoadedUniverse(load_result.universe, decision, repair_report, results)
    store = FragmentStore(facade, results)
    return store, facade, results


class TestFragmentStore14976a:
    def test_instances_count(self, tmp_path: Path):
        store, _, _ = _build_store("tests/data/14976_a", tmp_path)
        assert len(store.get_all_instances()) == 4

    def test_unique_count(self, tmp_path: Path):
        store, _, _ = _build_store("tests/data/14976_a", tmp_path)
        # Each segment is unique, so 4 unique keys
        assert len(store.get_unique_molecules()) == 4

    def test_copy_counts(self, tmp_path: Path):
        store, _, _ = _build_store("tests/data/14976_a", tmp_path)
        for key in store.get_unique_molecules():
            count = store.get_copy_count(key)
            assert count == 1

    def test_whole_system_instance(self, tmp_path: Path):
        store, _, _ = _build_store("tests/data/14976_a", tmp_path)
        system = store.get_whole_system_instance()
        assert system.instance_id == "mol_SYSTEM"
        assert system.atom_count == 82308  # whole system
        assert len(system.segment_ids) == 4

    def test_type_counts(self, tmp_path: Path):
        store, _, _ = _build_store("tests/data/14976_a", tmp_path)
        counts = store.get_unique_counts_by_type()
        # Should have lipid, water, ion, ion
        assert "ion" in counts
        assert "water" in counts

    def test_results_recorded(self, tmp_path: Path):
        store, _, results = _build_store("tests/data/14976_a", tmp_path)
        assert results.data_exists("fragments/unique")
        assert isinstance(results.get_data("fragments/type_counts"), dict)
        # Total fragment count is sum of all molecule counts across segments
        total = results.get_data("fragments/total_fragment_count")
        assert isinstance(total, int)
        assert total > 0


class TestFragmentStore16319:
    """TOP+GRO fixture. Per-molecule segment contract (triaged 2026-10-20,
    A' wave): MDAnalysis >= 2.9 names each molecule its own segment
    ('SOL_1', ...), so the store holds one instance per molecule segment;
    species aggregation lives in the molecules/discovery layer. The former
    aggregated {'DPPC','SOL','Na','Cl'} expectations predated that parser
    behavior (ledger entry 2026-10-02)."""

    def test_instances_count(self, tmp_path: Path):
        store, _, _ = _build_store("tests/data/16319", tmp_path)
        # one instance per per-molecule segment (72 DPPC + 2864 SOL + 8 Na + 8 Cl)
        assert len(store.get_all_instances()) == 2952

    def test_unique_segments(self, tmp_path: Path):
        store, _, _ = _build_store("tests/data/16319", tmp_path)
        instances = store.get_all_instances()
        prefixes = {inst.segment_ids[0].rsplit('_', 1)[0] for inst in instances}
        assert prefixes == {"DPPC", "SOL", "Na", "Cl"}

    def test_copy_numbers(self, tmp_path: Path):
        store, facade, _ = _build_store("tests/data/16319", tmp_path)
        instances = store.get_all_instances()
        groups = {}
        for inst in instances:
            groups.setdefault(inst.segment_ids[0].rsplit('_', 1)[0], []).append(inst)
        # one instance per molecule; species multiplicities from the fixture
        assert {k: len(v) for k, v in groups.items()} == {"DPPC": 72, "SOL": 2864, "Na": 8, "Cl": 8}
        assert all(inst.copy_number == 1 for inst in instances)
        assert all(inst.atom_count == 3 for inst in groups["SOL"])  # 3-site water

    def test_whole_system(self, tmp_path: Path):
        store, _, _ = _build_store("tests/data/16319", tmp_path)
        system = store.get_whole_system_instance()
        assert system.atom_count == 12208
        assert "O" in system.element_composition
        assert "H" in system.element_composition


class TestFragmentStore35193a:
    def test_segments(self, tmp_path: Path):
        store, _, _ = _build_store("tests/data/35193_a", tmp_path)
        instances = store.get_all_instances()
        names = [inst.segment_ids[0] for inst in instances]
        assert set(names) == {'seg_2_Na_s', 'seg_1_TIP3p', 'seg_0_POPC', 'seg_3_Cl_s'}


class TestFragmentDeduplication:
    def test_dedup_keys_deterministic(self, tmp_path: Path):
        store, _, _ = _build_store("tests/data/16319", tmp_path)
        unique = store.get_unique_molecules()
        keys = list(unique.keys())
        # Keys should be deterministic strings
        assert all(isinstance(k, str) for k in keys)
        assert len(keys) == len(set(keys))
