from __future__ import annotations
from rdkit.Chem.rdChemicalFeatures import FreeChemicalFeature
from rdkit.Chem.rdMolChemicalFeatures import MolChemicalFeature
from rdkit.Chem.rdMolChemicalFeatures import MolChemicalFeatureFactory
__all__ = ['FreeChemicalFeature', 'MCFF_GetFeaturesForMol', 'MolChemicalFeature', 'MolChemicalFeatureFactory']
def MCFF_GetFeaturesForMol(self, mol, includeOnly = '', confId = -1):
    ...
