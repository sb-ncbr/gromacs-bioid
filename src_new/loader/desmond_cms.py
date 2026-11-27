"""dm1 audit (L6): Desmond / Maestro system files (.cms, .mae) read without
the Schrodinger suite.

The Maestro format is blocks of typed keys, ``:::``, then values; atoms and
bonds are indexed blocks (``m_atom[N] { keys ::: rows ::: }``). A Desmond
.cms holds one f_m_ct block for the whole system (s_ffio_ct_type
"full_system") followed by one per component; the full system is used when
present, otherwise the components are concatenated. Atom names, residues,
chains, elements, bonds, coordinates and the box come from the file, so the
rest of the pipeline sees a system as complete as a topology load.
"""
from __future__ import annotations

import re
from pathlib import Path

_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|(:::)|([{}])|([^\s{}"]+)')


class CmsFormatError(ValueError):
    pass


def _tokens(text: str):
    text = re.sub(r"(?m)^\s*#.*?#\s*$", " ", text)  # "# comment #" lines
    for m in _TOKEN.finditer(text):
        if m.group(1) is not None:
            yield ("s", m.group(1).replace('\\"', '"').replace("\\\\", "\\"))
        elif m.group(2):
            yield (":::", None)
        elif m.group(3):
            yield (m.group(3), None)
        else:
            yield ("w", m.group(4))


class _Reader:
    def __init__(self, text: str):
        self.toks = list(_tokens(text))
        self.i = 0

    def next(self):
        if self.i >= len(self.toks):
            raise CmsFormatError("unexpected end of file")
        t = self.toks[self.i]
        self.i += 1
        return t

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def block(self) -> dict:
        """After '{': keys ::: values, then child blocks until '}'."""
        keys = []
        while self.peek()[0] == "w":
            keys.append(self.next()[1])
        values = {}
        if self.peek()[0] == ":::":
            self.next()
            for k in keys:
                values[k] = self.next()[1]
        children = []
        while True:
            kind, val = self.next()
            if kind == "}":
                return {"values": values, "children": children}
            if kind != "w":
                raise CmsFormatError(f"unexpected token {kind} {val!r}")
            m = re.fullmatch(r"(\w+)\[(\d+)\]", val)
            if self.next()[0] != "{":
                raise CmsFormatError(f"block {val} without '{{'")
            if m:
                children.append((m.group(1), self.table(int(m.group(2)))))
            else:
                children.append((val, self.block()))

    def table(self, n: int) -> dict:
        keys = []
        while self.peek()[0] == "w":
            keys.append(self.next()[1])
        if self.next()[0] != ":::":
            raise CmsFormatError("indexed block without ':::'")
        rows = []
        for _ in range(n):
            self.next()  # row index
            rows.append({k: self.next()[1] for k in keys})
        if self.next()[0] != ":::":
            raise CmsFormatError("indexed block not closed with ':::'")
        depth = 0
        while True:  # skip nested blocks inside tables, if any
            kind, _ = self.next()
            if kind == "{":
                depth += 1
            elif kind == "}":
                if depth == 0:
                    return {"keys": keys, "rows": rows}
                depth -= 1

    def document(self) -> list[tuple[str, dict]]:
        out = []
        while self.peek()[0] is not None:
            kind, val = self.next()
            if kind == "{":  # anonymous version block
                out.append(("", self.block()))
            elif kind == "w":
                if self.next()[0] != "{":
                    raise CmsFormatError(f"block {val} without '{{'")
                out.append((val, self.block()))
            else:
                raise CmsFormatError(f"unexpected token {kind}")
        return out


def _missing(v) -> bool:
    return v is None or v == "<>"


def read_cms(path: Path) -> dict:
    """Parse a .cms/.mae into flat atom/bond arrays (1 entry per atom)."""
    cts = [b for name, b in _Reader(Path(path).read_text(errors="replace")).document()
           if name == "f_m_ct"]
    if not cts:
        raise CmsFormatError("no f_m_ct block")
    full = [c for c in cts if c["values"].get("s_ffio_ct_type") == "full_system"]
    cts = full[:1] or cts
    atoms, bonds, box = [], [], None
    for ci, ct in enumerate(cts):
        tables = dict(ct["children"])
        table = tables.get("m_atom")
        if not table:
            continue
        base = len(atoms)
        for row in table["rows"]:
            chain = row.get("s_m_chain_name")
            atoms.append({
                "name": (row.get("s_m_pdb_atom_name") or "").strip() if not _missing(row.get("s_m_pdb_atom_name")) else "",
                "resname": (row.get("s_m_pdb_residue_name") or "UNK").strip() if not _missing(row.get("s_m_pdb_residue_name")) else "UNK",
                "resid": int(row["i_m_residue_number"]) if not _missing(row.get("i_m_residue_number")) else 1,
                "chain": chain.strip() if not _missing(chain) and chain.strip() else f"C{ci}",
                "z": int(row["i_m_atomic_number"]) if not _missing(row.get("i_m_atomic_number")) else 0,
                "xyz": (float(row["r_m_x_coord"]), float(row["r_m_y_coord"]), float(row["r_m_z_coord"])),
            })
        for row in (tables.get("m_bond") or {"rows": []})["rows"]:
            a, b = int(row["i_m_from"]) - 1 + base, int(row["i_m_to"]) - 1 + base
            if a != b:
                bonds.append((min(a, b), max(a, b)))
        if box is None:
            v = ct["values"]
            try:
                ax, by, cz = (float(v[k]) for k in ("r_chorus_box_ax", "r_chorus_box_by", "r_chorus_box_cz"))
                off = [float(v.get(k, 0) or 0) for k in ("r_chorus_box_ay", "r_chorus_box_az", "r_chorus_box_bx",
                                                          "r_chorus_box_bz", "r_chorus_box_cx", "r_chorus_box_cy")]
                if not any(off):
                    box = [ax, by, cz, 90.0, 90.0, 90.0]
            except (KeyError, TypeError, ValueError):
                pass
    if not atoms:
        raise CmsFormatError("no atoms")
    return {"atoms": atoms, "bonds": sorted(set(bonds)), "box": box}


def cms_universe(path: Path):
    """An MDAnalysis Universe of a .cms/.mae: one segment per chain, residues
    by (chain, residue number, residue name) runs, authored bonds."""
    import numpy as np
    from MDAnalysis import Universe
    from MDAnalysis.core.topology import Topology
    from MDAnalysis.core.topologyattrs import (
        Atomnames, Atomtypes, Bonds, Elements, Masses, Resids, Resnames, Segids)
    from MDAnalysis.guesser.tables import masses as _MASSES
    from rdkit.Chem import GetPeriodicTable

    data = read_cms(path)
    pt = GetPeriodicTable()
    seg_of: dict[str, int] = {}
    atom_res, res_seg, resnames, resids = [], [], [], []
    last = None
    for a in data["atoms"]:
        key = (a["chain"], a["resid"], a["resname"])
        if key != last:
            seg = seg_of.setdefault(a["chain"], len(seg_of))
            res_seg.append(seg)
            resnames.append(a["resname"])
            resids.append(a["resid"])
            last = key
        atom_res.append(len(resnames) - 1)
    elements = [pt.GetElementSymbol(a["z"]) if 0 < a["z"] < 119 else "X" for a in data["atoms"]]
    names = [a["name"] or f"{el}{i + 1}" for i, (a, el) in enumerate(zip(data["atoms"], elements))]
    top = Topology(len(names), len(resnames), len(seg_of),
                   atom_resindex=atom_res, residue_segindex=res_seg)
    top.add_TopologyAttr(Atomnames(names))
    top.add_TopologyAttr(Atomtypes(elements))
    top.add_TopologyAttr(Elements(elements))
    top.add_TopologyAttr(Masses([float(_MASSES.get(e.upper(), 0.0)) for e in elements]))
    top.add_TopologyAttr(Resids(resids))
    top.add_TopologyAttr(Resnames(resnames))
    top.add_TopologyAttr(Segids(list(seg_of)))
    top.add_TopologyAttr(Bonds(data["bonds"]))
    u = Universe(top)
    u.load_new(np.array([a["xyz"] for a in data["atoms"]], dtype=np.float32), format="memory")
    if data["box"]:
        u.dimensions = data["box"]
    return u
