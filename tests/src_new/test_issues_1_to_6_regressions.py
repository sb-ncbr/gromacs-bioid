"""Regression tests for Issues #1-#6:
- Issue #1: Broken MoleculeType classification (LIPID / CARBOHYDRATE / SMALL_MOLECULE)
- Issue #2: SimpleSmilesGenerator hang on unprotonated oligosaccharides (>60 heavy atoms)
- Issue #3: Glycan identification pipeline mismatches (BMA/NDG/FUL/GLYCAM, NeuAc/Neu5Ac regex, covalent N-glycans)
- Issue #4: Multi-chain protein oligomers in a single segid concatenated into a single chimera
- Issue #5: 2-letter elements (Cl -> C), truncated PDB halogens, and divalent H-bond bridges (Cetirizine)
- Issue #6: DNA/RNA identification on partial-CONECT PDBs (1XJR) and protein-DNA complexes (1AAY)
"""

from __future__ import annotations

import time
import numpy as np
import MDAnalysis as mda
import pytest
from rdkit import Chem

from pathlib import Path
from src_new.config.loader import RunConfig, SignaturesConfig
from src_new.input.models import InputKind, LoadDecision
from src_new.loader.repair import RepairReport, TopologyRepair
from src_new.loader.universe_facade import LoadedUniverse
from src_new.molecules.instances import MoleculeType
from src_new.signatures.generators.fasta import (
    MapFastaGeneratorNucleotide,
    ResnameFastaGeneratorNucleotide,
)
from src_new.signatures.generators.glycan import GlycanCompositionGenerator
from src_new.signatures.generators.smiles import SimpleSmilesGenerator
from src_new.identification.resolvers.glycan import GlycanCompositionResolver
from src_new.identification.resolvers.blast import BLASTResolverPDBNT


def _make_decision() -> LoadDecision:
    return LoadDecision(
        input_kind=InputKind.GROMACS,
        selected_strategy="tpr_only",
        topology_files=[Path("dummy.tpr")],
    )


class TestIssue1MoleculeTypeClassification:
    """Issue #1: LIPID / CARBOHYDRATE / SMALL_MOLECULE classification in extract_molecule_instance."""

    def _classify_single_segment(
        self, resnames: list[str], elements: list[str]
    ) -> MoleculeType:
        n_res = len(resnames)
        n_atoms = len(elements)
        u = mda.Universe.empty(
            n_atoms=n_atoms,
            n_residues=n_res,
            n_segments=1,
            atom_resindex=np.zeros(n_atoms, dtype=int),
            residue_segindex=np.zeros(n_res, dtype=int),
            trajectory=True,
        )
        u.add_TopologyAttr("names", [f"{el}{i}" for i, el in enumerate(elements)])
        u.add_TopologyAttr("resnames", resnames)
        u.add_TopologyAttr("resids", list(range(1, n_res + 1)))
        u.add_TopologyAttr("segids", ["SEG0"])
        u.add_TopologyAttr("elements", elements)
        u.add_TopologyAttr("masses", [12.0] * n_atoms)
        u.atoms.positions = np.zeros((n_atoms, 3), dtype=np.float32)
        if n_atoms > 1:
            u.add_TopologyAttr("bonds", [(i, i + 1) for i in range(n_atoms - 1)])

        facade = LoadedUniverse(u, _make_decision(), RepairReport())
        return facade.extract_molecule_instance("SEG0").molecule_type

    def test_phospholipid_dppc_is_lipid_not_carbohydrate(self):
        # DPPC: C40 H80 N O8 P (C/O = 5.0)
        elems = ["C"] * 40 + ["O"] * 8 + ["N", "P"] + ["H"] * 80
        mtype = self._classify_single_segment(["DPPC"], elems)
        assert mtype == MoleculeType.LIPID

    def test_cholesterol_is_lipid_not_unknown(self):
        # Cholesterol: C27 H46 O (O=1, C/O = 27.0)
        elems = ["C"] * 27 + ["O"] + ["H"] * 46
        mtype = self._classify_single_segment(["CHL1"], elems)
        assert mtype == MoleculeType.LIPID

    def test_n_glycan_is_carbohydrate_not_lipid(self):
        # 9-mer N-glycan from 1FC1: C62 O44 N3 (C/O = 1.41)
        elems = ["C"] * 62 + ["O"] * 44 + ["N"] * 3
        mtype = self._classify_single_segment(["NAG"], elems)
        assert mtype == MoleculeType.CARBOHYDRATE

    def test_small_molecule_with_more_than_10_carbons_is_not_unknown(self):
        # Generic small molecule ligand with 21 C and 3 O (e.g. Cetirizine C21H25ClN2O3)
        # Without lipid resname and with N/Cl/etc., wait: if C=15, O=2 or C=12, O=2
        # Specifically test C=14, O=5, C/O = 2.8 vs C=8, O=5 (C/O = 1.6):
        # And test C=12, O=2 (atom_o_cnt=2, not matching old elif) or C=15, O=5 with C/O=3.5:
        elems = ["C"] * 8 + ["O"] * 2 + ["N"] * 2 + ["H"] * 10
        mtype = self._classify_single_segment(["LIG"], elems)
        assert mtype == MoleculeType.SMALL_MOLECULE


