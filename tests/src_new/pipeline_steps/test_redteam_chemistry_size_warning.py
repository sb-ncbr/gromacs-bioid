"""bughunt BH-032: large molecules get no chemistry and no explanation.

M12 enramycin (309 atoms) produced no SMILES/InChI because
smiles_maximum_number_of_atoms = 250 — and no message anywhere.
_chemistry_size_skipped drives the new chemistry_skipped_size run
warning (formula and residue-name signatures still generate; the
smiles gate is unchanged).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src_new.pipeline_steps import _chemistry_size_skipped


class TestChemistrySizeSkipped:
    def test_enramycin_case_skipped(self):
        # 309 atoms, nothing chemistry-shaped generated
        assert _chemistry_size_skipped(309, ["molecular_formula", "fasta_map_protein"], 250)

    def test_large_molecule_with_smiles_not_skipped(self):
        # above the cap but the smiles gate let it through (explicit bonds
        # path, cap raised, etc.) — no warning
        assert not _chemistry_size_skipped(309, ["smiles", "molecular_formula"], 250)

    def test_small_molecule_never_warns(self):
        assert not _chemistry_size_skipped(42, [], 250)

    def test_none_atom_count_never_warns(self):
        # instance without atom metadata — conservative no-warning
        assert not _chemistry_size_skipped(None, [], 250)

    def test_chained_signature_key_handled(self):
        # B-05 chained fasta keys look like "fasta_map_protein[A]"
        assert _chemistry_size_skipped(309, ["fasta_map_protein[A]"], 250)
        assert not _chemistry_size_skipped(309, ["smiles[A]"], 250)
