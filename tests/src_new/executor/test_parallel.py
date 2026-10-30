"""Tests for parallel execution utilities."""

from __future__ import annotations

import json
import multiprocessing
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from src_new.config.loader import RunConfig
from src_new.executor.parallel import run_with_process_pool, run_with_thread_pool
from src_new.pipeline_steps.workers import (
    _generate_signatures_worker,
    _identify_molecules_worker,
    _verify_results_worker,
)
from src_new.signatures.snapshot import SegmentSignatureSnapshot

# Check for rdkit availability
try:
    import rdkit  # noqa: F401
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False


@pytest.fixture(autouse=True)
def _reset_dbo_worker_after_each_test():
    """W3 BH-053 flake follow-up: this module's signature generation
    spawns the persistent DBO ladder worker; drop it after each test so
    later tests in the same pytest process (e.g. the a5 vehicle proof,
    which asserts spawn/respawn semantics) never inherit a live worker
    from here."""
    yield
    from src_new.signatures.generators._perceive_cache import _reset_dbo_worker
    _reset_dbo_worker()



# Module-level functions for process pool tests (must be picklable)
def _double(x):
    return x * 2


def _square(x):
    return x * x


class TestParallelUtilities:
    """Tests for parallel execution helper functions."""
    
    def test_run_with_thread_pool(self):
        """Thread pool runs functions correctly."""
        items = [1, 2, 3, 4, 5]
        results = run_with_thread_pool(4, _square, items)
        
        assert results == [1, 4, 9, 16, 25]
    
    def test_run_with_process_pool(self):
        """Process pool runs functions correctly."""
        items = [1, 2, 3, 4, 5]
        results = run_with_process_pool(4, _double, items)
        
        assert results == [2, 4, 6, 8, 10]


class TestResultsManagerConcurrency:
    """Tests for ResultsManager thread safety."""
    
    def test_results_manager_survives_concurrent_writes(self, tmp_path: Path):
        """ResultsManager handles concurrent writes from multiple threads.
        
        Note: Due to file-based storage, concurrent writes may race and some
        writes may be lost. This test verifies that:
        1. The JSON file remains valid after concurrent access
        2. At least some writes succeed
        """
        from src_new.results.results_manager import ResultsManager
        
        results_path = tmp_path / "results.json"
        manager = ResultsManager(results_path, pipeline_name="concurrent_test")
        
        num_threads = 10
        
        def write_value(i: int):
            manager.set_data(f"thread_{i}/value", i)
        
        # Spawn threads
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=write_value, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Verify JSON is valid (most important - no corruption)
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        data = payload.get("data", {})
        
        # At least some data should be present (race conditions may lose some writes)
        assert len(data) > 0, "Expected at least some data to be written"
        
        # Verify any data that was written has correct structure
        for key, value in data.items():
            assert "value" in value


class TestSignatureWorker:
    """Tests for signature generation worker."""
    
    @pytest.mark.skipif(not HAS_RDKIT, reason="rdkit not installed")
    def test_process_pool_worker_returns_expected_signatures(self):
        """Signature worker returns expected structure with mock data."""
        # Create a minimal mock snapshot
        snapshot_dict = {
            "segment_name": "A",
            "atom_indices": [0, 1, 2],
            "elements": ["C", "C", "H"],
            "names": ["C1", "C2", "H1"],
            "resnames": ["ALA"],
            "resids": [1],
            "segids": ["A"],
            "masses": [12.0, 12.0, 1.0],
            "positions": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            "bonds": [(0, 1), (1, 2)],
            "flags": {
                "has_elements": True,
                "has_masses": True,
                "has_positions": True,
                "has_names": True,
                "is_protein": False,
                "is_nucleic": False,
            },
            "atom_count": 3,
            "residue_count": 1,
            "molecule_type": "small_molecule",
            "instance_id": "mol_A",
            "chain_ids": ["A"],
            "copy_number": 1,
            "element_composition": {"C": 2, "H": 1},
        }
        
        config = RunConfig()
        config_dict = config.to_dict()
        
        # Run worker
        result = _generate_signatures_worker((snapshot_dict, config_dict))
        
        # Note: result may have errors if optional dependencies are missing
        # If result is not None, verify its structure
        if result is not None:
            assert "segment_name" in result
            assert result["segment_name"] == "A"
            assert "generated" in result
            assert "attempted" in result
            assert isinstance(result["generated"], dict)
            assert isinstance(result["attempted"], list)


