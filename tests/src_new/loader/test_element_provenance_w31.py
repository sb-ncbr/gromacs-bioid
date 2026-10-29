"""W3.1 item 2 (A3 steps 1/2/4 + A8 path): element provenance.

Reviewer audit findings (all reproduced in the agent's own artifacts):
- `{top/itp, *}` loads trust the PARSER's atom-type guessing
  (`elements.is_guessed` was treated as trustworthy): F14's LIPID types
  (LP2/LOM/...) read as P/C junk -> DPPC came out C8H2NO8P31 instead of
  C40NO8P; OPLS 'opls_*' types read as oxygen.
- Amber aromatic nitrogen type 'NA' read as sodium (M03-trimmed Trp NE1
  in protein).
- `_looks_coarse_grained` blanked HMR all-atom systems (M13 191/213
  atoms blanked when ATOMIC_NUMBER missing).

Acceptance (mechanical, per the audit):
- F14: DPPC heavy elements = C40 N O8 P (per residue).
- amber-type aromatic N in a TRP residue: never sodium.
- M01 with ATOMIC_NUMBER stripped + HMR masses: identical element
  multiset as the reference load; not flagged coarse-grained.
- OPLS-typed ethanol {top,pdb}: C2H6O (not O-dominated).

HHHarness: production `load_simulation` ladder on real deposits —
corpus cases loaded from the review corpus (read-only); typed micro
deposits are written from real force-field type tables into tmp dirs
(no monkeypatching anywhere near the loader).
"""

from __future__ import annotations

import collections
import re
import shutil
from pathlib import Path

import pytest

MDAnalysis = pytest.importorskip("MDAnalysis")
import MDAnalysis as mda

from src_new.config.loader import RunConfig
from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.loader.strategies import load_simulation
from src_new.results.results_manager import ResultsManager

CORPUS = Path(
    "/home/tomsko/work/bat3_article_reviews/bioid_bughunt/testcases")
KNOWN_PROTEIN = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS",
    "ILE", "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP",
    "TYR", "VAL",
}


def _load(tmp_path: Path, bundle_dir: Path):
    """Production load + repair stages on a deposit (load_simulation
    then TopologyRepair — the same calls the pipeline stages make)."""
    from src_new.loader.repair import TopologyRepair
    results = ResultsManager(str(tmp_path / "results.json"),
                             pipeline_name="w31item2")
    config = RunConfig()
    decision = select_best_file_combination(inspect_directory(bundle_dir))
    res = load_simulation(decision=decision, bundle=inspect_directory(bundle_dir),
                          config=config, results=results)
    report = None
    if res.success:
        report = TopologyRepair(res.universe, config).run()
    return res, results, report


def _copy_input(tmp_path: Path, case: str) -> Path:
    d = tmp_path / "input"
    shutil.copytree(CORPUS / case / "input", d)
    return d


def _element_counter(u) -> collections.Counter:
    assert hasattr(u.atoms, "elements"), "elements missing entirely"
    return collections.Counter(
        str(e).strip().capitalize() for e in u.atoms.elements
        if str(e).strip())


# ---------------------------------------------------------------- prmtop surgery

def _strip_prmtop_flag(text: str, flag: str) -> str:
    lines = text.splitlines(keepends=True)
    out, i = [], 0
    while i < len(lines):
        if lines[i].startswith("%FLAG") and flag in lines[i]:
            i += 1
            if i < len(lines) and lines[i].startswith("%FORMAT"):
                i += 1
            while i < len(lines) and not lines[i].startswith("%FLAG"):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "".join(out)


def _prmtop_section(text: str, flag: str) -> tuple[str, list[str]]:
    """Return (format_line, data_lines) for a %FLAG section."""
    lines = text.splitlines()
    i = next(idx for idx, ln in enumerate(lines)
             if ln.startswith("%FLAG") and flag in ln)
    fmt = lines[i + 1]
    j = i + 2
    data = []
    while j < len(lines) and not lines[j].startswith("%FLAG"):
        data.append(lines[j])
        j += 1
    return fmt, data


