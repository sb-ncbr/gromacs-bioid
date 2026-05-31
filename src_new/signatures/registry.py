"""Registry for signature generators."""

from __future__ import annotations

import logging
from .base import SignatureGenerator
from ..config.loader import SignaturesConfig

logger = logging.getLogger("base")


class SignatureRegistry:
    """Registry that holds and manages signature generator instances."""
    
    def __init__(self, generators: list[SignatureGenerator]) -> None:
        """Initialize the registry with a list of generators.
        
        Args:
            generators: List of SignatureGenerator instances.
        """
        self.generators = generators
    
    @classmethod
    def from_generators(cls, generators: list[SignatureGenerator]) -> "SignatureRegistry":
        """Create a registry from a list of generators.
        
        Args:
            generators: List of SignatureGenerator instances.
            
        Returns:
            New SignatureRegistry instance.
        """
        return cls(generators)


def get_signature_type_map(config: SignaturesConfig) -> dict[str, str]:
    """Build mapping from signature generator name to signature type.
    
    Args:
        config: SignaturesConfig instance with feature toggles.
        
    Returns:
        Dict mapping generator names (e.g. "smiles", "smiles_not_sanitized") 
        to signature types (e.g. "smiles", "smiles").
    """
    generators = get_default_generators(config)
    return {gen.name: gen.signature_type for gen in generators}


def _try_import(module_name: str, class_name: str):
    """Try to import a class, returning None if the module is not available."""
    try:
        import importlib
        module = importlib.import_module(module_name)
        return getattr(module, class_name)
    except ImportError as e:
        logger.debug(f"Optional generator not available: {module_name}.{class_name}: {e}")
        return None


def get_default_generators(config: SignaturesConfig) -> list[SignatureGenerator]:
    """Get the default list of signature generators in a sensible order.
    
    Order: analytical first, then descriptive, then fallback last.
    
    Args:
        config: SignaturesConfig instance with feature toggles.
        
    Returns:
        List of SignatureGenerator instances ready to use.
    """
    from .generators.smiles import SimpleSmilesGenerator, SimpleSmilesGeneratorNoSanitize
    from .generators.fasta import (
        MapFastaGeneratorProtein,
        MapFastaGeneratorNucleotide,
        ResnameFastaGeneratorProtein,
        ResnameFastaGeneratorNucleotide,
    )
    from .generators.pdb import (
        PDBGeneratorSanitizeProtein,
        PDBGeneratorNoSanitizeProtein,
        PDBBackboneGeneratorSanitizeProtein,
        PDBBackboneGeneratorNoSanitizeProtein,
        PDBGeneratorSanitizeNucleic,
        PDBGeneratorNoSanitizeNucleic,
        PDBBackboneGeneratorSanitizeNucleic,
        PDBBackboneGeneratorNoSanitizeNucleic,
    )
    from .generators.atom import AtomGenerator
    from .generators.name import ChainNameGenerator, MoleculeNameGenerator, SegmentNameGenerator
    from .generators.fingerprint import FingerprintGenerator
    from .generators.inchi import InchiKeyGenerator
    from .generators.morgan import MorganFingerprintGenerator
    from .generators.formula import MolecularFormulaGenerator
    from .generators.tdi import ThreeDiGenerator
    from .generators.lipid import LipidShorthandGenerator
    from .generators.glycan import GlycanCompositionGenerator
    from .generators.mmcif import MmCifGenerator
    
    # Optional generators - imported lazily with full module path
    SelfiesGenerator = _try_import("src_new.signatures.generators.selfies", "SelfiesGenerator")
    
    generators: list[SignatureGenerator] = []
    
    # Analytical generators (SMILES, FASTA, PDB, etc.)
    generators.append(SimpleSmilesGenerator(config))
    generators.append(SimpleSmilesGeneratorNoSanitize(config))
    generators.append(InchiKeyGenerator(config))
    generators.append(MorganFingerprintGenerator(config))
    if SelfiesGenerator:
        generators.append(SelfiesGenerator(config))
    generators.append(MolecularFormulaGenerator(config))
    
    generators.append(MapFastaGeneratorProtein(config))
    generators.append(MapFastaGeneratorNucleotide(config))
    generators.append(ResnameFastaGeneratorProtein(config))
    generators.append(ResnameFastaGeneratorNucleotide(config))
    
    generators.append(PDBGeneratorSanitizeProtein(config))
    generators.append(PDBGeneratorNoSanitizeProtein(config))
    generators.append(PDBBackboneGeneratorSanitizeProtein(config))
    generators.append(PDBBackboneGeneratorNoSanitizeProtein(config))
    generators.append(PDBGeneratorSanitizeNucleic(config))
    generators.append(PDBGeneratorNoSanitizeNucleic(config))
    generators.append(PDBBackboneGeneratorSanitizeNucleic(config))
    generators.append(PDBBackboneGeneratorNoSanitizeNucleic(config))
    
    generators.append(ThreeDiGenerator(config))
    generators.append(LipidShorthandGenerator(config))
    generators.append(GlycanCompositionGenerator(config))
    generators.append(MmCifGenerator(config))
    
    # Descriptive generators (names)
    generators.append(ChainNameGenerator(config))
    generators.append(MoleculeNameGenerator(config))
    generators.append(SegmentNameGenerator(config))
    generators.append(AtomGenerator(config))
    
    # Fallback generators
    generators.append(FingerprintGenerator(config))
    
    return generators
