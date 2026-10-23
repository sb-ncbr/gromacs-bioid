"""Verification manager for BioID v2 pipeline."""

from __future__ import annotations

import dataclasses
import math
import re
from typing import TYPE_CHECKING

import logging

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..config.loader import RunConfig
    from ..results.results_manager import ResultsManager

from .base import VerificationWorker, SignatureFetcher, AnnotationQualityScorer
from .dedup import RawHit, collect_hits, deduplicate_and_score, BELIEF_RHO, BELIEF_KAPPA
from .models import VerifiedHit, VerificationScore, AnnotationQuality, similarity_meets_floor

_SEQUENCE_SIG_TAGS = ("residue_sequence",)
_STRUCTURE_SIG_TAGS = ("pdb_protein", "pdb_nucleic", "ca_only_pdb")


def _equivalence_class_id(ident_type: str, identifier: str,
                          signature_type: str | None,
                          canonical_signature: str | None,
                          donor: VerificationScore | None) -> str:
    """v3.142 Phase 4: visual-collapse class id for ONE hit.

    Same verified structure => same class id, regardless of which database
    record (or resolver) proposed it — presentation owns the collapse;
    rows/order/counts are never changed by this (per plan):
      - chemical: candidate skeleton-fp hex (the fp already computed for
        the F7 Tanimoto; same value), prefixed "skeleton:"
      - sequence-verified: round(identity×coverage, 2), prefixed "align:"
      - structure-verified: round(TM, 2), prefixed "tm:"
      - element: the element symbol, prefixed "element:"
      - fallback (no proof): the record itself ("record:{type}:{id}")
    Computed from keys already threaded to the manager (V-36 doctrine:
    no new results keys needed). The chemical class id uses fp_to_hex of
    the candidate's skeleton fp — the same hex the F7 Tanimoto compares
    against the molecule's stored skeleton signature ("skelfp:v1:<hex>").
    """
    if ident_type in CHEMICAL_IDENT_TYPES and canonical_signature:
        try:
            fp = _skel_fp(from_smiles(canonical_signature))
            if fp is not None:
                return "skeleton:" + _fp_to_hex(fp)
        except Exception:
            pass  # fall through to record-level id
    if ident_type == "ELEMENT":
        return f"element:{identifier}"
    # Red-team batch-4 (D-06): classes are keyed on the REFERENCE CONTENT
    # that produced the score (workers emit details['ref_seq_sha1']) — never
    # on a rounded alignment/TM bucket. The old align:/tm: classes collapsed
    # unrelated records sharing only a score (all structure hits were tm:0.0
    # under the fetcher-routing bug, forming one giant class). Two records
    # pointing at the SAME reference sequence/structure now share a class
    # regardless of their alignment score.
    if donor is not None:
        ref_sha = (donor.details or {}).get("ref_seq_sha1")
        if ref_sha:
            return f"seqref:{ref_sha}"
    return f"record:{ident_type}:{identifier}"


# v3.142 (Phase 3): confidence formula version for results provenance.
# Bump whenever the composition changes so old-run comparisons have an
# explicit version marker (stored in verification/_meta).
CONFIDENCE_FORMULA_VERSION = "v3.142.1"


def normalize_weights(w_resolver: float, w_similarity: float,
                      w_annotation: float) -> tuple[float, float, float]:
    """Normalize confidence term weights by their sum (v3.142 Phase 3).

    Users may supply un-normalized weights in the run config (e.g. 0.5/0.5/0.5);
    the composition must stay a weighted average bounded by the term range, so
    the RAW user values are divided by their sum at use-time. Sanitizing:
    non-finite or negative weights are treated as 0; if the effective sum is
    zero the documented fallback is equal thirds (1/3, 1/3, 1/3). Raw values
    are preserved separately (see verification/_meta provenance).
    """
    cleaned = [w if (isinstance(w, (int, float)) and math.isfinite(w) and w > 0) else 0.0
               for w in (w_resolver, w_similarity, w_annotation)]
    total = sum(cleaned)
    if total <= 0.0:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
    return (cleaned[0] / total, cleaned[1] / total, cleaned[2] / total)


def build_confidence_meta(cfg) -> dict:
    """v3.142 (Phase 3): confidence composition provenance dict for
    verification/_meta — raw user weights, sum-normalized effective weights,
    formula version and belief/annotation-live constants. Shared by
    VerificationManager.verify_all (monolithic/tests) and the verify_results
    STEP (parallel worker path discards the per-segment temp manager — the
    step must persist meta + class sizes itself).
    """
    weights_raw = (cfg.resolver_weight, cfg.similarity_weight, cfg.annotation_weight)
    w_r, w_s, w_a = normalize_weights(*weights_raw)
    return {
        "confidence_formula_version": CONFIDENCE_FORMULA_VERSION,
        "confidence_formula": "w_r*belief + w_s*match + w_a*annotation",
        "weights_raw": [float(w) if isinstance(w, (int, float)) and math.isfinite(w) else None
                        for w in weights_raw],
        "weights_effective": [w_r, w_s, w_a],
        "belief_constants": {"rho": BELIEF_RHO, "kappa": BELIEF_KAPPA},
        "annotation_live_fetch": cfg.annotation_live_fetch,
        "annotation_live_budget_per_segment": cfg.annotation_live_budget_per_segment,
        "annotation_fetch_timeout_s": cfg.annotation_fetch_timeout_s,
        "min_final_confidence": cfg.min_final_confidence,
    }
