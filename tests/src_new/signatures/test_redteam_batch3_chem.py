"""Batch-3 4.1 — B-14: perceive chemistry ONCE per fragment (cached Mol),
identical outputs, fail-fast family errors, soft timeout."""
from __future__ import annotations

import os
import time

import numpy as np
import MDAnalysis as mda
import pytest
from rdkit.Chem import rdDetermineBonds


def _acetate_fragment(with_charges=True):
    """CH3COO- bonded correctly: CH3 (C0 H1-3) - COO (C4 O5 O6). Optional
    topology partial charges summing to -1 (prmtop/tpr/psf/itp case)."""
    n = 7
    u = mda.Universe.empty(n, n_residues=1, n_segments=1,
                           atom_resindex=[0] * n, trajectory=True)
    u.add_TopologyAttr("elements", ["C", "H", "H", "H", "C", "O", "O"])
    u.add_TopologyAttr("names", [f"A{i}" for i in range(n)])
    u.add_TopologyAttr("resnames", ["ACT"])
    u.add_TopologyAttr("resids", [1])
    u.add_TopologyAttr("segids", ["SEG"])
    u.add_bonds([(0, 4), (0, 1), (0, 2), (0, 3), (4, 5), (4, 6)])
    u.atoms.positions = np.array([
        [0.0, 0.0, 0.0], [0.6, 0.8, 0.0], [0.6, -0.8, 0.0], [-0.9, 0.0, 0.0],
        [1.5, 0.0, 0.0], [2.1, 0.9, 0.0], [2.1, -0.9, 0.0]], dtype=np.float32)
    if with_charges:
        cc = np.array([0.09, 0.0, 0.0, 0.0, 0.67, -0.88, -0.88])
        cc *= -1.0 / cc.sum()
        u.add_TopologyAttr("charges", cc)
    return u.atoms


def _ethanol_fragment():
    """Neutral CH3CH2OH: no topology charges (the charged-ligand fix must
    leave neutral systems byte-identical)."""
    n = 9
    u = mda.Universe.empty(n, n_residues=1, n_segments=1,
                           atom_resindex=[0] * n, trajectory=True)
    u.add_TopologyAttr("elements",
                       ["C", "H", "H", "H", "C", "H", "H", "O", "H"])
    u.add_TopologyAttr("names", [f"A{i}" for i in range(n)])
    u.add_TopologyAttr("resnames", ["ETOH"])
    u.add_TopologyAttr("resids", [1])
    u.add_TopologyAttr("segids", ["SEG"])
    u.add_bonds([(0, 4), (0, 1), (0, 2), (0, 3), (4, 5), (4, 6), (4, 7), (7, 8)])
    u.atoms.positions = np.array([
        [0.0, 0.0, 0.0], [0.6, 0.8, 0.0], [0.6, -0.8, 0.0], [-0.9, 0.0, 0.0],
        [1.5, 0.0, 0.0], [2.0, 0.8, 0.0], [2.0, -0.8, 0.0], [2.7, 0.0, 0.0],
        [3.6, 0.2, 0.0]], dtype=np.float32)
    return u.atoms


def _instance(fragment):
    from src_new.molecules.instances import MoleculeInstance
    return MoleculeInstance(instance_id="inst0", atom_indices=list(fragment.indices))


def _chem_generators():
    from src_new.config.loader import SignaturesConfig
    from src_new.signatures.generators.smiles import (
        SimpleSmilesGenerator, SimpleSmilesGeneratorNoSanitize)
    from src_new.signatures.generators.inchi import InchiKeyGenerator
    from src_new.signatures.generators.selfies import SelfiesGenerator
    cfg = SignaturesConfig()
    return [SimpleSmilesGenerator(cfg), SimpleSmilesGeneratorNoSanitize(cfg),
            InchiKeyGenerator(cfg), SelfiesGenerator(cfg)]


@pytest.fixture(autouse=True)
def _clear_cache():
    from src_new.signatures.generators import _perceive_cache as pc
    pc.clear_cache()
    yield
    pc.clear_cache()