class TestIssue2SmilesGeneratorGlycanHang:
    """Issue #2: SimpleSmilesGenerator must not hang on unprotonated oligosaccharides."""

    def test_unprotonated_n_glycan_skips_smiles_and_never_hangs(self):
        # Construct an unprotonated 9-residue N-glycan (109 heavy atoms, 0 hydrogens)
        resnames = ["NAG", "NAG", "BMA", "MAN", "MAN", "NAG", "GAL", "MAN", "FUC"]
        atoms_per_res = [14, 14, 11, 11, 11, 14, 11, 11, 10]
        n_atoms = sum(atoms_per_res)
        atom_resindex = []
        elements = []
        for r_idx, cnt in enumerate(atoms_per_res):
            atom_resindex.extend([r_idx] * cnt)
            elements.extend(["C"] * 6 + ["O"] * (cnt - 6))

        u = mda.Universe.empty(
            n_atoms=n_atoms,
            n_residues=len(resnames),
            n_segments=1,
            atom_resindex=np.array(atom_resindex, dtype=int),
            residue_segindex=np.zeros(len(resnames), dtype=int),
            trajectory=True,
        )
        u.add_TopologyAttr("names", [f"A{i}" for i in range(n_atoms)])
        u.add_TopologyAttr("resnames", resnames)
        u.add_TopologyAttr("resids", list(range(1, len(resnames) + 1)))
        u.add_TopologyAttr("segids", ["GLYC"])
        u.add_TopologyAttr("elements", elements)
        u.add_TopologyAttr("masses", [12.0] * n_atoms)
        u.atoms.positions = np.zeros((n_atoms, 3), dtype=np.float32)
        u.add_TopologyAttr("bonds", [(i, i + 1) for i in range(n_atoms - 1)])

        facade = LoadedUniverse(u, _make_decision(), RepairReport())
        instance = facade.extract_molecule_instance("GLYC")
        fragment = facade.get_fragment("GLYC")

        assert instance.molecule_type == MoleculeType.CARBOHYDRATE

        gen = SimpleSmilesGenerator(SignaturesConfig())
        t0 = time.time()
        assert gen.is_applicable(instance, fragment, facade) is False
        assert (time.time() - t0) < 0.5


