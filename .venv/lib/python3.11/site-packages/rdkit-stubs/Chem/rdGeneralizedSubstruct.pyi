"""
Module containing functions for generalized substructure searching
"""
from __future__ import annotations
import typing
__all__ = ['CreateExtendedQueryMol', 'ExtendedQueryMol', 'MolGetSubstructMatch', 'MolGetSubstructMatches', 'MolHasSubstructMatch', 'PatternFingerprintTarget']
class ExtendedQueryMol(Boost.Python.instance):
    """
    Extended query molecule for use in generalized substructure searching.
    """
    __instance_size__: typing.ClassVar[int] = 40
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def InitFromBinary(self, pkl: str) -> None:
        """
            C++ signature :
                void InitFromBinary(RDKit::GeneralizedSubstruct::ExtendedQueryMol {lvalue},std::string)
        """
    def InitFromJSON(self, text: str) -> None:
        """
            C++ signature :
                void InitFromJSON(RDKit::GeneralizedSubstruct::ExtendedQueryMol {lvalue},std::string)
        """
    def PatternFingerprintQuery(self, fingerprintSize: int = 2048) -> typing.Any:
        """
            C++ signature :
                std::unique_ptr<ExplicitBitVect, std::default_delete<ExplicitBitVect> > PatternFingerprintQuery(RDKit::GeneralizedSubstruct::ExtendedQueryMol {lvalue} [,unsigned int=2048])
        """
    def ToBinary(self) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object ToBinary(RDKit::GeneralizedSubstruct::ExtendedQueryMol)
        """
    def ToJSON(self) -> str:
        """
            C++ signature :
                std::string ToJSON(RDKit::GeneralizedSubstruct::ExtendedQueryMol {lvalue})
        """
    def __init__(self, text: str, isJSON: bool = False) -> None:
        """
            constructor from either a binary string (from ToBinary()) or a JSON string.
        
            C++ signature :
                void __init__(_object*,std::string [,bool=False])
        """
def CreateExtendedQueryMol(mol: Mol, doEnumeration: bool = True, doTautomers: bool = True, adjustQueryProperties: bool = False, adjustQueryParameters: AdjustQueryParameters = None) -> ExtendedQueryMol:
    """
        Creates an ExtendedQueryMol from the input molecule
        
          This takes a query molecule and, conceptually, performs the following steps to
          produce an ExtendedQueryMol:
        
            1. Enumerates features like Link Nodes and SRUs
            2. Converts everything into TautomerQueries
            3. Runs adjustQueryProperties()
        
          Each step is optional
        
    
        C++ signature :
            RDKit::GeneralizedSubstruct::ExtendedQueryMol* CreateExtendedQueryMol(RDKit::ROMol [,bool=True [,bool=True [,bool=False [,RDKit::MolOps::AdjustQueryParameters*=None]]]])
    """
def MolGetSubstructMatch(mol: Mol, query: ExtendedQueryMol, params: SubstructMatchParameters = None) -> typing.Any:
    """
        returns first match (if any) of a molecule to a generalized substructure query
    
        C++ signature :
            _object* MolGetSubstructMatch(RDKit::ROMol,RDKit::GeneralizedSubstruct::ExtendedQueryMol [,RDKit::SubstructMatchParameters*=None])
    """
def MolGetSubstructMatches(mol: Mol, query: ExtendedQueryMol, params: SubstructMatchParameters = None) -> typing.Any:
    """
        returns all matches (if any) of a molecule to a generalized substructure query
    
        C++ signature :
            _object* MolGetSubstructMatches(RDKit::ROMol,RDKit::GeneralizedSubstruct::ExtendedQueryMol [,RDKit::SubstructMatchParameters*=None])
    """
def MolHasSubstructMatch(mol: Mol, query: ExtendedQueryMol, params: SubstructMatchParameters = None) -> bool:
    """
        determines whether or not a molecule is a match to a generalized substructure query
    
        C++ signature :
            bool MolHasSubstructMatch(RDKit::ROMol,RDKit::GeneralizedSubstruct::ExtendedQueryMol [,RDKit::SubstructMatchParameters*=None])
    """
def PatternFingerprintTarget(target: Mol, fingerprintSize: int = 2048) -> typing.Any:
    """
        Creates a pattern fingerprint for a target molecule that is compatible with an extended query
    
        C++ signature :
            std::unique_ptr<ExplicitBitVect, std::default_delete<ExplicitBitVect> > PatternFingerprintTarget(RDKit::ROMol [,unsigned int=2048])
    """
