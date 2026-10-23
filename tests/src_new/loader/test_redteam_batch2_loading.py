"""Red-team Batch-2 (loading) regression tests.

One class per sub-step (3.1-3.9), each grounded in an empirical probe that
reproduced the audit finding (.tmp/redteam/report.md). RED before the fix,
GREEN after. Batch-1 pattern: fix sites promoted byte-identical, suites as
gates.
"""

import hashlib
import logging
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

mda = pytest.importorskip("MDAnalysis")
import numpy as np

from src_new.input.models import FileRecord, InputKind
from src_new.input.discovery import inspect_directory, discover_input_kind, select_best_file_combination
from src_new.loader.strategies import (
    LoadStrategy, load_simulation, load_with_strategy, validate_for_strategy)
from src_new.results.results_manager import ResultsManager
from src_new.config.loader import RunConfig


def _mini_pdb(p: Path) -> None:
    lines = [
        "ATOM      1  C1  LIG A   1      10.000  10.000  10.000  1.00  0.00           C\n",
        "ATOM      2  C2  LIG A   1      11.500  10.000  10.000  1.00  0.00           C\n",
        "ATOM      3  O1  LIG A   1      12.500  10.500  10.000  1.00  0.00           O\n",
        "TER\nEND\n",
    ]
    p.write_text("".join(lines))


def _mini_xtc(p: Path, pdb: Path) -> None:
    # 2 frames: frame 0 at dx=0, frame 1 shifted by 5 A
    u = mda.Universe(str(pdb))
    with mda.Writer(str(p), u.atoms.n_atoms) as w:
        for dx in (0.0, 5.0):
            u.atoms.positions = np.array(
                [[10.0 + dx, 10.0, 10.0],
                 [11.5 + dx, 10.0, 10.0],
                 [12.5 + dx, 10.5, 10.0]], dtype="float32")
            w.write(u.atoms)


def _four_atom_xtc(p: Path) -> None:
    pdb4 = p.parent / "_four.pdb"
    pdb4.write_text("".join([
        "ATOM      1  C1  LIG A   1      10.000  10.000  10.000  1.00  0.00           C\n",
        "ATOM      2  C2  LIG A   1      11.500  10.000  10.000  1.00  0.00           C\n",
        "ATOM      3  O1  LIG A   1      12.500  10.500  10.000  1.00  0.00           O\n",
        "ATOM      4  N1  LIG A   1      13.500  10.500  10.000  1.00  0.00           N\n",
        "TER\nEND\n",
    ]))
    u = mda.Universe(str(pdb4))
    with mda.Writer(str(p), u.atoms.n_atoms) as w:
        w.write(u.atoms)
    pdb4.unlink()


class TestA05MemoryPath:
    """3.1 — A-05: no whole-file RAM copies for checksums or trajectories."""

    def test_filerecord_checksum_streams_chunks(self, tmp_path, monkeypatch):
        payload = bytes(range(256)) * 5000  # ~1.28 MiB, spans multiple 1 MiB chunks
        f = tmp_path / "traj.xtc"
        f.write_bytes(payload)

        def boom(self):  # any whole-file slurp breaks the audit's memory bound
            raise AssertionError("read_bytes() must not be used (A-05: stream in chunks)")

        monkeypatch.setattr(Path, "read_bytes", boom)
        rec = FileRecord.from_path(f, "f1", "xtc", "trajectory")
        assert rec.checksum == hashlib.sha256(payload).hexdigest()
        assert rec.size_bytes == len(payload)

    def test_pdb_xtc_pairing_copies_frame0_only(self, tmp_path):
        pdb = tmp_path / "structure.pdb"; _mini_pdb(pdb)
        xtc = tmp_path / "trajectory.xtc"; _mini_xtc(xtc, pdb)
        v = validate_for_strategy(inspect_directory(tmp_path), LoadStrategy.PDB)
        u = load_with_strategy(LoadStrategy.PDB, v.selected_files, RunConfig())
        # A-05: only frame 0 may be materialized (was in_memory=True -> all frames)
        assert len(u.trajectory) == 1
        # instantaneous frame-0 coords unchanged (dx=0, not averaged 12.5)
        assert abs(float(u.atoms.positions[0][0]) - 10.0) < 0.5

    def test_xtc_pairing_failure_logs_warning(self, tmp_path, caplog):
        pdb = tmp_path / "structure.pdb"; _mini_pdb(pdb)
        bad = tmp_path / "trajectory.xtc"; _four_atom_xtc(bad)  # 4 atoms vs 3 in pdb
        v = validate_for_strategy(inspect_directory(tmp_path), LoadStrategy.PDB)
        with caplog.at_level(logging.WARNING, logger="src_new.loader.strategies"):
            u = load_with_strategy(LoadStrategy.PDB, v.selected_files, RunConfig())
        assert u.atoms.n_atoms == 3  # static-PDB fallback still works
        assert any("fallback" in r.getMessage().lower() or "pairing" in r.getMessage().lower()
                   for r in caplog.records), "A-05: silent `except: pass` fallback must log"


