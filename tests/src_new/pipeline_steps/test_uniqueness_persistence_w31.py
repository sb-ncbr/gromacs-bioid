"""W3.1 item 3 (A7/A6): persistence regressions — uniqueness keys.

Reviewer audit (bioid_bughunt/W3_AUDIT_AND_TEST_STRATEGY.md §3 item 3):
- the per-unique key is INERT: `build_signature_snapshot` copies
  whole-UNIVERSE bond indices, so two physical copies of the same
  molecule never share a group key — F14 ran per-copy chemistry
  (generate_signatures 993 s vs the 120 s budget);
- no stereo signature: R- and S-ibuprofen in one system collapse into
  ONE unique group, so the S copies silently reuse the R signatures.

Fix contract (implemented in src_new after this file went RED):
1. fragment-local bond renumbering in `build_signature_snapshot`;
2. a cheap stereo tag (signed tetrahedral volume at each stereocentre
   candidate with canonically ranked neighbours) in the group key;
3. `_propagate_group_identifiers` stays correct (member inherits the
   representative's identifiers with `_shared_with`) and runs inside
   the deferred-writes window (pinned by the offline sweep timings).

Harness: REAL pipeline pieces only — RDKit-generated molecular geometry
(embedded, real coordinates) loaded into MDAnalysis universes, real
`LoadedUniverse` facades, `FragmentStore` instances, the production
`build_signature_snapshot`, `_snapshot_group_key`, the real signature
worker, `_group_segments` and `_propagate_group_identifiers` on real
ResultsManagers. No monkeypatching.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

MDAnalysis = pytest.importorskip("MDAnalysis")
rdkit = pytest.importorskip("rdkit")

import numpy as np
import MDAnalysis as mda
from MDAnalysis.core.topologyattrs import Bonds

try:
    from MDAnalysis.memory import MemoryReader  # noqa: F401
    _HAS_MEMORY = True
except Exception:  # pragma: no cover
    _HAS_MEMORY = False

from src_new.config.loader import RunConfig
from src_new.loader.universe_facade import LoadedUniverse
from src_new.loader.fragment_store import FragmentStore
from src_new.results.results_manager import ResultsManager
from src_new.signatures.snapshot import build_signature_snapshot
from src_new.pipeline_steps import (
    _snapshot_group_key,
    _group_segments,
    _propagate_group_identifiers,
)

IBUPROFEN_R = "CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O"
IBUPROFEN_S = "CC(C)Cc1ccc(cc1)[C@H](C)C(=O)O"
_MASSES = {"C": 12.011, "H": 1.008, "N": 14.007, "O": 15.999, "S": 32.06,
           "F": 18.998, "Cl": 35.45, "Br": 79.90, "P": 30.974}


def _embedded_coords(smiles: str, seed: int = 0xC0FFEE):
    """RDKit 3D geometry for a real molecule: names, elements, bonds,
    coordinates (Å)."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.MolFromSmiles(smiles)
    assert mol is not None
    mol = Chem.AddHs(mol)
    ps = AllChem.ETKDGv3()
    ps.randomSeed = seed
    assert AllChem.EmbedMolecule(mol, ps) == 0
    conf = mol.GetConformer()
    names, elements, pos = [], [], np.zeros((mol.GetNumAtoms(), 3))
    for i, atom in enumerate(mol.GetAtoms()):
        sym = atom.GetSymbol()
        names.append(f"{sym}{i + 1}")
        elements.append(sym)
        p = conf.GetAtomPosition(i)
        pos[i] = (p.x, p.y, p.z)
    bonds = [(b.GetBeginAtomIdx(), b.GetEndAtomIdx()) for b in mol.GetBonds()]
    return names, elements, bonds, pos