class TestB01NetCharge:
    """4.2 - B-01 [CRITICAL]: net charge reaches bond-order perception;
    charged ligands must no longer produce neutral/acid signatures."""

    ACETATE_KEY = "QTBSBXVTEAMEQO-UHFFFAOYSA-M"   # InChI=1S/C2H4O2/.../p-1

    def _one(self, gen, frag):
        from src_new.signatures.generators import _perceive_cache as pc
        pc.clear_cache()
        return gen._generate(_instance(frag), frag, None)

    def test_acetate_inchikey_with_topology_charges(self):
        from src_new.config.loader import SignaturesConfig
        from src_new.signatures.generators.inchi import InchiKeyGenerator
        ik = self._one(InchiKeyGenerator(SignaturesConfig()), _acetate_fragment())
        assert ik == self.ACETATE_KEY, (
            f"B-01: charged acetate must not come out as the neutral acid: {ik}")

    def test_acetate_smiles_has_no_bare_proton(self):
        from src_new.config.loader import SignaturesConfig
        from src_new.signatures.generators.smiles import SimpleSmilesGenerator
        sm = self._one(SimpleSmilesGenerator(SignaturesConfig()), _acetate_fragment())
        assert "[H+]" not in sm and "([OH])" not in sm, sm
        assert "C(=O)[O-]" in sm, sm

    def test_ladder_recovers_when_topology_has_no_charges(self):
        """No charges attr (PDB/GRO inputs): charge=0 fails (SetNoImplicit
        cannot protonate the carboxyl) and the +-ladder must find -1."""
        from src_new.config.loader import SignaturesConfig
        from src_new.signatures.generators.inchi import InchiKeyGenerator
        ik = self._one(InchiKeyGenerator(SignaturesConfig()),
                       _acetate_fragment(with_charges=False))
        assert ik == self.ACETATE_KEY, ik

    def test_neutral_system_byte_identical(self):
        """No regression for uncharged molecules (ethanol, no charges attr):
        charge=0 succeeds cleanly -> unchanged signature."""
        from src_new.config.loader import SignaturesConfig
        from src_new.signatures.generators.inchi import InchiKeyGenerator
        ik = self._one(InchiKeyGenerator(SignaturesConfig()), _ethanol_fragment())
        assert ik == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N", ik  # ethanol canonical key

    def test_regex_retry_deleted(self):
        """The bogus 'input (-3)' regex-retry path must be gone from smiles."""
        import inspect
        from src_new.signatures.generators import smiles as sm_mod
        src = inspect.getsource(sm_mod)
        assert "input\\s" not in src and "input \\(" not in src, (
            "charge-from-error-message regex still present")


class TestB14PerceiveOnce:
    def test_determine_bond_orders_called_once_per_family(self, monkeypatch):
        """B-14: families (smiles-class; inchi/selfies) each perceive at most
        once per fragment — today every generator pays its own build."""
        calls = {"dbo": 0}
        real_dbo = rdDetermineBonds.DetermineBondOrders

        def spy(*a, **k):
            calls["dbo"] += 1
            return real_dbo(*a, **k)

        monkeypatch.setattr(rdDetermineBonds, "DetermineBondOrders", spy)
        frag = _acetate_fragment()
        inst = _instance(frag)
        results = {}
        for gen in _chem_generators():
            results[gen.name] = gen._generate(inst, frag, None)
        assert any(results.values()), results
        assert calls["dbo"] <= 2, (
            f"B-14: {calls['dbo']} perceptions for one fragment — the mol cache "
            "is not effective (families: smiles-class, inchi/selfies)")

    def test_cache_off_matches_cache_on(self, monkeypatch):
        """Behavior-identical: with caching disabled every generator must
        produce the exact same strings as with caching enabled."""
        outs = {}
        for mode in ("off", "on"):
            monkeypatch.setenv("BAT3_PERCEIVE_CACHE_OFF", "1" if mode == "off" else "0")
            from src_new.signatures.generators import _perceive_cache as pc
            pc.clear_cache()
            frag = _acetate_fragment()
            inst = _instance(frag)
            outs[mode] = {g.name: g._generate(inst, frag, None)
                          for g in _chem_generators()}
        assert outs["off"] == outs["on"], (
            {k: (outs["off"][k], outs["on"][k]) for k in outs["off"]
             if outs["off"][k] != outs["on"][k]})

    def test_build_error_is_cached_and_fail_fast(self, monkeypatch):
        """First family member pays the (timed-out) build; every later member
        re-raises the SAME cached error without rebuilding."""
        from src_new.signatures.generators import _perceive_cache as pc

        frag = _acetate_fragment()
        called = {"n": 0}

        def sleepy_builder():
            called["n"] += 1
            time.sleep(2)
            raise AssertionError("must not complete")

        with pytest.raises(pc.PerceiveTimeoutError):
            pc.build_once_cached(frag, "fam", sleepy_builder, timeout_s=1)
        with pytest.raises(pc.PerceiveTimeoutError):
            pc.build_once_cached(frag, "fam", sleepy_builder, timeout_s=1)
        assert called["n"] == 1, "family error was not cached/fail-fast"


