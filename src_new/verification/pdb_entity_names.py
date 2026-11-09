"""Name PDB hits after the matched polymer entity, not the entry title.

UI pass 2026-11-07: a verified PDB hit was named by its entry title, which
is the title of a paper ("The mechanism of GM-CSF inhibition by human
GM-CSF auto-antibodies" for an antibody light chain). The entity that the
verification actually matched carries the molecule's own description
(rcsb_polymer_entity.pdbx_description, e.g. "IgG2a kappa light chain").

The matched entity comes from the verification details:
  structure path  tm_chain_ref -> the entity listing that chain
  sequence path   ref_seq_sha1 -> the entity with that sequence
  single entity   the only one
Anything ambiguous, missing or failing returns None and the caller keeps
the name it had. Lookups reuse the sequence fetcher's cached RCSB payloads.
"""

from __future__ import annotations

import os
import time
from typing import Optional

from .models import ref_seq_sha1

# Operational knobs (env, deployment-time). Naming is display-only, so every
# limit errs on the side of keeping the entry title.
PDB_NAME_LIMIT = int(os.environ.get("BAT3_PDB_NAME_LIMIT", "50"))          # hits per segment
PDB_NAME_BUDGET_S = float(os.environ.get("BAT3_PDB_NAME_BUDGET_S", "30"))  # wall per segment
PDB_NAME_RUN_CAP_S = float(os.environ.get("BAT3_PDB_NAME_RUN_CAP_S", "180"))  # wall per run
PDB_NAME_MAX_FAILURES = 3   # consecutive failed lookups: RCSB is down or slow, stop


def matched_entity(records: list[dict], details: Optional[dict]) -> Optional[dict]:
    """The polymer entity a verification matched, or None when unsure."""
    if not records:
        return None
    d = details or {}
    chain = d.get("tm_chain_ref")
    if chain:
        chain = str(chain)
        by_auth = [r for r in records if chain in (r.get("auth_asym_ids") or [])]
        if len(by_auth) == 1:
            return by_auth[0]
        by_label = [r for r in records if chain in (r.get("asym_ids") or [])]
        if len(by_label) == 1 and not by_auth:
            return by_label[0]
        return None
    sha = d.get("ref_seq_sha1")
    if sha:
        hits = [r for r in records if r.get("sequence") and ref_seq_sha1(r["sequence"]) == sha]
        return hits[0] if len({h["entity_id"] for h in hits}) == 1 else None
    return records[0] if len(records) == 1 else None


def entity_name(records: list[dict], details: Optional[dict]) -> tuple[Optional[str], Optional[str]]:
    """(description, organism) of the matched entity; (None, None) when unsure."""
    rec = matched_entity(records, details)
    if rec is None:
        return None, None
    desc = rec.get("description")
    desc = desc.strip() if isinstance(desc, str) else None
    if not desc:
        return None, None
    return desc, (rec.get("organism") or None)


def name_pdb_hits(hits: list, fetch_records, limit: int = PDB_NAME_LIMIT,
                  budget_s: float = PDB_NAME_BUDGET_S,
                  max_failures: int = PDB_NAME_MAX_FAILURES, clock=time.monotonic) -> int:
    """Rename verified PDB hits in place (display order), within limits.

    At most `limit` hits and `budget_s` seconds of wall time; stops after
    `max_failures` consecutive failed lookups (RCSB down or slow). Only a
    name the hit already has (the entry title) is replaced: a hit the
    annotation scorer could not describe stays unnamed. fetch_records(pdb_id)
    -> list of entity records (empty on failure). Returns how many hits were
    renamed. Never raises: a failure or an exhausted budget leaves the
    remaining hits as they were.
    (Until 2026-11-09 only the top 3 were named; the rest of the matches
    table showed entry titles: "RECRUITING ZINC TO MEDIATE POTENT, ...".)"""
    renamed = 0
    seen = 0
    failures = 0
    start = clock()
    for h in hits:
        if seen >= limit or failures >= max_failures or clock() - start >= budget_s:
            break
        if not getattr(h, "is_verified", False) or str(getattr(h, "ident_type", "")).upper() != "PDB_ID":
            continue
        seen += 1
        if not getattr(h, "name", None):
            continue
        try:
            records = fetch_records(h.identifier)
        except Exception:
            records = []
        if not records:
            failures += 1
            continue
        failures = 0
        try:
            desc, organism = entity_name(records, h.similarity_details)
        except Exception:
            continue
        if desc:
            h.name = desc
            if organism:
                h.organism = organism
            renamed += 1
    return renamed
