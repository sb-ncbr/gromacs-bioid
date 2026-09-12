from __future__ import annotations
import rdkit.Chem
import typing
__all__ = ['PatternFingerprintTautomerTarget', 'TautomerQuery', 'TautomerQueryCanSerialize']
class TautomerQuery(Boost.Python.instance):
    """
    The Tautomer Query Class.
      Creates a query that enables structure search accounting for matching of
      Tautomeric forms
    """
    __getstate_manages_dict__: typing.ClassVar[bool] = True
    __safe_for_unpickling__: typing.ClassVar[bool] = True
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def GetModifiedAtoms(self) -> UnsignedLong_Vect:
        """
            C++ signature :
                std::vector<unsigned long, std::allocator<unsigned long> > GetModifiedAtoms(RDKit::TautomerQuery {lvalue})
        """
    def GetModifiedBonds(self) -> UnsignedLong_Vect:
        """
            C++ signature :
                std::vector<unsigned long, std::allocator<unsigned long> > GetModifiedBonds(RDKit::TautomerQuery {lvalue})
        """
    @typing.overload
    def GetSubstructMatch(self, target: Mol, useChirality: bool = False, useQueryQueryMatches: bool = False) -> typing.Any:
        """
            C++ signature :
                _object* GetSubstructMatch(RDKit::TautomerQuery,RDKit::ROMol [,bool=False [,bool=False]])
        """
    @typing.overload
    def GetSubstructMatch(self, target: Mol, params: SubstructMatchParameters) -> typing.Any:
        """
            C++ signature :
                _object* GetSubstructMatch(RDKit::TautomerQuery,RDKit::ROMol,RDKit::SubstructMatchParameters)
        """
    @typing.overload
    def GetSubstructMatches(self, target: Mol, uniquify: bool = True, useChirality: bool = False, useQueryQueryMatches: bool = False, maxMatches: int = 1000) -> typing.Any:
        """
            C++ signature :
                _object* GetSubstructMatches(RDKit::TautomerQuery,RDKit::ROMol [,bool=True [,bool=False [,bool=False [,unsigned int=1000]]]])
        """
    @typing.overload
    def GetSubstructMatches(self, target: Mol, params: SubstructMatchParameters) -> typing.Any:
        """
            C++ signature :
                _object* GetSubstructMatches(RDKit::TautomerQuery,RDKit::ROMol,RDKit::SubstructMatchParameters)
        """
    @typing.overload
    def GetSubstructMatchesWithTautomers(self, target: Mol, uniquify: bool = True, useChirality: bool = False, useQueryQueryMatches: bool = False, maxMatches: int = 1000) -> typing.Any:
        """
            C++ signature :
                _object* GetSubstructMatchesWithTautomers(RDKit::TautomerQuery,RDKit::ROMol [,bool=True [,bool=False [,bool=False [,unsigned int=1000]]]])
        """
    @typing.overload
    def GetSubstructMatchesWithTautomers(self, target: Mol, params: SubstructMatchParameters) -> typing.Any:
        """
            C++ signature :
                _object* GetSubstructMatchesWithTautomers(RDKit::TautomerQuery,RDKit::ROMol,RDKit::SubstructMatchParameters)
        """
    def GetTautomers(self) -> typing.Any:
        """
            C++ signature :
                _object* GetTautomers(RDKit::TautomerQuery)
        """
    def GetTemplateMolecule(self) -> rdkit.Chem.Mol:
        """
            C++ signature :
                RDKit::ROMol GetTemplateMolecule(RDKit::TautomerQuery {lvalue})
        """
    @typing.overload
    def IsSubstructOf(self, target: Mol, recursionPossible: bool = True, useChirality: bool = False, useQueryQueryMatches: bool = False) -> bool:
        """
            C++ signature :
                bool IsSubstructOf(RDKit::TautomerQuery,RDKit::ROMol [,bool=True [,bool=False [,bool=False]]])
        """
    @typing.overload
    def IsSubstructOf(self, target: Mol, params: SubstructMatchParameters) -> bool:
        """
            C++ signature :
                bool IsSubstructOf(RDKit::TautomerQuery,RDKit::ROMol,RDKit::SubstructMatchParameters)
        """
    def PatternFingerprintTemplate(self, fingerprintSize: int = 2048) -> ExplicitBitVect:
        """
            C++ signature :
                ExplicitBitVect* PatternFingerprintTemplate(RDKit::TautomerQuery {lvalue} [,unsigned int=2048])
        """
    def ToBinary(self) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object ToBinary(RDKit::TautomerQuery)
        """
    def __getinitargs__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getinitargs__(RDKit::TautomerQuery)
        """
    def __getstate__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getstate__(boost::python::api::object)
        """
    @typing.overload
    def __init__(self, arg1: Mol) -> typing.Any:
        """
            C++ signature :
                void* __init__(boost::python::api::object,RDKit::ROMol)
        """
    @typing.overload
    def __init__(self, arg1: Mol, arg2: str) -> typing.Any:
        """
            C++ signature :
                void* __init__(boost::python::api::object,RDKit::ROMol,std::string)
        """
    @typing.overload
    def __init__(self, pickle: str) -> None:
        """
            C++ signature :
                void __init__(_object*,std::string)
        """
    def __setstate__(self, data: tuple) -> None:
        """
            C++ signature :
                void __setstate__(boost::python::api::object,boost::python::tuple)
        """
def PatternFingerprintTautomerTarget(target: Mol, fingerprintSize: int = 2048) -> ExplicitBitVect:
    """
        C++ signature :
            ExplicitBitVect* PatternFingerprintTautomerTarget(RDKit::ROMol [,unsigned int=2048])
    """
def TautomerQueryCanSerialize() -> bool:
    """
        Returns True if the TautomerQuery is serializable (requires that the RDKit was built with boost::serialization)
    
        C++ signature :
            bool TautomerQueryCanSerialize()
    """