from ..signatures.skeletize import from_smiles, hex_to_fp, parse_signature, skeleton_fp as _skel_fp, tanimoto as _skel_tanimoto, fp_to_hex as _fp_to_hex
from .models import CHEMICAL_IDENT_TYPES, SKELF_VERIFY_THRESHOLD
from .registry import VerificationRegistry, get_default_registry


def _molecule_skeleton_fp_hex(results, segment: str):
    """Fetch the molecule's skeleton_fp signature hex for a segment, if any."""
    try:
        value = results.get_data(f"signatures/{segment}/generated/skeleton_fp")
    except Exception:
        return None
    if not value:
        return None
    hex_part, _ = parse_signature(str(value))
    return hex_part


def _molecule_smiles(results, segment: str) -> str | None:
    """Fetch the molecule's generated smiles signature for a segment (the
    molecule's OWN structure, used by the D-02 always-compare rule)."""
    try:
        value = results.get_data(f"signatures/{segment}/generated/smiles")
    except Exception:
        return None
    if not value or not isinstance(value, str):
        return None
    return value.split(":", 1)[1] if value.startswith("smiles:") else value


_FORMULA_PARTS_RE = re.compile(r"([A-Z][a-z]?)(\d*)")


def _formula_parts(formula: str) -> dict | None:
    """Parse a plain formula string into element counts (Hill or not)."""
    if not formula or not isinstance(formula, str):
        return None
    parts: dict = {}
    for sym, num in _FORMULA_PARTS_RE.findall(formula.strip()):
        parts[sym] = parts.get(sym, 0) + (int(num) if num else 1)
    return parts or None


def _candidate_formula_parts(canonical_signature) -> dict | None:
    """Formula+H count of a candidate's canonical SMILES via RDKit.
    None when unparseable (never matches, D-16)."""
    if not canonical_signature:
        return None
    try:
        from rdkit import Chem
        from rdkit.Chem import rdMolDescriptors
        mol = Chem.MolFromSmiles(canonical_signature)
        if mol is None:
            return None
        return _formula_parts(rdMolDescriptors.CalcMolFormula(mol))
    except Exception:
        return None


def _water_formula_match(results, segment: str, canonical_signature):
    """v3.143 (D-16): does the candidate stoichiometry match the molecule's
    generated formula? True=match (pin OK), False=mismatch (never pin),
    None=formula unknown (legacy first-skel-1.0 pin behavior).

    The v3.140 pin named the FIRST fingerprint-identical hit "water" — db
    order put hydroxide/hydronium/peroxide in that slot because their
    skeleton fingerprints are identical to water's."""
    try:
        formula = results.get_data(f"signatures/{segment}/generated/molecular_formula")
    except Exception:
        return None
    if not formula:
        return None
    mol_parts = _formula_parts(str(formula))
    if mol_parts is None:
        return None
    cand_parts = _candidate_formula_parts(canonical_signature)
    if cand_parts is None:
        return False
    return cand_parts == mol_parts


def _monoatomic_atom_count(results, segment: str):
    """Atom membership for the segment's molecule fragment, if known.

    Reads universe/segments/<segment>/properties (written by the loader
    facade: atom_count_fragment, fallback atom_count_total). Returns None
    when the properties are unavailable, in which case callers must stay
    on the conservative weighted path.
    """
    try:
        props = results.get_data(f"universe/segments/{segment}/properties") or {}
    except Exception:
        return None
    for key in ("atom_count_fragment", "atom_count_total"):
        value = props.get(key)
        if isinstance(value, int) and value >= 0:
            return value
    return None


def _water_segment(results, segment: str) -> bool:
    """True when the analyzed segment is typed water (fragments/segments record
    written by analyze_universe via the loader facade's molecule typing).

    Used by the water ground-truth rule: skeleton fingerprints IDENTICAL to
    the molecule's fp mean exactly one chemical identity (water) regardless of
    which database record supplied the canonical smiles — all skel==1.0 hits
    are the same molecule, one is ground truth, the rest are duplicate records."""

    for key in ("fragments/segments",):
        try:
            segments = results.get_data(key) or []
        except Exception:
            return False
        for entry in segments:
            if isinstance(entry, dict) and entry.get("segment") == segment:
                return entry.get("type") == "water"
    return False


def _element_ground_truth(results, segment: str, ident_type: str, hit_type: str) -> bool:
    """True only for the documented element ground-truth rule.

    User ruling 2026-10-11 ("ion identification is by definition ground
    truth — we own it; there is nothing to verify"): for a segment whose
    molecule is a SINGLE atom, an ELEMENT identity hit is the ground truth.
    Annotation-weight corroboration is unprovable by construction for a bare
    element, so the weighted aggregate structurally caps at 80; the override
    lifts final_confidence to 100 (recorded via ground_truth_override).

    Hard scope guards (both must hold, else normal weighted path):
      * ident_type == "ELEMENT" — never a chemical ident type, so the F7
        fingerprint gate and all chemistry verification are untouched;
      * hit_type == "identity" — similarity listings are not assertions;
      * molecule atom membership == 1 — polyatomic single-element fragments
        (S8, carbon clusters) stay on the weighted path.
    """
    if ident_type != "ELEMENT" or hit_type != "identity":
        return False
    return _monoatomic_atom_count(results, segment) == 1


