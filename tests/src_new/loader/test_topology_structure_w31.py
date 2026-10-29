"""W3.1 item 10 (A8): topology + structure loads — restart in the
PRMTOP_PDB chain, per-index name check, solvent-stripped prefix match.

Audit §3 item 10 / §2 A8 hazards (live evidence at HEAD):
- {prmtop, rst7/mdcrd, pdb} bundles never try the restart file (the
  PRMTOP_PDB ladder has only the pdb step);
- the prmtop/pdb atom order is never checked — a swapped residue
  loads silently with wrong 3D/stereo;
- the solvent-stripped prefix match is not implemented: M03 (GROMACS
  top + pdb) fails gromacs_top_pdb on the atom-count mismatch (its
  PDB is exactly the first 9,519 of 66,999 topology atoms) and falls
  back to PDB-only, losing bonds/charges/types/masses.

Accept (audit): M03 loads with its topology.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

MDAnalysis = pytest.importorskip("MDAnalysis")

CASES = Path("/home/tomsko/work/bat3_article_reviews/bioid_bughunt/testcases")
M03 = CASES / "M03_ace2_gromacs_top/input"


def _write_probe(dir_path: Path) -> Path:
    """REAL GROMACS top+itp+pdb probe: 7 atoms, two residues (HEM x6,
    FE x1), topology bonds FE-NAx4. The PDB carries the same atoms —
    the equal-count topology+structure path."""
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "heme.itp").write_text(
        "[ moleculetype ]\n"
        "; name  nrexcl\n"
        "HEME    3\n"
        "\n"
        "[ atoms ]\n"
        ";  nr  type  resnr residue  atom  cgnr  charge    mass\n"
        "     1   NP      1    HEM     NA     1    0.00  14.0067\n"
        "     2   NP      1    HEM     NB     1    0.00  14.0067\n"
        "     3   NP      1    HEM     NC     1    0.00  14.0067\n"
        "     4   NP      1    HEM     ND     1    0.00  14.0067\n"
        "     5   CT      1    HEM     CM1    1    0.00  12.0110\n"
        "     6   CT      1    HEM     CM2    1    0.00  12.0110\n"
        "     7   FE      2    FE      FE     2    2.00  55.8450\n"
        "\n"
        "[ bonds ]\n"
        ";  ai  aj  funct\n"
        "      1   5     1\n"
        "      2   5     1\n"
        "      3   6     1\n"
        "      4   6     1\n"
        "      1   7     1\n"
        "      2   7     1\n"
        "      3   7     1\n"
        "      4   7     1\n")
    (dir_path / "heme.top").write_text(
        '#include "heme.itp"\n'
        "\n"
        "[ system ]\n"
        "topology + structure probe\n"
        "\n"
        "[ molecules ]\n"
        "HEME 1\n")
    atoms = [("HEM", " NA ", " N", 1, 1.000, 1.000, 1.000),
             ("HEM", " NB ", " N", 2, 0.000, 1.000, 1.000),
             ("HEM", " NC ", " N", 3, 1.000, 0.000, 1.000),
             ("HEM", " ND ", " N", 4, 0.000, 0.000, 1.000),
             ("HEM", "CM1 ", " C", 5, 1.300, 1.300, 1.000),
             ("HEM", "CM2 ", " C", 6, 0.700, 0.700, 1.000),
             ("FE ", "FE  ", "FE", 7, 0.500, 0.500, 1.000)]
    lines = []
    for i, (res, name, elem, resid, x, y, z) in enumerate(atoms, 1):
        lines.append(
            f"ATOM  {i:5d} {name:4s}{'':1s}{res:>3s} {'A':1s}{resid:4d}{'':1s}   "
            f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{0.00:6.2f}"
            f"          {elem:>2s}  ")
    lines.append("TER\nEND")
    (dir_path / "heme.pdb").write_text("\n".join(lines) + "\n")
    return dir_path


def _run(case_dir: Path, tmp_path: Path, input_kind: str = "gromacs"):
    w31 = importlib.import_module(
        "tests.src_new.loader.test_chainless_topology_w31")
    return w31._run_results(case_dir, tmp_path, input_kind=input_kind)


def _attempts(data: dict) -> list[dict]:
    loading = data.get("loading") or {}
    return loading.get("attempts") or []


class TestM03TopologyLoad:
    def test_m03_loads_with_its_topology(self, tmp_path):
        """REAL corpus deposit (audit acceptance): the PDB is exactly
        the topology's first 9,519 atoms (solvent stripped for
        deposition) — the prefix match must load M03 WITH its topology
        (bonds/charges/types/masses), not fall back to PDB-only.
        RED at HEAD: gromacs_top_pdb fails on the atom-count
        mismatch, final strategy is plain PDB."""
        if not M03.is_dir():
            pytest.skip("corpus deposit not available")
        data = _run(M03, tmp_path)
        attempts = _attempts(data)
        top_pdb = [a for a in attempts
                   if a.get("strategy") == "gromacs_top_pdb"]
        assert top_pdb, f"no gromacs_top_pdb attempt: {attempts}"
        assert top_pdb[0].get("status") == "success", top_pdb[0]
        # the topology load must not corrupt the chemistry: the protein
        # formula carries no Na (atom types like 'NA' are AMBER N, and
        # M03 has no sodium)
        for seg, payload in (data.get("signatures") or {}).items():
            formula = str(((payload or {}).get("generated") or {})
                          .get("molecular_formula") or "")
            assert "Na" not in formula, (seg, formula)


class TestNameOrderCheck:
    def test_swapped_structure_atoms_rejected_loudly(self, tmp_path):
        """REAL top+itp+pdb files with two ATOM lines swapped in the
        PDB: the per-index name check (H-name normalised) must reject
        the topology+structure load instead of attaching wrong 3D
        silently. RED at HEAD: gromacs_top_pdb SUCCEEDS on the swapped
        structure."""
        probe = _write_probe(tmp_path / "probe")
        lines = (probe / "heme.pdb").read_text().splitlines()
        # swap the first two ATOM lines (NA <-> NB): same atom count,
        # wrong per-index names
        atom_lines = [i for i, l in enumerate(lines)
                      if l.startswith("ATOM")]
        assert len(atom_lines) >= 2
        i, j = atom_lines[0], atom_lines[1]
        lines[i], lines[j] = lines[j], lines[i]
        (probe / "heme.pdb").write_text("\n".join(lines) + "\n")
        data = _run(probe, tmp_path)
        attempts = _attempts(data)
        top_pdb = [a for a in attempts
                   if a.get("strategy") == "gromacs_top_pdb"]
        assert top_pdb, f"no gromacs_top_pdb attempt: {attempts}"
        assert top_pdb[0].get("status") == "failed", top_pdb[0]
        assert top_pdb[0].get("error_code") == "structure_name_mismatch", (
            top_pdb[0])

    def test_h_names_normalised(self, tmp_path):
        """REAL files, legitimate PDB H-name spelling (leading digit,
        '1HB' style) on an equal-count load: the name check must NOT
        fire. Uses a C-H pair where the PDB writes 'HC1' as '1HC'."""
        probe = _write_probe(tmp_path / "probe")
        # legit PDB H-name spelling: the topology writes 'HB1', the PDB
        # writes the same hydrogen with the leading-digit form '1HB' —
        # the normalised names are equal and the gate must NOT fire
        itp = probe / "heme.itp"
        itp.write_text(itp.read_text().replace("CM1", "HB1"))
        lines = (probe / "heme.pdb").read_text().splitlines()
        pdb = probe / "heme.pdb"
        pdb.write_text("\n".join(lines).replace("CM1 ", "1HB ") + "\n")
        data = _run(probe, tmp_path)
        attempts = _attempts(data)
        top_pdb = [a for a in attempts
                   if a.get("strategy") == "gromacs_top_pdb"]
        assert top_pdb and top_pdb[0].get("status") == "success", (
            attempts)


class TestPrmtopPdbChain:
    def test_prmtop_pdb_chain_tries_restart_files(self):
        """The PRMTOP_PDB decision ladder must include the restart
        coordinate sources (RST7, MDCRD) — a {prmtop, rst7, pdb}
        bundle previously never tried the restart file. RED at HEAD:
        the chain is only [PRMTOP_PDB, PARM7_PDB]."""
        from src_new.loader.strategies import (
            get_fallback_strategies, LoadStrategy)
        from src_new.input.models import (InputBundle, FileRecord,
                                           LoadDecision, InputKind)
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            files = [
                FileRecord(path=root / f"sys.{ext}", file_id=str(i),
                           file_type=ext, role="input")
                for i, ext in enumerate(("prmtop", "rst7", "mdcrd",
                                          "pdb"))]
            bundle = InputBundle(root_directory=root, files=files)
            decision = LoadDecision(input_kind=InputKind.AMBER,
                                    selected_strategy="PRMTOP_PDB")
            ladder = get_fallback_strategies(decision, bundle)
            assert LoadStrategy.AMBER_PRMTOP_RST7 in ladder, ladder
            assert LoadStrategy.AMBER_PRMTOP_MDCRD in ladder, ladder
            # and the static structure step stays available
            assert LoadStrategy.AMBER_PRMTOP_PDB in ladder, ladder