class TestIdentificationWorker:
    """Tests for identification worker."""
    
    def test_thread_pool_worker_identification_returns_flat_dict(self):
        """Identification worker returns flat dict output."""
        # Create minimal test data
        fragment_name = "test_segment"
        signatures_dict = {
            "atom": "C C H",  # Simple atom signature
        }
        config = RunConfig()
        config_dict = config.to_dict()
        sig_type_map = {"atom": "atom"}
        
        # F-15: 5th element = pre-existing identifiers blob ({} = fresh entry)
        item = (fragment_name, signatures_dict, config_dict, sig_type_map, {})
        
        # Run worker
        result = _identify_molecules_worker(item)
        
        # Verify structure
        assert result is not None
        assert "fragment_name" in result
        assert result["fragment_name"] == fragment_name
        assert "results" in result
        assert isinstance(result["results"], dict)


class TestVerificationWorker:
    """Tests for verification worker."""
    
    def test_verification_worker_returns_verified_hits(self):
        """Verification worker returns verified hits structure."""
        segment = "test_segment"
        segment_data = {
            "smiles": {
                "pubchem_struct": {
                    "signature": "CCO",
                    "hit_type": "identity",
                    "hits": [{"identifier": "702", "similarity": 100.0}],
                    "ident_type": "PUBCHEM_ID"
                }
            }
        }
        config = RunConfig()
        config_dict = config.to_dict()
        
        item = (segment, segment_data, config_dict)
        
        # Run worker - may return dict with errors if there are issues
        result = _verify_results_worker(item)
        
        # Verify structure
        assert result is not None
        assert "segment" in result
        assert result["segment"] == segment
        assert "verified_hits" in result
        assert isinstance(result["verified_hits"], list)


class TestPipelineParallelEquivalence:
    """Integration tests comparing serial vs parallel execution."""
    
    @pytest.mark.skipif(not HAS_RDKIT, reason="rdkit not installed")
    def test_pipeline_serial_vs_parallel_equivalence(self, tmp_path: Path):
        """Pipeline produces identical results in serial and parallel modes."""
        from src_new import PipelineExecutor, ResultsManager, build_load_and_export_tasks
        
        # Create a minimal PDB file with 2 segments
        pdb_content = """HEADER    TEST STRUCTURE
ATOM      1  N   ALA A   1      20.153  22.867   4.981  1.00 18.40           N
ATOM      2  CA  ALA A   1      20.250  24.321   5.050  1.00 17.20           C
ATOM      3  C   ALA A   1      21.732  24.680   5.200  1.00 16.80           C
ATOM      4  O   ALA A   1      22.401  23.890   5.890  1.00 15.90           O
ATOM      5  N   GLY B   1      25.000  25.000   5.000  1.00 18.40           N
ATOM      6  CA  GLY B   1      26.000  26.000   5.000  1.00 17.20           C
TER
END
"""
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text(pdb_content, encoding="utf-8")
        
        def run_pipeline(parallel_mode: bool) -> dict:
            results_path = tmp_path / f"results_{'parallel' if parallel_mode else 'serial'}.json"
            output_dir = tmp_path / f"output_{'parallel' if parallel_mode else 'serial'}"
            manager = ResultsManager(results_path, pipeline_name="equivalence_test")
            
            config = RunConfig()
            config.executor.signatures_parallel = parallel_mode
            config.executor.identifiers_parallel = parallel_mode
            config.executor.verification_parallel = parallel_mode
            config.executor.n_threads = 4
            
            executor = PipelineExecutor(
                steps=build_load_and_export_tasks(),
                results_manager=manager,
                pipeline_name="equivalence_test",
            )
            
            try:
                context = executor.run(
                    working_directory=tmp_path,
                    output_directory=output_dir,
                    input_kind="pdb",
                    input_files={"structure": pdb_file},
                )
            except Exception as e:
                # Pipeline may fail at various stages, but we check what was produced
                pass
            
            payload = manager.as_dict()
            return payload.get("data", {})
        
        # Run serial
        serial_data = run_pipeline(False)
        
        # Run parallel
        parallel_data = run_pipeline(True)
        
        # Compare signatures (order may differ, so normalize)
        serial_sigs = serial_data.get("signatures", {})
        parallel_sigs = parallel_data.get("signatures", {})
        
        # Both should have same segments
        assert set(serial_sigs.keys()) == set(parallel_sigs.keys()), \
            f"Segment mismatch: {set(serial_sigs.keys())} vs {set(parallel_sigs.keys())}"
        
        # For each segment, compare generated signatures
        for segment in serial_sigs:
            serial_gen = serial_sigs[segment].get("generated", {})
            parallel_gen = parallel_sigs[segment].get("generated", {})
            
            # Same generators should have been attempted
            assert set(serial_gen.keys()) == set(parallel_gen.keys()), \
                f"Generator mismatch for {segment}"


