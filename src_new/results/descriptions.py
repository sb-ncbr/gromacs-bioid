"""dm1 audit (I5): coarse-grained and CA-only proteins are DESCRIBED.

A bead model has no atomistic chemistry, so nothing in it can be verified the
way an all-atom molecule is, and the meaning of identification and
verification does not change. What a bead model does carry is its residue
sequence and its fold: structure searches still find the protein
(figshare/11343020, CA-only BTK kinase domain: RCSB 3P08 at 100, Foldseek
Q06187 at 97.4). Each such protein segment gets a description: the
residue-name sequence and the top structure / sequence leads, all marked
unverified, under data/descriptions.
"""
from __future__ import annotations

from ..constants import KNOWN_RESIDUE_CODES

#: at most this many atoms per residue on average reads as a bead model
#: (CA-only: 1, Martini: 2-5 beads with side chain; all-atom proteins >= 7)
BEAD_ATOMS_PER_RESIDUE = 5.0
TOP_LEADS = 3

#: resolvers whose hits are database records of the whole molecule
_LEAD_RESOLVERS = ("pdb_struct_protein", "mmcif_struct", "foldseek_3di", "foldseek_pdb",
                   "alphafind_struct", "blast_swissprot_protein", "blast_uniprot",
                   "blast_pdb_protein", "blast_uniref50", "blast_nr_protein")


def _one_letter(resname: str) -> str:
    code = KNOWN_RESIDUE_CODES.get(resname.strip().upper()[:3])
    return code if isinstance(code, str) and len(code) == 1 else "X"


def _leads(identifiers: dict) -> list[dict]:
    out = []
    for sig_type, by_resolver in (identifiers or {}).items():
        if not isinstance(by_resolver, dict):
            continue
        for resolver, entry in by_resolver.items():
            base = resolver.split("@")[0]
            if not isinstance(entry, dict) or base not in _LEAD_RESOLVERS:
                continue
            hits = entry.get("hits") or []
            for rank, hit in enumerate(hits[:TOP_LEADS]):
                ident, score = (hit[0], hit[1]) if isinstance(hit, (list, tuple)) else (hit, None)
                out.append({"identifier": ident, "score": score, "resolver": base,
                            "signature_type": sig_type, "rank": rank + 1, "verified": False})
    out.sort(key=lambda h: (h["rank"], -(h["score"] or 0)))
    seen, unique = set(), []
    for h in out:
        if h["identifier"] not in seen:
            seen.add(h["identifier"])
            unique.append(h)
    return unique[:2 * TOP_LEADS]


def describe_bead_proteins(facade, data: dict) -> list[dict]:
    """One description per protein segment represented by beads."""
    cg_system = bool(((data.get("repair") or {}).get("report") or {}).get("coarse_grained"))
    segments = {s.get("segment"): s for s in ((data.get("fragments") or {}).get("segments") or [])
                if isinstance(s, dict)}
    out = []
    for name, seg in sorted(segments.items()):
        if seg.get("type") != "protein":
            continue
        try:
            frag = facade.get_fragment(name)
            n_res = len(frag.residues)
            per_res = frag.n_atoms / n_res if n_res else 0.0
        except Exception:
            continue
        if not n_res or (per_res > BEAD_ATOMS_PER_RESIDUE and not cg_system):
            continue
        sequence = "".join(_one_letter(r) for r in frag.residues.resnames)
        if set(sequence) == {"X"}:
            continue
        out.append({
            "segment": name,
            "state": "described",
            "representation": "coarse-grained" if cg_system or per_res > 1.5 else "CA-only",
            "atoms_per_residue": round(per_res, 2),
            "residues": n_res,
            "sequence": sequence,
            "leads": _leads((data.get("identifiers") or {}).get(name)),
            "note": "bead model: identifiers are leads, not verified identifications",
        })
    return out
