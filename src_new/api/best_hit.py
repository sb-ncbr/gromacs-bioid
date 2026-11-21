"""A molecule's answer, decided exactly as the web application decides it.

Mirror of ui/src/features/results/viewmodel (adapter.ts resultOf, derive.ts
stateOf / formatDb / confLabel, labels.ts DB_LABELS): the verified hits are
ranked by final_confidence, highest first (ties keep the stored order); the
top one is the answer. Ground-truth overrides and element matches are
"exact" and carry no confidence; a verified answer below 50 is a "lead".
A coarse-grained molecule (beads, no atoms) with nothing verified is
"coarse_grained" (2026-11-21, mdval audit item 8b).
Keep the two in step (tests/src_new/api/test_best_hit.py pins the rules).
"""
from __future__ import annotations

from typing import Any, Optional

from .utils import build_database_url, normalize_identifier

HIGH_MIN = 80
MEDIUM_MIN = 50

# ui/src/features/results/viewmodel/labels.ts DB_LABELS
DB_LABELS = {
    "pdb": "PDB", "pdb_id": "PDB", "uniprot": "UniProt", "uniprot_id": "UniProt",
    "pubchem_cid": "PubChem", "pubchem": "PubChem", "chembl": "ChEMBL", "chebi": "ChEBI",
    "swisslipids": "SwissLipids", "alphafold": "AlphaFold DB", "element": "Element",
    "nr": "NCBI protein", "nt": "NCBI nucleotide", "core_nt": "NCBI nucleotide",
    "lm": "LIPID MAPS", "lipidmaps": "LIPID MAPS", "glytoucan": "GlyTouCan",
}

STATE_LABELS = {"identified": "identified", "lead": "lead", "exact": "exact",
                "not_identified": "not identified", "coarse_grained": "coarse-grained"}


def format_db(db: Optional[str]) -> str:
    if not db:
        return "Database"
    return DB_LABELS.get(db) or db[:1].upper() + db[1:].replace("_", " ")


def conf_label(confidence: Optional[float]) -> Optional[str]:
    if confidence is None:
        return None
    if confidence >= HIGH_MIN:
        return "high"
    if confidence >= MEDIUM_MIN:
        return "medium"
    return "low"


def ranked_verified(hits: list[Any]) -> list[dict[str, Any]]:
    verified = [h for h in hits if isinstance(h, dict) and h.get("is_verified")]
    conf = lambda h: h.get("final_confidence") if h.get("final_confidence") is not None else -1
    return sorted(verified, key=conf, reverse=True)  # stable, like Array.sort


def state_of(top: Optional[dict[str, Any]], coarse_grained: bool = False) -> str:
    if not top:
        # 2026-11-21 (mdval audit item 8b): a bead model cannot be checked
        # against a database — not a failed identification. A verified hit
        # (a Martini protein's sequence BLASTs fine) still wins.
        return "coarse_grained" if coarse_grained else "not_identified"
    if top.get("ground_truth_override") or top.get("database") == "element":
        return "exact"
    conf = top.get("final_confidence")
    if conf is not None and conf < MEDIUM_MIN:
        return "lead"
    return "identified"


def _display_id(hit: dict[str, Any]) -> str:
    ident = hit.get("identifier") or ""
    return normalize_identifier(ident, hit.get("ident_type") or "") or ident


def coarse_grained_label(verdict: Optional[dict[str, Any]]) -> str:
    """ui derive.ts cgLabel: "Coarse-grained (Martini POPE)"."""
    verdict = verdict or {}
    what = " ".join(x for x in (verdict.get("model"), verdict.get("residue")) if x)
    return f"Coarse-grained ({what})" if what else "Coarse-grained"


def coarse_grained_of(data: dict[str, Any], segment: str) -> Optional[dict[str, Any]]:
    """2026-11-21 (mdval audit item 8b): a molecule's coarse-grained verdict
    ({"model", "residue", "by_name"?}) or None. Runs before the verdict was
    recorded per molecule: a coarse-grained run's molecule without elements."""
    d = (data or {}).get("data") or data or {}
    for entry in ((d.get("fragments") or {}).get("segments") or []):
        if isinstance(entry, dict) and entry.get("segment") == segment:
            if isinstance(entry.get("coarse_grained"), dict):
                return entry["coarse_grained"]
            break
    report = (d.get("universe") or {}).get("repair_report") or {}
    if report.get("coarse_grained") or report.get("elements_source") == "coarse_grained_blank":
        props = (((d.get("universe") or {}).get("segments") or {}).get(segment) or {}).get("properties") or {}
        if props and not props.get("has_elements", True):
            return {"model": report.get("coarse_grained_model") or "", "residue": ""}
    return None


def molecule_result(hits: list[Any], coarse_grained: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """best hit, state, database label, identifier, URL, confidence, alternatives."""
    verified = ranked_verified(hits)
    top = verified[0] if verified else None
    state = state_of(top, coarse_grained=coarse_grained is not None)
    confidence = None if (top is None or state == "exact") else top.get("final_confidence")
    if state == "coarse_grained":
        return {
            "best": None, "state": state, "state_label": STATE_LABELS[state],
            "database": "", "identifier": "", "url": "",
            "confidence": None, "confidence_label": None, "alternatives": [],
            "name": coarse_grained_label(coarse_grained),
            "by_name": (coarse_grained or {}).get("by_name"),
        }
    return {
        "best": top,
        "state": state,
        "state_label": STATE_LABELS[state],
        "database": format_db(top.get("database")) if top else "",
        "identifier": _display_id(top) if top else "",
        "url": (build_database_url(top.get("identifier"), top.get("ident_type") or "") or "") if top else "",
        "confidence": confidence,
        "confidence_label": conf_label(confidence),
        "alternatives": [f"{format_db(h.get('database'))}:{_display_id(h)}" for h in verified[1:4]],
    }
