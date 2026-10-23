"""Red-team Batch 1.8 (verification/API) regression tests.

  D-15: fidelity tie-break "identifier asc" compared numerically-typed ids
        as strings ('10' < '2') — deterministic but semantically wrong
        order on every plateau.
  D-16: the water ground-truth pin fired on the FIRST skel==1.0 chemical
        hit — db-ordered, so hydroxide/hydronium/peroxide could be named
        "water". The pin requires a formula+H-count match now.
  D-17: rejected rows stored similarity/annotation scores as None even
        when a worker ran ('never compared' == 'measured 12'); database
        name derivation was inconsistent ('pubchem_cid' vs 'pdb').
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest


def _hit(identifier, skel=1.0, sim=50.0, conf=50.0, ev=1, ident_type="PUBCHEM_CID"):
    return SimpleNamespace(
        identifier=identifier, ident_type=ident_type, skeleton_sim=skel,
        similarity_score=sim, final_confidence=conf,
        supporting_evidence_count=ev, is_verified=True,
    )


class TestD15NumericTieBreak:
    def test_numeric_identifiers_sort_numerically_on_plateaus(self):
        from src_new.verification.manager import _fidelity_order_hits

        hits = [_hit("10"), _hit("2"), _hit("1"), _hit("20")]
        ordered = _fidelity_order_hits(hits)
        assert [h.identifier for h in ordered] == ["1", "2", "10", "20"], (
            "string-asc tie-break put CID '10' before '2' on plateaus (D-15)"
        )

    def test_mixed_identifiers_stay_deterministic(self):
        from src_new.verification.manager import _fidelity_order_hits

        hits = [_hit("9XYZ", ident_type="PDB_ID"), _hit("3"), _hit("1ABC", ident_type="PDB_ID")]
        ordered = _fidelity_order_hits(hits)
        # numeric ids first (numeric), then lexical ids — deterministic
        assert [h.identifier for h in ordered] == ["3", "1ABC", "9XYZ"]


class TestD16WaterPinFormulaMatch:
    def _results_with(self, segment, formula=None, atom_count_fragment=3):
        store = {f"universe/segments/{segment}/properties": {
            "type": "water",
            "atom_count_fragment": atom_count_fragment,
        }}
        if formula:
            store[f"signatures/{segment}/generated/molecular_formula"] = formula

        class _R:
            def get_data(self, path):
                return store.get(path)
        return _R()

    def test_h2o_candidate_pins(self):
        from src_new.verification.manager import _water_formula_match

        results = self._results_with("SOL", formula="H2O")
        assert _water_formula_match(results, "SOL", "[OH2]") is True

    def test_hydroxide_and_peroxide_do_not_pin(self):
        """The observed failure class: db order put OH-/H2O2 first in the
        sku fingerprint plateau and the segment was named after them."""
        from src_new.verification.manager import _water_formula_match

        results = self._results_with("SOL", formula="H2O")
        assert _water_formula_match(results, "SOL", "[OH-]") is False
        assert _water_formula_match(results, "SOL", "OO") is False

    def test_unparseable_candidate_never_pins(self):
        from src_new.verification.manager import _water_formula_match

        results = self._results_with("SOL", formula="H2O")
        assert _water_formula_match(results, "SOL", None) is False
        assert _water_formula_match(results, "SOL", "not-a-smiles-!!") is False

    def test_missing_molecule_formula_keeps_legacy_first_match(self):
        """No formula signature generated: the API must not silently
        downgrade runs — legacy behavior (first skel==1.0 pins)."""
        from src_new.verification.manager import _water_formula_match

        results = self._results_with("SOL", formula=None)
        assert _water_formula_match(results, "SOL", "[OH2]") is None


class TestD17MeasurementsAndNames:
    def test_unverified_row_keeps_measurements(self):
        from src_new.verification.models import VerifiedHit

        hit = VerifiedHit.unverified(
            identifier="1234", ident_type="PUBCHEM_CID", database="pubchem",
            resolver_score=50.0, rejection_reason="below_threshold",
            similarity_score=12.0,
        )
        d = hit.__dict__ if not hasattr(hit, "model_dump") else hit.model_dump()
        assert d["similarity_score"] == 12.0, (
            "a rejected row with measured S=12 was indistinguishable from "
            "'never compared' (D-17)"
        )
        # rejected rows keep the 0.0 confidence floor
        assert d["final_confidence"] == 0.0

    def test_database_name_normalization(self):
        from src_new.verification.manager import _database_name

        assert _database_name("PUBCHEM_CID") == "pubchem"
        assert _database_name("INCHIKEY") == "pubchem"
        assert _database_name("PDB_ID") == "pdb"
        assert _database_name("UNIPROT_ID") == "uniprot"
        assert _database_name("ELEMENT") == "element"

    def test_single_belief_field(self):
        import src_new.verification.models as m

        src = open(m.__file__).read()
        assert src.count("belief: float | None = None") == 1, (
            "duplicate `belief` field declaration in VerifiedHit (D-17)"
        )
