"""GitHub #17: the mmCIF fallback writer must produce a loop gemmi can read
(it read 0 models / 0 atoms, so mmcif-routed hits never got a TM-score),
while the PDB text the mmcif_struct resolver sends to RCSB stays the same."""
from __future__ import annotations

import os

import pytest

gemmi = pytest.importorskip("gemmi")
mda = pytest.importorskip("MDAnalysis")

from src_new.identification.resolvers.mmcif import (  # noqa: E402
    _mmcif_text_to_pdb, _na_only_mmcif_payload, _no_polymer_mmcif_payload)
from src_new.signatures.generators.mmcif import MmCifGenerator  # noqa: E402
from src_new.verification.workers.structure_worker import extract_ca_chains  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "nucleic")


def _fallback(path, tmp_path):
    u = mda.Universe(path)
    if not hasattr(u.atoms, "elements"):  # the loader guesses elements
        u.add_TopologyAttr("elements", [n.lstrip("0123456789")[:1] for n in u.atoms.names])
    gen = MmCifGenerator.__new__(MmCifGenerator)
    return u, gen._generate_mmcif_fallback(u.atoms, str(tmp_path / "x.cif"))


def _old_format(u) -> str:
    """The pre-#17 writer (10 columns), for the RCSB-payload comparison."""
    lines = ["data_mock", "", "loop_"] + [f"_atom_site.{c}" for c in (
        "group_PDB", "id", "label_atom_id", "label_comp_id", "label_asym_id",
        "label_seq_id", "Cartn_x", "Cartn_y", "Cartn_z", "type_symbol")]
    a = u.atoms
    for i in range(a.n_atoms):
        p = a.positions[i]
        lines.append(f"ATOM {i+1} {a.names[i]} {a.resnames[i]} {a.segids[i]} {a.resids[i]} "
                     f"{p[0]:.3f} {p[1]:.3f} {p[2]:.3f} {a.elements[i]}")
    return "\n".join(lines + ["#"])


def test_gemmi_reads_fallback_and_ca_traces_exist(tmp_path):
    u, text = _fallback(os.path.join(FIXTURES, "cytc_protein.pdb"), tmp_path)
    st = gemmi.read_structure_string(text) if hasattr(gemmi, "read_structure_string") else None
    if st is None:
        p = tmp_path / "s.cif"
        p.write_text(text)
        st = gemmi.read_structure(str(p))
    assert len(st) == 1
    assert sum(len(r) for c in st[0] for r in c) == u.atoms.n_atoms
    traces = extract_ca_chains(text)
    assert traces and sum(len(seq) for _c, seq, _x in traces) == len(u.select_atoms("name CA"))


def test_rcsb_payload_unchanged(tmp_path):
    u, text = _fallback(os.path.join(FIXTURES, "cytc_protein.pdb"), tmp_path)
    if any(not str(e).strip() for e in u.atoms.elements) or any(not str(s).strip() for s in u.atoms.segids):
        pytest.skip("fixture has blank fields (old format dropped those rows)")
    assert _mmcif_text_to_pdb(text) == _mmcif_text_to_pdb(_old_format(u))


def test_payload_classifiers_unchanged(tmp_path):
    for name in ("cytc_protein.pdb", "cytc_dna.pdb", "cytc_hem.pdb"):
        u, text = _fallback(os.path.join(FIXTURES, name), tmp_path)
        old = _old_format(u)
        assert _na_only_mmcif_payload(text) == _na_only_mmcif_payload(old), name
        assert _no_polymer_mmcif_payload(text) == _no_polymer_mmcif_payload(old), name


def test_blank_fields_become_placeholders(tmp_path):
    from src_new.signatures.generators.mmcif import _ATOM_SITE_COLUMNS, _cif_value
    assert _cif_value("") == "?" and _cif_value(" ") == "?" and _cif_value("CA") == "CA"
    _u, text = _fallback(os.path.join(FIXTURES, "cytc_protein.pdb"), tmp_path)
    rows = [ln for ln in text.splitlines() if ln.startswith("ATOM ")]
    assert all(len(r.split()) == len(_ATOM_SITE_COLUMNS) for r in rows)
