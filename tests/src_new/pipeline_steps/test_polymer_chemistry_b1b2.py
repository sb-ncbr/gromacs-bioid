"""W3 B1/B2 (BH-042/BH-043): polymer segments get no chemistry signatures.

Production evidence (structural gate B-01): 17 polymer-typed segments
(P03 protein x12, P16 I_1 DNA, P17 E_1/F_1, P26) carried SMILES/InChI/
SELFIES signatures and were fed to chemistry resolvers — wasted budget
and noise-source. Polymers must route to sequence/structure resolvers
only. The `chemistry_skipped_size` warning exists for NON-polymer
molecules above the atom cap (M12 class); a polymer has no chemistry
signatures BY DESIGN, so warning on it is wrong, and it must not repeat
per segment.

Acceptance pinned here:
1. generate_signatures on a protein-typed segment does not even ATTEMPT
   smiles/smiles_not_sanitized/selfies/inchi_key; a small-molecule
   segment still does.
2. chemistry_skipped_size fires only for non-polymer segments above the
   chemistry atom cap, and at most once per segment.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

MDAnalysis = pytest.importorskip("MDAnalysis")
pytest.importorskip("rdkit")
import MDAnalysis as mda


def _tiny_two_segment_universe():
    """seg A: 2x ALA residues, bonded backbone (polymer).
    seg L: 1x LIG residue (small molecule, 4 heavy atoms + explicit Hs)."""
    atom_resindex = [0] * 8 + [1] * 6 + [2] * 4 + [3] * 6
    residue_segindex = [0, 0, 1, 1]
    rest = list(zip(
        ["N", "CA", "C", "O", "CB", "H", "HA1", "HA2",           # ALA-0
         "N", "CA", "C", "OE", "CB", "HB",                       # ALA-1
         "C1", "C2", "O1", "H1", "H2", "H3", "H4", "H5", "H6", "H7"][:len(atom_resindex)]))
    names = [x[0] for x in rest]
    u = mda.Universe.empty(
        len(names), n_residues=4, n_segments=2,
        atom_resindex=atom_resindex, residue_segindex=residue_segindex,
        trajectory=True)
    u.add_TopologyAttr("names", names)
    # per-residue attrs (4 residues), per-segment attrs (2 segments)
    u.add_TopologyAttr("resids", [1, 2, 3, 4])
    u.add_TopologyAttr("resnames", ["ALA", "ALA", "LIG", "LIG"])
    u.add_TopologyAttr("segids", ["A", "L"])
    # segids are per-residue attrs in Universe.empty(..., atom_resindex,...)
    elems = (["N", "C", "C", "O", "C", "H", "H", "H",
              "N", "C", "C", "O", "C", "H",
              "C", "C", "O", "H", "H", "H", "H", "H", "H", "H"])
    u.add_TopologyAttr("elements", elems)
    bonds = [(0, 1), (1, 2), (2, 3), (1, 4), (2, 8), (8, 9), (9, 10),
             (10, 11), (9, 12), (0, 5), (1, 6), (1, 7),
             (14, 15), (15, 16), (14, 17), (14, 18), (15, 19), (16, 20),
             (17, 21), (18, 22), (18, 23)]
    u.add_TopologyAttr("bonds", bonds)
    rng = np.random.default_rng(7)
    u.load_new(rng.uniform(-10, 10, size=(1, len(names), 3)).astype(np.float32),
               format="memory")
    return u


def _ctx(tmp_path, universe, instances, warnings_sink):
    from unittest.mock import MagicMock
    from src_new.config.loader import RunConfig
    from src_new.results.results_manager import ResultsManager

    cfg = RunConfig()
    cfg.executor.signatures_parallel = False  # serial path
    results = ResultsManager(str(tmp_path / "results.json"),
                             pipeline_name="b1b2")

    facade = MagicMock()
    facade.get_segments.return_value = {"A", "L"}
    facade.get_fragment.side_effect = lambda name: universe.select_atoms(
        f"segid {name}")
    facade.get_segment_properties.return_value = SimpleNamespace(
        flags={"has_elements": True})
    store = SimpleNamespace(
        get_all_instances=lambda: instances)

    ctx = MagicMock()
    ctx.config = cfg
    ctx.results = results
    ctx.working_directory = tmp_path
    ctx.debug_directory = tmp_path
    ctx.get_value.side_effect = lambda k, *a, **kw: {
        "facade": facade, "fragment_store": store,
        "stage_deadline_epoch": None}.get(k)
    ctx.fail.side_effect = Exception("context.fail called")
    ctx.add_warning.side_effect = lambda code, msg, details=None: (
        warnings_sink.append((code, msg)))
    return ctx, results


def _inst(seg, mtype, atom_count, resids=None):
    from src_new.molecules.instances import MoleculeInstance, MoleculeType
    return MoleculeInstance(
        instance_id=f"inst-{seg}", segment_ids=[seg],
        molecule_type=MoleculeType(mtype), atom_count=atom_count,
        resids=list(resids) if resids else [])


class TestPolymerChemistrySuppression:
    def test_polymer_segment_skips_chemistry_generators(self, tmp_path):
        from src_new.pipeline_steps import _generate_signatures
        from src_new.molecules.instances import MoleculeType
        u = _tiny_two_segment_universe()
        warns: list = []
        ctx, results = _ctx(tmp_path, u, [
            _inst("A", MoleculeType.PROTEIN, 14,
                  resids=[1, 2, 3, 4, 5, 6]),  # real polymer (>5 res)
            _inst("L", MoleculeType.SMALL_MOLECULE, 10),
        ], warns)
        _generate_signatures(ctx)
        attempted_a = set(results.get_data("signatures/A/attempted") or [])
        attempted_l = set(results.get_data("signatures/L/attempted") or [])
        for chem in ("smiles", "smiles_not_sanitized", "selfies",
                     "inchi_key"):
            assert chem not in attempted_a, (chem, "attempted on polymer",
                                             attempted_a)
        # non-chemistry generators still ran on the polymer (the stage
        # did not blanket-skip the segment)
        assert attempted_a & {"name_molecule", "resname", "name_chain",
                              "mmcif", "sequence", "fasta"}, attempted_a
        assert "smiles" in attempted_l or "inchi_key" in attempted_l, (
            attempted_l)
        gen_a = set(results.get_data("signatures/A/generated") or {})
        assert not ({"smiles", "smiles_not_sanitized", "selfies",
                     "inchi_key"} & gen_a), gen_a

    def test_chemistry_skipped_size_only_non_polymer_and_once(self, tmp_path):
        """BH-043: the sizeable-molecule skip warning is meaningless for
        polymers (no chemistry by design) and must not duplicate."""
        from src_new.pipeline_steps import _generate_signatures
        from src_new.molecules.instances import MoleculeType
        u = _tiny_two_segment_universe()
        warns: list = []
        ctx, results = _ctx(tmp_path, u, [
            _inst("A", MoleculeType.PROTEIN, 14,
                  resids=[1, 2, 3, 4, 5, 6]),  # real polymer (>5 res)
            _inst("L", MoleculeType.SMALL_MOLECULE, 10),
        ], warns)
        ctx.config.signatures.smiles_maximum_number_of_atoms = 3  # both over
        _generate_signatures(ctx)
        size_warns = [w for w in warns if w[0] == "chemistry_skipped_size"]
        assert not any("A" in str(w[1]) for w in size_warns), (
            "polymer must not get chemistry_skipped_size", size_warns)
        lig_warns = [w for w in size_warns if "L" in str(w[1])]
        assert len(lig_warns) == 1, size_warns