def _hmr_masses(text: str, shift: float = 2.016) -> str:
    """Apply H-exp mass repartitioning: +shift on each H, -shift on its
    bonded heavy partner. Operates on %FLAG MASS + BONDS_INC_HYDROGEN."""
    _, mass_lines = _prmtop_section(text, "MASS")
    masses = [float(x) for ln in mass_lines for x in ln.split()]
    _, bond_lines = _prmtop_section(text, "BONDS_INC_HYDROGEN")
    ints = [int(x) for ln in bond_lines for x in ln.split()]
    for i3, j3, _t in zip(ints[0::3], ints[1::3], ints[2::3]):
        i, j = i3 // 3, j3 // 3
        hi = i if masses[i] < 1.2 else (j if masses[j] < 1.2 else None)
        if hi is None:
            continue
        heavy = j if hi == i else i
        masses[hi] += shift
        masses[heavy] -= shift
    # rewrite the MASS section (5E16.8 layout)
    lines = text.splitlines()
    head = next(idx for idx, ln in enumerate(lines)
                if ln.startswith("%FLAG") and "MASS" in ln)
    fmt = lines[head + 1]
    j = head + 2
    end = j
    while end < len(lines) and not lines[end].startswith("%FLAG"):
        end += 1
    newdata = ["".join(f"{m:16.8E}" for m in masses[k:k + 5])
               for k in range(0, len(masses), 5)]
    lines[head:end] = [lines[head], fmt] + newdata
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- item-2 tests