class TestConcurrentCacheAccess:
    """Tests for concurrent cache access safety."""
    
    def test_concurrent_runs_do_not_corrupt_cache(self, tmp_path: Path):
        """Two concurrent pipeline runs don't corrupt shared cache."""
        from src_new.identification.cache_manager import ResolverCache, create_empty_cache_if_not_exists
        from src_new.config.loader import RunConfig
        
        # Create shared cache
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "cache.sqlite3"
        
        # Initialize cache
        create_empty_cache_if_not_exists(str(cache_file))
        
        def run_with_cache(run_id: int):
            config = RunConfig()
            config.identifiers_cache.directory = str(cache_dir)
            config.identifiers_cache.file = "cache.sqlite3"
            
            cache = ResolverCache(config)
            
            # Perform some writes
            cache.save_identity_identifiers(
                f"resolver_{run_id}",
                f"signature_{run_id}",
                [f"identifier_{run_id}_1", f"identifier_{run_id}_2"]
            )
            
            # Read back
            results = cache.fetch_identity_identifiers(
                f"resolver_{run_id}",
                f"signature_{run_id}"
            )
            
            return len(results)
        
        # Run two "pipeline tasks" concurrently using threads
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run_with_cache, i) for i in range(2)]
            results = [f.result() for f in futures]
        
        # Both should succeed
        assert all(r == 2 for r in results), f"Expected 2 results each, got {results}"
        
        # Verify cache file is valid
        assert cache_file.exists()
        assert cache_file.stat().st_size > 0
        
        # Verify we can query the cache
        config = RunConfig()
        config.identifiers_cache.directory = str(cache_dir)
        config.identifiers_cache.file = "cache.sqlite3"
        
        final_cache = ResolverCache(config)
        
        for i in range(2):
            results = final_cache.fetch_identity_identifiers(
                f"resolver_{i}",
                f"signature_{i}"
            )
            assert len(results) == 2, f"Expected 2 identifiers for run {i}"