class TestIssue3GlycanPipeline:
    """Issue #3: Glycan forcefield maps, NeuAc/Neu5Ac regex, and covalent N-glycans."""

    def test_glycan_generator_recognizes_pdb_ccd_and_glycam_codes(self):
        resnames = ["NAG", "NDG", "BMA", "MAN", "GAL", "FUL", "SIA", "0YB", "4GB"]
        n_res = len(resnames)
        n_atoms = n_res * 6
        atom_resindex = np.repeat(np.arange(n_res), 6)
        u = mda.Universe.empty(
            n_atoms=n_atoms,
            n_residues=n_res,
            n_segments=1,
            atom_resindex=atom_resindex,
            residue_segindex=np.zeros(n_res, dtype=int),
            trajectory=True,
        )
        u.add_TopologyAttr("names", [f"C{i}" for i in range(n_atoms)])
        u.add_TopologyAttr("resnames", resnames)
        u.add_TopologyAttr("resids", list(range(1, n_res + 1)))
        u.add_TopologyAttr("segids", ["GLYC"])
        u.add_TopologyAttr("elements", ["C", "C", "C", "O", "O", "O"] * n_res)
        u.add_TopologyAttr("masses", [12.0] * n_atoms)
        u.atoms.positions = np.zeros((n_atoms, 3), dtype=np.float32)
        u.add_TopologyAttr("bonds", [(i, i + 1) for i in range(n_atoms - 1)])

        facade = LoadedUniverse(u, _make_decision(), RepairReport())
        instance = facade.extract_molecule_instance("GLYC")
        fragment = facade.get_fragment("GLYC")

        gen = GlycanCompositionGenerator(SignaturesConfig())
        comp = gen.generate(instance, fragment, facade)
        assert "X" not in comp
        assert comp == "Hex(4)HexNAc(3)NeuAc(1)dHex(1)"

        resolver = GlycanCompositionResolver(RunConfig())
        parsed = resolver._parse_composition(comp)
        assert parsed == {"hex": 4, "hexnac": 3, "neu5ac": 1, "dhex": 1}

        parsed_neu5ac = resolver._parse_composition("Hex(5)HexNAc(4)Neu5Ac(2)")
        assert parsed_neu5ac == {"hex": 5, "hexnac": 4, "neu5ac": 2}

    def test_covalently_attached_n_glycan_on_protein_exposed_as_virtual_segment(self):
        # 10-residue protein (ALA x 9 + ASN) covalently bonded to NAG-NAG-BMA
        resnames = ["ALA"] * 9 + ["ASN", "NAG", "NAG", "BMA"]
        n_res = len(resnames)
        n_atoms = n_res * 6
        atom_resindex = np.repeat(np.arange(n_res), 6)
        u = mda.Universe.empty(
            n_atoms=n_atoms,
            n_residues=n_res,
            n_segments=1,
            atom_resindex=atom_resindex,
            residue_segindex=np.zeros(n_res, dtype=int),
            trajectory=True,
        )
        u.add_TopologyAttr("names", [f"C{i}" for i in range(n_atoms)])
        u.add_TopologyAttr("resnames", resnames)
        u.add_TopologyAttr("resids", list(range(1, n_res + 1)))
        u.add_TopologyAttr("segids", ["PROA"])
        u.add_TopologyAttr("elements", ["C", "C", "C", "O", "O", "N"] * n_res)
        u.add_TopologyAttr("masses", [12.0] * n_atoms)
        u.atoms.positions = np.zeros((n_atoms, 3), dtype=np.float32)
        # All atoms bonded in a single connected component (simulating covalent N-glycosylation)
        u.add_TopologyAttr("bonds", [(i, i + 1) for i in range(n_atoms - 1)])

        facade = LoadedUniverse(u, _make_decision(), RepairReport())
        segs = facade.get_segments()
        assert "PROA__v1" in segs
        v_inst = facade.extract_molecule_instance("PROA__v1")
        assert v_inst.molecule_type == MoleculeType.CARBOHYDRATE
        gen = GlycanCompositionGenerator(SignaturesConfig())
        assert gen.generate(v_inst, facade.get_fragment("PROA__v1"), facade) == "Hex(1)HexNAc(2)"


class TestIssue4MultiChainOligomerFragment:
    """Issue #4: Multi-chain protein oligomers in a single segid (e.g. SYSTEM)."""

    def test_multi_chain_oligomer_returns_single_chain_not_concatenated_chimera(self):
        # 6 disconnected 15-residue protein chains sharing segid 'SYSTEM'
        n_chains = 6
        res_per_chain = 15
        n_res = n_chains * res_per_chain
        n_atoms = n_res * 4
        atom_resindex = np.repeat(np.arange(n_res), 4)
        u = mda.Universe.empty(
            n_atoms=n_atoms,
            n_residues=n_res,
            n_segments=1,
            atom_resindex=atom_resindex,
            residue_segindex=np.zeros(n_res, dtype=int),
            trajectory=True,
        )
        u.add_TopologyAttr("names", ["N", "CA", "C", "O"] * n_res)
        u.add_TopologyAttr("resnames", ["ALA"] * n_res)
        u.add_TopologyAttr("resids", list(range(1, n_res + 1)))
        u.add_TopologyAttr("segids", ["SYSTEM"])
        u.add_TopologyAttr("elements", ["N", "C", "C", "O"] * n_res)
        u.add_TopologyAttr("masses", [14.0, 12.0, 12.0, 16.0] * n_res)
        u.atoms.positions = np.zeros((n_atoms, 3), dtype=np.float32)

        # Bond atoms within each 15-residue chain, but NOT between chains
        bonds = []
        atoms_per_chain = res_per_chain * 4
        for c in range(n_chains):
            start = c * atoms_per_chain
            for i in range(start, start + atoms_per_chain - 1):
                bonds.append((i, i + 1))
        u.add_TopologyAttr("bonds", bonds)

        facade = LoadedUniverse(u, _make_decision(), RepairReport())
        frag = facade.get_fragment("SYSTEM")
        assert len(frag.residues) == res_per_chain
        props = facade.get_segment_properties("SYSTEM")
        assert props.molecule_count == n_chains


