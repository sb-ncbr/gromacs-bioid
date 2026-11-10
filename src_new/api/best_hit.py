"""A molecule's answer, decided exactly as the web application decides it.

Mirror of ui/src/features/results/viewmodel (adapter.ts resultOf, derive.ts
stateOf / formatDb / confLabel, labels.ts DB_LABELS): the verified hits are
ranked by final_confidence, highest first (ties keep the stored order); the
top one is the answer. Ground-truth overrides and element matches are
"exact" and carry no confidence; a verified answer below 50 is a "lead".
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
                "not_identified": "not identified"}


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


def state_of(top: Optional[dict[str, Any]]) -> str:
    if not top:
        return "not_identified"
    if top.get("ground_truth_override") or top.get("database") == "element":
        return "exact"
    conf = top.get("final_confidence")
    if conf is not None and conf < MEDIUM_MIN:
        return "lead"
    return "identified"


def _display_id(hit: dict[str, Any]) -> str:
    ident = hit.get("identifier") or ""
    return normalize_identifier(ident, hit.get("ident_type") or "") or ident


def molecule_result(hits: list[Any]) -> dict[str, Any]:
    """best hit, state, database label, identifier, URL, confidence, alternatives."""
    verified = ranked_verified(hits)
    top = verified[0] if verified else None
    state = state_of(top)
    confidence = None if (top is None or state == "exact") else top.get("final_confidence")
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
