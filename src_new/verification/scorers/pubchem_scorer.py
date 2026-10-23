"""PubChem annotation quality scorer."""

from __future__ import annotations

import os

import requests

from ..base import AnnotationQualityScorer
from ..models import AnnotationQuality

_LOCAL_DB = None
_LOCAL_DB_READY = False

# v3.142 (1c): single source of truth for the PubChem signal schema (total 100).
_PUBCHEM_SIGNAL_POINTS = {
    "base": 20.0,            # record exists (base points)
    "canonical_smiles": 20.0,
    "isomeric_smiles": 15.0,
    "molecular_formula": 15.0,
    "iupac_name": 15.0,
    "synonyms": 15.0,
}


def _pubchem_schema_score(signals: list[str]) -> float:
    """Score = base + sum of achieved signal points (uniform denominator)."""
    return _PUBCHEM_SIGNAL_POINTS["base"] + sum(
        _PUBCHEM_SIGNAL_POINTS[s] for s in set(signals))


def _pug_props_url(identifier: str, is_inchikey: bool) -> str:
    kind = "inchikey" if is_inchikey else "cid"
    # D-07: current PUG property names (legacy CanonicalSMILES/
    # IsomericSMILES requests now return renamed columns — see
    # _extract_pug_signals).
    return (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/{kind}/"
            f"{identifier}/property/ConnectivitySMILES,SMILES,IUPACName,MolecularFormula/JSON")


def _pug_synonyms_url(identifier: str, is_inchikey: bool) -> str:
    kind = "inchikey" if is_inchikey else "cid"
    return (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/{kind}/"
            f"{identifier}/synonyms/JSON")


def _pug_smiles_signals(props: dict) -> tuple[bool, bool]:
    """(has_connectivity_smiles, has_isomeric_smiles) from a PUG Properties
    record. Live-verified 2026-10-23 on CID 702: current responses carry
    'ConnectivitySMILES' and 'SMILES'; the historic 'CanonicalSMILES' and
    'IsomericSMILES' keys are read as fallbacks only."""
    has_canonical = bool(props.get("ConnectivitySMILES")
                         or props.get("CanonicalSMILES"))
    has_isomeric = bool(props.get("SMILES") or props.get("IsomericSMILES"))
    return has_canonical, has_isomeric


def _local_db():
    """Lazy per-process handle to the local PubChem mirror (None when absent).

    Same pattern as verification/fetchers/compound_fetcher._local_db:
    path override via PUBCHEM_LOCAL_DB env var (tests, staging).

    2026-09-25 spin-class: per-candidate PUG HTTP calls (2x timeout=10s each)
    were the verify-stage wall-stall driver after the cluster egress got
    rate-limited by NCBI; the local mirror answers in ~1ms instead.
    """
    global _LOCAL_DB, _LOCAL_DB_READY
    if not _LOCAL_DB_READY:
        path = os.environ.get(
            "PUBCHEM_LOCAL_DB", "/app/databases/pubchem/current/pubchem.sqlite"
        )
        try:
            from ...molecules.pubchem_db import PubChemDB

            db = PubChemDB(path)
            if db.exists():
                _LOCAL_DB = db
        except Exception:
            _LOCAL_DB = None
        _LOCAL_DB_READY = True
    return _LOCAL_DB


