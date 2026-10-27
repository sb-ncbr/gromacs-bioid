"""Wave-2 item 8b/8c/8d: glycan composition generator map-union, sialic
alias round-trip in the resolver, and the SMILES-generator carbohydrate
skip (1FC1 hang class).
"""

from __future__ import annotations

import types

from src_new.config.loader import RunConfig, SignaturesConfig
from src_new.identification.resolvers.glycan import GlycanCompositionResolver
from src_new.molecules.instances import MoleculeType
from src_new.signatures.generators.glycan import GlycanCompositionGenerator
from src_new.signatures.generators.smiles import SimpleSmilesGenerator


def _fragment(resnames):
    return types.SimpleNamespace(
        residues=types.SimpleNamespace(resnames=resnames),
        segids=["C"],
    )


def _instance(mtype):
    return types.SimpleNamespace(instance_id="t", molecule_type=mtype)


class TestGlycanCompositionGeneratorMaps:
    def test_1fc1_like_ccd_composition(self):
        # 1FC1 segments C/D shape: NAG2-BMA-MAN2-FUC via CCD codes
        gen = GlycanCompositionGenerator(SignaturesConfig())
        frag = _fragment(["NAG", "NAG", "BMA", "MAN", "MAN", "FUC"])
        out = gen._generate(_instance(MoleculeType.CARBOHYDRATE), frag, None)
        assert out == "Hex(3)HexNAc(2)dHex(1)"

    def test_all_map_families_consulted(self):
        # glycam (0GA/0YB/0SA) + charmm36 (AGLC) + ccd (SIA) in one segment
        gen = GlycanCompositionGenerator(SignaturesConfig())
        frag = _fragment(["0GA", "0YB", "0SA", "AGLC", "SIA"])
        out = gen._generate(_instance(MoleculeType.CARBOHYDRATE), frag, None)
        assert out == "Hex(2)HexNAc(1)NeuAc(2)"

    def test_unmapped_residue_is_x(self):
        gen = GlycanCompositionGenerator(SignaturesConfig())
        frag = _fragment(["NAG", "QRS"])
        out = gen._generate(_instance(MoleculeType.CARBOHYDRATE), frag, None)
        assert out == "HexNAc(1)X(1)"

    def test_applicable_only_for_carbohydrate(self):
        gen = GlycanCompositionGenerator(SignaturesConfig())
        frag = _fragment(["NAG"])
        assert gen._is_applicable(_instance(MoleculeType.CARBOHYDRATE), frag, None)
        assert not gen._is_applicable(_instance(MoleculeType.SMALL_MOLECULE), frag, None)


class TestSialicAliasRoundTrip:
    def _parse(self, s):
        return GlycanCompositionResolver(RunConfig())._parse_composition(s)

    def test_neuac_maps_to_neu5ac(self):
        # the generator emits "NeuAc" — the resolver must accept it
        assert self._parse("Hex(3)NeuAc(1)") == {"hex": 3, "neu5ac": 1}

    def test_neugc_variants_map_to_neu5gc(self):
        assert self._parse("NeuGc(1)") == {"neu5gc": 1}
        assert self._parse("Neu5Gc(2)") == {"neu5gc": 2}
        assert self._parse("Neu5G(1)") == {"neu5gc": 1}  # legacy spelling

    def test_case_insensitive(self):
        assert self._parse("HEX(2)hexnac(1)DHEX(1)") == {
            "hex": 2, "hexnac": 1, "dhex": 1}

    def test_full_1fc1_string_round_trip(self):
        out = self._parse("Hex(3)HexNAc(2)dHex(1)")
        assert out == {"hex": 3, "hexnac": 2, "dhex": 1}


class TestSmilesSkipsCarbohydrates:
    def test_carbohydrate_instance_not_applicable(self):
        gen = SimpleSmilesGenerator(SignaturesConfig())
        frag = _fragment(["NAG", "BMA"])
        assert gen._is_applicable(
            _instance(MoleculeType.CARBOHYDRATE), frag, None) is False

    def test_small_molecule_gate_unchanged(self):
        # non-carbohydrate instances still consult the facade flags
        gen = SimpleSmilesGenerator(SignaturesConfig())
        facade = types.SimpleNamespace(
            get_segment_properties=lambda name: types.SimpleNamespace(
                flags={"has_elements": True}))
        frag = types.SimpleNamespace(
            residues=types.SimpleNamespace(resnames=["LIG"]),
            segids=["S"],
            n_atoms=1,
        )
        # 1 atom < 2 -> still not applicable, but via the OLD gate path
        assert gen._is_applicable(
            _instance(MoleculeType.SMALL_MOLECULE), frag, facade) is False
