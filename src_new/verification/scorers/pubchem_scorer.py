"""PubChem annotation quality scorer."""

from __future__ import annotations

import os

import requests

from ..base import AnnotationQualityScorer
from ..models import AnnotationQuality

_LOCAL_DB = None
_LOCAL_DB_READY = False


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
    """Scores annotation quality for PubChem compounds."""

    def supports(self, ident_type: str) -> bool:
        """Check if this scorer supports the given identifier type."""
        return ident_type == "PUBCHEM_CID"

    def score(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
        """Score the annotation quality for a PubChem CID.
        
        Args:
            identifier: PubChem CID (e.g., "962").
            ident_type: Should be "PUBCHEM_CID".
            
        Returns:
            AnnotationQuality with score 0-100 and signals found.
            Returns low score (0.0) on any failure without raising.

        Scoring note (2026-09-25): the local-mirror path yields a max of 70
        (base 20 + canonical_smiles 20 + isomeric_smiles 15 + molecular_formula
        15; mirror stores isomeric SMILES by design and has no IUPAC/synonyms),
        versus 100 for the full-PUG path. Deliberate trade: bounded ~1ms offline
        lookups instead of two `timeout=10s` HTTP calls per candidate against a
        rate-limited API.
        """
        if not self.supports(ident_type):
            return None

        cid = identifier

        # Local PubChem mirror first: ~1ms, immune to PUG rate-limiting.
        db = _local_db()
        if db is not None:
            try:
                row = db.by_cid(cid)
            except Exception:
                row = None
            if row is not None:
                signals = []
                score = 20.0  # Base points for having the entry
                if row.smiles:
                    # Mirror stores isomeric SMILES (connectivity superset of
                    # PUG CanonicalSMILES) -> both structure signals apply.
                    signals.append("canonical_smiles")
                    score += 20.0
                    signals.append("isomeric_smiles")
                    score += 15.0
                if row.formula_hill:
                    signals.append("molecular_formula")
                    score += 15.0
                return AnnotationQuality(
                    database="pubchem", score=min(score, 100.0), signals=signals
                )

        # Mirror miss or mirror absent: PUG fallback (unchanged semantics,
        # timeouts bounded at 3s so a banned/throttled API cannot stall verify).
        try:
            # Fetch properties
            props_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/CanonicalSMILES,IsomericSMILES,IUPACName,MolecularFormula/JSON"
            props_response = requests.get(props_url, timeout=3)
            props_response.raise_for_status()
            props_data = props_response.json()
        except Exception:
            return AnnotationQuality(database="pubchem", score=0.0, signals=[])
        
        signals = []
        score = 20.0  # Base points for having the entry
        
        # Extract properties from response
        prop_list = props_data.get("PropertyTable", {}).get("Properties", [])
        if prop_list and len(prop_list) > 0:
            props = prop_list[0]
            
            # Check canonical_smiles
            canonical_smiles = props.get("CanonicalSMILES", "")
            if canonical_smiles:
                signals.append("canonical_smiles")
                score += 20.0
            
            # Check isomeric_smiles
            isomeric_smiles = props.get("IsomericSMILES", "")
            if isomeric_smiles:
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
        
        # Fetch synonyms
        try:
            synonyms_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/synonyms/JSON"
            synonyms_response = requests.get(synonyms_url, timeout=3)
            synonyms_response.raise_for_status()
            synonyms_data = synonyms_response.json()
            
            info_list = synonyms_data.get("InformationList", {}).get("Information", [])
            if info_list and len(info_list) > 0:
                synonyms = info_list[0].get("Synonym", [])
                if synonyms and len(synonyms) > 0:
                    signals.append("synonyms")
                    score += 15.0
        except Exception:
            # Synonyms fetch failure is not fatal, just don't add the signal
            pass
        
        return AnnotationQuality(
            database="pubchem",
            score=min(score, 100.0),
            signals=signals,
        )
