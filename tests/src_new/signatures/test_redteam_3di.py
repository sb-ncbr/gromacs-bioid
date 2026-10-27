"""bughunt BH-008: the 3Di generator always failed.

encode_atoms was called as (n, ca, c, cb) — the API is (ca, cb, n, c) —
and the returned uint8 states were treated as strings
('Cannot set fill value of string with array of dtype uint8'), so every
protein logged 'mini3di encoding failed' and 3di_sequence was never
produced.
"""

from __future__ import annotations

import types

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis")
pytest.importorskip("mini3di")

from src_new.config.loader import SignaturesConfig
from src_new.molecules.instances import MoleculeType
from src_new.signatures.generators.tdi import ThreeDiGenerator


def _helix_universe(n_res: int):
    """Ideal-ish alpha-helix backbone: CA on a helix, N/C one step back/
    forth along the helix, CB radially outward."""
    atoms = []
    for i in range(n_res):
        th = np.deg2rad(100.0 * i)
        def p(r, dy, ph):
            t = th + np.deg2rad(ph)
            return [r * np.cos(t), 1.5 * i + dy, r * np.sin(t)]
        atoms += [
            ("N", p(1.5, -1.0, 0)),
            ("CA", p(2.3, 0.0, 0)),
            ("C", p(1.5, 1.0, 57)),
            ("CB", p(3.8, 0.0, 0)),
        ]
    n = len(atoms)
    u = mda.Universe.empty(n, n_residues=n_res, n_segments=1,
                           atom_resindex=[i // 4 for i in range(n)],
                           trajectory=True)
    u.add_TopologyAttr("names", [a[0] for a in atoms])
    u.add_TopologyAttr("elements", ["N", "C", "C", "C"] * n_res)
    u.add_TopologyAttr("resnames", ["ALA"] * n_res)
    u.add_TopologyAttr("resids", list(range(1, n_res + 1)))
    u.add_TopologyAttr("segids", ["A"])
    u.load_new(np.array([[a[1] for a in atoms]], dtype=np.float32),
               format="memory")
    return u


class TestThreeDiGeneration:
    def test_helix_encodes_one_state_per_residue(self):
        n_res = 24
        u = _helix_universe(n_res)
        gen = ThreeDiGenerator(SignaturesConfig())
        seq = gen._generate(
            types.SimpleNamespace(instance_id="t", molecule_type=MoleculeType.PROTEIN),
            u.atoms, None)
        assert len(seq) == n_res
        assert seq.isalpha() and seq == seq.lower()
        # helix interior states should repeat (not random garbage)
        assert len(set(seq)) < n_res