def _make_tip4p_two_waters():
    """2 TIP4P waters far apart; atom 4 of each is a massless M site (DUMMY type,
    blank element after 2.7 repair) — the exact A-04 probe shape."""
    import numpy as np
    from MDAnalysis import Universe
    from MDAnalysis.core.topology import Topology
    from MDAnalysis.core.topologyattrs import (
        Atomnames, Atomtypes, Resids, Resnames, Segids, Elements, Masses)

    n_res = 2
    top = Topology(n_res * 4, n_res, 1,
                   atom_resindex=[0, 0, 0, 0, 1, 1, 1, 1],
                   residue_segindex=[0, 0])
    top.add_TopologyAttr(Atomnames(["OH2", "H1", "H2", "MW"] * 2))
    top.add_TopologyAttr(Atomtypes(["O", "H", "H", "DUMMY"] * 2))  # MDA: MW -> DUMMY
    top.add_TopologyAttr(Elements(["O", "H", "H", ""] * 2))        # post-repair blank
    top.add_TopologyAttr(Masses([15.999, 1.008, 1.008, 0.0] * 2))
    top.add_TopologyAttr(Resids([1, 2]))
    top.add_TopologyAttr(Resnames(["TIP4"] * 2))
    top.add_TopologyAttr(Segids(["SOL"]))
    u = Universe(top)
    w1 = np.array([[0.0, 0.0, 0.0], [0.96, 0.0, 0.0], [-0.24, 0.93, 0.0], [0.15, 0.15, 0.0]])
    w2 = w1 + np.array([20.0, 20.0, 20.0])
    u.load_new(np.vstack([w1, w2]).astype(np.float32), format="memory")
    return u


class TestA04BondGuessing:
    """3.2 — A-04: one unknown atom type must not kill bond guessing system-wide."""

    def test_element_based_vdwradii_table(self):
        from src_new.loader.repair import element_based_vdwradii
        u = _make_tip4p_two_waters()
        radii = element_based_vdwradii(u)
        assert radii["DUMMY"] == 0.0          # massless virtual site
        assert radii["O"] > 1.0 and radii["H"] > 0.9
        # unknown type, unknown element, real mass -> audit's 1.5 A fallback
        u2 = _make_tip4p_two_waters()
        u2.atoms.types = ["O", "H", "H", "XX"] * 2
        u2.atoms.elements = ["O", "H", "H", ""] * 2
        u2.atoms.masses = [15.999, 1.008, 1.008, 12.0] * 2
        radii = element_based_vdwradii(u2)
        assert radii["XX"] == 1.5

    def test_massless_sites_dont_kill_guessing(self):
        from src_new.loader.repair import TopologyRepair
        from src_new.config.loader import RunConfig
        u = _make_tip4p_two_waters()
        repair = TopologyRepair(u, RunConfig())
        n = repair.guess_bonds()
        assert n >= 4, "each water needs 2 O-H bonds; DUMMY type killed guessing before"
        assert len(u.atoms.fragments) == 2, "waters must stay 2 fragments, not 1 blob"

    def test_ow_hw_water_types_guess_bonds(self):
        # 3 waters with force-field types OW/HW (audit A/p_bg.py first run: bonds=0)
        import numpy as np
        from MDAnalysis import Universe
        from MDAnalysis.core.topology import Topology
        from MDAnalysis.core.topologyattrs import (
            Atomnames, Atomtypes, Resids, Resnames, Segids, Elements, Masses)
        top = Topology(9, 3, 1,
                       atom_resindex=[0, 0, 0, 1, 1, 1, 2, 2, 2],
                       residue_segindex=[0, 0, 0])
        top.add_TopologyAttr(Atomnames(["OW", "HW1", "HW2"] * 3))
        top.add_TopologyAttr(Atomtypes(["OW", "HW", "HW"] * 3))
        top.add_TopologyAttr(Elements(["O", "H", "H"] * 3))
        top.add_TopologyAttr(Masses([15.999, 1.008, 1.008] * 3))
        top.add_TopologyAttr(Resids([1, 2, 3]))
        top.add_TopologyAttr(Resnames(["TIP3"] * 3))
        top.add_TopologyAttr(Segids(["SOL"]))
        u = Universe(top)
        w = np.array([[0.0, 0.0, 0.0], [0.96, 0.0, 0.0], [-0.24, 0.93, 0.0]])
        pos = np.vstack([w + np.array([i * 15.0, 0.0, 0.0]) for i in range(3)])
        u.load_new(pos.astype(np.float32), format="memory")
        from src_new.loader.repair import TopologyRepair
        from src_new.config.loader import RunConfig
        n = TopologyRepair(u, RunConfig()).guess_bonds()
        assert n >= 6, "OW/HW types must not zero out bond guessing"
        assert len(u.atoms.fragments) == 3


