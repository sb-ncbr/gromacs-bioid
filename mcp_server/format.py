"""Turning BioID API payloads into compact, model-readable summaries.

The interpretation mirrors the BioID web UI (ui/src/features/results/
viewmodel): a molecule's answer is its highest-confidence *verified* hit;
confidence >= 80 is "high", >= 50 "medium", below that a "lead"; an element
match (monoatomic ion) is exact.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

HIGH_MIN = 80.0
MEDIUM_MIN = 50.0

DB_LABELS = {
    "pdb": "PDB", "pdb_id": "PDB", "uniprot": "UniProt", "uniprot_id": "UniProt",
    "pubchem": "PubChem", "pubchem_cid": "PubChem", "chembl": "ChEMBL", "chebi": "ChEBI",
    "swisslipids": "SwissLipids", "alphafold": "AlphaFold DB", "element": "Element",
    "lipidmaps": "LIPID MAPS", "glytoucan": "GlyTouCan", "rnacentral": "RNAcentral",
    "nr": "NCBI protein", "nt": "NCBI nucleotide", "core_nt": "NCBI nucleotide", "lm": "LIPID MAPS",
}

_CHEMICAL_DBS = {"pubchem", "pubchem_cid", "chembl", "chebi", "swisslipids", "lipidmaps"}
_SEQUENCE_DBS = {"pdb", "pdb_id", "uniprot", "uniprot_id", "alphafold"}

TERMINAL = {"success", "failed", "cancelled"}

GUIDE = """\
How to read BioID results
- Each molecule (a segment of the simulated system: a protein chain, a ligand,
  a lipid type, ions, water, ...) is searched in public databases (PDB, UniProt,
  PubChem, ChEMBL, ChEBI, SwissLipids, ...). Every database hit is then
  VERIFIED against the simulated molecule itself (sequence identity, chemical
  structure / skeleton similarity, element), and given a final confidence 0-100.
- Only verified hits count. The answer for a molecule is its verified hit with
  the highest confidence; other verified hits are equivalent or close records
  in the same or other databases.
- Confidence: >= 80 high, 50-80 medium, < 50 low ("lead": a plausible but weak
  match). state="exact" means a definitive match (a monoatomic ion matched to
  its element); state="not_identified" means nothing passed verification
  (rejected hits explain why - e.g. sequence identity too low, different
  formula).
- Simulation force fields often rename or strip atoms (hydrogens, protonation,
  united-atom lipids, coarse-grained beads), so a correct molecule can still
  get a medium score; similarity hits (homologues/analogues) are reported with
  their identity/similarity in the evidence text.
- A run that reports 'partial' searches (e.g. a BLAST database timed out) may
  have missed some databases; the status warnings name them.
"""


RESULTS_JSON_GUIDE = """\
results.json: the complete record of a BioID run (1-5 MB, more for big systems).
Full reference: {docs}
Download: GET {api}/<run_id>/download/results.json (or the get_results_json tool).

Main paths (segment = one distinct molecule; ligands/ions/water split off a
chain are virtual segments named <chain>__v<N>):
- pipeline.status                      queued|running|success|failed|cancelled
- tasks.<stage>.status / .summary      per pipeline stage; summary.partial=true = time budget hit
- warnings[]                           {{code, message, severity, details}}
- data.fragments.segments[]            {{segment, type, copies, atoms_per_copy}} = the molecule list
- data.signatures.<seg>.generated      generator -> description searched (sequence, SMILES, formula...)
- data.identifiers.<seg>.<generator>.<resolver>
                                       raw database hits: {{hits[], hits_metadata, hit_type, ident_type}};
                                       resolver@sim = similarity search
- data.stage_errors.identifiers.<seg>  failed searches {{generator, resolver, error}}
- data.verification.<seg>.verified_hits[]
                                       THE RESULT: {{identifier, database, name, organism, hit_type,
                                       is_verified, final_confidence 0-100, belief, similarity_score,
                                       annotation_quality_score, equivalence_class_id, rejection_reason}}
                                       NOT sorted: best = max final_confidence among is_verified