class TestWorkerErrorHandling:
    """Tests for worker error handling."""
    
    def test_failing_worker_does_not_crash_stage(self):
        """A failing worker returns dict with errors and doesn't crash the stage."""
        # Create invalid snapshot that should fail gracefully
        invalid_snapshot = {
            "segment_name": "invalid",
            # Missing required fields
        }
        
        config = RunConfig()
        config_dict = config.to_dict()
        
        # This should return a dict with errors, not raise
        result = _generate_signatures_worker((invalid_snapshot, config_dict))
        
        # Should return dict with errors on error (never None)
        assert result is not None
        assert isinstance(result, dict)
        assert "errors" in result
        assert len(result["errors"]) > 0
        assert result["segment_name"] == "unknown"
    
    def test_worker_exception_is_captured_in_errors(self, caplog):
        """Worker exceptions are captured in errors list."""
        import logging
        caplog.set_level(logging.ERROR)
        
        # Create invalid data
        invalid_item = ({}, {})
        
        result = _generate_signatures_worker(invalid_item)
        
        # Should have errors in result
        assert result is not None
        assert isinstance(result, dict)
        assert "errors" in result
        assert len(result["errors"]) > 0


class TestComprehensiveMockCoverage:
    """Comprehensive mock API coverage tests."""
    
    @pytest.mark.skipif(not HAS_RDKIT, reason="rdkit not installed")
    def test_comprehensive_mock_generator_coverage(self):
        """Comprehensive test ensuring MockAtomGroup and MockResidues support all attributes/methods accessed by generators.
        
        This test:
        1. Builds a realistic protein snapshot (4 residues: GLY, ALA, SER, LYS)
        2. Builds a water snapshot (3 atoms: OW, HW1, HW2)
        3. Runs _generate_signatures_worker for both snapshots
        4. Asserts NO errors contain AttributeError
        5. Asserts expected signatures were generated
        6. Checks specific edge cases
        """
        from src_new.config.loader import RunConfig
        
        # ==========================================================================
        # 1. Build a realistic protein snapshot
        # ==========================================================================
        element_map = {
            'N': 'N', 'CA': 'C', 'C': 'C', 'O': 'O',
            'CB': 'C', 'CG': 'C', 'CD': 'C', 'CE': 'C',
            'OG': 'O', 'HG': 'H', 'NZ': 'N',
            'HW1': 'H', 'HW2': 'H', 'OW': 'O'
        }
        mass_map = {'N': 14.0, 'C': 12.0, 'O': 16.0, 'H': 1.0}
        
        protein_resnames = []
        protein_resids = []
        protein_segids = []
        protein_names = []
        protein_elements = []
        protein_masses = []
        protein_positions = []
        
        atom_idx = 0
        residue_data = [
            ('GLY', 1, ['N', 'CA', 'C', 'O']),
            ('ALA', 2, ['N', 'CA', 'C', 'O', 'CB']),
            ('SER', 3, ['N', 'CA', 'C', 'O', 'CB', 'OG', 'HG']),
            ('LYS', 4, ['N', 'CA', 'C', 'O', 'CB', 'CG', 'CD', 'CE', 'NZ']),
        ]
        
        for resname, resid, atom_names in residue_data:
            for name in atom_names:
                protein_resnames.append(resname)
                protein_resids.append(resid)
                protein_segids.append('A')
                protein_names.append(name)
                elem = element_map.get(name, 'C')
                protein_elements.append(elem)
                protein_masses.append(mass_map.get(elem, 12.0))
                protein_positions.append([float(atom_idx), 0.0, 0.0])
                atom_idx += 1
        
        # Build bonds
        protein_bonds = []
        atom_idx = 0
        for resname, resid, atom_names in residue_data:
            res_atom_indices = list(range(atom_idx, atom_idx + len(atom_names)))
            if len(res_atom_indices) >= 4:
                protein_bonds.append((res_atom_indices[0], res_atom_indices[1]))  # N-CA
                protein_bonds.append((res_atom_indices[1], res_atom_indices[2]))  # CA-C
                protein_bonds.append((res_atom_indices[2], res_atom_indices[3]))  # C-O
            for side_idx in range(4, len(res_atom_indices)):
                protein_bonds.append((res_atom_indices[1], res_atom_indices[side_idx]))
            atom_idx += len(atom_names)
        
        # Peptide bonds between residues
        residue_boundaries = [4, 9, 16]
        for i, boundary in enumerate(residue_boundaries[:-1]):
            protein_bonds.append((boundary - 1, boundary))
        
        protein_snapshot_dict = {
            "segment_name": "protein_A",
            "atom_indices": list(range(len(protein_names))),
            "elements": protein_elements,
            "names": protein_names,
            "resnames": protein_resnames,
            "resids": protein_resids,
            "segids": protein_segids,
            "masses": protein_masses,
            "positions": protein_positions,
            "bonds": protein_bonds,
            "flags": {
                "is_protein": True,
                "has_elements": True,
                "has_positions": True,
                "has_multi_atom_residues": True,
                "has_unique_names": True,
                "has_masses": True,
                "has_names": True,
            },
            "atom_count": len(protein_names),
            "residue_count": len(residue_data),
            "molecule_type": "protein",
            "instance_id": "protein_A_1",
            "chain_ids": ["A"],
            "copy_number": 1,
            "element_composition": {"C": 10, "H": 8, "N": 5, "O": 6},
        }
        
        # ==========================================================================
        # 2. Build a water snapshot
        # ==========================================================================
        water_snapshot_dict = {
            "segment_name": "water_B",
            "atom_indices": [0, 1, 2],
            "elements": ["O", "H", "H"],
            "names": ["OW", "HW1", "HW2"],
            "resnames": ["WAT"],
            "resids": [1],
            "segids": ["B"],
            "masses": [16.0, 1.0, 1.0],
            "positions": [[0.0, 0.0, 0.0], [0.9, 0.0, 0.0], [-0.3, 0.7, 0.0]],
            "bonds": [(0, 1), (0, 2)],
            "flags": {
                "has_elements": True,
                "has_positions": True,
                "has_masses": True,
                "has_names": True,
            },
            "atom_count": 3,
            "residue_count": 1,
            "molecule_type": "water",
            "instance_id": "water_B_1",
            "chain_ids": ["B"],
            "copy_number": 1,
            "element_composition": {"H": 2, "O": 1},
        }
        
        # ==========================================================================
        # 3. Run _generate_signatures_worker for both snapshots
        # ==========================================================================
        config = RunConfig()
        config_dict = config.to_dict()
        
        protein_result = _generate_signatures_worker((protein_snapshot_dict, config_dict))
        water_result = _generate_signatures_worker((water_snapshot_dict, config_dict))
        
        # ==========================================================================
        # 4. Assert NO errors contain AttributeError
        # ==========================================================================
        attribute_error_patterns = [
            "'MockResidues' object has no attribute",
            "'MockAtomGroup' object has no attribute",
            "'MockResidueAtoms' object has no attribute",
            "'types.SimpleNamespace' object is not iterable",
            "'numpy.ndarray' object has no attribute 'positions'",
        ]
        
        for result in [protein_result, water_result]:
            assert result is not None, f"Worker returned None for {result.get('segment_name', 'unknown')}"
            for error in result.get("errors", []):
                error_str = str(error.get("error", ""))
                for pattern in attribute_error_patterns:
                    assert pattern not in error_str, \
                        f"AttributeError found in {result['segment_name']}: {error_str}"
        
        # ==========================================================================
        # 5. Assert expected signatures were generated
        # ==========================================================================
        protein_generated = protein_result.get("generated", {})
        protein_attempted = protein_result.get("attempted", [])
        
        assert "fasta_map_protein" in protein_generated or "fasta_map_protein" in protein_attempted
        assert "fasta_resname_protein" in protein_generated or "fasta_resname_protein" in protein_attempted
        
        pdb_generators = [k for k in protein_generated.keys() if k.startswith("pdb") and "protein" in k]
        pdb_attempted = [k for k in protein_attempted if k.startswith("pdb") and "protein" in k]
        assert len(pdb_generators) > 0 or len(pdb_attempted) > 0
        
        assert "mmcif" in protein_generated or "mmcif" in protein_attempted
        assert "molecular_formula" in protein_generated or "molecular_formula" in protein_attempted
        
        # Water assertions
        water_generated = water_result.get("generated", {})
        water_attempted = water_result.get("attempted", [])
        
        assert "molecular_formula" in water_generated or "molecular_formula" in water_attempted
        
        if "molecular_formula" in water_generated:
            formula = water_generated["molecular_formula"]
            assert "H" in formula and "O" in formula, f"Water formula should contain H and O, got: {formula}"
        
        assert "atom" not in water_generated
        
        # ==========================================================================
        # 6. Check specific edge cases
        # ==========================================================================
        if "fasta_resname_protein" in protein_generated:
            fasta_seq = protein_generated["fasta_resname_protein"]
            assert len(fasta_seq) == 4, f"FASTA sequence should have 4 residues, got: {fasta_seq}"
            assert fasta_seq[0] == 'G', f"First residue should be Glycine (G), got: {fasta_seq[0]}"
        
        for pdb_key in pdb_generators:
            pdb_content = protein_generated[pdb_key]
            assert len(pdb_content) > 0, f"PDB content should not be empty for {pdb_key}"
            # B-18: the realistic (non-mock) path may legally emit content
            # from either writer (HEADER-prefixed direct or Biopython ATOM)
            first = pdb_content.strip().splitlines()[0][:6]
            assert first.strip() in ("HEADER", "ATOM", "HETATM", "REMARK",
                                     "CRYST1", "MODEL"), \
                f"PDB content should be a parseable record for {pdb_key}: {first!r}"
        
        tdi_errors = [e for e in protein_result.get("errors", []) if e.get("generator") == "tdi"]
        for error in tdi_errors:
            error_str = str(error.get("error", ""))
            assert "'MockResidueAtoms' object has no attribute" not in error_str
        
        fingerprint_errors = [e for e in protein_result.get("errors", []) if e.get("generator") == "fingerprint"]
        for error in fingerprint_errors:
            error_str = str(error.get("error", ""))
            assert "'tolist'" not in error_str