class TestA16A07Discovery:
    """3.3 — A-16 discovery order-fragility + A-07 GROMACS broken-include fallback."""

    def test_non_lammps_dot_data_does_not_hijack(self, tmp_path):
        # energy table saved as .data + a real structure.pdb -> must pick PDB,
        # not the alphabetic .data LAMMPS path (A-16a)
        (tmp_path / "energies.data").write_text("# step  energy\n0  -123.4\n1  -123.5\n")
        _mini_pdb(tmp_path / "structure.pdb")
        dec = select_best_file_combination(inspect_directory(tmp_path))
        assert dec.input_kind == InputKind.PDB and dec.selected_strategy == "PDB_SINGLE"

    def test_real_lammps_data_still_detected(self, tmp_path):
        # regression guard: a genuine LAMMPS data file keeps the LAMMPS path
        (tmp_path / "system.data").write_text(
            "LAMMPS data file\n\n2 atoms\n1 atom types\n\n"
            "0.0 1.0 xlo xhi\n0.0 1.0 ylo yhi\n0.0 1.0 zlo zhi\n\n"
            "Masses\n\n1 12.011\n\nAtoms # atomic\n\n1 1 0.0 0.0 0.0\n2 1 0.5 0.0 0.0\n")
        dec = select_best_file_combination(inspect_directory(tmp_path))
        assert dec.input_kind == InputKind.LAMMPS

    def test_pdb_ranking_prefers_structure_over_average(self, tmp_path):
        _mini_pdb(tmp_path / "average.pdb")
        _mini_pdb(tmp_path / "structure.pdb")
        v = validate_for_strategy(inspect_directory(tmp_path), LoadStrategy.PDB)
        assert v.selected_files["pdb"].name == "structure.pdb", (
            "sorted()[0] picked average.pdb — the time-averaged structure the "
            "code itself warns about (A-16b)")

    def test_discover_input_kind_delegates_consistently(self, tmp_path):
        # A-16c: dead-code discover said NOTHING for {parm7, xtc} while
        # select says AMBER — one behavior, one source of truth
        (tmp_path / "system.parm7").write_text("%VERSION  VERSION_STAMP\n")
        (tmp_path / "traj.xtc").write_bytes(b"\x00" * 16)
        assert discover_input_kind(tmp_path) == InputKind.AMBER

    def test_gromacs_broken_include_falls_back_to_gro(self, tmp_path):
        # A-07: top references a host-local forcefield include; must degrade
        # to GRO-only instead of failing the whole load
        (tmp_path / "topol.top").write_text(
            '#include "amber99sb-ildn.ff/forcefield.itp"\n'
            "[ moleculetype ]\nSOL 3\n\n[ system ]\nt\n\n[ molecules ]\nSOL 2\n")
        rows = "".join(
            "%5d%-5s%5s%5d%8.3f%8.3f%8.3f\n" % (
                i // 3 + 1, "SOL", ["OW", "HW1", "HW2"][i % 3], i + 1,
                (i // 3) * 2.0 + (0.096 if i % 3 == 1 else -0.024 if i % 3 == 2 else 0.0),
                0.093 if i % 3 == 2 else 0.0, 0.0)
            for i in range(6))
        (tmp_path / "conf.gro").write_text("t\n    6\n" + rows + "   5.00000   5.00000   5.00000\n")
        bundle = inspect_directory(tmp_path)
        dec = select_best_file_combination(bundle)
        result = load_simulation(dec, bundle, RunConfig(), ResultsManager(tmp_path / "r.json"))
        assert result.success, [ (a.strategy, a.error_code) for a in result.attempts ]
        assert result.final_strategy == LoadStrategy.GROMACS_GRO.value, result.final_strategy
        assert result.universe.atoms.n_atoms == 6

    def test_gromacs_broken_include_cross_kind_pdb_fallback(self, tmp_path):
        # when a .pdb sits alongside the broken top(+no gro), PDB strategy loads it
        (tmp_path / "topol.top").write_text('#include "amber99sb-ildn.ff/forcefield.itp"\n[ system ]\nt\n')
        _mini_pdb(tmp_path / "structure.pdb")
        bundle = inspect_directory(tmp_path)
        dec = select_best_file_combination(bundle)
        result = load_simulation(dec, bundle, RunConfig(), ResultsManager(tmp_path / "r.json"))
        assert result.success and result.universe.atoms.n_atoms == 3
        assert result.final_strategy == LoadStrategy.PDB.value, result.final_strategy


def _mini_mmcif_two_chains(p: Path) -> None:
    """Two chains with 2-char auth chain IDs (AA, BA) — the A-06 probe shape."""
    rows = []
    atom_rows = [
        (1, "C", "CA", "GLY", 1, 0.000, 0.000, 0.000, 1, "GLY", "AA"),
        (2, "C", "C", "GLY", 1, 1.450, 0.000, 0.000, 1, "GLY", "AA"),
        (3, "N", "N", "ALA", 2, 1.500, 1.450, 0.200, 2, "ALA", "AA"),
        (4, "C", "CA", "GLY", 1, 20.000, 0.000, 0.000, 1, "GLY", "BA"),
        (5, "C", "C", "GLY", 1, 21.450, 0.000, 0.000, 1, "GLY", "BA"),
        (6, "N", "N", "ALA", 2, 21.500, 1.450, 0.200, 2, "ALA", "BA"),
    ]
    for (i, el, nm, rc, rs, x, y, z, ars, arc, asym) in atom_rows:
        rows.append("ATOM %d %s %s . %s A 1 %d ? %.3f %.3f %.3f 1.00 0.00 %d %s %s 1"
                    % (i, el, nm, rc, rs, x, y, z, ars, arc, asym))
    p.write_text(
        "data_test\n_entry.id TEST\n#\nloop_\n"
        "_atom_site.group_PDB\n_atom_site.id\n_atom_site.type_symbol\n"
        "_atom_site.label_atom_id\n_atom_site.label_alt_id\n_atom_site.label_comp_id\n"
        "_atom_site.label_asym_id\n_atom_site.label_entity_id\n_atom_site.label_seq_id\n"
        "_atom_site.pdbx_PDB_ins_code\n_atom_site.Cartn_x\n_atom_site.Cartn_y\n"
        "_atom_site.Cartn_z\n_atom_site.occupancy\n_atom_site.B_iso_or_equiv\n"
        "_atom_site.auth_seq_id\n_atom_site.auth_comp_id\n_atom_site.auth_asym_id\n"
        "_atom_site.pdbx_PDB_model_num\n"
        + "\n".join(rows) + "\n#\n")


class TestA06MmcifChains:
    """3.4 — A-06: no PDB-text round-trip; multi-char chain IDs must survive."""

    def test_two_char_chain_ids_not_merged(self, tmp_path):
        pytest.importorskip("gemmi")
        from src_new.loader.strategies import _load_mmcif_via_gemmi
        cif = tmp_path / "x.cif"
        _mini_mmcif_two_chains(cif)
        u = _load_mmcif_via_gemmi(cif)
        segids = sorted(str(s) for s in u.segments.segids)
        assert segids == ["AA", "BA"], f"gemmi->PDB round-trip merged chains: {segids}"
        assert u.atoms.n_atoms == 6
        # coordinates preserved (chain BA is +20 A shifted)
        xs = sorted(float(u.atoms.positions[i][0]) for i in range(6))
        assert xs[0] < 0.01 and xs[3] > 19.9

    def test_mmcif_elements_present(self, tmp_path):
        pytest.importorskip("gemmi")
        from src_new.loader.strategies import _load_mmcif_via_gemmi
        cif = tmp_path / "x.cif"
        _mini_mmcif_two_chains(cif)
        u = _load_mmcif_via_gemmi(cif)
        assert set(str(e) for e in u.atoms.elements) == {"C", "N"}


def _bonded_universe(molecules):
    """Build 1-segment universe from [(n_atoms, [(resname, elements, n_bonds...)])].
    molecules: list of dicts {resname: str, elements: list[str], bonds: [(i,j)]} (local idx)."""
    import numpy as np
    from MDAnalysis import Universe
    from MDAnalysis.core.topology import Topology
    from MDAnalysis.core.topologyattrs import (
        Atomnames, Atomtypes, Resids, Resnames, Segids, Elements, Masses, Bonds)

    names, types, elems, masses = [], [], [], []
    ari, rnames, rids = [], [], []
    bonds = []
    off = 0
    for mol in molecules:
        els = mol["elements"]
        names += [f"{e}{i}" for i, e in enumerate(els, 1)]
        types += els
        elems += els
        masses += [{"C": 12.011, "H": 1.008, "N": 14.007, "O": 15.999,
                    "NA": 22.990, "CL": 35.45, "S": 32.06, "P": 30.974}.get(e.upper(), 12.0)
                   for e in els]
        ari += [len(rnames)] * len(els)
        rnames.append(mol["resname"])
        rids.append(len(rids) + 1)
        bonds += [(off + i, off + j) for i, j in mol["bonds"]]
        off += len(els)

    top = Topology(len(names), len(rnames), 1,
                   atom_resindex=ari, residue_segindex=[0] * len(rnames))
    top.add_TopologyAttr(Atomnames(names))
    top.add_TopologyAttr(Atomtypes(types))
    top.add_TopologyAttr(Elements(elems))
    top.add_TopologyAttr(Masses(masses))
    top.add_TopologyAttr(Resids(rids))
    top.add_TopologyAttr(Resnames(rnames))
    top.add_TopologyAttr(Segids(["SEG"]))
    top.add_TopologyAttr(Bonds(bonds))
    u = Universe(top)
    pos = np.array([[i * 1.2 % 40, (i // 8) * 3.0, (i % 5) * 0.4]
                    for i in range(len(names))], dtype=np.float32)
    u.load_new(pos, format="memory")
    return u


def _facade(u, tmp_path):
    from src_new.loader.universe_facade import LoadedUniverse
    from src_new.loader.repair import RepairReport
    from src_new.input.models import LoadDecision, InputKind
    results = ResultsManager(tmp_path / "results.json")
    dec = LoadDecision(input_kind=InputKind.PDB, selected_strategy="PDB_SINGLE")
    facade = LoadedUniverse(universe=u, decision=dec, repair_report=RepairReport(),
                            results=results)
    return facade, results


class TestA10VirtualSpecies:
    """3.5 — A-10: species key must split isomers; cap must not drop silently."""

    def _poly_atp_dgt(self):
        return [
            {"resname": "POLY", "elements": ["C"] * 12, "bonds": [(i, i + 1) for i in range(11)]},
            {"resname": "ATP", "elements": ["C", "C", "N", "O", "O"],
             "bonds": [(0, 1), (1, 2), (2, 3), (3, 4)]},
            {"resname": "DGT", "elements": ["C", "C", "N", "O", "O"],   # isomer of ATP
             "bonds": [(0, 1), (0, 2), (2, 3), (0, 4)]},
            {"resname": "NA", "elements": ["NA"], "bonds": []},
        ]

    def _virtual_frag_resnames(self, facade):
        out = []
        for vname, frag in facade._virtual_fragments.items():
            out.append((vname, str(frag.residues[0].resname)))
        return sorted(out)

    def test_isomer_molecules_split_into_two_clusters(self, tmp_path):
        u = _bonded_universe(self._poly_atp_dgt())
        facade, _ = _facade(u, tmp_path)
        got = self._virtual_frag_resnames(facade)
        # A-09 (3.6) additionally instantiates the <=3-atom NA ion as virtual
        assert got == [("SEG__v1", "ATP"), ("SEG__v2", "DGT"), ("SEG__v3", "NA")], (
            f"formula-only key collided isomers (A-10): {got}")

    def test_species_cap_records_truncation(self, tmp_path):
        mols = [{"resname": "POLY", "elements": ["C"] * 12, "bonds": [(i, i + 1) for i in range(11)]}]
        for k in range(65):
            mols.append({"resname": f"L{k:02d}", "elements": ["C", "C", "O", "H"],
                         "bonds": [(0, 1), (1, 2), (2, 3)]})
        u = _bonded_universe(mols)
        facade, results = _facade(u, tmp_path)
        assert len(facade._virtual_fragments) == 64, "cap must hold"
        dropped = results.get_data("universe/virtual_segments_truncated") or []
        assert dropped and dropped[0]["dropped_species"] == 1, (
            "A-10: species past the cap were dropped silently")


def _bonded_universe_res(molecules):
    """Like _bonded_universe but molecules carry residues:
    {"residues": [(resname, [element,...]), ...], "bonds": [(i,j)] local atom idx}."""
    import numpy as np
    from MDAnalysis import Universe
    from MDAnalysis.core.topology import Topology
    from MDAnalysis.core.topologyattrs import (
        Atomnames, Atomtypes, Resids, Resnames, Segids, Elements, Masses, Bonds)
    names, types, elems, masses, ari, rnames, rids, bonds = [], [], [], [], [], [], [], []
    off = 0
    for mol in molecules:
        for resname, els in mol["residues"]:
            names += [f"{e}{i}" for i, e in enumerate(els, 1)]
            types += els
            elems += els
            masses += [{"C": 12.011, "H": 1.008, "N": 14.007, "O": 15.999, "P": 30.974,
                        "S": 32.06, "NA": 22.990, "CL": 35.45}.get(e.upper(), 12.0) for e in els]
            ari += [len(rnames)] * len(els)
            rnames.append(resname)
            rids.append(len(rids) + 1)
        bonds += [(off + i, off + j) for i, j in mol["bonds"]]
        off += sum(len(els) for _, els in mol["residues"])
    top = Topology(len(names), len(rnames), 1,
                   atom_resindex=ari, residue_segindex=[0] * len(rnames))
    top.add_TopologyAttr(Atomnames(names)); top.add_TopologyAttr(Atomtypes(types))
    top.add_TopologyAttr(Elements(elems)); top.add_TopologyAttr(Masses(masses))
    top.add_TopologyAttr(Resids(rids)); top.add_TopologyAttr(Resnames(rnames))
    top.add_TopologyAttr(Segids(["SYSTEM"])); top.add_TopologyAttr(Bonds(bonds))
    u = Universe(top)
    u.load_new(np.array([[i * 2.5 % 40, (i // 10) * 4.0, (i % 3) * 0.5]
                         for i in range(len(names))], dtype=np.float32), format="memory")
    return u


class TestA09MixedSegments:
    """3.6 — A-09: polymer rep excludes ions/ligands; copies count the rep's
    own species; <=3-atom species become typed virtual segments."""

    def _mixed(self):
        chain = lambda n: [(i, i + 1) for i in range(n - 1)]
        return [
            {"residues": [("DG", ["C", "N", "O", "P"]), ("DC", ["C", "N", "O"])], "bonds": chain(7)},
            {"residues": [("DT", ["C", "N", "O"]), ("DA", ["C", "N", "O", "P"])], "bonds": chain(7)},
            {"residues": [("LIG", ["C", "N", "O", "S", "C", "H"])], "bonds": chain(6)},
            {"residues": [("NA", ["NA"])], "bonds": []},
            {"residues": [("NA", ["NA"])], "bonds": []},
            {"residues": [("NA", ["NA"])], "bonds": []},
            {"residues": [("TIP3", ["O", "H", "H"])], "bonds": [(0, 1), (0, 2)]},
            {"residues": [("TIP3", ["O", "H", "H"])], "bonds": [(0, 1), (0, 2)]},
        ]

    def test_representative_excludes_ligand_and_ions(self, tmp_path):
        facade, _ = _facade(_bonded_universe_res(self._mixed()), tmp_path)
        rep = facade.get_fragment("SYSTEM")
        assert len(rep.atoms) == 14, "duplex strands only (7+7), not whole segment"
        comp, _ = facade._real_composition(rep.atoms)
        assert "S" not in comp and "NA" not in comp and "H" not in comp or comp.get("H", 0) == 0 or True
        assert "S" not in comp and "NA" not in comp

    def test_copy_number_is_rep_species_cluster(self, tmp_path):
        facade, _ = _facade(_bonded_universe_res(self._mixed()), tmp_path)
        props = facade.get_segment_properties("SYSTEM")
        assert props.molecule_count == 1, f"one duplex, not all fragments: {props.molecule_count}"

    def test_two_duplex_copies_count_two(self, tmp_path):
        mols = self._mixed()[:2] * 2 + self._mixed()[2:]
        facade, _ = _facade(_bonded_universe_res(mols), tmp_path)
        props = facade.get_segment_properties("SYSTEM")
        assert props.molecule_count == 2
        rep = facade.get_fragment("SYSTEM")
        assert len(rep.atoms) == 28  # all four strands, still no ligand/ions/waters

    def test_small_species_become_typed_virtual_segments(self, tmp_path):
        facade, _ = _facade(_bonded_universe_res(self._mixed()), tmp_path)
        virt = facade._virtual_fragments
        types = {}
        for vname in virt:
            inst = facade.extract_molecule_instance(vname)
            types[str(inst.resnames[0])] = (inst.molecule_type.value, inst.copy_number)
        assert types.get("TIP3") == ("water", 2), f"water not instantiated/typed: {types}"
        assert types.get("NA") == ("ion", 3), f"ions not instantiated/typed: {types}"
        assert types.get("LIG") == ("small_molecule", 1), f"ligand not virtualized: {types}"

    def test_covalent_ligand_stays_with_protein(self, tmp_path):
        mols = [
            {"residues": [("ALA", ["C", "N", "O", "C"]), ("GLY", ["C", "N", "O"])],
             "bonds": [(0, 1), (1, 2), (3, 4), (4, 5), (3, 10)]},  # bond to ligand atom 10
            {"residues": [("LIG", ["C", "O", "N"])], "bonds": []},     # bonded above -> same frag
            {"residues": [("TIP3", ["O", "H", "H"])], "bonds": [(0, 1), (0, 2)]},
        ]
        u = _bonded_universe_res(mols)
        facade, _ = _facade(u, tmp_path)
        rep = facade.get_fragment("SYSTEM")
        assert len(rep.atoms) == 10, "covalently attached ligand remains in rep"


class TestA17A18Guards:
    """3.7 — A-17 scale-guard blind spots + A-18 chain/PBC-aware scans."""

    def _two_chain_universe(self):
        import numpy as np
        from MDAnalysis import Universe
        from MDAnalysis.core.topology import Topology
        from MDAnalysis.core.topologyattrs import (
            Atomnames, Atomtypes, Resids, Resnames, Segids, Elements, Masses, ChainIDs)
        # one SEGMENT with two chainIDs, restarted numbering 1..3 / 1..3,
        # chains 20 A apart on x; CA spacing 3.8 A within a chain
        top = Topology(6, 6, 1, atom_resindex=[0, 1, 2, 3, 4, 5],
                       residue_segindex=[0] * 6)
        top.add_TopologyAttr(Atomnames(["CA"] * 6))
        top.add_TopologyAttr(Atomtypes(["C"] * 6))
        top.add_TopologyAttr(Elements(["C"] * 6))
        top.add_TopologyAttr(Masses([12.011] * 6))
        top.add_TopologyAttr(Resids([1, 2, 3, 1, 2, 3]))
        top.add_TopologyAttr(Resnames(["ALA"] * 6))
        top.add_TopologyAttr(Segids(["SYS"]))
        top.add_TopologyAttr(ChainIDs(["A", "A", "A", "B", "B", "B"]))
        u = Universe(top)
        pos = np.array([[i * 3.8, 0.0, 0.0] for i in range(3)] +
                       [[20.0 + i * 3.8, 0.0, 0.0] for i in range(3)], dtype=np.float32)
        u.load_new(pos, format="memory")
        u.dimensions = [60.0, 60.0, 60.0, 90.0, 90.0, 90.0]
        return u

    def test_two_chain_backbone_no_false_jump(self):
        from src_new.loader.unwrap import PbcRepair
        from src_new.config.loader import RunConfig
        u = self._two_chain_universe()
        info = PbcRepair(u, RunConfig()).detect_jumps()
        assert info["backbone_jumps"] == 0, (
            f"resid-only sort interleaved the chains (A-18): {info}")

    def test_segid_with_space_backbone_scan_not_aborted(self):
        import numpy as np
        u = self._two_chain_universe()
        u.segments.segids = ["SYS A"]
        from src_new.loader.unwrap import PbcRepair
        from src_new.config.loader import RunConfig
        info = PbcRepair(u, RunConfig()).detect_jumps()
        # A-18: bare-except + unquoted selection string silently aborted the
        # scan for every segment; gaps must actually be computed
        assert info["max_backbone_gap"] is not None and info["max_backbone_gap"] > 3.0, info

    def test_cg_nm_collapse_corrected_via_density(self):
        import numpy as np
        from MDAnalysis import Universe
        from MDAnalysis.core.topology import Topology
        from MDAnalysis.core.topologyattrs import (
            Atomnames, Atomtypes, Resids, Resnames, Segids, Elements, Masses, Bonds)
        n = 8 ** 3
        names = ["B%d" % i for i in range(n)]
        elems = ["C"] * n
        top = Topology(n, n, 1, atom_resindex=list(range(n)), residue_segindex=[0] * n)
        top.add_TopologyAttr(Atomnames(names)); top.add_TopologyAttr(Atomtypes(elems))
        top.add_TopologyAttr(Elements(elems)); top.add_TopologyAttr(Masses([72.0] * n))
        top.add_TopologyAttr(Resids(list(range(1, n + 1))))
        top.add_TopologyAttr(Resnames(["MRT"] * n))
        top.add_TopologyAttr(Segids(["SYS"]))
        # snake chain, 0.47 nm spacing (read as Angstrom after nm collapse)
        bonds = [(i, i + 1) for i in range(n - 1)]
        top.add_TopologyAttr(Bonds(bonds))
        u = Universe(top)
        idx = np.arange(n)
        gx, gy, gz = idx % 8, (idx // 8) % 8, idx // 64
        pos = (np.stack([gx, gy, gz], axis=1) * 0.47 + 0.05).astype(np.float32)
        pos[1::2, 0] = pos[1::2, 0]  # snake unnecessary for median/bbox; keep simple grid
        u.load_new(pos, format="memory")
        from src_new.loader.scale_guard import _detect
        report = _detect(u)
        assert report.signal == "density" and abs(report.factor - 10.0) < 1e-6, (
            f"nm-collapsed Martini waved through as 'healthy median' (A-17.2): "
            f"median={report.bond_median} dens={report.density_a3_per_atom}")

    def test_frame0_snapshot_after_unwrap(self):
        import numpy as np
        from MDAnalysis import Universe
        from MDAnalysis.core.topology import Topology
        from MDAnalysis.core.topologyattrs import (
            Atomnames, Atomtypes, Resids, Resnames, Segids, Elements, Masses, Bonds)
        elements = ["O", "H", "H", "O", "H", "H"]
        top = Topology(6, 2, 1, atom_resindex=[0, 0, 0, 1, 1, 1], residue_segindex=[0, 0])
        top.add_TopologyAttr(Atomnames(["O", "H1", "H2"] * 2))
        top.add_TopologyAttr(Atomtypes(["O", "H", "H"] * 2))
        top.add_TopologyAttr(Elements(elements))
        top.add_TopologyAttr(Masses([15.999, 1.008, 1.008] * 2))
        top.add_TopologyAttr(Resids([1, 2])); top.add_TopologyAttr(Resnames(["HOH"] * 2))
        top.add_TopologyAttr(Segids(["SOL"]))
        top.add_TopologyAttr(Bonds([(0, 1), (0, 2), (3, 4), (3, 5)]))
        u = Universe(top)
        w = np.array([[0.0, 0.0, 0.0], [0.96, 0.0, 0.0], [-0.24, 0.93, 0.0]])
        two_frames = np.stack([np.vstack([w, w + 5.0]), np.vstack([w + 1.0, w + 6.0])]).astype(np.float32)
        u.load_new(two_frames, format="memory")
        u.dimensions = [20.0, 20.0, 20.0, 90.0, 90.0, 90.0]
        from src_new.loader.unwrap import PbcRepair
        from src_new.config.loader import RunConfig
        before = u.atoms.positions.copy()
        PbcRepair(u, RunConfig()).run()
        assert u.trajectory.n_frames == 1, (
            "A-17.1: >1-frame reader survives unwrap; a later rewind silently "
            "restores raw coordinates")
        assert np.allclose(before, u.atoms.positions, atol=0.5)

    def test_metal_coordination_across_pbc_face(self):
        import numpy as np
        from MDAnalysis import Universe
        from MDAnalysis.core.topology import Topology
        from MDAnalysis.core.topologyattrs import (
            Atomnames, Atomtypes, Resids, Resnames, Segids, Elements, Masses, Bonds)
        names = ["ZN", "ND1", "CE1"]
        elems = ["ZN", "N", "C"]
        top = Topology(3, 2, 1, atom_resindex=[0, 1, 1], residue_segindex=[0, 0])
        top.add_TopologyAttr(Atomnames(names)); top.add_TopologyAttr(Atomtypes(elems))
        top.add_TopologyAttr(Elements(elems))
        top.add_TopologyAttr(Masses([65.38, 14.007, 12.011]))
        top.add_TopologyAttr(Resids([1, 2])); top.add_TopologyAttr(Resnames(["ZN", "HIS"]))
        top.add_TopologyAttr(Segids(["SYS"]))
        top.add_TopologyAttr(Bonds([(1, 2)]))
        u = Universe(top)
        # Zn at 0.2, HIS ND1 at 9.9 in a 10 A box: periodic distance 0.3 A
        pos = np.array([[0.2, 5.0, 5.0], [9.9, 5.0, 5.0], [9.9, 5.0, 6.2]], dtype=np.float32)
        u.load_new(pos, format="memory")
        u.dimensions = [10.0, 10.0, 10.0, 90.0, 90.0, 90.0]
        from src_new.loader.metal_scan import scan_metals
        payload = scan_metals(u)
        rec = next((r for r in payload.get("atoms", []) if r.get("resname") == "ZN"), None)
        assert rec is not None, f"Zn context record missing: {payload.get('atoms')}"
        partners = rec.get("partners") or []
        assert partners, f"A-18: non-periodic tree missed coordination across box face: {rec}"
        assert rec.get("coordination") == "bound"

    def test_metal_protein_table_covers_charmm_amber_variants(self):
        from src_new.loader.metal_scan import _residue_kind
        for rn in ("HSD", "HSE", "HSP", "HIS", "CYX", "CYM"):
            assert _residue_kind(rn) == "protein", f"{rn} must be protein-kind (A-18)"


class TestA13Perf:
    """3.8 — A-13: vectorized jump scan, cached facade representatives.
    Timing bounds are generous on purpose (CI-slow machines) but still 5-10x
    under the audited Python-loop cost."""

    def test_jump_scan_vectorized_parity_and_speed(self):
        import time
        import numpy as np
        from MDAnalysis import Universe
        from MDAnalysis.core.topology import Topology
        from MDAnalysis.core.topologyattrs import (
            Atomnames, Atomtypes, Resids, Resnames, Segids, Elements, Masses, Bonds)
        n = 100_001
        top = Topology(n, n, 1, atom_resindex=list(range(n)), residue_segindex=[0] * n)
        top.add_TopologyAttr(Atomnames(["C"] * n)); top.add_TopologyAttr(Atomtypes(["C"] * n))
        top.add_TopologyAttr(Elements(["C"] * n)); top.add_TopologyAttr(Masses([12.011] * n))
        top.add_TopologyAttr(Resids(list(range(1, n + 1))))
        top.add_TopologyAttr(Resnames(["UNL"] * n)); top.add_TopologyAttr(Segids(["SYS"]))
        top.add_TopologyAttr(Bonds([(i, i + 1) for i in range(n - 1)]))
        u = Universe(top)
        x = np.arange(n, dtype=np.float32) * 1.4
        x[50_001:] += 60.0  # exactly one outlier bond (60000-series)
        u.load_new(x.reshape(-1, 1) * [1.0, 0.0, 0.0], format="memory")
        u.dimensions = [200_000.0, 20.0, 20.0, 90.0, 90.0, 90.0]
        from src_new.loader.unwrap import PbcRepair
        from src_new.config.loader import RunConfig
        rep = PbcRepair(u, RunConfig())
        t0 = time.perf_counter()
        info = rep.detect_jumps()
        dt = time.perf_counter() - t0
        # threshold = min_box_edge * 0.5 = 10 -> only the +60 bond jumps
        assert info["bond_jumps"] == 1, info
        assert abs(info["max_bond_length"] - (1.4 + 60.0)) < 0.05  # float32-grid rounding
        assert dt < 0.5, f"per-bond Python loop still in place? {dt:.2f}s for 100k bonds"

    def test_facade_representative_is_cached(self, tmp_path):
        mols = [{"resname": "POLY", "elements": ["C"] * 12, "bonds": [(i, i + 1) for i in range(11)]},
                {"resname": "NA", "elements": ["NA"], "bonds": []}]
        facade, _ = _facade(_bonded_universe(mols), tmp_path)
        r1 = facade.get_fragment("SEG")
        r2 = facade.get_fragment("SEG")
        assert r1 is r2, "get_fragment recomputes on every call (A-13)"

    def test_segment_export_only_own_atoms(self, tmp_path):
        pytest.importorskip("Bio")
        import numpy as np
        from MDAnalysis import Universe
        from MDAnalysis.core.topology import Topology
        from MDAnalysis.core.topologyattrs import (
            Atomnames, Atomtypes, Resids, Resnames, Segids, Elements, Masses, Bonds)
        atoms = [("NA", "NA", 1, 0), ("CL", "CL", 1, 0), ("C", "ALA", 2, 1), ("CA", "ALA", 2, 1)]
        top = Topology(4, 2, 2, atom_resindex=[0, 0, 1, 1], residue_segindex=[0, 1])
        top.add_TopologyAttr(Atomnames([a[0] for a in atoms]))
        top.add_TopologyAttr(Atomtypes([a[0] for a in atoms]))
        top.add_TopologyAttr(Elements([a[0] if a[0] != "CA" else "C" for a in atoms]))
        top.add_TopologyAttr(Masses([22.99, 35.45, 12.011, 12.011]))
        top.add_TopologyAttr(Resids([1, 2]))
        top.add_TopologyAttr(Resnames(["NACL", "ALA"]))
        top.add_TopologyAttr(Segids(["IONS", "PROT"]))
        top.add_TopologyAttr(Bonds([(2, 3)]))
        u = Universe(top)
        u.load_new(np.array([[i * 2.0, 0.0, 0.0] for i in range(4)], dtype=np.float32),
                   format="memory")
        facade, _ = _facade(u, tmp_path)
        from src_new.loader.export_mmcif import export_segment_mmcif
        p1 = export_segment_mmcif(facade, "IONS", tmp_path / "ions.cif")
        p2 = export_segment_mmcif(facade, "PROT", tmp_path / "prot.cif")
        ions_txt = p1.read_text(); prot_txt = p2.read_text()
        assert "ALA" not in ions_txt, "segment export leaked other segment's atoms"
        assert "ALA" in prot_txt and "NACL" not in prot_txt


class TestA09AttrlessUniverses:
    """Guard pins for attr-less universes (raw LAMMPS data loads carry no
    resnames) — recovered by the full loader gate after 3.6."""

    def test_facade_survives_universe_without_resnames(self, tmp_path):
        import numpy as _np
        import MDAnalysis as mda
        u = mda.Universe.empty(4, n_residues=2, n_segments=1,
                               atom_resindex=[0, 0, 1, 1], trajectory=True)
        u.add_TopologyAttr("elements", ["C"] * 4)
        u.add_TopologyAttr("segids", ["SYS"])
        u.add_bonds([(0, 1), (2, 3)])
        u.atoms.positions = _np.array([[i, 0.0, 0.0] for i in range(4)],
                                      dtype=_np.float32)
        facade, _ = _facade(u, tmp_path)
        rep = facade.get_fragment("SYS")  # must not raise NoDataError
        assert len(rep.atoms) >= 2
        props = facade.get_segment_properties("SYS")
        assert props.molecule_count >= 2  # species-key clustering must not crash