def _structure_rerank_groups(sorted_groups, skel_map, threshold):
    """Re-order chemical groups within the consensus-sorted candidate list.

    Fixes the structure-blind verify_top_n window cut (audit 2026-09-26:
    formula-family floods are identity-typed at consensus 100, so the top-100
    window excluded the structurally-correct isomer at median rank ~3,097).

    Raise-only semantics: if NO chemical candidate reaches `threshold`
    skeleton similarity, the input ordering is returned UNCHANGED (an
    uninformative/corrupt molecule skeleton cannot alter anything). When the
    threshold is reached by at least one candidate, chemical groups sort by
    (skeleton sim desc, consensus desc); non-chemical groups keep their exact
    relative positions (permutation is confined to chemical slots).

    Args:
        sorted_groups: list of ((normalized_id, ident_type), metadata) sorted
            by consensus_score descending (legacy order).
        skel_map: {(normalized_id, ident_type): float|None} for chemical
            candidates (None = structure fetch/compute failed; treated as 0).
        threshold: minimum skeleton similarity that activates reranking
            (SKELF_VERIFY_THRESHOLD).

    Returns:
        New list of ((normalized_id, ident_type), metadata) tuples.
    """
    best = max(((s or 0.0) for s in skel_map.values()), default=0.0)
    if best < threshold:
        return list(sorted_groups)
    chem = [
        ((key, meta), (skel_map.get(key) or 0.0))
        for (key, meta) in sorted_groups
        if key[1] in CHEMICAL_IDENT_TYPES
    ]
    chem.sort(key=lambda item: (-item[1], -item[0][1].get("consensus_score", 0.0)))
    chem_iter = iter(chem)
    out = []
    for key, meta in sorted_groups:
        if key[1] in CHEMICAL_IDENT_TYPES:
            out.append(next(chem_iter)[0])
        else:
            out.append((key, meta))
    return out


def _chemical_corroboration(results, segment: str, canonical_signature):
    """Skeleton Tanimoto between molecule and candidate canonical SMILES.

    Returns (sim, method) or (None, reason).
    """
    if not canonical_signature or not isinstance(canonical_signature, str):
        return None, "fingerprint_unavailable"
    mol_hex = _molecule_skeleton_fp_hex(results, segment)
    if not mol_hex:
        return None, "fingerprint_unavailable"
    try:
        mol_fp = hex_to_fp(mol_hex)
        cand_fp = _skel_fp(from_smiles(canonical_signature))
        if mol_fp is None or cand_fp is None:
            return None, "fingerprint_unavailable"
        return _skel_tanimoto(mol_fp, cand_fp), "skelfp:v1"
    except Exception:
        return None, "fingerprint_unavailable"


def _database_name(ident_type: str) -> str:
    """v3.143 (D-17): consistent target-database naming derived from the
    ident type. Plain replace("_ID","").lower() yielded 'pubchem_cid' and
    'inchikey' next to 'pdb'/'uniprot' — normalize to the SOURCE database."""
    _MAP = {
        "PUBCHEM_CID": "pubchem", "INCHIKEY": "pubchem",
        "PUBCHEM_FORMULA": "pubchem", "PUBCHEM_STRUCT": "pubchem",
        "CHEMBL_ID": "chembl",
    }
    return _MAP.get(ident_type, ident_type.replace("_ID", "").lower())


def _fidelity_order_key(hit):
    """Deterministic tie-break chain for fidelity-first presentation order.

    Contract (UI 2026-10-01): stored order IS display order; backend owns
    ranking, UI owns presentation; the verified flag is never a sort key for
    display purposes (it only defines which hits participate in block 1).

    Red-team batch-4 (D-02): tuple = skeleton bucket (0.05) desc ->
    is-identity desc -> similarity desc (None = -1.0, "unknown") ->
    belief desc -> evidence count desc -> confidence desc -> identifier ->
    ident_type. The identity slot ranks asserted-identity rows (whose S is
    legitimately absent) above similarity-only rows with a measured score,
    and a missing S no longer sinks below a measured degenerate 0.0 in the
    identity case that produced that absence (d_p3 DPPC-vs-DMPC, d_p4
    mmCIF-identity-vs-tm:0.0).

    v3.140-1 (observed run b4813beb): similarity_score joins the chain. With
    skel all-equal and confidence plateau-nulled, the prior chain degenerated
    to identifier-ascending — hits carrying real resolver similarity (62.9)
    sorted BELOW sim=None rows purely by CID number accident.
    A6 (2026-10-08): evidence count ranks before confidence within a
    same-skeleton plateau (pubchem-family final_confidence is quantized).
    """
    s = hit.skeleton_sim
    if s is None or (isinstance(s, float) and (math.isnan(s) or math.isinf(s))):
        bucket = -1
    else:
        bucket = round(s / 0.05)
    identity = 1 if getattr(hit, "hit_type", None) == "identity" else 0
    sim = getattr(hit, "similarity_score", None)
    if sim is None or (isinstance(sim, float) and (math.isnan(sim) or math.isinf(sim))):
        sim = -1.0
    belief = getattr(hit, "belief", None)
    if belief is None or (isinstance(belief, float) and (math.isnan(belief) or math.isinf(belief))):
        belief = -1.0
    ev = getattr(hit, "supporting_evidence_count", 1) or 1
    ident = str(hit.identifier)
    # v3.143 (D-15): compare numerically-typed ids numerically in the
    # tie-break — '10' < '2' under a plain string sort inverted presentation
    # order on every plateau. Numeric ids first, then lexical, both asc.
    ident_key = (0, int(ident), "") if ident.isdigit() else (1, 0, ident)
    return (-bucket, -identity, -sim, -belief, -ev,
            -(hit.final_confidence or 0.0), ident_key, str(hit.ident_type))