class PubChemAnnotationScorer(AnnotationQualityScorer):
    """Scores annotation quality for PubChem-compound identifiers.

    (v3.142 1c) Uniform signal schema — total 100 — applied identically
    regardless of store: base 20 + canonical_smiles 20 + isomeric_smiles 15
    + molecular_formula 15 + iupac_name 15 + synonyms 15. The local mirror
    structurally supplies the first four (no IUPAC/synonyms by design);
    with live-fetch enabled (default ON, config
    verification.annotation_live_fetch) and per-segment budget remaining
    (annotation_live_budget_per_segment, re-armed by the manager per segment
    via begin_segment), missing signals are fetched live from PUG so the
    reachable score is STORE-INDEPENDENT. Mirror-only / budget-exhausted /
    network-failure floors at 70 — a store floor, documented, never a cap.
    Supports PUBCHEM_CID and (via the mirror's inchikey column / PUG inchikey
    endpoints) INCHIKEY.
    """

    def __init__(self) -> None:
        self._live_fetch = True
        self._timeout_s = 3.0
        self._remaining = 0
        # Red-team batch-4 (D-07 position-independence): records are
        # immutable, so a successful score is cached per (ident_type,
        # identifier) and served verbatim on repeats — identical records can
        # no longer decay with window position / budget consumption. The
        # cache deliberately survives begin_segment (cross-segment repeats
        # are the same record); transient None failures are never cached.
        self._score_cache: dict[tuple[str, str], AnnotationQuality] = {}

    def configure(self, *, live_fetch: bool, timeout_s: float) -> None:
        """Per-manager wiring (v3.142): live-fetch policy from config."""
        self._live_fetch = bool(live_fetch)
        self._timeout_s = float(timeout_s)

    def begin_segment(self, budget: int) -> None:
        """Re-arm the per-segment live-call budget (manager calls once per
        segment)."""
        self._remaining = int(budget)

    def _live_get_json(self, url: str) -> dict | None:
        """One budgeted live call. Returns parsed JSON or None (never raises:
        budget exhaustion / network failure are silent fallbacks)."""
        if not self._live_fetch or self._remaining <= 0:
            return None
        self._remaining -= 1
        try:
            r = requests.get(url, timeout=self._timeout_s)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def supports(self, ident_type: str) -> bool:
        """Check if this scorer supports the given identifier type."""
        return ident_type in ("PUBCHEM_CID", "INCHIKEY", "INCHI_KEY")

    def score(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
        """Score the annotation quality for a PubChem CID.

        Caching wrapper around _score_uncached (red-team batch-4, D-07): a
        record scores once and repeats verbatim — identical records can no
        longer decay with window position. Transient None failures are not
        cached (a retry recomputes them).
        """
        if not self.supports(ident_type):
            return None
        key = (ident_type, str(identifier))
        cached = self._score_cache.get(key)
        if cached is not None:
            return cached
        result = self._score_uncached(identifier, ident_type)
        if result is not None:
            self._score_cache[key] = result
        return result

    def _score_uncached(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
        """Score the annotation quality for a PubChem CID (fetch path).
        
        Args:
            identifier: PubChem CID (e.g., "962").
            ident_type: Should be "PUBCHEM_CID".
            
        Returns:
            AnnotationQuality with score 0-100 and signals found.
            Returns low score (0.0) on any failure without raising.

        Scoring note (v3.142 1c, supersedes the 2026-09-25 cap note): the
        local-mirror path yields base 20 + canonical_smiles 20 +
        isomeric_smiles 15 + molecular_formula 15 = 70 (mirror stores no
        IUPAC/synonyms by design). With live-fetch enabled and budget left,
        the two missing signals are filled from PUG, so the store floor is
        not a cap: both stores can reach the full 100-signal schema.
        """
        if not self.supports(ident_type):
            return None

        is_inchikey = ident_type in ("INCHIKEY", "INCHI_KEY")
        cid = identifier

        # Local PubChem mirror first: ~1ms, immune to PUG rate-limiting.
        db = _local_db()
        if db is not None:
            try:
                row = (db.by_inchikey(identifier) if is_inchikey
                       else db.by_cid(cid))
            except Exception:
                row = None
            if row is not None:
                signals = []
                if row.smiles:
                    # Mirror stores isomeric SMILES (connectivity superset of
                    # PUG CanonicalSMILES) -> both structure signals apply.
                    signals.append("canonical_smiles")
                    signals.append("isomeric_smiles")
                if row.formula_hill:
                    signals.append("molecular_formula")
                # Live fill for mirror-missing signals (IUPAC/synonyms).
                self._live_fill(identifier, is_inchikey, signals,
                                "iupac_name" not in signals,
                                "synonyms" not in signals)
                # re-sum from achieved signals (single source of truth)
                return AnnotationQuality(
                    database="pubchem",
                    score=min(_pubchem_schema_score(signals), 100.0),
                    signals=signals,
                )

        # Mirror miss or mirror absent: full PUG path (budgeted live calls).
        props_data = self._live_get_json(
            _pug_props_url(identifier, is_inchikey))
        if props_data is None:
            # Live fetch disabled / budget exhausted / network failure:
            # nothing provable locally about this record.
            return None
        
        # v3.143 (D-17): the signal extraction below used to appear
        # twice in a row; the first copy was overwritten before use
        # (dead code, removed).
        signals = []
        score = 20.0  # Base points for having the entry
        
        # Extract properties from response
        prop_list = props_data.get("PropertyTable", {}).get("Properties", [])
        if prop_list and len(prop_list) > 0:
            props = prop_list[0]
            
            # Check canonical_smiles / isomeric_smiles (D-07: PUG renamed
            # the keys; read via the shared extractor)
            has_canonical, has_isomeric = _pug_smiles_signals(props)
            if has_canonical:
                signals.append("canonical_smiles")
                score += 20.0
            if has_isomeric:
                signals.append("isomeric_smiles")
                score += 15.0
            
            # Check iupac_name
            iupac_name = props.get("IUPACName", "")
            if iupac_name:
                signals.append("iupac_name")
                score += 15.0
            
            # Check molecular_formula
            mol_formula = props.get("MolecularFormula", "")
            if mol_formula:
                signals.append("molecular_formula")
                score += 15.0
        
        # Fetch synonyms (budgeted live call; failure is non-fatal)
        synonyms_data = self._live_get_json(_pug_synonyms_url(identifier, is_inchikey))
        if synonyms_data is not None:
            info_list = synonyms_data.get("InformationList", {}).get("Information", [])
            if info_list and len(info_list) > 0:
                synonyms = info_list[0].get("Synonym", [])
                if synonyms and len(synonyms) > 0:
                    signals.append("synonyms")
                    score += 15.0
        
        return AnnotationQuality(
            database="pubchem",
            score=min(score, 100.0),
            signals=signals,
        )

    def _live_fill(self, identifier: str, is_inchikey: bool, signals: list,
                   missing_iupac: bool, missing_syn: bool) -> None:
        """Fill mirror-missing signals from PUG (bounded live calls).

        Mutates `signals` in place with whatever PUG proves; stays silent on
        any failure (mirror floor retained).
        """
        if missing_iupac:
            props_data = self._live_get_json(_pug_props_url(identifier, is_inchikey))
            if props_data is not None:
                prop_list = props_data.get("PropertyTable", {}).get("Properties", [])
                if prop_list:
                    props = prop_list[0]
                    if props.get("IUPACName"):
                        signals.append("iupac_name")
                    # free bonus fill (PUG carries these anyway); mirror rows
                    # already hold them, so guard against duplication.
                    has_canonical, has_isomeric = _pug_smiles_signals(props)
                    if has_canonical and "canonical_smiles" not in signals:
                        signals.append("canonical_smiles")
                    if has_isomeric and "isomeric_smiles" not in signals:
                        signals.append("isomeric_smiles")
                    if props.get("MolecularFormula") and "molecular_formula" not in signals:
                        signals.append("molecular_formula")
        if missing_syn:
            synonyms_data = self._live_get_json(_pug_synonyms_url(identifier, is_inchikey))
            if synonyms_data is not None:
                info_list = synonyms_data.get("InformationList", {}).get("Information", [])
                if info_list and info_list[0].get("Synonym"):
                    signals.append("synonyms")