- data.verification._meta              confidence formula and weights
- data.config                          the configuration the run used
"""


def conf_label(confidence: Optional[float]) -> Optional[str]:
    if confidence is None:
        return None
    if confidence >= HIGH_MIN:
        return "high"
    if confidence >= MEDIUM_MIN:
        return "medium"
    return "low"


def db_label(db: Optional[str]) -> str:
    if not db:
        return ""
    return DB_LABELS.get(db.lower(), db)


def _pct(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    p = value * 100 if value <= 1 else value
    return round(p, 1)


def _fmt(p: float) -> str:
    return str(int(p)) if float(p).is_integer() else f"{p:.1f}"


def evidence(hit: dict[str, Any]) -> str:
    db = (hit.get("database") or "").lower()
    if db == "element":
        return "same element"
    if db in ("foldseek", "alphafind"):
        return "same structure (stereo not compared)"
    if db in _SEQUENCE_DBS:
        p = _pct(hit.get("similarity_score"))
        return f"{_fmt(p)}% sequence identity" if p is not None else "matched by sequence"
    if db in _CHEMICAL_DBS:
        p = _pct(hit.get("similarity_score"))
        if p is not None and p >= 99:
            return "same structure"
        s = _pct(hit.get("skeleton_sim"))
        if s is not None:
            return f"similar skeleton ({_fmt(s)}%)"
        if p is not None:
            return f"similar skeleton ({_fmt(p)}%)"
        return "matched by structure"
    return "database match"


def rejection_clause(reason: Optional[str]) -> str:
    if not reason:
        return "did not pass verification"
    r = reason.lower()
    m = re.search(r"identity[^\d]*(\d+(?:\.\d+)?)", r)
    if m:
        return f"sequence identity below {m.group(1)}%"
    if "identity" in r:
        return "sequence identity too low"
    if "unavailable" in r:
        return "could not be checked"
    if "struct" in r or "fingerprint" in r or "skeleton" in r:
        return "chemical structure does not match"
    if "formula" in r:
        return "different chemical formula"
    if "element" in r:
        return "different element"
    if any(k in r for k in ("check", "verify", "fail")):
        return "could not be checked"
    return "did not pass verification"


def _round(v: Optional[float]) -> Optional[float]:
    return None if v is None else round(float(v), 1)


def sorted_verified(hits: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    verified = [h for h in hits if isinstance(h, dict) and h.get("is_verified")]
    # stable: equal confidences keep the server's order (as the UI does)
    return sorted(verified, key=lambda h: -(h.get("final_confidence") if h.get("final_confidence") is not None else -1))


def hit_view(hit: dict[str, Any], *, full: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "database": db_label(hit.get("database")),
        "id": hit.get("identifier"),
        "name": hit.get("name"),
    }
    if hit.get("organism"):
        out["organism"] = hit["organism"]
    conf = _round(hit.get("final_confidence"))
    out["confidence"] = conf
    out["confidence_label"] = conf_label(conf)
    out["evidence"] = evidence(hit)
    if hit.get("database_url"):
        out["url"] = hit["database_url"]
    if full:
        for key in ("similarity_score", "skeleton_sim", "resolver_score", "annotation_quality_score"):
            if hit.get(key) is not None:
                out[key] = _round(hit[key])
        out["ident_type"] = hit.get("ident_type")
    return {k: v for k, v in out.items() if v is not None}


def state_of(top: Optional[dict[str, Any]]) -> str:
    if not top:
        return "not_identified"
    if top.get("ground_truth_override") or (top.get("database") or "").lower() == "element":
        return "exact"
    conf = top.get("final_confidence")
    if conf is not None and conf < MEDIUM_MIN:
        return "lead"
    return "identified"


def identification(hits: list[dict[str, Any]], *, other_db_limit: int = 4) -> dict[str, Any]:
    """Per-molecule answer from that molecule's verification hits."""
    verified = sorted_verified(hits)
    rejected = [h for h in hits if isinstance(h, dict) and not h.get("is_verified")]
    top = verified[0] if verified else None
    out: dict[str, Any] = {"state": state_of(top)}
    if top:
        out["best"] = hit_view(top)
        seen_db = {(top.get("database") or "").lower()}
        also: list[str] = []
        for h in verified[1:]:
            db = (h.get("database") or "").lower()
            if db in seen_db:
                continue
            seen_db.add(db)
            also.append(f"{db_label(db)}:{h.get('identifier')}")
            if len(also) >= other_db_limit:
                break
        if also:
            out["also_in"] = also
    out["verified_hits"] = len(verified)
    out["rejected_hits"] = len(rejected)
    return out


def hits_by_segment(verification: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_seg: dict[str, list[dict[str, Any]]] = {}
    default_seg = verification.get("segment")
    for h in verification.get("hits") or []:
        if not isinstance(h, dict):
            continue
        seg = h.get("segment") or default_seg or ""
        by_seg.setdefault(seg, []).append(h)
    return by_seg


def molecule_rows(molecules: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    segments = molecules.get("segments") or []
    meta = molecules.get("segment_meta") or {}
    return [(seg, meta.get(seg) or {}) for seg in segments]


def molecule_head(seg: str, meta: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"molecule": seg}
    name = meta.get("display_name")
    if name and name != seg:
        out["display_name"] = name
    out["kind"] = meta.get("type") or "unknown"
    copies = meta.get("copies")
    if copies and copies != 1:
        out["copies"] = copies
    if meta.get("atom_count"):
        out["atoms_per_copy"] = meta["atom_count"]
    if meta.get("residue_count"):
        out["residues_per_copy"] = meta["residue_count"]
    if meta.get("chain"):
        out["chain"] = meta["chain"]
    return out


def parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def elapsed_minutes(started: Optional[str], finished: Optional[str],
                    now: Optional[datetime] = None) -> Optional[float]:
    start = parse_time(started)
    if not start:
        return None
    end = parse_time(finished) or now or datetime.now(timezone.utc)
    return round(max(0.0, (end - start).total_seconds()) / 60.0, 1)


def split_run_name(run_name: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """The UI stores 'Title>Description' in run_name."""
    if not run_name:
        return None, None
    if ">" in run_name:
        title, desc = run_name.split(">", 1)
        return title.strip() or None, desc.strip() or None
    return run_name.strip() or None, None


def summarize_overrides(overrides: dict[str, Any], defaults: Optional[dict[str, Any]] = None) -> list[str]:
    """Human-readable lines for a preset's overrides."""
    lines: list[str] = []
    for section, fields in (overrides or {}).items():
        if not isinstance(fields, dict):
            continue
        if section == "identifiers":
            off = sorted(k for k, v in fields.items() if v is False)
            on = sorted(k for k, v in fields.items() if v is True)
            if off:
                lines.append("searches disabled: " + ", ".join(off))
            if on:
                lines.append("searches enabled: " + ", ".join(on))
            continue
        for key, value in fields.items():
            default = ((defaults or {}).get(section) or {}).get(key)
            suffix = f" (default {default})" if default is not None and default != value else ""
            lines.append(f"{section}.{key} = {value}{suffix}")
    return lines