def _fidelity_order_hits(hits):
    """Stable repartition: verified hits first, fidelity-sorted.

    Block 1: all verified hits, sorted by _fidelity_order_key.
    Block 2: everything else, original relative order preserved.

    v3.140-2: eligibility widened from verified chemical ident_types to ALL
    verified hits (observed run b4813beb/seg_3_SOD: the ground-truth ELEMENT
    hit — ident_type ELEMENT, outside CHEMICAL_IDENT_TYPES — stayed in block 2
    beneath 33 rejected chemical candidates even though it was the only true
    answer; for monoatomic segments verified==ELEMENT by construction).
    Ordering-only: no verification state, score, or schema is modified.
    Idempotent: re-application returns the identical order.
    Projection-validated (rerank_projection_v3140.json, 2026-10-21, 5,993
    campaign annotations, cache-only): D-chain validated@5/@10 = 95.9/96.0
    vs baseline 95.8/95.9 (gate 0.7) — at-or-above on every metric.
    """
    block1 = [h for h in hits if h.is_verified]
    if not block1:
        return list(hits)
    block1.sort(key=_fidelity_order_key)
    idx = {id(h) for h in block1}
    block2 = [h for h in hits if id(h) not in idx]
    return block1 + block2


def _ident_family(ident_type: str) -> str:
    """Coarse diversity family for the verify window (red-team batch-4,
    D-03). Each ident type is its own family except three deliberate pools:
    UniProt+SwissProt (same database), the NCBI sequence stores, and all
    chemical identifiers (one chemical window family)."""
    if not ident_type:
        return "other"
    it = ident_type.upper()
    if it in ("UNIPROT_ID", "SWISSPROT_ID"):
        return "uniprot"
    if it in ("NR_ID", "NT_ID", "CORE_NT_ID"):
        return "ncbi"
    if it in CHEMICAL_IDENT_TYPES or it.startswith("CHEBI") or it in (
            "LM_ID", "GLYTOUCAN_ID", "LIPIDMAPS_ID"):
        return "chemical"
    _FAMILIES = {
        "PDB_ID": "pdb",
        "ALPHAFOLD_ID": "alphafold",
        "ALPHAFIND_ID": "alphafind",
        "ELEMENT": "other",
    }
    return _FAMILIES.get(it, "other")


def _family_interleave(sorted_groups, top_n: int):
    """Round-robin the consensus-sorted groups across ident families.

    Red-team batch-4 (D-03): one shared window sorted by consensus let a
    single ident type (150 identical lysozyme PDB chains, all consensus 100)
    fill 100/100 slots, evicting the only UniProt-family record entirely.
    Round-robin keeps consensus order WITHIN each family (input order is
    the consensus order) but rotates across families, so every family
    represented in the segment gets window slots before any family's
    flood fills the rest.

    Returns (window, stats) with stats = {"n_groups", "n_window",
    "n_dropped_by_type"} for additive persistence under
    verification/<seg>/window.
    """
    from collections import deque

    families: dict[str, deque] = {}
    order: list[str] = []
    for key, meta in sorted_groups:
        fam = _ident_family(key[1])
        if fam not in families:
            families[fam] = deque()
            order.append(fam)
        families[fam].append((key, meta))

    window: list = []
    while len(window) < top_n:
        progressed = False
        for fam in order:
            if len(window) >= top_n:
                break
            if families[fam]:
                window.append(families[fam].popleft())
                progressed = True
        if not progressed:
            break

    stats = {
        "n_groups": len(sorted_groups),
        "n_window": len(window),
        "n_dropped_by_type": {fam: len(q) for fam, q in families.items() if q},
    }
    return window, stats


