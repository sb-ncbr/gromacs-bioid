"""Supplementary databases: a second identify pass that can only add evidence.

UniRef50, Foldseek-vs-PDB, SwissLipids, local ChEBI and SIFTS (2026-11-09,
UI runs). They are kept out of get_default_resolvers on purpose:

- the existing resolvers run first on every segment, in the same order and
  with the same stage budget as before; these run afterwards on what is left,
  so a slow new database never costs an existing search its time;
- each is built only when its [identifiers] toggle is on (declared OFF, so
  the MDDBR evaluation config enables none) and its data is present;
- verification picks its window from the existing evidence first and
  verifies groups found only by these sources after it (manager.py).

With none of them enabled run_supplementary_pass does nothing.
"""
from __future__ import annotations

import logging
from typing import Callable

from ..config.loader import RunConfig
from .base import IdentifierResolver
from .reference_indexes import index_available, sifts_uniprot

logger = logging.getLogger("identifier")

SIFTS_RESOLVER = "sifts_uniprot"

# Resolver names whose evidence verification treats as supplementary.
SUPPLEMENTARY_RESOLVERS = frozenset({
    "blast_uniref50", "foldseek_pdb", "swisslipids", "chebi_local", SIFTS_RESOLVER,
})

# SIFTS: identity-matched PDB chains mapped to at most this many accessions.
_SIFTS_MAX_ACCESSIONS = 25


def _enabled(config: RunConfig, name: str) -> bool:
    ids = config.identifiers
    return bool(getattr(ids, name, False) or getattr(ids, f"{name}_similarity", False))


def get_supplementary_resolvers(config: RunConfig) -> list[IdentifierResolver]:
    """Enabled supplementary resolvers whose data is present."""
    resolvers: list[IdentifierResolver] = []
    if _enabled(config, "blast_uniref50"):
        from .resolvers.blast import BLASTResolverUNIREF50
        r = BLASTResolverUNIREF50(config)
        if r.database_present():
            resolvers.append(r)
        else:
            logger.warning("blast_uniref50 enabled but no BLAST db at %r", r.db_path)
    if _enabled(config, "foldseek_pdb"):
        from .resolvers.foldseek import FoldseekPDBResolver
        r = FoldseekPDBResolver(config)
        if r.available():
            resolvers.append(r)
        else:
            logger.warning("foldseek_pdb enabled but binary or db %r missing",
                           config.foldseek.pdb_db_path)
    for name, path, module, cls in (
        ("swisslipids", config.identifiers.swisslipids_db, "swisslipids", "SwissLipidsResolver"),
        ("chebi_local", config.identifiers.chebi_db, "chebi_local", "ChebiLocalResolver"),
    ):
        if not _enabled(config, name):
            continue
        if not index_available(path):
            logger.warning("%s enabled but index %r missing", name, path)
            continue
        mod = __import__(f"{__package__}.resolvers.{module}", fromlist=[cls])
        resolvers.append(getattr(mod, cls)(config))
    return resolvers


def derive_sifts_hits(results, segment: str, config: RunConfig) -> int:
    """UniProt candidates for the PDB chains a segment matched exactly.

    Reads the identity listing of blast_pdb_protein (hits like "1AQ7_A") and
    writes, next to it, a sifts_uniprot identity listing of the UniProt
    accessions SIFTS assigns to those chains. Chains SIFTS maps to more than
    one accession (fusions, chimeras) are skipped. Returns the number of
    listings written. sifts_mode "xref" records the mapping under
    identification/sifts/<segment> only, leaving scoring untouched.
    """
    ids = config.identifiers
    path = ids.sifts_db
    if not ids.sifts_uniprot or not index_available(path):
        return 0
    data = results.get_data(f"identifiers/{segment}")
    if not isinstance(data, dict):
        return 0
    written = 0
    xref: dict[str, str] = {}
    for generator, blobs in data.items():
        if not isinstance(blobs, dict):
            continue
        blob = blobs.get("blast_pdb_protein")
        if not isinstance(blob, dict) or blob.get("hit_type") != "identity":
            continue
        accessions: list[str] = []
        chains: dict[str, list[str]] = {}
        for hit in blob.get("hits") or []:
            pdb, _, chain = str(hit).partition("_")
            if not chain:
                continue
            mapped = sifts_uniprot(path, pdb, chain)
            if len(mapped) != 1:
                continue
            acc = mapped[0]
            xref[str(hit)] = acc
            if acc not in chains:
                if len(accessions) >= _SIFTS_MAX_ACCESSIONS:
                    continue
                accessions.append(acc)
                chains[acc] = []
            chains[acc].append(str(hit))
        if not accessions or ids.sifts_mode != "corroborate":
            continue
        results.set_data(f"identifiers/{segment}/{generator}/{SIFTS_RESOLVER}", {
            "signature": blob.get("signature"),
            "hit_type": "identity",
            "hits": accessions,
            "ident_type": "UNIPROT_ID",
            "signature_type": blob.get("signature_type"),
            "hits_metadata": {acc: {"via": "sifts", "pdb_chains": chains[acc][:10]}
                              for acc in accessions},
        })
        written += 1
    if xref:
        results.set_data(f"identification/sifts/{segment}", xref)
    return written


def run_supplementary_pass(
    results,
    items: list[tuple[str, dict]],
    config: RunConfig,
    signature_type_map: dict | None,
    working_directory: str,
    deadline_epoch: float | None,
    budget_exceeded: Callable[[], bool],
) -> list[dict]:
    """Resolve every (segment, signatures) item with the supplementary
    resolvers, then derive SIFTS listings. Returns per-segment
    {"fragment_name", "errors"} records; [] when nothing is enabled."""
    resolvers = get_supplementary_resolvers(config)
    sifts_on = bool(config.identifiers.sifts_uniprot) and index_available(config.identifiers.sifts_db)
    if not resolvers and not sifts_on:
        return []
    from .cache_manager import ResolverCache
    from .registry import IdentifierRegistry
    from .resolution_manager import IdentifierResolutionManager

    manager = IdentifierResolutionManager(IdentifierRegistry(resolvers), config,
                                          signature_type_map=signature_type_map)
    cache = ResolverCache(config)
    out: list[dict] = []
    for fragment_name, valid_sigs in items:
        if budget_exceeded():
            logger.warning("supplementary pass: stage budget exhausted at %s", fragment_name)
            break
        errors: list[dict] = []
        if resolvers:
            seen: set[tuple] = set()
            for generator_name, signature in valid_sigs.items():
                if budget_exceeded():
                    break
                pair = ((signature_type_map or {}).get(generator_name), signature)
                if pair in seen:
                    continue
                seen.add(pair)
                manager.resolve(
                    results=results,
                    segment=fragment_name,
                    signature_generator_name=generator_name,
                    signature=signature,
                    cache=cache,
                    working_directory=working_directory,
                    errors=errors,
                    deadline_epoch=deadline_epoch,
                    merge_attempted=True,
                )
        if sifts_on:
            try:
                derive_sifts_hits(results, fragment_name, config)
            except Exception as exc:  # never fail the step over a cross-reference
                logger.warning("SIFTS derivation failed for %s: %s", fragment_name, exc)
        out.append({"fragment_name": fragment_name, "errors": errors})
    return out
