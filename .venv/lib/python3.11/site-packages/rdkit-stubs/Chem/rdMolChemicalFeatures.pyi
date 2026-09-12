"""
Module containing from chemical feature and functions to generate the
"""
from __future__ import annotations
import rdkit.Chem
import typing
__all__ = ['BuildFeatureFactory', 'BuildFeatureFactoryFromString', 'GetAtomMatch', 'MolChemicalFeature', 'MolChemicalFeatureFactory']
class MolChemicalFeature(Boost.Python.instance):
    """
    Class to represent a chemical feature.
        These chemical features may or may not have been derived from molecule object;
        i.e. it is possible to have a chemical feature that was created just from its type
        and location.
    """
    @staticmethod
    def __init__(*args, **kwargs):
        """
        Raises an exception
        This class cannot be instantiated from Python
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def ClearCache(self) -> None:
        """
            Clears the cache used to store position information.
        
            C++ signature :
                void ClearCache(RDKit::MolChemicalFeature {lvalue})
        """
    def GetActiveConformer(self) -> int:
        """
            Gets the conformer to use.
        
            C++ signature :
                int GetActiveConformer(RDKit::MolChemicalFeature {lvalue})
        """
    def GetAtomIds(self) -> typing.Any:
        """
            Get the IDs of the atoms that participate in the feature
        
            C++ signature :
                _object* GetAtomIds(RDKit::MolChemicalFeature)
        """
    def GetFactory(self) -> MolChemicalFeatureFactory:
        """
            Get the factory used to generate this feature
        
            C++ signature :
                RDKit::MolChemicalFeatureFactory const* GetFactory(RDKit::MolChemicalFeature {lvalue})
        """
    def GetFamily(self) -> str:
        """
            Get the family to which the feature belongs; donor, acceptor, etc.
        
            C++ signature :
                std::string GetFamily(RDKit::MolChemicalFeature {lvalue})
        """
    def GetId(self) -> int:
        """
            Returns the identifier of the feature
            
        
            C++ signature :
                int GetId(RDKit::MolChemicalFeature {lvalue})
        """
    def GetMol(self) -> rdkit.Chem.Mol:
        """
            Get the molecule used to derive the features
        
            C++ signature :
                RDKit::ROMol const* GetMol(RDKit::MolChemicalFeature {lvalue})
        """
    @typing.overload
    def GetPos(self, confId: int) -> Point3D:
        """
            Get the location of the chemical feature
        
            C++ signature :
                RDGeom::Point3D GetPos(RDKit::MolChemicalFeature {lvalue},int)
        """
    @typing.overload
    def GetPos(self) -> Point3D:
        """
            Get the location of the default chemical feature (first position)
        
            C++ signature :
                RDGeom::Point3D GetPos(RDKit::MolChemicalFeature {lvalue})
        """
    def GetType(self) -> str:
        """
            Get the specific type for the feature
        
            C++ signature :
                std::string GetType(RDKit::MolChemicalFeature {lvalue})
        """
    def SetActiveConformer(self, confId: int) -> None:
        """
            Sets the conformer to use (must be associated with a molecule).
        
            C++ signature :
                void SetActiveConformer(RDKit::MolChemicalFeature {lvalue},int)
        """
class MolChemicalFeatureFactory(Boost.Python.instance):
    """
    Class to featurize a molecule
    """
    @staticmethod
    def __init__(*args, **kwargs):
        """
        Raises an exception
        This class cannot be instantiated from Python
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def GetFeatureDefs(self) -> dict:
        """
            Get a dictionary with SMARTS definitions for each feature type
        
            C++ signature :
                boost::python::dict GetFeatureDefs(RDKit::MolChemicalFeatureFactory)
        """
    def GetFeatureFamilies(self) -> tuple:
        """
            Get a tuple of feature types
        
            C++ signature :
                boost::python::tuple GetFeatureFamilies(RDKit::MolChemicalFeatureFactory)
        """
    def GetMolFeature(self, mol: Mol, idx: int, includeOnly: str = '', recompute: bool = True, confId: int = -1) -> MolChemicalFeature:
        """
            returns a particular feature (by index)
        
            C++ signature :
                boost::shared_ptr<RDKit::MolChemicalFeature> GetMolFeature(RDKit::MolChemicalFeatureFactory,RDKit::ROMol,int [,std::string='' [,bool=True [,int=-1]]])
        """
    def GetNumFeatureDefs(self) -> int:
        """
            Get the number of feature definitions
        
            C++ signature :
                int GetNumFeatureDefs(RDKit::MolChemicalFeatureFactory {lvalue})
        """
    def GetNumMolFeatures(self, mol: Mol, includeOnly: str = '') -> int:
        """
            Get the number of features the molecule has
        
            C++ signature :
                int GetNumMolFeatures(RDKit::MolChemicalFeatureFactory,RDKit::ROMol [,std::string=''])
        """
def BuildFeatureFactory(fileName: str) -> MolChemicalFeatureFactory:
    """
        Construct a feature factory given a feature definition in a file
    
        C++ signature :
            RDKit::MolChemicalFeatureFactory* BuildFeatureFactory(std::string)
    """
def BuildFeatureFactoryFromString(fdefString: str) -> MolChemicalFeatureFactory:
    """
        Construct a feature factory given a feature definition block
    
        C++ signature :
            RDKit::MolChemicalFeatureFactory* BuildFeatureFactoryFromString(std::string)
    """
def GetAtomMatch(featMatch: typing.Any, maxAts: int = 1024) -> typing.Any:
    """
        Returns an empty list if any of the features passed in share an atom.
         Otherwise a list of lists of atom indices is returned.
        
    
        C++ signature :
            boost::python::api::object GetAtomMatch(boost::python::api::object [,int=1024])
    """