class VerificationManager:
    """Manages the verification pipeline for identification results.
    
    Consumes identification results from ResultsManager and re-verifies hits
    by comparing simulation-extracted signatures against canonical database signatures.
    
    Non-verification is a normal outcome, not a fatal failure.
    """
    
    def __init__(
        self, 
        config: RunConfig,
        registry: VerificationRegistry | None = None,
    ) -> None:
        """Initialize the verification manager.
        
        Args:
            config: Run configuration with verification settings.
            registry: VerificationRegistry with workers, fetchers, and scorers.
                     If None, uses get_default_registry() (empty lists).
        """
        self.config = config
        self._verification_config = config.verification
        self._registry = registry if registry is not None else get_default_registry()
    
    def verify_all(
        self,
        results: ResultsManager,
        deadline_epoch: float | None = None,
    ) -> dict[str, list[VerifiedHit]]:
        """Verify all identification hits from the results manager.

        Args:
            results: ResultsManager containing identification results to verify.
            deadline_epoch: Optional wall-clock deadline (time.time() seconds).
                When exceeded, verification returns the partial results gathered
                so far instead of burning more time on fetch-bound candidate
                fan-out (stage-time-budget policy, wave-3 stall fix).

        Returns:
            Dict mapping segment name -> list of VerifiedHit objects.
            Each hit has is_verified=True if verification succeeded, False otherwise.
        """
        import time as _time
        per_segment_results: dict[str, list[VerifiedHit]] = {}

        def _over_budget() -> bool:
            return deadline_epoch is not None and _time.time() > deadline_epoch

        # Get all segment names from identifiers data
        identifiers_data = results.get_data("identifiers")
        if not identifiers_data or not isinstance(identifiers_data, dict):
            return per_segment_results
        
        segment_names = list(identifiers_data.keys())
        
        # v3.142 (Phase 3): effective composition weights — user raw values
        # normalized by their sum once per run (never per candidate), with
        # provenance written to verification/_meta so any stored row can be
        # traced back to the exact formula + weights that produced it.
        # NOTE: in the parallel step path this temp-manager write is discarded;
        # the step re-persists the identical dict via build_confidence_meta.
        cfg = self._verification_config
        meta = build_confidence_meta(cfg)
        w_resolver, w_similarity, w_annotation = meta["weights_effective"]
        results.set_data("verification/_meta", meta)
        
        for segment in segment_names:
            if _over_budget():
                logger.warning(f"verify_all: deadline exceeded before segment {segment}; returning partial results")
                # v3.143 (red-team D-04): segments cut by the budget are NOT
                # "searched and empty" — mark them partial so consumers can
                # tell a budget cut from a true no-hit.
                for skipped in segment_names[segment_names.index(segment):]:
                    if not results.data_exists(f"identifiers/{skipped}"):
                        continue
                    if results.get_data(f"verification/{skipped}/verified_hits") is None:
                        results.set_data(f"verification/{skipped}/verified_hits", [])
                    results.set_data(f"verification/{skipped}/partial", True)
                return per_segment_results
            # Check if identifiers/{segment}/ exists
            segment_path = f"identifiers/{segment}"
            if not results.data_exists(segment_path):
                continue
            
            # v3.142 (1c): re-arm per-segment live-annotation budget + policy
            cfg = self._verification_config
            begin = getattr(self._registry, "begin_segment", None)
            if callable(begin):
                begin(live_fetch=cfg.annotation_live_fetch,
                      budget=cfg.annotation_live_budget_per_segment,
                      timeout_s=cfg.annotation_fetch_timeout_s)
            
            # Collect and deduplicate hits
            raw_hits = collect_hits(results, segment)
            if not raw_hits:
                continue
            
            deduped = deduplicate_and_score(raw_hits)
            if not deduped:
                continue
            
            # Sort groups by consensus_score descending
            sorted_groups = sorted(
                deduped.items(),
                key=lambda x: x[1]["consensus_score"],
                reverse=True
            )

            # Take top N
            top_n = self._verification_config.verify_top_n

            # F14: skeleton-aware rerank of chemical candidates so the window
            # stops being a consensus lottery over formula-family floods
            # (gt_absent C1 class, audit 2026-09-26). Raise-only: legacy order
            # is preserved whenever no candidate reaches the gate threshold.
            try:
                sorted_groups = self._maybe_structure_rerank(
                    results, segment, sorted_groups, top_n, _over_budget
                )
            except Exception as exc:
                logger.warning(
                    f"structure rerank failed for segment {segment} "
                    f"({exc}); keeping consensus order"
                )

            top_groups, window_stats = _family_interleave(sorted_groups, top_n)
            # D-03: persist window composition/truncation additively (legacy
            # runs simply lack the key).
            results.set_data(f"verification/{segment}/window", window_stats)
            
            # Batch-warm canonical structures for chemical candidates (one CSV
            # call per ~50 CIDs instead of N serial 503-prone calls; F7 gate)
            try:
                chem_cids = [str(nid) for (nid, it), _m in top_groups if it in CHEMICAL_IDENT_TYPES]
                if chem_cids:
                    from .fetchers.compound_fetcher import prefetch_pubchem
                    prefetch_pubchem(chem_cids)
            except Exception as warm_exc:
                logger.warning(f"chemical prefetch failed (non-fatal): {warm_exc}")
            
            verified_hits: list[VerifiedHit] = []
            seg_budget_hit = False
            # Water ground-truth rule (v3.140): on water segments, the FIRST
            # fingerprint-identical (skel==1.0) chemical hit is promoted as the
            # water identity; subsequent fingerprint-identical hits are database
            # duplicates of that identity, demoted to unverified with a clear
            # reason instead of 67 near-identical rows (run b4813beb / TIP3).
            water_seg = _water_segment(results, segment)
            water_pinned = False

            for (normalized_id, ident_type), metadata in top_groups:
                if _over_budget():
                    logger.warning(
                        f"verify_all: deadline exceeded mid-segment {segment} "
                        f"({len(verified_hits)}/{len(top_groups)} verified); keeping partial results"
                    )
                    # v3.143 (red-team D-04): keep the gathered hits — the
                    # normal tail below stores them; then flag the segment as
                    # partial and stop (later segments would also be cut).
                    seg_budget_hit = True
                    break
                signature = metadata["signature"]
                signature_type = metadata["signature_type"]
                consensus_score = metadata["consensus_score"]
                source_resolvers = metadata["source_resolvers"]
                hit_type = metadata["hit_type"]
                
                # Look up SignatureFetcher (red-team batch-4: signature-type
                # aware so PDB_ID hits on structure signatures get the
                # structure fetcher, not the sequence one).
                fetcher = self._registry.get_fetcher(ident_type, signature_type=signature_type)
                canonical_signature: str | None = None
                if fetcher:
                    try:
                        canonical_signature = fetcher.fetch(normalized_id, ident_type)
                    except Exception:
                        # Fetch failed, but we continue
                        pass
                
                skeleton_sim = None
                skeleton_method = None
                if ident_type in CHEMICAL_IDENT_TYPES:
                    skeleton_sim, _c_m = _chemical_corroboration(
                        results, segment, canonical_signature
                    )
                    skeleton_method = _c_m if skeleton_sim is not None else None

                # Red-team batch-4 (D-02): verify against EVERY member
                # signature of the group — the representative may be an
                # inchikey/name while another member carries the smiles/
                # fasta with a real worker. The best applicable score wins.
                sig_candidates: list[tuple[str, str | None]] = []
                if signature:
                    sig_candidates.append((signature, signature_type))
                for m_sig, m_type in metadata.get("member_signatures", []):
                    if m_sig and (m_sig, m_type) not in sig_candidates:
                        sig_candidates.append((m_sig, m_type))
                
                # Lazily re-fetch a canonical per distinct signature kind
                # only when the representative's fetch does not apply
                # (structure-vs-sequence routing, 5.1); cached per group.
                _canonical_cache: dict = {signature_type: canonical_signature}

                def _canonical_for(st):
                    if st not in _canonical_cache:
                        f = self._registry.get_fetcher(ident_type, signature_type=st)
                        c = None
                        if f:
                            try:
                                c = f.fetch(normalized_id, ident_type)
                            except Exception:
                                pass
                        _canonical_cache[st] = c
                    return _canonical_cache[st]
                
                similarity_score: VerificationScore | None = None
                rejection_reason: str | None = None
                saw_workers = False
                
                for sig_c, st_c in sig_candidates:
                    workers = self._registry.get_applicable_workers(st_c, ident_type)
                    if not workers:
                        continue
                    saw_workers = True
                    canon_c = _canonical_for(st_c)
                    for worker in workers:
                        try:
                            score = worker.verify(
                                sig_c, normalized_id, ident_type,
                                canon_c, signature_type=st_c)
                        except Exception:
                            # Worker failed, try next one
                            continue
                        if score is not None and (
                                similarity_score is None
                                or score.normalized_score
                                > similarity_score.normalized_score):
                            similarity_score = score
                            break  # first non-None for this signature kind
                
                # D-02 fix b: with a fetched canonical SMILES for a chemical,
                # ALWAYS compare against the molecule's own generated smiles
                # — even when no member signature was worker-applicable —
                # so inchikey/formula/name-represented groups still get a
                # real multi-fingerprint measurement.
                if (ident_type in CHEMICAL_IDENT_TYPES
                        and isinstance(canonical_signature, str)
                        and canonical_signature
                        and similarity_score is None):
                    mol_smiles = _molecule_smiles(results, segment)
                    if mol_smiles:
                        for worker in self._registry.get_applicable_workers(
                                "smiles", ident_type):
                            saw_workers = True
                            try:
                                score = worker.verify(
                                    mol_smiles, normalized_id, ident_type,
                                    canonical_signature,
                                    signature_type="smiles")
                            except Exception:
                                continue
                            if score is not None and (
                                    similarity_score is None
                                    or score.normalized_score
                                    > similarity_score.normalized_score):
                                similarity_score = score
                                break
                
                if similarity_score is None:
                    rejection_reason = "verification_failed" if saw_workers else "no_worker"
                
                
                # Look up AnnotationQualityScorer (v3.142: honor the
                # enable_annotation_quality config knob — previously unread)
                scorer = (self._registry.get_scorer(ident_type)
                          if cfg.enable_annotation_quality else None)
                annotation_score: float | None = None
                if scorer:
                    try:
                        quality = scorer.score(normalized_id, ident_type)
                        if quality is not None:
                            annotation_score = quality.normalized_score if hasattr(quality, 'normalized_score') else quality.score
                    except Exception:
                        # Scorer failed, continue
                        pass
                
                # Aggregate final confidence with the run's effective
                # (sum-normalized) weights — computed once in verify_all.
                # v3.142 (R-a): resolver component = calibrated agreement-
                # structure belief (dedup.resolver_belief; chain counts only,
                # never resolver score magnitudes). Fallback to the legacy
                # capped-consensus value only for hand-built legacy metadata
                # dicts that predate the belief field.
                resolver_component = float(metadata.get(
                    "belief", min(consensus_score, 100.0)))
                # v3.142 (M-a): similarity component = the verification
                # WORKER's measurement, with skeleton_sim*100 as fallback for
                # chemical rows that never got a worker score. The skeleton
                # fp still gates CHEMICAL verification (SKELF_VERIFY_THRESHOLD)
                # and still leads the fidelity ordering — but it no longer
                # FLOORS the displayed term: raising worker signals (62-64 on
                # skeleton-saturated plateaux) to a constant 100 destroyed the
                # only row-level information exactly at saturated classes.
                # Corpus proof that no ranking changes (5,993 annotations,
                # floor-vs-nofloor identical on all 12 validated@k cells):
                # .tmp/CALIBRATION_v3142.md (checkpoint 0).
                if similarity_score is not None:
                    similarity_component = similarity_score.normalized_score
                elif ident_type in CHEMICAL_IDENT_TYPES and skeleton_sim is not None:
                    similarity_component = skeleton_sim * 100.0
                else:
                    similarity_component = 0.0
                annotation_component = annotation_score if annotation_score else 0.0
                
                # Sanitize NaN/Inf in components
                if similarity_component is not None and (math.isnan(similarity_component) or math.isinf(similarity_component)):
                    similarity_component = 0.0
                if annotation_component is not None and (math.isnan(annotation_component) or math.isinf(annotation_component)):
                    annotation_component = 0.0
                
                # F-07 NOTE: resolver_score magnitudes from pubchem-family
                # resolvers are CONSTANT threshold stubs (ordinal-only within
                # that resolver; see resolvers/pubchem.py docstrings). They
                # never enter the composition: the resolver component is the
                # chain-count belief term (dedup.resolver_belief, v3.142 R-a).
                # The legacy capped-consensus value is still stored on hits as
                # `resolver_score` for traceability of the old field.
                final_confidence = (
                    w_resolver * resolver_component +
                    w_similarity * similarity_component +
                    w_annotation * annotation_component
                )
                
                # Sanitize NaN/Inf in final_confidence
                if math.isnan(final_confidence) or math.isinf(final_confidence):
                    final_confidence = 0.0
                
                # Determine if verified
                # Identity hits can be verified without similarity/annotation scores
                # For non-identity hits, require positive evidence (score > 0).
                # Red-team batch-4 (D-09): annotation_score > 0 alone is no
                # longer positive evidence — existence of an annotated record
                # is not a molecule-vs-record comparison.
                min_confidence = self._verification_config.min_final_confidence
                # Red-team batch-4 (known issue #2): a degenerate similarity
                # measurement (0.0-TM, gap-scattered near-zero identity) is
                # not corroboration and can never be positive evidence.
                sim_nondegenerate = (
                    similarity_score is not None
                    and similarity_meets_floor(
                        similarity_score.metric_name,
                        similarity_score.normalized_score)
                )
                if (similarity_score is not None and not sim_nondegenerate
                        and rejection_reason is None):
                    rejection_reason = "below_similarity_floor"
                has_positive_evidence = (
                    sim_nondegenerate or hit_type == "identity"
                )
                
                # F7 chemical gate: identity/candidate hits are NEVER sufficient
                # for chemical compounds - require skeleton-fingerprint
                # corroboration between the molecule and the candidate structure.
                if ident_type in CHEMICAL_IDENT_TYPES:
                    has_positive_evidence = (
                        skeleton_sim is not None
                        and skeleton_sim >= SKELF_VERIFY_THRESHOLD
                    )
                    if not has_positive_evidence:
                        rejection_reason = (
                            "fingerprint_mismatch" if skeleton_sim is not None
                            else "fingerprint_unavailable"
                        )
                    # Water duplicate demotion: fingerprint-identical hits after
                    # the pinned water identity are duplicate db records of it.
                    elif water_seg and skeleton_sim == 1.0 and water_pinned:
                        has_positive_evidence = False
                        rejection_reason = "water_duplicate_identity"
                
                if final_confidence >= min_confidence and has_positive_evidence:
                    # v3.142 Phase 4: visual-collapse class id (see helper
                    # docstring; computed from already-threaded keys only).
                    eq_class_id = _equivalence_class_id(
                        ident_type, normalized_id, signature_type,
                        canonical_signature, similarity_score)
                    # F-17: telemetry flag (ruling 2026-10-04: identity stays
                    # identity either way — flag ONLY records that this
                    # non-chemical identity hit verified with no corroboration
                    # signal at all). No effect on is_verified or any count.
                    verified_without_corroboration = (
                        hit_type == "identity"
                        and ident_type not in CHEMICAL_IDENT_TYPES
                        and similarity_score is None
                    )
                    # Element ground truth (user ruling 2026-10-11): monoatomic
                    # ELEMENT identity hits are ground truth — confidence 100,
                    # rule recorded in ground_truth_override. Everything else
                    # keeps the weighted aggregate unchanged.
                    gt_override = None
                    if _element_ground_truth(results, segment, ident_type, hit_type):
                        final_confidence = 100.0
                        gt_override = "element_monoatomic"
                    # Water ground truth (v3.140): on water segments the first
                    # fingerprint-identical chemical hit IS the water identity;
                    # same confidence lift as element_monoatomic, same rationale
                    # (identity is owned ground truth, corroboration unprovable).
                    elif (water_seg and ident_type in CHEMICAL_IDENT_TYPES
                          and skeleton_sim == 1.0 and not water_pinned
                          and _water_formula_match(results, segment,
                                                   canonical_signature) is not False):
                        final_confidence = 100.0
                        gt_override = "water_triatomic"
                        water_pinned = True
                    # v3.142: confidence is ALWAYS numeric (user ruling: no
                    # "—"/null anywhere). The v3.140 plateau-null block is
                    # removed: with the calibrated belief term (R-a,
                    # never ==100) and the worker-primary similarity term
                    # (M-a, row-varying on plateaux) the former flat-94
                    # family constant cannot form; intra-class sameness is
                    # presented by the equivalence-class collapse instead
                    # (Phase 4), not by hiding the number.
                    emitted_confidence: float | None = min(final_confidence, 100.0)
                    # Create verified hit
                    verified_hit = VerifiedHit(
                        identifier=normalized_id,
                        ident_type=ident_type,
                        database=_database_name(ident_type),
                        resolver_score=min(consensus_score, 100.0),
                        similarity_score=similarity_score.normalized_score if similarity_score else None,
                        annotation_quality_score=annotation_score,
                        final_confidence=emitted_confidence,
                        supporting_evidence_count=len(source_resolvers),
                        is_verified=True,
                        skeleton_sim=skeleton_sim,
                        skeleton_method=skeleton_method,
                        verified_without_corroboration=verified_without_corroboration,
                        belief=metadata.get("belief"),
                        equivalence_class_id=eq_class_id,
                        ground_truth_override=gt_override,
                        similarity_details=(similarity_score.details or None
                                            if similarity_score else None),
                        hit_type=hit_type,
                    )
                else:
                    # Create unverified hit (workers may still have run for it)
                    # — same class id when provable, so the collapse semantics
                    # stay complete if a row flips to verified by a rule.
                    eq_class_id = _equivalence_class_id(
                        ident_type, normalized_id, signature_type,
                        canonical_signature, similarity_score)
                    # Create unverified hit
                    if rejection_reason is None:
                        rejection_reason = "below_threshold"
                    
                    verified_hit = VerifiedHit.unverified(
                        identifier=normalized_id,
                        ident_type=ident_type,
                        database=_database_name(ident_type),
                        resolver_score=min(consensus_score, 100.0),
                        supporting_evidence_count=len(source_resolvers),
                        rejection_reason=rejection_reason,
                        # v3.143 (D-17): keep measurements that were actually
                        # taken for this row (worker ran, scorer ran).
                        similarity_score=(similarity_score.normalized_score
                                          if similarity_score else None),
                        annotation_quality_score=annotation_score,
                        similarity_details=(similarity_score.details or None
                                            if similarity_score else None),
                        hit_type=hit_type,
                    )
                    verified_hit.belief = metadata.get("belief")
                    verified_hit.equivalence_class_id = eq_class_id
                    if ident_type in CHEMICAL_IDENT_TYPES:
                        verified_hit.skeleton_sim = skeleton_sim
                        verified_hit.skeleton_method = skeleton_method
                
                verified_hits.append(verified_hit)
            
            # F16: fidelity-first presentation order (stored order = display
            # order; ordering-only, deterministic tie-break chain).
            verified_hits = _fidelity_order_hits(verified_hits)
            # Store results back to ResultsManager
            output_path = f"verification/{segment}/verified_hits"
            hits_as_dicts = [dataclasses.asdict(hit) for hit in verified_hits]
            results.set_data(output_path, hits_as_dicts)
            # v3.142 Phase 4 (additive): per-segment class sizes over the
            # verified rows — the UI collapse is visual-only; stored rows and
            # their order/counts are never altered.
            try:
                class_sizes: dict[str, int] = {}
                for h in verified_hits:
                    if h.is_verified and h.equivalence_class_id:
                        class_sizes[h.equivalence_class_id] = (
                            class_sizes.get(h.equivalence_class_id, 0) + 1)
                results.set_data(f"verification/{segment}/class_sizes", class_sizes)
            except Exception:
                pass  # class sizes are presentation-only; never block verify
            
            per_segment_results[segment] = verified_hits
            if seg_budget_hit:
                results.set_data(f"verification/{segment}/partial", True)
                return per_segment_results
        
        return per_segment_results

    def _maybe_structure_rerank(self, results, segment, sorted_groups, top_n, _over_budget):
        """Try skeleton-aware rerank of chemical groups before the window cut.

        Only acts when the window actually binds: more chemical candidate
        groups than verify_top_n AND the segment has a molecule skeleton_fp.
        Raises no exceptions; falls back to legacy consensus order.

        Cost: one mirror/canonical fetch + skeleton FP per chemical candidate
        (~ms each offline), bounded by verify_rerank_max_candidates and the
        stage budget probe `_over_budget`.
        """
        chem_groups = [
            (key, meta) for (key, meta) in sorted_groups
            if key[1] in CHEMICAL_IDENT_TYPES
        ]
        if len(chem_groups) <= top_n:
            return sorted_groups  # window fits: nothing to rescue
        mol_hex = _molecule_skeleton_fp_hex(results, segment)
        if not mol_hex:
            return sorted_groups
        mol_fp = hex_to_fp(mol_hex)
        if mol_fp is None:
            return sorted_groups
        max_cands = int(
            getattr(self._verification_config, "verify_rerank_max_candidates", 25000)
            or 25000
        )
        if len(chem_groups) > max_cands:
            logger.warning(
                f"structure rerank skipped for segment {segment}: "
                f"{len(chem_groups)} chemical candidates > cap {max_cands}; "
                f"keeping consensus order"
            )
            return sorted_groups

        import time as _time
        t0 = _time.time()
        skel_map: dict = {}
        n_fetched = 0
        for key, meta in chem_groups:
            if _over_budget():
                logger.warning(
                    f"structure rerank budget-exceeded for segment {segment} "
                    f"after {len(skel_map)}/{len(chem_groups)} candidates; "
                    f"keeping consensus order"
                )
                return sorted_groups
            nid, ident_type = key
            sim = None
            fetcher = self._registry.get_fetcher(ident_type)
            if fetcher:
                try:
                    canonical = fetcher.fetch(nid, ident_type)
                except Exception:
                    canonical = None
                if canonical:
                    n_fetched += 1
                    try:
                        cand_fp = _skel_fp(from_smiles(canonical))
                        if cand_fp is not None:
                            sim = _skel_tanimoto(mol_fp, cand_fp)
                    except Exception:
                        sim = None
            skel_map[key] = sim

        if not any((s or 0.0) >= SKELF_VERIFY_THRESHOLD for s in skel_map.values()):
            logger.debug(
                f"structure rerank inert for segment {segment}: "
                f"{len(chem_groups)} chemical candidates, none reached "
                f"{SKELF_VERIFY_THRESHOLD}; consensus order kept"
            )
            return sorted_groups
        out = _structure_rerank_groups(sorted_groups, skel_map, SKELF_VERIFY_THRESHOLD)
        best = max((s or 0.0) for s in skel_map.values())
        n_gate = sum(1 for s in skel_map.values() if (s or 0.0) >= SKELF_VERIFY_THRESHOLD)
        logger.info(
            f"structure rerank for segment {segment}: {len(chem_groups)} "
            f"chemical candidates ({n_fetched} structures fetched), "
            f"{n_gate} at/above gate {SKELF_VERIFY_THRESHOLD}, best={best:.3f}; "
            f"rerank took {_time.time() - t0:.1f}s"
        )
        return out