def _protein_chain(n_res=20, break_bond_at=None):
    """Bonded poly-ALA chain with a name-exact backbone (per residue:
    N, CA, C, O, CB; peptide bonds C(i)-N(i+1) as required by the
    B-02/B-03 backbone walk). break_bond_at omits peptide C(k)-N(k+1)
    to force the legacy matrix path."""
    atoms_per_res = 5
    names = ["N", "CA", "C", "O", "CB"]
    n = n_res * atoms_per_res
    u = mda.Universe.empty(n, n_residues=n_res, n_segments=1,
                           atom_resindex=[i // atoms_per_res for i in range(n)],
                           trajectory=True)
    u.add_TopologyAttr("elements",
                       [e for _ in range(n_res) for e in ("N", "C", "C", "O", "C")])
    u.add_TopologyAttr("names",
                       [nm for _ in range(n_res) for nm in names])
    u.add_TopologyAttr("resnames", ["ALA"] * n_res)
    u.add_TopologyAttr("resids", list(range(1, n_res + 1)))
    u.add_TopologyAttr("segids", ["PRO"])
    bonds = []
    for k in range(n_res):
        b = k * atoms_per_res
        bonds += [(b, b + 1), (b + 1, b + 2), (b + 2, b + 3), (b + 1, b + 4)]
        if k + 1 < n_res and break_bond_at != k + 1:
            bonds.append((b + 2, (k + 1) * atoms_per_res))  # peptide C->N
    u.add_bonds(bonds)
    u.atoms.positions = np.arange(n * 3, dtype=np.float32).reshape(n, 3) / 10.0
    return u.atoms


class TestB07Perf:
    def test_full_coverage_chain_never_builds_matrices(self, monkeypatch):
        """B-07: the backbone short-circuit must run BEFORE the O(N^2)
        adjacency-matrix allocation; today matrices are built first."""
        from src_new.signatures.generators import fasta
        from src_new.config.loader import SignaturesConfig
        built = {"n": 0}
        real = fasta._mk_residue_atom_adjacency_matrix

        def spy(*a, **k):
            built["n"] += 1
            return real(*a, **k)

        monkeypatch.setattr(fasta, "_mk_residue_atom_adjacency_matrix", spy)
        seq = fasta.fragment_to_protseq_map_based(
            _protein_chain(20), SignaturesConfig())
        assert set(seq) == {"A"} and len(seq) == 20, seq
        assert built["n"] == 0, (
            "B-07: matrices built before the short-circuit (8 B/cell @ N^2 "
            "-> ~4 GB runaway on 22k-atom proteins)")

    def test_broken_chain_still_uses_legacy_matrix_path(self, monkeypatch):
        """Parity pin: partial graphs MUST keep the legacy machinery."""
        from src_new.signatures.generators import fasta
        from src_new.config.loader import SignaturesConfig
        built = {"n": 0}
        real = fasta._mk_residue_atom_adjacency_matrix

        def spy(*a, **k):
            built["n"] += 1
            return real(*a, **k)

        monkeypatch.setattr(fasta, "_mk_residue_atom_adjacency_matrix", spy)
        seq = fasta.fragment_to_protseq_map_based(
            _protein_chain(20, break_bond_at=10), SignaturesConfig())
        assert built["n"] == 1 and seq, (built, seq)

    def test_fingerprint_single_index_map(self, monkeypatch):
        """fingerprint must not rebuild indices.tolist() + .index() per bond
        (O(N*B)); 12k-atom fragment must finish well under the audited 3.6 s."""
        import time
        from src_new.config.loader import SignaturesConfig
        from src_new.signatures.generators.fingerprint import FingerprintGenerator
        frag = _protein_chain(2400)  # 12000 atoms, ~12k bonds
        inst = _instance(frag)
        t0 = time.perf_counter()
        out = FingerprintGenerator(SignaturesConfig())._generate(inst, frag, None)
        dt = time.perf_counter() - t0
        assert out and dt < 2.0, f"B-07 fingerprint still quadratic: {dt:.2f}s"


def _ua_ethanol_fragment(with_masses=True):
    """United-atom ethanol: CH3(15.035) - CH2(14.027) - OH(17.007), no H atoms
    (GROMOS/ATB-style). With masses inferred implicit H must recover all-atom
    ethanol; without masses the open-valence mode applies."""
    n = 3
    u = mda.Universe.empty(n, n_residues=1, n_segments=1,
                           atom_resindex=[0] * n, trajectory=True)
    u.add_TopologyAttr("elements", ["C", "C", "O"])
    u.add_TopologyAttr("names", ["C1", "C2", "O1"])
    u.add_TopologyAttr("resnames", ["ETOH"])
    u.add_TopologyAttr("resids", [1])
    u.add_TopologyAttr("segids", ["SEG"])
    u.add_bonds([(0, 1), (1, 2)])
    u.atoms.positions = np.array([[0.0, 0.0, 0.0], [1.5, 0.0, 0.0],
                                  [2.7, 0.4, 0.0]], dtype=np.float32)
    if with_masses:
        u.add_TopologyAttr("masses", [15.035, 14.027, 17.007])
    return u.atoms


def _benzene_hless_fragment():
    """H-less benzene ring (PDB ligand style: heavy atoms only, no masses)."""
    n = 6
    u = mda.Universe.empty(n, n_residues=1, n_segments=1,
                           atom_resindex=[0] * n, trajectory=True)
    u.add_TopologyAttr("elements", ["C"] * n)
    u.add_TopologyAttr("names", [f"C{i}" for i in range(n)])
    u.add_TopologyAttr("resnames", ["BEN"])
    u.add_TopologyAttr("resids", [1])
    u.add_TopologyAttr("segids", ["SEG"])
    import math
    u.add_bonds([(i, (i + 1) % 6) for i in range(6)])
    u.atoms.positions = np.array(
        [[1.4 * math.cos(i * math.pi / 3), 1.4 * math.sin(i * math.pi / 3), 0.0]
         for i in range(6)], dtype=np.float32)
    return u.atoms


class TestB10UnitedAtom:
    """4.4 - B-10: united-atom / H-less molecules must not be perceived as
    radicals/carbanions; formula must account for inferred H."""

    ETHANOL_KEY = "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
    BENZENE_KEY = "UHOVQNZJYSORNB-UHFFFAOYSA-N"

    def _one(self, gen_cls, frag):
        from src_new.config.loader import SignaturesConfig
        from src_new.signatures.generators import _perceive_cache as pc
        pc.clear_cache()
        return gen_cls(SignaturesConfig())._generate(_instance(frag), frag, None)

    def test_ethanol_united_atom_recovers_standard_key(self):
        from src_new.signatures.generators.inchi import InchiKeyGenerator
        ik = self._one(InchiKeyGenerator, _ua_ethanol_fragment())
        assert ik == self.ETHANOL_KEY, (
            f"B-10: united-atom ethanol perceived as radicals: {ik}")

    def test_ethanol_united_atom_formula_has_inferred_h(self):
        from src_new.signatures.generators.formula import MolecularFormulaGenerator
        f = self._one(MolecularFormulaGenerator, _ua_ethanol_fragment())
        assert f == "C2H6O", f"B-10: H-less formula {f}"

    def test_ethanol_heavy_variant_emitted(self):
        from src_new.signatures.generators.formula import (
            MolecularFormulaHeavyGenerator)
        hv = self._one(MolecularFormulaHeavyGenerator, _ua_ethanol_fragment())
        assert hv == "C2O", hv

    def test_heavy_variant_not_applicable_for_all_atom(self):
        from src_new.config.loader import SignaturesConfig
        from src_new.signatures.generators.formula import (
            MolecularFormulaHeavyGenerator)
        gen = MolecularFormulaHeavyGenerator(SignaturesConfig())
        frag = _acetate_fragment()
        assert not gen.is_applicable(_instance(frag), frag, None)

    BENZENE_TODAY_KEY = "PXCDDPIOUAJVRE-UHFFFAOYSA-N"  # c1c#cc#cc#1 (limited)

    def test_benzene_hless_flagged_not_altered(self):
        """Mass-less H-less (open mode): H counts are not recoverable in
        general (benzene vs cyclohexane is ambiguous; even rdDetermineBonds
        yields the carbyne). Perception stays byte-identical to today,
        but the fragment is FLAGGED h_inferred and the heavy formula is
        emitted so queries have a sane fallback (B-10 evidence class)."""
        from src_new.config.loader import SignaturesConfig
        from src_new.signatures.generators._perceive_cache import _h_deficiency
        from src_new.signatures.generators.inchi import InchiKeyGenerator
        from src_new.signatures.generators.formula import (
            MolecularFormulaGenerator, MolecularFormulaHeavyGenerator)
        frag = _benzene_hless_fragment()
        assert _h_deficiency(frag) == {}, "open mode must be flagged"
        assert self._one(InchiKeyGenerator, frag) == self.BENZENE_TODAY_KEY
        assert self._one(MolecularFormulaGenerator, frag) == "C6"
        assert self._one(MolecularFormulaHeavyGenerator, frag) == "C6"

    def test_all_atom_formula_unchanged(self):
        """Acetate fixture (explicit H, no masses): zero behavior change."""
        from src_new.signatures.generators.formula import MolecularFormulaGenerator
        f = self._one(MolecularFormulaGenerator, _acetate_fragment())
        assert f == "C2H3O2", f

    def test_segment_flag_h_inferred(self):
        """The deficiency must be marked on the segment pipeline record."""
        from src_new.signatures.generators._perceive_cache import _h_deficiency
        assert _h_deficiency(_ua_ethanol_fragment()) is not None
        assert _h_deficiency(_acetate_fragment()) is None


def _frag_from_rdkit_mol(mol):
    """All-atom fragment from an RDKit mol (conformer 0), single residue."""
    import MDAnalysis as _mda
    n = mol.GetNumAtoms()
    els = [a.GetSymbol() for a in mol.GetAtoms()]
    u = _mda.Universe.empty(n, n_residues=1, n_segments=1,
                            atom_resindex=[0] * n, trajectory=True)
    u.add_TopologyAttr("elements", els)
    u.add_TopologyAttr("names", [f"{s}{i}" for i, s in enumerate(els)])
    u.add_TopologyAttr("resnames", ["LIG"])
    u.add_TopologyAttr("resids", [1])
    u.add_TopologyAttr("segids", ["SEG"])
    u.add_bonds([(int(b.GetBeginAtomIdx()), int(b.GetEndAtomIdx()))
                 for b in mol.GetBonds()])
    conf = mol.GetConformer()
    import numpy as _np
    u.atoms.positions = _np.array(
        [list(conf.GetAtomPosition(i)) for i in range(n)], dtype=_np.float32)
    return u.atoms


def _embed_rdkit(smiles, seed=0xF00D):
    """Deterministic ETKDG embedding (+3D stereo tags) of a smiles string."""
    from rdkit import Chem as _C
    from rdkit.Chem import AllChem
    m = _C.AddHs(_C.MolFromSmiles(smiles))
    AllChem.EmbedMolecule(m, randomSeed=seed)
    _C.AssignStereochemistryFrom3D(m)
    return m


class TestB11StereoFrom3D:
    """4.5 - B-11: with 3D coordinates available, InChIKey/SMILES must carry
    stereochemistry (today every key is the flat UHFFFAOYSA block)."""

    L_NICOTINE_KEY = "SNICXCGAKADSCV-JTQLQIEISA-N"     # (S)-nicotine, PubChem
    # verified vs RDKit MolToInchiKey("C/C=C/C") -> carries the /b4-3+ E layer
    TRANS_2BUTENE_KEY = "IAQRGUVFOMOMEM-ONEGZZNKSA-N"

    def _key(self, frag):
        from src_new.config.loader import SignaturesConfig
        from src_new.signatures.generators.inchi import InchiKeyGenerator
        from src_new.signatures.generators import _perceive_cache as pc
        pc.clear_cache()
        return InchiKeyGenerator(SignaturesConfig())._generate(
            _instance(frag), frag, None)

    def test_nicotine_chirality(self):
        frag = _frag_from_rdkit_mol(_embed_rdkit("CN1CCC[C@H]1c1cccnc1"))
        assert self._key(frag) == self.L_NICOTINE_KEY, (
            "B-11: chiral centre lost -> flat key (reference: PubChem nicotine)")

    def test_trans_2butene_ez(self):
        frag = _frag_from_rdkit_mol(_embed_rdkit("C/C=C/C"))
        assert self._key(frag) == self.TRANS_2BUTENE_KEY, (
            "B-11: E/Z geometry lost -> flat key")

    def test_achiral_system_flat_key_unchanged(self):
        """Achiral molecules keep the flat UHFFFAOYSA block (ethanol gate)."""
        ik = self._key(_ethanol_fragment())
        assert ik == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N", ik


def _two_chain_fragment(chainids=True):
    """Chains A and B in ONE unbonded fragment, ALA-GLY alternating, both
    resnumbered from 1 (the interleaving case from probe (c)); each chain has
    intact peptide C-N bonds."""
    names = ["N", "CA", "C", "O", "CB"]
    els = ["N", "C", "C", "O", "C"]
    apr = 5
    res_seq_a = ["ALA", "GLY", "SER", "ALA", "GLY"]
    res_seq_b = ["GLY", "SER", "ALA", "GLY", "SER"]
    n_res = 10
    n = n_res * apr
    u = mda.Universe.empty(n, n_residues=n_res, n_segments=1,
                           atom_resindex=[i // apr for i in range(n)],
                           trajectory=True)
    u.add_TopologyAttr("elements", els * n_res)
    u.add_TopologyAttr("names", names * n_res)
    u.add_TopologyAttr("resnames", res_seq_a + res_seq_b)
    u.add_TopologyAttr("resids", [1, 2, 3, 4, 5] * 2)
    if chainids:
        u.add_TopologyAttr("chainIDs", ["A"] * (apr * 5) + ["B"] * (apr * 5))
    u.add_TopologyAttr("segids", ["PRO"])
    bonds = []
    for k in range(n_res):
        b = k * apr
        bonds += [(b, b + 1), (b + 1, b + 2), (b + 2, b + 3), (b + 1, b + 4)]
        if k + 1 < n_res and (k + 1) % 5 != 0:  # no bond between chains
            bonds.append((b + 2, (k + 1) * apr))
    u.add_bonds(bonds)
    u.atoms.positions = np.arange(n * 3, dtype=np.float32).reshape(n, 3) / 7.0
    return u.atoms


class TestB05PerChainFasta:
    """4.6 - B-05: multi-chain fragments must emit one sequence per chain;
    interleaved/chimeric single strings are identification poison."""

    SEQ_A = "AGSAG"
    SEQ_B = "GSAGS"

    def _run(self, gen_cls, frag, **kw):
        from src_new.config.loader import SignaturesConfig
        gen = gen_cls(SignaturesConfig())
        return gen._generate(_instance(frag), frag, None)

    def test_map_protein_emits_per_chain(self):
        from src_new.signatures.generators.fasta import MapFastaGeneratorProtein
        out = self._run(MapFastaGeneratorProtein, _two_chain_fragment())
        assert isinstance(out, dict), f"no chain split: {out!r}"
        assert out.get("A") == self.SEQ_A and out.get("B") == self.SEQ_B, out

    def test_resname_protein_emits_per_chain(self):
        from src_new.signatures.generators.fasta import ResnameFastaGeneratorProtein
        out = self._run(ResnameFastaGeneratorProtein, _two_chain_fragment())
        assert isinstance(out, dict), f"no chain split: {out!r}"
        assert out.get("A") == self.SEQ_A and out.get("B") == self.SEQ_B, out

    def test_connectivity_split_without_chainids(self):
        from src_new.signatures.generators.fasta import MapFastaGeneratorProtein
        out = self._run(MapFastaGeneratorProtein, _two_chain_fragment(chainids=False))
        assert isinstance(out, dict) and set(out) == {"A", "B"}, out
        assert self.SEQ_A in out.values() and self.SEQ_B in out.values(), out

    def test_single_chain_returns_plain_string_unchanged(self):
        """Payload compatibility: one chain -> exactly today's string."""
        from src_new.signatures.generators.fasta import (
            MapFastaGeneratorProtein, fragment_to_protseq_map_based)
        from src_new.config.loader import SignaturesConfig
        frag = _protein_chain(6)
        out = self._run(MapFastaGeneratorProtein, frag)
        legacy = fragment_to_protseq_map_based(frag, SignaturesConfig())
        assert isinstance(out, str) and out == legacy == "AAAAAA", (out, legacy)

    def test_chain_suffix_canonical_normalization(self):
        from src_new.signatures.canonical import canonical_signature_type
        assert canonical_signature_type("fasta_map_protein[A]") == "residue_sequence_protein"
        assert canonical_signature_type("fasta_resname_nucleic[B]") == "residue_sequence_nucleotide"
        assert canonical_signature_type("smiles") == "smiles"