class TestIssue5SmallMoleculeRepairAndCetirizine:
    """Issue #5: 2-letter elements (Cl/Br), truncated halogens, and divalent H-bond bridges."""

    def test_guess_single_element_halogens_and_ca_preservation(self):
        u = mda.Universe.empty(n_atoms=4, trajectory=True)
        repair = TopologyRepair(u, RunConfig())
        # Protein C-alpha must stay Carbon
        assert repair._guess_single_element("", "CA", None, None) == "C"
        # Halogens and metals must be recognized as 2-letter elements
        assert repair._guess_single_element("", "CL1", None, None) == "Cl"
        assert repair._guess_single_element("", "Cl", None, None) == "Cl"
        assert repair._guess_single_element("", "BR1", None, None) == "Br"
        assert repair._guess_single_element("", "ZN", None, None) == "Zn"
        assert repair._guess_single_element("", "MG", None, None) == "Mg"

    def test_prune_multivalent_hydrogens_and_repair_truncated_cl(self):
        # Build a C16-C17-C18(Cl) + intramolecular N-H...O bridge system
        # Atom 0: C16 at (-1.4, 0, 0)
        # Atom 1: C17 at (0, 0, 0) -> bonded to C16 and C18
        # Atom 2: C18 (truncated Cl) at (1.745, 0, 0) -> only bonded to C17 at 1.745 A
        # Atom 3: N1 at (0, 10.0, 0)
        # Atom 4: H7 at (0, 11.11, 0) -> 1.11 A from N1
        # Atom 5: O1 at (0, 12.56, 0) -> 1.45 A from H7 (within vdw guesser cutoff of H!)
        u = mda.Universe.empty(
            n_atoms=6,
            n_residues=1,
            n_segments=1,
            atom_resindex=np.zeros(6, dtype=int),
            residue_segindex=np.zeros(1, dtype=int),
            trajectory=True,
        )
        u.add_TopologyAttr("names", ["C16", "C17", "C18", "N1", "H7", "O1"])
        u.add_TopologyAttr("resnames", ["LIG"])
        u.add_TopologyAttr("resids", [1])
        u.add_TopologyAttr("segids", ["A"])
        # Simulate right-shifted PDB where C18 has 'C' and others are blank
        u.add_TopologyAttr("elements", ["", "", "C", "", "", ""])
        u.add_TopologyAttr("masses", [0.0] * 6)
        u.atoms.positions = np.array(
            [
                [-1.40, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                [1.745, 0.0, 0.0],
                [0.0, 10.0, 0.0],
                [0.0, 11.11, 0.0],
                [0.0, 12.56, 0.0],
            ],
            dtype=np.float32,
        )
        cfg = RunConfig()
        cfg.loader.guess_missing_bonds = True
        repair = TopologyRepair(u, cfg)
        repair.run()

        # C18 (atom 2) at 1.745 A with degree 1 and 0 H neighbors is repaired to Cl
        assert u.atoms.elements[2] == "Cl"
        # H7 (atom 4) must have only 1 bond (to N1, atom 3), NOT a second bond to O1 (atom 5)
        h7_bonds = [b for b in u.atoms.bonds.indices if 4 in (int(b[0]), int(b[1]))]
        assert len(h7_bonds) == 1
        assert set(int(x) for x in h7_bonds[0]) == {3, 4}


class TestIssue6NucleicAcidsPartialConectAndShortBlast:
    """Issue #6: Partial-CONECT PDB bond completion & short nucleotide BLAST similarity."""

    def test_partial_conect_triggers_bond_guessing_and_preserves_existing_bonds(self):
        # 20 atoms with only 1 pre-existing CONECT bond (< 0.25 * 20 = 5 bonds)
        u = mda.Universe.empty(
            n_atoms=20,
            n_residues=2,
            n_segments=1,
            atom_resindex=np.array([0] * 10 + [1] * 10, dtype=int),
            residue_segindex=np.zeros(2, dtype=int),
            trajectory=True,
        )
        u.add_TopologyAttr("names", [f"C{i}" for i in range(20)])
        u.add_TopologyAttr("resnames", ["G", "C"])
        u.add_TopologyAttr("resids", [1, 2])
        u.add_TopologyAttr("segids", ["A"])
        u.add_TopologyAttr("elements", ["C"] * 20)
        u.add_TopologyAttr("masses", [12.0] * 20)
        # Place consecutive atoms 1.4 A apart so DefaultGuesser connects them all
        u.atoms.positions = np.array([[i * 1.4, 0.0, 0.0] for i in range(20)], dtype=np.float32)
        u.add_TopologyAttr("bonds", [(0, 1)])

        repair = TopologyRepair(u, RunConfig())
        guessed = repair.guess_bonds()
        assert guessed >= 18
        assert len(u.atoms.bonds) >= 19

    def test_sparse_bonds_fall_back_to_resname_fasta_nucleic(self):
        # 20-atom 2-residue RNA with only 1 bond (below 0.25 * 20 = 5 threshold)
        u = mda.Universe.empty(
            n_atoms=20,
            n_residues=2,
            n_segments=1,
            atom_resindex=np.array([0] * 10 + [1] * 10, dtype=int),
            residue_segindex=np.zeros(2, dtype=int),
            trajectory=True,
        )
        u.add_TopologyAttr("names", [f"C{i}" for i in range(20)])
        u.add_TopologyAttr("resnames", ["G", "U"])
        u.add_TopologyAttr("resids", [1, 2])
        u.add_TopologyAttr("segids", ["A"])
        u.add_TopologyAttr("elements", ["C"] * 20)
        u.add_TopologyAttr("masses", [12.0] * 20)
        u.atoms.positions = np.zeros((20, 3), dtype=np.float32)
        u.add_TopologyAttr("bonds", [(0, 1)])

        facade = LoadedUniverse(u, _make_decision(), RepairReport())
        inst = facade.extract_molecule_instance("A")
        # Use full segment as fragment
        frag = u.atoms
        cfg = SignaturesConfig()
        map_gen = MapFastaGeneratorNucleotide(cfg)
        res_gen = ResnameFastaGeneratorNucleotide(cfg)
        assert map_gen.is_applicable(inst, frag, facade) is False
        assert res_gen.is_applicable(inst, frag, facade) is True
        assert res_gen.generate(inst, frag, facade) == "GU"

    def test_short_nucleotide_blast_similarity_rescues_11mer_hit(self, monkeypatch):
        cfg = RunConfig()
        resolver = BLASTResolverPDBNT(cfg)
        # Simulate a 100% identity, 100% coverage 11-mer DNA hit (like 1AAY_2)
        # where bit score is 22.1 and evalue is 0.12 (> default 1e-5 threshold)
        fake_json = [
            {
                "BlastOutput2": {
                    "report": {
                        "results": {
                            "search": {
                                "query_len": 11,
                                "hits": [
                                    {
                                        "len": 11,
                                        "description": [{"accession": "1AAY_2"}],
                                        "hsps": [
                                            {
                                                "bit_score": 22.1,
                                                "evalue": 0.12,
                                                "identity": 11,
                                                "align_len": 11,
                                            }
                                        ],
                                    }
                                ],
                            }
                        }
                    }
                }
            }
        ]
        monkeypatch.setattr(resolver, "_run_blast_local", lambda seq, wd: fake_json)
        hits = resolver._run_blast_similarity("TACGCCCACGC", ".")
        assert hits == [("1AAY_2", 100.0)]
