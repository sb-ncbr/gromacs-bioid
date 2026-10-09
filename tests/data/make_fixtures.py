#!/usr/bin/env python3
"""Generate tiny synthetic test fixtures for the widened loading-strategy matrix.

Creates deterministic deposits under tests/data/ for:
  CHARMM  (psf+pdb / psf+crd / psf+dcd, dcd-only, psf+pdb atom-mismatch)
  AMBER   (prmtop+rst7, prmtop+mdcrd)
  LAMMPS  (.data)
  gate    (solvent-only pdb -> empty-catalog success)

The base system (38 atoms) deliberately uses CHARMM naming so fixtures double
as the naming-normalization probe: protein segid PROA residues
1 ALA, 2 GLY, 3 HSE (CHARMM histidine), 4 ALA; 2 x TIP3 waters; SOD + CLA ions.

Running this script writes all deposits AND parses each with MDAnalysis,
printing OK/FAIL per deposit (CP0 gate). Idempotent: overwrites files.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent

# ---------------------------------------------------------------- base system
# (resname, atomname, atomtype, element_mass, charge) per atom, in order.
PROTEIN_ATOMS: list[tuple[str, str, str, float, float]] = [
    # resid 1 ALA
    ("ALA", "N", "NH1", 14.007, -0.47),
    ("ALA", "HN", "H", 1.008, 0.31),
    ("ALA", "CA", "CT1", 12.011, 0.07),
    ("ALA", "HA", "HB1", 1.008, 0.09),
    ("ALA", "CB", "CT3", 12.011, -0.27),
    ("ALA", "C", "C", 12.011, 0.51),
    ("ALA", "O", "O", 15.999, -0.51),
    # resid 2 GLY
    ("GLY", "N", "NH1", 14.007, -0.47),
    ("GLY", "HN", "H", 1.008, 0.31),
    ("GLY", "CA", "CT2", 12.011, -0.02),
    ("GLY", "HA2", "HB2", 1.008, 0.09),
    ("GLY", "HA3", "HB2", 1.008, 0.09),
    ("GLY", "C", "C", 12.011, 0.51),
    ("GLY", "O", "O", 15.999, -0.51),
    # resid 3 HSE (CHARMM histidine)
    ("HSE", "N", "NH1", 14.007, -0.47),
    ("HSE", "CA", "CT1", 12.011, 0.07),
    ("HSE", "CB", "CT2", 12.011, -0.08),
    ("HSE", "CG", "CPG", 12.011, -0.05),
    ("HSE", "ND1", "NR1", 14.007, -0.36),
    ("HSE", "CE1", "CPH", 12.011, 0.32),
    ("HSE", "CD2", "CPT", 12.011, -0.19),
    ("HSE", "C", "C", 12.011, 0.51),
    ("HSE", "O", "O", 15.999, -0.51),
    # resid 4 ALA
    ("ALA", "N", "NH1", 14.007, -0.47),
    ("ALA", "CA", "CT1", 12.011, 0.07),
    ("ALA", "CB", "CT3", 12.011, -0.27),
    ("ALA", "C", "C", 12.011, 0.51),
    ("ALA", "O", "O", 15.999, -0.51),
]
WATER_ATOMS = [("TIP3", "OH2", "OT", 15.999, -0.834), ("TIP3", "H1", "HT", 1.008, 0.417),
               ("TIP3", "H2", "HT", 1.008, 0.417)]
ION_ATOMS = [("SOD", "SOD", "SOD", 22.990, 1.0), ("CLA", "CLA", "CLA", 35.450, -1.0)]


def _atoms() -> list[dict]:
    """Flat atom records: segid, resid, resname, name, type, mass, charge, pos."""
    out: list[dict] = []
    i = 0
    resid = 0
    prev = None
    for resname, name, atype, mass, q in PROTEIN_ATOMS:
        if prev is None or resname != prev or name == "N":
            if name == "N" or prev is None:
                resid = resid + 1 if prev is not None else 1
        prev = resname
        out.append({"segid": "PROA", "resid": resid, "resname": resname, "name": name,
                    "type": atype, "mass": mass, "charge": q,
                    "pos": (i * 1.9 + 1.0, (i % 5) * 1.2, (i % 3) * 0.9)})
        i += 1
    for w in range(2):
        for resname, name, atype, mass, q in WATER_ATOMS:
            out.append({"segid": "SOLV", "resid": 5 + w, "resname": resname, "name": name,
                        "type": atype, "mass": mass, "charge": q,
                        "pos": (i * 1.9 + 1.0, 8.0 + w, (i % 2) * 0.8)})
            i += 1
    for ion, (resname, name, atype, mass, q) in enumerate(ION_ATOMS):
        out.append({"segid": "IONS", "resid": 7 + ion, "resname": resname, "name": name,
                    "type": atype, "mass": mass, "charge": q,
                    "pos": (i * 1.9 + 1.0, -5.0, ion * 2.0)})
        i += 1
    return out


def _bonds(atoms: list[dict]) -> list[tuple[int, int]]:
    """1-based bond pairs: chain neighbours within each segment."""
    bonds = []
    start = 0
    for segid in ("PROA", "SOLV", "IONS"):
        idx = [i for i, a in enumerate(atoms) if a["segid"] == segid]
        if segid == "PROA":
            bonds += [(i + 1, j + 1) for i, j in zip(idx[:-1], idx[1:])]
        else:  # within residue only
            by_res: dict[int, list[int]] = {}
            for i in idx:
                by_res.setdefault(atoms[i]["resid"], []).append(i)
            for res in by_res.values():
                bonds += [(i + 1, j + 1) for i, j in zip(res[:-1], res[1:])]
        start += len(idx)
    return bonds


N = len(_atoms())


# --------------------------------------------------------------- file writers
def write_psf(path: Path) -> None:
    atoms = _atoms()
    bonds = _bonds(atoms)
    lines = ["PSF", "", "       1 !NTITLE", " REMARKS synthetic bat3 test fixture", ""]
    lines.append(f"{len(atoms):8d} !NATOM")
    for i, a in enumerate(atoms, 1):
        lines.append(
            f"{i:8d} {a['segid']:<4s} {a['resid']:<4d} {a['resname']:4s} {a['name']:4s} "
            f"{a['type']:4s} {a['charge']:>10.6f} {a['mass']:>13.4f}           0"
        )
    lines.append("")
    lines.append(f"{len(bonds):8d} !NBOND: bonds")
    for i in range(0, len(bonds), 4):
        chunk = bonds[i:i + 4]
        lines.append("".join(f"{a:8d}{b:8d}" for a, b in chunk))
    path.write_text("\n".join(lines) + "\n")


_PDB_RESNAME = {"TIP3": "WAT"}  # 3-char PDB limit


def write_pdb(path: Path, skip_last: int = 0) -> None:
    atoms = _atoms()
    if skip_last:
        atoms = atoms[:-skip_last]
    chain = {"PROA": "A", "SOLV": "W", "IONS": "I"}
    lines = []
    for i, a in enumerate(atoms, 1):
        rn = _PDB_RESNAME.get(a["resname"], a["resname"])[:3]
        x, y, z = a["pos"]
        elem = a["name"][0]
        lines.append(
            f"ATOM  {i:5d} {a['name']:^4s} {rn:>3s} {chain[a['segid']]}{a['resid']:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {elem:>2s}"
        )
    lines.append("END")
    path.write_text("\n".join(lines) + "\n")


def write_crd(path: Path) -> None:
    atoms = _atoms()
    lines = ["* synthetic bat3 test fixture", "*", f"{len(atoms):5d}"]
    for i, a in enumerate(atoms, 1):
        x, y, z = a["pos"]
        lines.append(
            f"{i:5d}{a['resid']:5d} {a['resname']:>4s} {a['name']:>4s}"
            f"{x:10.5f}{y:10.5f}{z:10.5f} {a['segid']:>4s} {a['resid']:>4d} {'0.0':>10s}"
        )
    path.write_text("\n".join(lines) + "\n")


def write_prmtop(path: Path) -> None:
    atoms = _atoms()
    bonds = _bonds(atoms)
    nres = max(a["resid"] for a in atoms)
    pointers = [0] * 31
    pointers[0] = len(atoms)    # NATOM
    pointers[3] = len(bonds)    # MBONA (bonds w/o hydrogen)
    pointers[12] = len(bonds)   # NBONA
    pointers[11] = nres         # NRES

    def flag(name: str, fmt: str, values: list, per_line: int, width: int, kind: str) -> list[str]:
        out = [f"%FLAG {name}", f"%FORMAT({fmt})"]
        for i in range(0, len(values), per_line):
            row = values[i:i + per_line]
            if kind == "i":
                out.append("".join(f"{v:{width}d}" for v in row))
            elif kind == "e":
                out.append("".join(f"{v:{width}.8E}" for v in row))
            else:
                out.append("".join(f"{str(v):<{width}s}" for v in row))
        return out

    lines = ["%VERSION  VERSION_STAMP = V0001.000  DATE = 01/01/26  00:00:00",
             "%FLAG TITLE", "%FORMAT(20a4)", "BAT3synthetictestfixtur"]
    lines += flag("POINTERS", "10I8", pointers, 10, 8, "i")
    lines += flag("ATOM_NAME", "20A4", [a["name"] for a in atoms], 20, 4, "s")
    lines += flag("CHARGE", "5E16.8", [a["charge"] * 18.2223 for a in atoms], 5, 16, "e")
    lines += flag("ATOMIC_NUMBER", "10I8", [int(round(a["mass"])) for a in atoms], 10, 8, "i")
    lines += flag("MASS", "5E16.8", [a["mass"] for a in atoms], 5, 16, "e")
    lines += flag("RESIDUE_LABEL", "20A4",
                  [atoms[j - 1]["resname"] for j in range(1, nres + 1)], 20, 4, "s")
    # RESIDUE_POINTER: first atom index (1-based) of each residue
    first_atoms, seen = [], set()
    for i, a in enumerate(atoms, 1):
        if a["resid"] not in seen:
            first_atoms.append(i)
            seen.add(a["resid"])
    lines += flag("RESIDUE_POINTER", "10I8", first_atoms, 10, 8, "i")
    lines += flag("AMBER_ATOM_TYPE", "20A4", [a["type"] for a in atoms], 20, 4, "s")
    # AMBER bond triplets: (3*(i-1), 3*(j-1), param_idx) for 1-based atom pairs
    triplets: list[int] = []
    for i, j in bonds:
        triplets += [3 * (i - 1), 3 * (j - 1), 1]
    lines += flag("BONDS_WITHOUT_HYDROGEN", "10I8", triplets, 10, 8, "i")
    lines += flag("BONDS_INC_HYDROGEN", "10I8", [], 10, 8, "i")
    lines += flag("ANGLES_WITHOUT_HYDROGEN", "10I8", [], 10, 8, "i")
    lines += flag("ANGLES_INC_HYDROGEN", "10I8", [], 10, 8, "i")
    lines += flag("DIHEDRALS_WITHOUT_HYDROGEN", "10I8", [], 10, 8, "i")
    lines += flag("DIHEDRALS_INC_HYDROGEN", "10I8", [], 10, 8, "i")
    path.write_text("\n".join(lines) + "\n")


def _write_coord70(path: Path, per_line: int, fmt: str) -> None:
    atoms = _atoms()
    flat = [c for a in atoms for c in a["pos"]]
    lines = ["default_name", f"{len(atoms):5d}"]
    for i in range(0, len(flat), per_line):
        lines.append("".join(fmt.format(v) for v in flat[i:i + per_line]))
    path.write_text("\n".join(lines) + "\n")


def write_rst7(path: Path) -> None:
    _write_coord70(path, per_line=6, fmt="{:12.7f}")


def write_mdcrd(path: Path) -> None:
    # MDAnalysis TRJReader (AMBER .mdcrd): title line, then coords 10/line F8.3.
    # NO natom header line (n_atoms comes from the paired topology).
    atoms = _atoms()
    flat = [c for a in atoms for c in a["pos"]]
    lines = ["default_name"]
    for i in range(0, len(flat), 10):
        lines.append("".join(f"{v:8.3f}" for v in flat[i:i + 10]))
    # AMBER box line (a b c alpha beta gamma) — TRJReader reads the line after
    # the frame for box detection and crashes on EOF (StopIteration).
    lines.append("".join(f"{v:8.3f}" for v in (80.0, 80.0, 80.0, 90.0, 90.0, 90.0)))
    path.write_text("\n".join(lines) + "\n")


def write_data(path: Path) -> None:
    atoms = _atoms()
    types: list[float] = sorted({a["mass"] for a in atoms})
    tmap = {m: k + 1 for k, m in enumerate(types)}
    lines = ["LAMMPS data file (bat3 test fixture)", "",
             f"{len(atoms):6d} atoms", f"{len(types):6d} atom types", "",
             "0.0 80.0 xlo xhi", "0.0 80.0 ylo yhi", "0.0 80.0 zlo zhi", "",
             "Masses", ""]
    lines += [f"{tmap[m]:6d} {m:10.4f}" for m in types]
    lines += ["", "Atoms  # full", ""]
    for i, a in enumerate(atoms, 1):
        x, y, z = a["pos"]
        lines.append(f"{i:6d} {a['resid']:6d} {tmap[a['mass']]:6d} {a['charge']:8.4f} "
                     f"{x:10.4f} {y:10.4f} {z:10.4f}")
    path.write_text("\n".join(lines) + "\n")


def write_solvent_pdb(path: Path) -> None:
    lines = []
    i = 1
    for w in range(3):
        for j, name in enumerate(("OH2", "H1", "H2")):
            lines.append(
                f"ATOM  {i:5d} {name:^4s} {'WAT':>3s} {'W'}{w + 1:4d}    "
                f"{w * 2.5:8.3f}{j * 0.9:8.3f}{0.0:8.3f}  1.00  0.00          {name[0]:>2s}"
            )
            i += 1
    lines.append("END")
    path.write_text("\n".join(lines) + "\n")


def write_dcd(path: Path, psf: Path, pdb: Path, frames: int = 3) -> None:
    import MDAnalysis as mda

    u = mda.Universe(str(psf), str(pdb))
    with mda.coordinates.DCD.DCDWriter(str(path), n_atoms=u.atoms.n_atoms) as w:
        for f in range(frames):
            u.atoms.positions = np.asarray([a["pos"] for a in _atoms()], dtype=np.float32) + f * 0.1
            w.write(u)


# ------------------------------------------------------------------- deposits
def build() -> dict[str, tuple]:
    """deposit name -> (verifier fn or None, expected n_atoms or None)."""

    def dep(name: str):
        d = DATA / name
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        return d

    builds: dict[str, tuple] = {}

    def register(name, writer, verifier, expected):
        writer()
        builds[name] = (verifier, expected)

    import MDAnalysis as mda

    d = dep("charmm_psf_pdb")
    psf, pdb = d / "system.psf", d / "system.pdb"
    register("charmm_psf_pdb", lambda: (write_psf(psf), write_pdb(pdb)),
             lambda: mda.Universe(str(psf), str(pdb)), N)

    d = dep("charmm_psf_crd")
    psf2, crd = d / "system.psf", d / "system.crd"
    register("charmm_psf_crd", lambda: (write_psf(psf2), write_crd(crd)),
             lambda: mda.Universe(str(psf2), str(crd)), N)

    d = dep("charmm_psf_dcd")
    psf3, dcd = d / "system.psf", d / "traj.dcd"
    register("charmm_psf_dcd", lambda: (write_psf(psf3), write_dcd(dcd, psf, pdb)),
             lambda: mda.Universe(str(psf3), str(dcd)), N)

    d = dep("charmm_dcd_only")
    dcd2 = d / "traj.dcd"
    register("charmm_dcd_only", lambda: write_dcd(dcd2, psf, pdb), None, None)

    d = dep("charmm_psf_pdb_mismatch")
    psf4, bad = d / "system.psf", d / "bad.pdb"
    register("charmm_psf_pdb_mismatch", lambda: (write_psf(psf4), write_pdb(bad, skip_last=6)),
             None, None)

    d = dep("amber_prmtop_rst7")
    prm, rst = d / "system.prmtop", d / "coords.rst7"
    register("amber_prmtop_rst7", lambda: (write_prmtop(prm), write_rst7(rst)),
             lambda: mda.Universe(str(prm), str(rst), topology_format="PRMTOP", format="RESTRT"), N)

    d = dep("amber_prmtop_mdcrd")
    prm2, md = d / "system.prmtop", d / "traj.mdcrd"
    register("amber_prmtop_mdcrd", lambda: (write_prmtop(prm2), write_mdcrd(md)),
             lambda: mda.Universe(str(prm2), str(md), topology_format="PRMTOP"), N)

    d = dep("lammps_data")
    dat = d / "system.data"
    register("lammps_data", lambda: write_data(dat),
             lambda: mda.Universe(str(dat), atom_style="id resid type q x y z"), N)

    d = dep("solvent_only_pdb")
    w = d / "waters.pdb"
    register("solvent_only_pdb", lambda: write_solvent_pdb(w), lambda: mda.Universe(str(w)), 9)

    return builds


def main() -> int:
    builds = build()
    failed = 0
    for name, (verifier, expected) in builds.items():
        if verifier is None:
            print(f"SKIP {name} (negative fixture, nothing to parse)")
            continue
        try:
            u = verifier()
            assert u.atoms.n_atoms == expected, f"expected {expected} atoms, got {u.atoms.n_atoms}"
            print(f"OK   {name}: {u.atoms.n_atoms} atoms, {len(u.residues)} residues")
        except Exception as exc:  # noqa: BLE001 - generator gate reports all failures
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
            failed += 1
    print(f"\n{len(builds) - failed}/{len(builds)} fixtures verified")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