def _system_universe(mols) -> mda.Universe:
    """A REAL MDAnalysis universe carrying several molecules (one segid
    each) — copies/enantiomers live in ONE system, exactly like the
    audit's 'R + S in one system' probe. Each mol is a dict with names,
    elements, bonds (LOCAL indices), positions, segid, offset."""
    n_atoms_total = sum(len(m["names"]) for m in mols)
    atom_resindex = np.concatenate([
        np.full(len(m["names"]), i, dtype=int) for i, m in enumerate(mols)])
    residue_segindex = np.arange(len(mols), dtype=int)
    u = mda.Universe.empty(n_atoms=n_atoms_total, n_residues=len(mols),
                           n_segments=len(mols),
                           atom_resindex=atom_resindex,
                           residue_segindex=residue_segindex,
                           trajectory=True)
    names, types_, elements = [], [], []
    resnames, resids, segids, chain_ids, masses = [], [], [], [], []
    pos = np.zeros((n_atoms_total, 3))
    bond_list = []
    offset_atoms = 0
    for i, m in enumerate(mols):
        k = len(m["names"])
        names.extend(m["names"])
        types_.extend(m["elements"])
        elements.extend(m["elements"])
        resnames.append("LIG")
        resids.append(i + 1)
        segids.append(m["segid"])
        chain_ids.extend([m["segid"]] * k)
        masses.extend(_MASSES.get(e, 12.0) for e in m["elements"])
        pos[offset_atoms:offset_atoms + k] = (
            np.asarray(m["positions"], dtype=float)
            + np.asarray(m.get("offset", (0.0, 0.0, 0.0)), dtype=float))
        bond_list.extend(
            (int(a) + offset_atoms, int(b) + offset_atoms)
            for a, b in m["bonds"])
        offset_atoms += k
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("types", types_)
    u.add_TopologyAttr("elements", elements)
    u.add_TopologyAttr("resnames", resnames)
    u.add_TopologyAttr("resids", resids)
    u.add_TopologyAttr("segids", segids)
    u.add_TopologyAttr("chainIDs", chain_ids)
    u.add_TopologyAttr("masses", masses)
    u.add_TopologyAttr(Bonds(bond_list))
    u.load_new(pos, format="memory")
    return u


def _mol(names, elements, bonds, positions, segid, offset=(0.0, 0.0, 0.0)):
    return {"names": names, "elements": elements, "bonds": bonds,
            "positions": positions, "segid": segid, "offset": offset}


def _facade(u) -> tuple[LoadedUniverse, dict]:
    from src_new.input.models import LoadDecision
    from src_new.loader.repair import RepairReport
    cfg = RunConfig()
    rmgr = ResultsManager(
        str(Path(tempfile.mkdtemp(prefix="w31item3_")) / "rm.json"), "w31item3")
    decision = LoadDecision(input_kind=None, selected_strategy="synthetic")
    facade = LoadedUniverse(universe=u, decision=decision,
                            repair_report=RepairReport(),
                            results=rmgr, enhanced_nucleic_recognition=False)
    store = FragmentStore(facade, rmgr)
    s2i = {}
    for inst in store.get_all_instances():
        if inst.segment_ids:
            s2i.setdefault(inst.segment_ids[0], inst)
    return facade, s2i


def _snapshots_for(u) -> dict:
    facade, s2i = _facade(u)
    out = {}
    for seg in sorted(facade.get_segments()):
        inst = s2i.get(seg)
        if inst is None:
            continue
        out[seg] = build_signature_snapshot(
            seg, facade.get_fragment(seg), inst, facade)
    return out