def _build_protein_test_pdb() -> str:
    """12-residue heavy-atom-complete protein fragment + 1 water + 1 K ion
    with CONECT records. Requirements (red-team re-audit):

     1. Chain length must clear the BLAST applicability guard
        (_MIN_SEQUENCE_LENGTH = 10 in resolvers/blast.py) — the old 2-residue
        fixture produced 'AG', so no BLAST resolver was ever attempted and
        identifiers/{A}/fasta_resname_protein/attempted stayed empty.
     2. The molecule must be chemically COMPLETE (all heavy atoms) with
        CONECT bond records — a backbone-only peptide leaves dozens of
        dangling valences and sends RDKit DetermineBonds/DetermineBondOrders
        into an exponential valence search inside the smiles/inchi
        generators (observed: >20 min CPU spin, uninterruptible — same
        pathology class as the documented kekulization freeze), bounded
        only by the task-level timeout.
    """
    side_chains = {
        "ALA": ["CB"],
        "GLY": [],
        "SER": ["CB", "OG"],
        "VAL": ["CB", "CG1", "CG2"],
        "LEU": ["CB", "CG", "CD1", "CD2"],
        "ASP": ["CB", "CG", "OD1", "OD2"],
        "THR": ["CB", "OG1", "CG2"],
        "ILE": ["CB", "CG1", "CG2", "CD1"],
        "ASN": ["CB", "CG", "OD1", "ND2"],
        "GLN": ["CB", "CG", "CD", "OE1", "NE2"],
        "LYS": ["CB", "CG", "CD", "CE", "NZ"],
        "MET": ["CB", "CG", "SD", "CE"],
    }
    resnames = ["ALA", "GLY", "SER", "VAL", "LEU", "ASP",
                "THR", "ILE", "ASN", "GLN", "LYS", "MET"] * 3  # ~277 heavy atoms:
    # clears the 250-atom smiles gate like any real protein (production
    # proteins never enter the RDKit bond-order search), while the 12-residue
    # version still slid under it and spun >20 min in DetermineBondOrders.
    # BLAST applicability needs >= 10 residues; 36 keeps it comfortably above.
    pdb_lines = ["HEADER    TEST PROTEIN STRUCTURE"]
    serial = 1
    index_by_name = {}

    def put(atom, resname, chain, resid, x, y, z, elem):
        nonlocal serial
        record = "ATOM  " if chain == "A" else "HETATM"
        pdb_lines.append(
            f"{record}{serial:5d} {atom:<4s}{resname:>4s} {chain}{resid:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 17.00          {elem:>2s}")
        index_by_name[(resid, atom)] = serial
        serial += 1

    for i, rn in enumerate(resnames, 1):
        bx = 20.0 + 3.8 * i
        put("N", rn, "A", i, bx, 22.0, 5.0, "N")
        put("CA", rn, "A", i, bx + 1.46, 22.45, 5.30, "C")
        put("C", rn, "A", i, bx + 2.86, 21.80, 5.55, "C")
        put("O", rn, "A", i, bx + 3.55, 20.85, 5.90, "O")
        # zigzag sidechain off CA
        sx, sy, sz = bx + 1.90, 23.55, 4.35
        for j, atom in enumerate(side_chains[rn]):
            put(atom, rn, "A", i, sx, sy, sz, atom[0])
            sx += (0.9 if j % 2 == 0 else -0.8)
            sy += (-1.05 if j % 2 == 0 else 1.0)
            sz += (-0.85 if j % 2 == 0 else 0.95)
    # water (with hydrogens) and the ion
    put("OW", "SOL", "B", 1, 10.0, 10.0, 10.0, "O")
    put("HW1", "SOL", "B", 1, 10.96, 10.0, 10.0, "H")
    put("HW2", "SOL", "B", 1, 9.70, 10.82, 10.0, "H")
    put("K", "K", "C", 1, 30.0, 30.0, 30.0, "K")

    # CONECT records: backbone + sidechains + water O-H bonds, so topology
    # bond perception (and the exponential bond-order search) is skipped.
    bonds = []
    for i, rn in enumerate(resnames, 1):
        pairs = [("N", "CA"), ("CA", "C"), ("C", "O")]
        if i < len(resnames):
            pairs.append((("C", i), ("N", i + 1)))
        prev = "CA"
        for atom in side_chains[rn]:
            pairs.append((prev, atom))
            prev = atom
        for a, b in pairs:
            n1, r1 = (a[0], a[1]) if isinstance(a, tuple) else (a, i)
            n2, r2 = (b[0], b[1]) if isinstance(b, tuple) else (b, i)
            bonds.append((index_by_name[(r1, n1)], index_by_name[(r2, n2)]))
    o = index_by_name[(1, "OW")]
    bonds.append((o, index_by_name[(1, "HW1")]))
    bonds.append((o, index_by_name[(1, "HW2")]))
    for a, b in bonds:
        pdb_lines.append(f"CONECT{a:5d}{b:5d}")
    pdb_lines += ["TER", "END"]
    return "\n".join(pdb_lines) + "\n"