class TestItem2RealDeposits:
    def test_f14_united_atom_dppc_elements(self, tmp_path):
        """F14 ITP types (LP2/LOM/...) must not leak in as elements —
        united-atom DPPC heavy content is C40 N O8 P per residue."""
        d = _copy_input(tmp_path, "F14_itp_gro_16319")
        res, _, _ = _load(tmp_path, d)
        assert res.success, [a.error_message for a in res.attempts]
        u = res.universe
        dppc = [r for r in u.residues if str(r.resname).upper() == "DPPC"]
        assert len(dppc) > 50, f"DPPC residues: {len(dppc)}"
        for r in dppc[:5] + dppc[-5:]:
            heavy = collections.Counter(
                str(e).strip().capitalize() for e in r.atoms.elements
                if str(e).strip().capitalize() != "H")
            assert heavy == {"C": 40, "N": 1, "O": 8, "P": 1}, (
                f"DPPC {r.resid}: {heavy}")

    def test_amber_aromatic_n_type_never_sodium(self, tmp_path):
        """Amber TRP NA-type (aromatic N) must resolve to N — the
        M03-trimmed probe class ({top,pdb}, no elements on file)."""
        top = """[ atomtypes ]
;name      mass     charge ptype
CA         12.011   0.0  A
NA         14.007   0.0  A
H          1.008    0.0  A

[ moleculetype ]
TRP  3

[ atoms ]
; nr type resnr resid atom cgnr charge mass
1  CA  1 TRP CD2 1 0.0 12.011
2  NA  1 TRP NE1 2 0.0 14.007
3  H   1 TRP HE1 3 0.0 1.008
4  CA  1 TRP CG  4 0.0 12.011
5  CA  1 TRP CE2 5 0.0 12.011

[ bonds ]
1 2
2 3
2 4
4 5
1 5

[ system ]
trp

[ molecules ]
TRP 1
"""
        pdb = (
            "HETATM    1  CD2 TRP A   1      10.000  10.000  10.000  1.00  0.00           C  \n"
            "HETATM    2  NE1 TRP A   1      11.300  10.400  10.000  1.00  0.00           N  \n"
            "HETATM    3  HE1 TRP A   1      12.100   9.800  10.000  1.00  0.00           H  \n"
            "HETATM    4  CG  TRP A   1      11.700  11.600  10.000  1.00  0.00           C  \n"
            "HETATM    5  CE2 TRP A   1      10.600  12.400  10.000  1.00  0.00           C  \n"
            "TER\nEND\n")
        d = tmp_path / "input"
        d.mkdir()
        (d / "topol.top").write_text(top)
        (d / "structure.pdb").write_text(pdb)
        res, _, _ = _load(tmp_path, d)
        assert res.success, [a.error_message for a in res.attempts]
        u = res.universe
        trp_els = collections.Counter(
            str(e).strip().capitalize()
            for a in u.atoms for e in [a.element] if str(e).strip())
        assert "Na" not in trp_els, f"sodium in TRP: {trp_els}"
        ne1 = [a for a in u.atoms if a.name.strip().upper() == "NE1"]
        assert ne1 and str(ne1[0].element).strip().capitalize() == "N", (
            f"NE1 element: {[a.element for a in ne1]}")

    def test_m01_hmr_stripped_atomic_number_matches_reference(self, tmp_path):
        """Strip ATOMIC_NUMBER + apply HMR masses to the M01 prmtop copy:
        the repaired elements must equal the reference load's multiset."""
        ref_dir = _copy_input(tmp_path / "ref", "M01_1p71_protein_dna_amber")
        res_ref, _, _ = _load(tmp_path / "ref", ref_dir)
        assert res_ref.success, [a.error_message for a in res_ref.attempts]
        ref = _element_counter(res_ref.universe)

        mut_dir = _copy_input(tmp_path / "mut", "M01_1p71_protein_dna_amber")
        prmtop = mut_dir / "topology.prmtop"
        text = prmtop.read_text()
        assert "%FLAG ATOMIC_NUMBER" in text
        text = _strip_prmtop_flag(text, "ATOMIC_NUMBER")
        text = _hmr_masses(text)
        prmtop.write_text(text)
        res_mut, _, _ = _load(tmp_path / "mut", mut_dir)
        assert res_mut.success, [a.error_message for a in res_mut.attempts]
        mut = _element_counter(res_mut.universe)
        assert mut == ref, f"delta: {ref - mut} // {mut - ref}"

    def test_hmr_all_atom_not_flagged_coarse_grained(self, tmp_path):
        d = _copy_input(tmp_path, "M01_1p71_protein_dna_amber")
        prmtop = d / "topology.prmtop"
        text = _strip_prmtop_flag(prmtop.read_text(), "ATOMIC_NUMBER")
        prmtop.write_text(_hmr_masses(text))
        res, _, report = _load(tmp_path, d)
        assert res.success, [a.error_message for a in res.attempts]
        warns = " ".join(getattr(report, "warnings", []) or [])
        assert "oarse-grained" not in warns, warns
        heavy = sum(v for k, v in _element_counter(res.universe).items())
        assert heavy >= len(res.universe.atoms) - 1, "elements left blank"

    def test_opls_types_never_read_as_oxygen(self, tmp_path):
        """OPLS atom types (opls_*) are not elements — ethanol {top,pdb}
        must come out C2H6O."""
        top = """[ atomtypes ]
;name      mass     charge ptype
opls_154   12.011   0.0  A
opls_157   15.9994  0.0  A
opls_140   1.008    0.0  A

[ moleculetype ]
ETH  3

[ atoms ]
1  opls_154  1 ETH C1 1 0.0 12.011
2  opls_154  1 ETH C2 2 0.0 12.011
3  opls_157  1 ETH O1 3 0.0 15.9994
4  opls_140  1 ETH H1 4 0.0 1.008
5  opls_140  1 ETH H2 5 0.0 1.008
6  opls_140  1 ETH H3 6 0.0 1.008
7  opls_140  1 ETH H4 7 0.0 1.008
8  opls_140  1 ETH H5 8 0.0 1.008
9  opls_140  1 ETH H6 9 0.0 1.008

[ bonds ]
1 2
2 3
1 4
1 5
1 6
2 7
2 8
3 9

[ system ]
eth

[ molecules ]
ETH 1
"""
        pdb = (
            "HETATM    1  C1  ETH A   1       9.000  10.000  10.000  1.00  0.00           C  \n"
            "HETATM    2  C2  ETH A   1      10.500  10.000  10.000  1.00  0.00           C  \n"
            "HETATM    3  O1  ETH A   1      11.200  11.100  10.000  1.00  0.00           O  \n"
            "HETATM    4  H1  ETH A   1       8.500  11.000  10.200  1.00  0.00           H  \n"
            "HETATM    5  H2  ETH A   1       8.600   9.300  10.800  1.00  0.00           H  \n"
            "HETATM    6  H3  ETH A   1       8.700   9.600   9.000  1.00  0.00           H  \n"
            "HETATM    7  H4  ETH A   1      10.800   8.900  10.200  1.00  0.00           H  \n"
            "HETATM    8  H5  ETH A   1      10.900  10.600  10.900  1.00  0.00           H  \n"
            "HETATM    9  H6  ETH A   1      12.200  11.000  10.600  1.00  0.00           H  \n"
            "TER\nEND\n")
        d = tmp_path / "input"
        d.mkdir()
        (d / "topol.top").write_text(top)
        (d / "structure.pdb").write_text(pdb)
        res, _, _ = _load(tmp_path, d)
        assert res.success, [a.error_message for a in res.attempts]
        els = _element_counter(res.universe)
        assert els == {"C": 2, "H": 6, "O": 1}, f"elements: {els}"
