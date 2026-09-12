"""
Module containing functions for working with molecular abbreviations
"""
from __future__ import annotations
import rdkit.Chem
import typing
__all__ = ['AbbreviationDefinition', 'CondenseAbbreviationSubstanceGroups', 'CondenseMolAbbreviations', 'GetDefaultAbbreviations', 'GetDefaultLinkers', 'LabelMolAbbreviations', 'ParseAbbreviations', 'ParseLinkers']
class AbbreviationDefinition(Boost.Python.instance):
    """
    Abbreviation Definition
    """
    __instance_size__: typing.ClassVar[int] = 96
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    @property
    def displayLabel(*args, **kwargs):
        """
        the label in a drawing when the bond comes from the right
        """
    @displayLabel.setter
    def displayLabel(*args, **kwargs):
        ...
    @property
    def displayLabelW(*args, **kwargs):
        """
        the label in a drawing when the bond comes from the west
        """
    @displayLabelW.setter
    def displayLabelW(*args, **kwargs):
        ...
    @property
    def label(*args, **kwargs):
        """
        the label
        """
    @label.setter
    def label(*args, **kwargs):
        ...
    @property
    def mol(*args, **kwargs):
        """
        the query molecule (should have a dummy as the first atom)
        """
    @mol.setter
    def mol(*args, **kwargs):
        ...
class _vectN5RDKit13Abbreviations22AbbreviationDefinitionE(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<RDKit::Abbreviations::AbbreviationDefinition, std::allocator<RDKit::Abbreviations::AbbreviationDefinition> > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<RDKit::Abbreviations::AbbreviationDefinition, std::allocator<RDKit::Abbreviations::AbbreviationDefinition> > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<RDKit::Abbreviations::AbbreviationDefinition, std::allocator<RDKit::Abbreviations::AbbreviationDefinition> >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __iter__(self) -> typing.Any:
        """
            C++ signature :
                boost::python::objects::iterator_range<boost::python::return_internal_reference<1ul, boost::python::default_call_policies>, __gnu_cxx::__normal_iterator<RDKit::Abbreviations::AbbreviationDefinition*, std::vector<RDKit::Abbreviations::AbbreviationDefinition, std::allocator<RDKit::Abbreviations::AbbreviationDefinition> > > > __iter__(boost::python::back_reference<std::vector<RDKit::Abbreviations::AbbreviationDefinition, std::allocator<RDKit::Abbreviations::AbbreviationDefinition> >&>)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<RDKit::Abbreviations::AbbreviationDefinition, std::allocator<RDKit::Abbreviations::AbbreviationDefinition> > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<RDKit::Abbreviations::AbbreviationDefinition, std::allocator<RDKit::Abbreviations::AbbreviationDefinition> > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<RDKit::Abbreviations::AbbreviationDefinition, std::allocator<RDKit::Abbreviations::AbbreviationDefinition> > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<RDKit::Abbreviations::AbbreviationDefinition, std::allocator<RDKit::Abbreviations::AbbreviationDefinition> > {lvalue},boost::python::api::object)
        """
def CondenseAbbreviationSubstanceGroups(mol: Mol) -> rdkit.Chem.Mol:
    """
        Finds and replaces abbreviation (i.e. "SUP") substance groups in a molecule. The result is not sanitized.
    
        C++ signature :
            RDKit::ROMol* CondenseAbbreviationSubstanceGroups(RDKit::ROMol const*)
    """
def CondenseMolAbbreviations(mol: Mol, abbrevs: typing.Any, maxCoverage: float = 0.4, sanitize: bool = True) -> rdkit.Chem.Mol:
    """
        Finds and replaces abbreviations in a molecule. The result is not sanitized.
    
        C++ signature :
            RDKit::ROMol* CondenseMolAbbreviations(RDKit::ROMol const*,boost::python::api::object [,double=0.4 [,bool=True]])
    """
def GetDefaultAbbreviations() -> ...:
    """
        returns a list of the default abbreviation definitions
    
        C++ signature :
            std::vector<RDKit::Abbreviations::AbbreviationDefinition, std::allocator<RDKit::Abbreviations::AbbreviationDefinition> > GetDefaultAbbreviations()
    """
def GetDefaultLinkers() -> ...:
    """
        returns a list of the default linker definitions
    
        C++ signature :
            std::vector<RDKit::Abbreviations::AbbreviationDefinition, std::allocator<RDKit::Abbreviations::AbbreviationDefinition> > GetDefaultLinkers()
    """
def LabelMolAbbreviations(mol: Mol, abbrevs: typing.Any, maxCoverage: float = 0.4) -> rdkit.Chem.Mol:
    """
        Finds abbreviations and adds to them to a molecule as "SUP" SubstanceGroups
    
        C++ signature :
            RDKit::ROMol* LabelMolAbbreviations(RDKit::ROMol const*,boost::python::api::object [,double=0.4])
    """
def ParseAbbreviations(text: str, removeExtraDummies: bool = False, allowConnectionToDummies: bool = False) -> ...:
    """
        returns a set of abbreviation definitions from a string
    
        C++ signature :
            std::vector<RDKit::Abbreviations::AbbreviationDefinition, std::allocator<RDKit::Abbreviations::AbbreviationDefinition> > ParseAbbreviations(std::string [,bool=False [,bool=False]])
    """
def ParseLinkers(text: str) -> ...:
    """
        returns a set of linker definitions from a string
    
        C++ signature :
            std::vector<RDKit::Abbreviations::AbbreviationDefinition, std::allocator<RDKit::Abbreviations::AbbreviationDefinition> > ParseLinkers(std::string)
    """
