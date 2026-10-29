"""W3.1 item 9 (A7): identify grouping-key defects (remaining parts —
the fasta bracket keys were fixed with item 1b).

Audit §2/§3 item 9:
- the water skip never fires: name_molecule carries the common name
  ("water"), not a resname, and the formula (H2O) was never checked —
  C05/P04 water segments were grouped as small molecules and resolved;
- the standard InChIKey merges tautomers (C18: 2-pyridone vs
  2-hydroxypyridine share UBQKCCHYAOITMY-UHFFFAOYSA-N but had
  different top-1 hits pre-W3) — key must add the canonical SMILES;
- the name-based fallback key ("ion", display name) merges unrelated
  species that happen to share a name — must be a singleton (real ions
  carry molecular_formula_heavy, C13/C16/C17, and merge via formula);
- the polymer -> ligand -> ion group ordering is computed but never
  applied to the resolution order;
- nothing retries with another member when the representative fails.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("MDAnalysis")
pytest.importorskip("rdkit")

CASES = Path("/home/tomsko/work/bat3_article_reviews/bioid_bughunt/testcases")
C05 = CASES / "C05_caffeine_in_water/input"
C18 = CASES / "C18_pyridone_tautomers/input"
P04 = CASES / "P04_3ptb_trypsin_benzamidine/input"


def _groups_for(case: Path, tmp_path: Path, input_kind: str = "pdb"):
    """REAL corpus deposit through the real executor (stages 0-5),
    then the production _group_segments on the real generated data —
    exactly the items _identify_molecules would build."""
    from src_new.pipeline_steps import _group_segments
    w31 = importlib.import_module(
        "tests.src_new.loader.test_chainless_topology_w31")
    data = w31._run_results(case, tmp_path, input_kind=input_kind)
    sigs = data.get("signatures") or {}
    items = []
    for name in sorted(sigs):
        gen = (sigs[name] or {}).get("generated") or {}
        if not gen or not {k: v for k, v in gen.items() if v}:
            continue
        items.append((name, gen))
    reps, member_map, rep_to_group = _group_segments(items)
    return items, reps, member_map, rep_to_group


class TestWaterSkip:
    @pytest.mark.parametrize("case", [C05, P04])
    def test_water_segments_skipped_from_groups(self, case, tmp_path):
        """C05 (water with an InChIKey — the inchi branch) and P04
        (water with formula only — the small_formula branch): water is
        not worth resolving and must be skipped from the groups
        entirely. RED at HEAD: both water segments were grouped."""
        if not case.is_dir():
            pytest.skip("corpus deposit not available")
        items, reps, member_map, _ = _groups_for(case, tmp_path)
        water = [name for name, gen in items
                 if str(gen.get("molecular_formula") or "").strip()
                 in ("H2O", "D2O")]
        assert water, f"no water segment found in {case.parent.name}"
        grouped = set(reps) | set(member_map)
        assert not (set(water) & grouped), (
            f"water segments must be skipped, not grouped: {water}")

    def test_water_key_paths(self):
        """Unit pins for the skip itself: common name, resname, and
        formula each fire it (the old check only matched resnames
        through name_molecule/name_segment)."""
        from src_new.pipeline_steps import _identify_group_key
        assert _identify_group_key("W", {
            "name_molecule": "water"}) is None
        assert _identify_group_key("W", {
            "resname": "HOH"}) is None
        assert _identify_group_key("W", {
            "molecular_formula": "H2O"}) is None
        assert _identify_group_key("W", {
            "name_molecule": "water"}) is None
        # heavy-water spellings
        assert _identify_group_key("W", {
            "resname": "DOD"}) is None
        # NOT water: keep grouping
        assert _identify_group_key("L", {
            "name_molecule": "caffeine",
            "inchi_key": "RYYVLZVUVIJVGH-UHFFFAOYSA-N"}) is not None


class TestTautomerSafeKey:
    def test_c18_tautomers_in_different_groups(self, tmp_path):
        """REAL corpus deposit: 2-pyridone and 2-hydroxypyridine share
        an InChIKey but are different molecules with different resolvers
        answers (pre-W3 evidence) — they must NOT share an identify
        group. RED at HEAD: both keyed ("small", same InChIKey)."""
        if not C18.is_dir():
            pytest.skip("corpus deposit not available")
        items, reps, member_map, rep_to_group = _groups_for(C18, tmp_path)
        assert len(items) == 2, items
        a, b = items[0][0], items[1][0]
        assert member_map.get(b) != a and member_map.get(a) != b, (
            f"tautomers merged into one group: {rep_to_group}")
        # and they are two separate groups, not just ungrouped
        assert {a, b} <= set(reps), (reps, member_map)

    def test_identical_copies_still_merge(self):
        """Guard: adding the SMILES to the key must not split true
        copies (identical generated payloads stay one group)."""
        from src_new.pipeline_steps import _identify_group_key
        payload = {"inchi_key": "UBQKCCHYAOITMY-UHFFFAOYSA-N",
                   "smiles": "O=c1cccc[nH]1"}
        assert _identify_group_key("A", payload) == \
            _identify_group_key("B", dict(payload))

    def test_key_includes_smiles(self):
        from src_new.pipeline_steps import _identify_group_key
        k1 = _identify_group_key("A", {
            "inchi_key": "UBQKCCHYAOITMY-UHFFFAOYSA-N",
            "smiles": "O=c1cccc[nH]1"})
        k2 = _identify_group_key("B", {
            "inchi_key": "UBQKCCHYAOITMY-UHFFFAOYSA-N",
            "smiles": "Oc1ccccn1"})
        assert k1 != k2, "tautomers (same InChIKey, different SMILES)"


class TestFallbackSingleton:
    def test_name_fallback_is_singleton(self):
        """Two DIFFERENT species sharing a display name and lacking
        chemistry+formula must not merge (audit: the fallback key can
        merge unrelated species)."""
        from src_new.pipeline_steps import _identify_group_key
        k1 = _identify_group_key("X1", {"name_molecule": "unknown"})
        k2 = _identify_group_key("X2", {"name_molecule": "unknown"})
        assert k1 != k2

    def test_real_ions_still_merge_via_formula(self):
        """Guard: real ions carry molecular_formula_heavy (C13/C16/C17
        evidence) — identical ions must keep merging through the
        formula branch."""
        from src_new.pipeline_steps import _identify_group_key
        ion = {"atom": "Cl", "molecular_formula_heavy": "Cl",
               "fingerprint": "fp-Cl"}
        assert _identify_group_key("A", dict(ion)) == \
            _identify_group_key("B", dict(ion))


class TestGroupOrderApplied:
    def test_resolution_follows_group_order(self, tmp_path):
        """The polymer -> small -> ion ordering must be APPLIED to the
        resolution order (audit: computed but never applied). Names are
        chosen so alphabetical order differs from group order.
        RED at HEAD: calls follow the alphabetical item order."""
        a7 = importlib.import_module(
            "tests.src_new.pipeline_steps.test_identify_grouping_a7")
        sigs = {"Z_PROT": a7._poly_sigs("KDKAAAA"),
                "M_LIG": a7._small_sigs("DOAKLVKFURWEDJ-HOASTROESA-K"),
                "A_ION": a7._ion_sigs("Cl")}
        ctx, results, _ = a7._ctx(tmp_path, sigs)
        instances = a7._run_identify(ctx)
        order: list = []
        for inst in instances:
            for seg in inst.calls:
                if seg not in order:
                    order.append(seg)
        assert order == ["Z_PROT", "M_LIG", "A_ION"], (
            f"resolution must follow the group order, got {order}")


class TestRetryNextMember:
    def test_rep_failure_retries_with_next_member(self, tmp_path):
        """A resolver failure on the representative must not unresolve
        the whole group: the next member is retried and, on success,
        its identifiers are promoted to the group. RED at HEAD: the
        group goes unresolved, nobody retries."""
        a7 = importlib.import_module(
            "tests.src_new.pipeline_steps.test_identify_grouping_a7")
        sigs = {s: a7._poly_sigs("KDKAAAA") for s in ("A", "B", "C")}

        class _MgrFailRep:
            """Real-shaped double: the resolution manager resolves any
            segment EXCEPT the representative 'A' (transient resolver
            failure on the first copy)."""
            instances: list = []

            def __init__(self, *a, **k):
                self.calls: list = []
                _MgrFailRep.instances.append(self)

            def resolve(self, results, segment, signature_generator_name,
                        signature, cache, working_directory, errors,
                        deadline_epoch=None):
                self.calls.append(segment)
                if segment == "A":
                    errors.append({"resolver": "stub",
                                   "generator": signature_generator_name,
                                   "error": "transient failure"})
                    return 0
                results.set_data(
                    f"identifiers/{segment}/{signature_generator_name}",
                    {"identity": {"ident_type": "UNIPROT_ID", "hits": [
                        {"ident_value": "P0A6F9",
                         "confidence": 99.0}]}})

        _MgrFailRep.instances.clear()
        ctx, results, warnings_ = a7._ctx(tmp_path, sigs)
        with patch("src_new.identification.resolution_manager"
                   ".IdentifierResolutionManager", _MgrFailRep):
            from src_new.pipeline_steps import \
                _identify_molecules as identify_molecules
            identify_molecules(ctx)

        for seg in ("A", "B", "C"):
            payload = results.get_data(f"identifiers/{seg}")
            assert payload, (
                f"{seg} must have identifiers after the member retry")
        # the promoted source carries its own identifiers; the OTHER
        # members (including the failed representative) inherit with
        # _shared_with pointing at the source
        sources = {seg for seg in ("A", "B", "C")
                   if results.get_data(f"identifiers/{seg}")
                   and "_shared_with" not in str(
                       results.get_data(f"identifiers/{seg}"))}
        assert len(sources) == 1, sources
        src = sources.pop()
        for seg in ("A", "B", "C"):
            if seg == src:
                continue
            shared = results.get_data(f"identifiers/{seg}")
            assert shared.get("_shared_with") == src, (seg, src)
        unresolved = results.get_data("identification/unresolved_groups")
        assert not [g for g in (unresolved or [])
                    if "A" in (g.get("members") or [])], unresolved
