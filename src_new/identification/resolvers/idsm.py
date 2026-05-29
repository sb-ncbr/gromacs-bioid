"""IDSM identifier resolver with SPARQL-based structural search."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from SPARQLWrapper import SPARQLWrapper, JSON

from ..base import IdentifierResolver, IdentifierResolutionError

if TYPE_CHECKING:
    from ...config.loader import RunConfig

logger = logging.getLogger("identifier")


def _escape_sparql_string(s: str) -> str:
    """Escape special characters for safe SPARQL string literal insertion.

    This prevents SPARQL injection when inserting SMILES strings into queries.

    Args:
        s: String to escape.

    Returns:
        Escaped string safe for SPARQL literal.
    """
    # Escape backslashes first, then quotes
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("'", "\\'")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    return s


class IDSMResolver(IdentifierResolver):
    """Base resolver for SMILES/SELFIES signatures using IDSM SPARQL endpoint."""

    accepted_signatures = ["smiles", "selfies"]

    def __init__(
        self,
        config: RunConfig,
        use_pubchem: bool = False,
        use_chembl: bool = False,
        use_chebi: bool = False,
    ) -> None:
        """Initialize IDSM resolver.

        Args:
            config: RunConfig instance containing idsm settings.
            use_pubchem: If True, search PubChem via IDSM.
            use_chembl: If True, search ChEMBL via IDSM.
            use_chebi: If True, search ChEBI via IDSM.
        """
        assert use_chembl or use_pubchem or use_chebi, "One mode of operation is necessary"
        assert not (use_chembl and use_pubchem), "Only one mode of operation is allowed"

        self._use_pubchem = use_pubchem
        self._use_chembl = use_chembl
        self._use_chebi = use_chebi

        # Set name and identifier_type based on mode
        if use_pubchem:
            name = "idsm_pubchem"
            identifier_type = "PUBCHEM_CID"
        elif use_chembl:
            name = "idsm_chembl"
            identifier_type = "CHEMBL_ID"
        else:
            name = "idsm_chebi"
            identifier_type = "CHEBI_ID"

        # Store for dynamic access
        self._resolver_name = name
        self._identifier_type = identifier_type

        super().__init__(config)

    @property
    def name(self) -> str:
        """Resolver name."""
        return self._resolver_name

    @property
    def identifier_type(self) -> str:
        """Identifier type returned by this resolver."""
        return self._identifier_type

    def _is_applicable(self, signature: str) -> bool:
        """Check if signature is applicable for IDSM search.

        Args:
            signature: The signature string to check.

        Returns:
            True (assumes valid SMILES/SELFIES from signature generator).
        """
        return True

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """Resolve SMILES/SELFIES to exact-match identifiers via IDSM.

        Args:
            signature: SMILES or SELFIES string to resolve.
            working_directory: Unused.

        Returns:
            List of identifier strings (CID, CHEMBL_ID, or CHEBI_ID).

        Raises:
            IdentifierResolutionError: If resolution fails.
        """
        # Decode SELFIES to SMILES if needed
        smiles = self._decode_selfies(signature)
        # Identity = 100% similarity
        results = idsm_fetch_similarity_match(
            smiles,
            threshold=100,
            include_similarity=False,
            as_pubchem=self._use_pubchem,
            as_chembl=self._use_chembl,
            as_chebi=self._use_chebi,
        )
        # Convert to strings
        return [str(r[0]) if isinstance(r, tuple) else str(r) for r in results]

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """Resolve SMILES/SELFIES to similar identifiers via IDSM.

        Args:
            signature: SMILES or SELFIES string to resolve.
            working_directory: Unused.

        Returns:
            List of (identifier, similarity_score) tuples.

        Raises:
            IdentifierResolutionError: If resolution fails (no results is OK).
        """
        # Decode SELFIES to SMILES if needed
        smiles = self._decode_selfies(signature)
        threshold = self.config.idsm.similarity_threshold
        results = idsm_fetch_similarity_match(
            smiles,
            threshold=threshold,
            include_similarity=True,
            as_pubchem=self._use_pubchem,
            as_chembl=self._use_chembl,
            as_chebi=self._use_chebi,
        )
        # Convert identifiers to strings
        return [(str(r[0]), r[1]) if isinstance(r, tuple) else (str(r), 100.0) for r in results]

    def _decode_selfies(self, signature: str) -> str:
        """Decode SELFIES to SMILES if signature is SELFIES.

        Args:
            signature: SMILES or SELFIES string.

        Returns:
            SMILES string.
        """
        # Check if this looks like SELFIES (contains [C], [O], etc.)
        if "[" in signature and "]" in signature:
            try:
                import selfies
                return selfies.decoder(signature)
            except ImportError:
                logger.warning("selfies package not installed; treating as SMILES")
            except Exception as exc:
                logger.warning(f"SELFIES decode failed: {exc}; treating as SMILES")
        return signature


class IDSMResolverPubchem(IDSMResolver):
    """IDSM resolver for PubChem identifiers."""

    def __init__(self, config: RunConfig) -> None:
        """Initialize PubChem mode IDSM resolver.

        Args:
            config: RunConfig instance.
        """
        super().__init__(config, use_pubchem=True, use_chembl=False, use_chebi=False)


class IDSMResolverChembl(IDSMResolver):
    """IDSM resolver for ChEMBL identifiers."""

    def __init__(self, config: RunConfig) -> None:
        """Initialize ChEMBL mode IDSM resolver.

        Args:
            config: RunConfig instance.
        """
        super().__init__(config, use_pubchem=False, use_chembl=True, use_chebi=False)


class IDSMResolverChebi(IDSMResolver):
    """IDSM resolver for ChEBI identifiers."""

    def __init__(self, config: RunConfig) -> None:
        """Initialize ChEBI mode IDSM resolver.

        Args:
            config: RunConfig instance.
        """
        super().__init__(config, use_pubchem=False, use_chembl=False, use_chebi=True)


def idsm_fetch_similarity_match(
    smiles: str,
    threshold: int | None,
    include_similarity: bool = False,
    as_pubchem: bool = False,
    as_chembl: bool = False,
    as_chebi: bool = False,
) -> list[str] | list[tuple[str, float]]:
    """Search IDSM SPARQL endpoint for similarity matches.

    Args:
        smiles: SMILES string to search.
        threshold: Similarity threshold (0-100, 100 = identity).
        include_similarity: If True, return (id, score) tuples.
        as_pubchem: If True, search PubChem.
        as_chembl: If True, search ChEMBL.
        as_chebi: If True, search ChEBI.

    Returns:
        List of identifier strings or (id, score) tuples.

    Raises:
        IdentifierResolutionError: On IDSM search failure.
    """
    cutoff = "0.8" if threshold is None else str(round(threshold / 100, 1))

    assert as_pubchem or as_chembl or as_chebi, "One mode of operation is mandatory"

    try:
        endpoint = "https://idsm.elixir-czech.cz/sparql/endpoint/idsm"
        # Fix: Escape SMILES to prevent SPARQL injection
        escaped_smiles = _escape_sparql_string(smiles)

        query = f'''
        PREFIX sachem: <http://bioinfo.uochb.cas.cz/rdf/v1.0/sachem#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

        SELECT * WHERE {{
          [ sachem:compound ?COMPOUND;
            sachem:score ?SCORE ] sachem:similaritySearch [
                  sachem:query "{escaped_smiles}";
                  sachem:cutoff "{cutoff}"^^xsd:double ].
        }}
        '''

        sparql = SPARQLWrapper(endpoint)
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        # Fix: Add timeout to SPARQL query (30 seconds)
        sparql.setTimeout(30)

        results = sparql.query().convert()

        ret = []
        for result in results["results"]["bindings"]:
            id_val = similarity = None
            compound_uri = result["COMPOUND"]["value"]

            if as_pubchem and "pubchem" in compound_uri.lower():
                # Fix: Robust parsing
                match = re.search(r"CID(\d+)", compound_uri)
                if match:
                    id_val = match.group(1)
                similarity = float(result["SCORE"]["value"]) * 100
            elif as_chembl and "chembl" in compound_uri.lower():
                # Fix: Robust parsing (old code used .split("CHEMBL")[1])
                match = re.search(r"CHEMBL(\d+)", compound_uri)
                if match:
                    id_val = match.group(1)
                similarity = float(result["SCORE"]["value"]) * 100
            elif as_chebi and "chebi" in compound_uri.lower():
                # Fix: Robust parsing (old code used .split("CHEBI_")[1])
                match = re.search(r"CHEBI[:_]?(\d+)", compound_uri, re.IGNORECASE)
                if match:
                    id_val = match.group(1)
                similarity = float(result["SCORE"]["value"]) * 100

            if id_val is not None and threshold is not None and similarity < threshold:
                continue

            if id_val is not None:
                if include_similarity:
                    ret.append((id_val, similarity))
                else:
                    ret.append(id_val)

        return ret
    except Exception as exc:
        logger.error("IDSM search failed!")
        logger.exception(exc)
        raise IdentifierResolutionError(f"[Identifier] IDSM searching failed: {exc}")