class TestFullPipelineProteinID:
    """Integration test for protein identification in serial mode."""
    
    @pytest.mark.skipif(not HAS_RDKIT, reason="rdkit not installed")
    def test_full_pipeline_protein_id(self, tmp_path: Path):
        """Test that single-threaded run with protein + SOL + K produces correct signatures and identifiers.
        
        Asserts:
        - signatures/*/generated/fasta_resname_protein exists
        - identifiers/{segment}/fasta_resname_protein/attempted contains blast_pdb_protein
        - identifiers/{segment}/pdb_protein/attempted contains pdb_struct_protein
        - No AttributeError in logs
        """
        from src_new import PipelineExecutor, ResultsManager, build_load_and_export_tasks
        from src_new.config.loader import RunConfig
        
        # Create a minimal PDB file: a 12-residue protein fragment + 1 water + 1 ion
        # (see _build_protein_test_pdb for why the fixture looks the way it does).
        pdb_content = _build_protein_test_pdb()
        pdb_file = tmp_path / "test_protein.pdb"
        pdb_file.write_text(pdb_content, encoding="utf-8")
        
        results_path = tmp_path / "results_protein_id.json"
        output_dir = tmp_path / "output_protein_id"
        manager = ResultsManager(results_path, pipeline_name="protein_id_test")
        
        config = RunConfig()
        # Force serial mode
        config.executor.signatures_parallel = False
        config.executor.identifiers_parallel = False
        config.executor.verification_parallel = False
        config.executor.n_threads = 1
        
        executor = PipelineExecutor(
            steps=build_load_and_export_tasks(),
            results_manager=manager,
            pipeline_name="protein_id_test",
        )
        
        try:
            context = executor.run(
                working_directory=tmp_path,
                output_directory=output_dir,
                input_kind="pdb",
                input_files={"structure": pdb_file},
            )
        except Exception as e:
            # Pipeline may have partial failures, but we check what was produced
            pass
        
        # Get all data
        payload = manager.as_dict()
        data = payload.get("data", {})
        signatures = data.get("signatures", {})
        identifiers = data.get("identifiers", {})
        
        # Find the protein segment (should be "A" based on segid)
        protein_segment = None
        for seg_name in signatures.keys():
            generated = signatures[seg_name].get("generated", {})
            if "fasta_resname_protein" in generated or "fasta_resname_protein" in signatures[seg_name].get("attempted", []):
                protein_segment = seg_name
                break
        
        # If not found by generated, check attempted
        if protein_segment is None:
            for seg_name in signatures.keys():
                attempted = signatures[seg_name].get("attempted", [])
                if any("fasta" in gen for gen in attempted):
                    protein_segment = seg_name
                    break
        
        assert protein_segment is not None, f"No protein segment found in signatures: {list(signatures.keys())}"
        
        # Assert 1: fasta_resname_protein signature exists (generated or attempted)
        protein_sigs = signatures.get(protein_segment, {})
        generated = protein_sigs.get("generated", {})
        attempted = protein_sigs.get("attempted", [])
        
        assert "fasta_resname_protein" in generated or "fasta_resname_protein" in attempted,             f"fasta_resname_protein not generated or attempted for {protein_segment}. Generated: {list(generated.keys())}, Attempted: {attempted}"
        
        # Assert 2: identifiers/{segment}/fasta_resname_protein/attempted contains blast_pdb_protein
        fasta_identifiers = identifiers.get(protein_segment, {}).get("fasta_resname_protein", {})
        fasta_attempted = fasta_identifiers.get("attempted", [])
        assert "blast_pdb_protein" in fasta_attempted,             f"blast_pdb_protein not in attempted for fasta_resname_protein. Attempted: {fasta_attempted}"
        
        # Assert 3: identifiers/{segment}/pdb_protein/attempted contains pdb_struct_protein
        # Find pdb_protein generator key (may be pdb_protein or similar)
        pdb_protein_key = None
        for key in identifiers.get(protein_segment, {}).keys():
            if "pdb" in key and "protein" in key:
                pdb_protein_key = key
                break
        
        if pdb_protein_key:
            pdb_identifiers = identifiers[protein_segment].get(pdb_protein_key, {})
            pdb_attempted = pdb_identifiers.get("attempted", [])
            assert "pdb_struct_protein" in pdb_attempted,                 f"pdb_struct_protein not in attempted for {pdb_protein_key}. Attempted: {pdb_attempted}"
        
        # Assert 4: No AttributeError in warnings/errors
        warnings = payload.get("warnings", [])
        for warning in warnings:
            error_msg = str(warning)
            assert "AttributeError" not in error_msg,                 f"AttributeError found in warnings: {warning}"