class TestA6FragmentLocalKeys:
    def test_identical_copies_share_group_key(self):
        """Two physical copies of the same molecule (translated) must
        share the per-unique snapshot group key — universe-level bond
        indices made this key differ per copy (dedup inert; F14's
        generate_signatures ran per-copy chemistry)."""
        names, els, bonds, pos = _embedded_coords("CCO")  # ethanol
        u = _system_universe([
            _mol(names, els, bonds, pos, "A"),
            _mol(names, els, bonds, pos, "B", offset=(25.0, 0.0, 0.0))])
        snaps = _snapshots_for(u)
        assert len(snaps) == 2, f"expected one snapshot per copy: {list(snaps)}"
        k1, k2 = (_snapshot_group_key(s) for s in snaps.values())
        assert k1 == k2, (
            f"copies of one molecule must share the group key:\n{k1}\nvs\n{k2}")

    def test_enantiomers_split_group_key(self):
        """R- vs S-ibuprofen must land in DIFFERENT unique groups — without
        a stereo signature both copies of a mixed system silently reuse
        the first enantiomer's signatures (audit: 'a test mixing
        ibuprofen R + S in one system -> 2 groups')."""
        names_r, els_r, bonds_r, pos_r = _embedded_coords(IBUPROFEN_R)
        names_s, els_s, bonds_s, pos_s = _embedded_coords(IBUPROFEN_S)
        assert bonds_r == bonds_s and els_r == els_s, (
            "enantiomer SMILES must differ only in parity")
        # one molecule per universe: identical graph, names, elements,
        # residue data — the ONLY difference is the stereocentre parity,
        # so this test isolates the missing stereo signature (in a shared
        # universe the bond-index defect would split them anyway).
        u_r = _system_universe([_mol(names_r, els_r, bonds_r, pos_r, "A")])
        u_s = _system_universe([_mol(names_s, els_s, bonds_s, pos_s, "B")])
        snaps = {}
        for u in (u_r, u_s):
            snaps.update(_snapshots_for(u))
        assert len(snaps) == 2, f"expected one snapshot per enantiomer: {list(snaps)}"
        k_r, k_s = (_snapshot_group_key(s) for s in snaps.values())
        assert k_r != k_s, "R and S ibuprofen must not share a unique group"

    def test_translation_and_proper_rotation_invariant(self):
        """The key must be geometry-invariant under translation and
        proper rotation (it is not a shape hash)."""
        names, els, bonds, pos = _embedded_coords("CCO")
        rng = np.random.default_rng(7)
        m = rng.normal(size=(3, 3))
        q, r = np.linalg.qr(m)
        q = q @ np.diag(np.sign(np.diag(r)))
        if np.linalg.det(q) < 0:
            q[:, 0] = -q[:, 0]
        pos_rot = pos @ q.T + np.array([5.0, -7.0, 11.0])
        u = _system_universe([
            _mol(names, els, bonds, pos, "A"),
            _mol(names, els, bonds, pos_rot, "B")])
        snaps = _snapshots_for(u)
        k1, k2 = (_snapshot_group_key(s) for s in snaps.values())
        assert k1 == k2, "rigid motion must not change the group key"


class TestBudgetHitKeepsPartials:
    def test_generate_signatures_budget_cut_keeps_partial_signatures(
            self, tmp_path, monkeypatch):
        """Audit §3 item 3: a stage-budget hit must MERGE whatever was
        generated (partial signatures persist). Real executor on a real
        deposit: M05 (generate_signatures ~2.4 s over 4 grouped reps) with
        a 1 s budget — the cut always fires mid-generation, so the merge
        must still persist the first segment's partial signatures.

        Pre-fix behaviour this pins against: the merge loop re-checked
        the exhausted generation deadline and discarded EVERY partial
        (2 s of chemistry computed, 0 signatures persisted)."""
        import json
        import shutil
        from src_new.executor.executor import PipelineExecutor
        from src_new.results.results_manager import ResultsManager
        import importlib
        w31 = importlib.import_module(
            "tests.src_new.loader.test_chainless_topology_w31")

        case = Path("/home/tomsko/work/bat3_article_reviews/bioid_bughunt/"
                    "testcases/M05_nucleosome_ligand_amber/input")
        if not case.is_dir():  # corpus not mounted: skip, not fail
            pytest.skip("corpus deposit not available")
        monkeypatch.setenv("VALIDATION_STAGE_BUDGETS",
                           '{"generate_signatures": 1.0}')
        work = tmp_path / "input"
        shutil.copytree(case, work)
        results_path = tmp_path / "results.json"
        manager = ResultsManager(str(results_path), pipeline_name="w31b")
        executor = PipelineExecutor(steps=w31._stage_steps(),
                                    results_manager=manager,
                                    pipeline_name="w31b")
        executor.run(working_directory=work,
                     output_directory=tmp_path / "out",
                     input_kind="pdb",
                     input_files={p.name: p for p in work.iterdir()})
        payload = json.loads(results_path.read_text())
        assert payload["pipeline"]["status"] == "success", (
            payload.get("critical_errors"))
        # the cut is RECORDED ...
        all_warnings = (payload.get("warnings")
                        or payload.get("pipeline", {}).get("warnings")
                        or [])
        warn_codes = [w.get("code") for w in all_warnings]
        assert "stage_time_budget" in warn_codes, (
            f"budget cut not recorded: {warn_codes}")
        # ... and the PARTIALS survive: the budget fired mid-generation
        # (the full stage needs ~2.4 s > 1 s), so at least the first
        # segment's signatures must have been merged, never wiped
        sigs = payload.get("data", {}).get("signatures") or {}
        assert len(sigs) >= 1, (
            "budget cut discarded the partial signatures that were "
            "already generated")


