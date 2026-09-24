"""Registry for identifier resolvers."""

from __future__ import annotations

from ..config.loader import RunConfig
from .base import IdentifierResolver
from .resolvers.pubchem import PubChemResolver
from .resolvers.chembl import ChemblResolver
from .resolvers.idsm import IDSMResolverPubchem, IDSMResolverChembl, IDSMResolverChebi
from .resolvers.inchikey import InchiKeyResolver, InchiKeySelfResolver
from .resolvers.hfamily import FormulaHFamilyResolver
from .resolvers.formula import FormulaResolver, FormulaChEMBLResolver
from .resolvers.blast import (
    BLASTResolverPDBAA, BLASTResolverPDBNT, BLASTResolverUNIPROT,
    BLASTResolverNR, BLASTResolverSWISSPROT,
    BLASTResolverCORENT, BLASTResolverNT
)
from .resolvers.pdb_struct import PDBStructResolverProtein, PDBStructResolverNucleotide
from .resolvers.alphafind import AlphaFindStructResolver
from .resolvers.foldseek import Foldseek3DiResolver
from .resolvers.mmcif import MmCifResolver
from .resolvers.lipid import LipidShorthandResolver
from .resolvers.glycan import GlycanCompositionResolver
from .resolvers.atom import AtomResolver
from .resolvers.name import NameResolverCCD, NameResolverMAPS, NameResolverMANUAL


class IdentifierRegistry:
    """Registry for managing identifier resolvers.
    
    Provides lookup of applicable resolvers based on signature type and mode.
    """
    
    def __init__(self, resolvers: list[IdentifierResolver]) -> None:
        """Initialize the registry with resolvers.
        
        Args:
            resolvers: List of IdentifierResolver instances to register.
        """
        self._resolvers: list[IdentifierResolver] = list(resolvers)
    
    def get_applicable_resolvers(
        self, 
        signature_type: str, 
        as_similarity: bool = False
    ) -> list[IdentifierResolver]:
        """Get resolvers applicable for the given signature type.
        
        Args:
            signature_type: Type of signature (e.g. "smiles", "inchikey").
            as_similarity: If True, filter for similarity-capable resolvers.
            
        Returns:
            List of applicable IdentifierResolver instances.
        """
        applicable = []
        for resolver in self._resolvers:
            # Check if signature_type is in accepted_signatures
            if signature_type not in resolver.accepted_signatures:
                continue
            
            # Check enabled flags
            if as_similarity:
                if not resolver.enabled_similarity:
                    continue
            else:
                if not resolver.enabled_identity:
                    continue
            
            applicable.append(resolver)
        
        return applicable


def get_default_resolvers(config: RunConfig) -> list[IdentifierResolver]:
    """Get default list of identifier resolvers.
    
    Args:
        config: RunConfig instance for resolver initialization.
        
    Returns:
        List of default IdentifierResolver instances.
        Includes: PubChem, ChEMBL, IDSM (pubchem/chembl/chebi), InChIKey, Formula,
        BLAST (PDB protein/nucleic, UniProt), PDB struct (protein/nucleotide),
        AlphaFind, Foldseek, mmCIF.
    """
    resolvers = []
    
    # Phase 2 resolvers (existing)
    resolvers.append(PubChemResolver(config))
    resolvers.append(ChemblResolver(config))
    resolvers.append(IDSMResolverPubchem(config))
    resolvers.append(IDSMResolverChembl(config))
    resolvers.append(IDSMResolverChebi(config))
    resolvers.append(InchiKeyResolver(config))
    # Offline identity pass-through: InChIKey signature is itself a candidate
    # (verification fetches its structure via cactus chain). PUB-indepedent.
    resolvers.append(InchiKeySelfResolver(config))
    # Local PubChem mirror (formula -> CIDs): primary formula channel when the
    # built DB is present; degrades silently to the PUG/ChEMBL chain otherwise.
    if getattr(config.identifiers, "formula_local", True):
        from .resolvers.formula_local import FormulaLocalResolver
        from ..molecules.pubchem_db import PubChemDB as _PubChemDB

        _local_path = getattr(config.pubchem, "local_db_path", "")
        if _local_path and _PubChemDB(_local_path).exists():
            resolvers.append(FormulaLocalResolver(config))
        else:
            import logging as _logging

            _logging.getLogger("identifier").warning(
                "formula_local enabled but mirror DB missing at %r; PUG chain in use", _local_path
            )
    resolvers.append(FormulaResolver(config))
    # ChEMBL exact-formula fallback: only meaningful while PubChem is
    # cluster-blocked; gated on config flag or VALIDATION_SKIP_PUG.
    import os as _os
    if getattr(config.identifiers, "formula_chembl", False) or _os.environ.get("VALIDATION_SKIP_PUG"):
        resolvers.append(FormulaChEMBLResolver(config))
    resolvers.append(FormulaHFamilyResolver(config))
    
    # Phase 3 resolvers (macromolecule identifiers)
    resolvers.append(BLASTResolverPDBAA(config))
    resolvers.append(BLASTResolverPDBNT(config))
    resolvers.append(BLASTResolverUNIPROT(config))
    resolvers.append(BLASTResolverNR(config))
    resolvers.append(BLASTResolverSWISSPROT(config))
    resolvers.append(BLASTResolverCORENT(config))
    resolvers.append(BLASTResolverNT(config))
    resolvers.append(PDBStructResolverProtein(config))
    resolvers.append(PDBStructResolverNucleotide(config))
    resolvers.append(AlphaFindStructResolver(config))
    resolvers.append(Foldseek3DiResolver(config))
    resolvers.append(MmCifResolver(config))
    

    # New resolvers (lipids, glycans, atoms, names)
    resolvers.append(LipidShorthandResolver(config))
    resolvers.append(GlycanCompositionResolver(config))
    resolvers.append(AtomResolver(config))
    resolvers.append(NameResolverCCD(config))
    resolvers.append(NameResolverMAPS(config))
    resolvers.append(NameResolverMANUAL(config))

    return resolvers