class TestA7PropagationContract:
    def test_members_inherit_rep_identifiers(self, tmp_path):
        """`_propagate_group_identifiers` on a REAL ResultsManager: group
        members get the representative's payload with `_shared_with`."""
        rmgr = ResultsManager(str(tmp_path / "rm.json"), "w31item3a7")
        payload = {"inchi_key": "QEIXBHNVLUSZPT-UHFFFAOYSA-N",
                   "name_molecule": "ibuprofen"}
        rmgr.set_data("identifiers/SYSTEM__A", payload)
        rep_to_group = [
            ("SYSTEM__A", ["SYSTEM__A", "SYSTEM__B"],
             ("small", "QEIXBHNVLUSZPT-UHFFFAOYSA-N")),
        ]
        copied = _propagate_group_identifiers(rmgr, rep_to_group)
        assert copied == 1
        shared = rmgr.get_data("identifiers/SYSTEM__B")
        assert shared and shared.get("_shared_with") == "SYSTEM__A"
        assert shared.get("inchi_key") == payload["inchi_key"]

    def test_real_worker_payloads_group_and_propagate(self, tmp_path):
        """End-to-end A7 contract on REAL generated payloads: two copies
        of one molecule (real signature worker output, inchi_key path)
        form ONE identify group and the member inherits the rep's
        identifiers. Guards the propagation move into _deferred_writes."""
        names, els, bonds, pos = _embedded_coords("CCO")
        u = _system_universe([
            _mol(names, els, bonds, pos, "A"),
            _mol(names, els, bonds, pos, "B", offset=(25.0, 0.0, 0.0))])
        from src_new.pipeline_steps.workers import _generate_signatures_worker
        cfg = RunConfig()
        items = []
        for seg, snap in _snapshots_for(u).items():
            w = _generate_signatures_worker((snap.__dict__, cfg.to_dict()))
            assert not w.get("errors"), w.get("errors")
            items.append((seg, w.get("generated") or {}))
        reps, member_map, rep_to_group = _group_segments(items)
        assert len(reps) == 1, (
            f"two copies of ethanol must form one group: {rep_to_group}")
        rmgr = ResultsManager(str(tmp_path / "rm2.json"), "w31item3a7b")
        for gen_seg, gen in items:
            rmgr.set_data(f"identifiers/{gen_seg}", dict(gen))
        copied = _propagate_group_identifiers(rmgr, rep_to_group)
        assert copied >= 1
        rep, members, _gk = rep_to_group[0]
        for m in members[1:]:
            shared = rmgr.get_data(f"identifiers/{m}")
            assert shared and shared.get("_shared_with") == rep
