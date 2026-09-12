"""
Module containing the core chemistry functionality of the RDKit
"""
from __future__ import annotations
import rdkit.Chem
import typing
__all__ = ['ALLOW_CHARGE_SEPARATION', 'ALLOW_INCOMPLETE_OCTETS', 'AddMolSubstanceGroup', 'AllProps', 'Atom', 'AtomKekulizeException', 'AtomMonomerInfo', 'AtomMonomerType', 'AtomPDBResidueInfo', 'AtomProps', 'AtomSanitizeException', 'AtomValenceException', 'Bond', 'BondDir', 'BondProps', 'BondStereo', 'BondType', 'CHI_ALLENE', 'CHI_OCTAHEDRAL', 'CHI_OTHER', 'CHI_SQUAREPLANAR', 'CHI_TETRAHEDRAL', 'CHI_TETRAHEDRAL_CCW', 'CHI_TETRAHEDRAL_CW', 'CHI_TRIGONALBIPYRAMIDAL', 'CHI_UNSPECIFIED', 'COMPOSITE_AND', 'COMPOSITE_OR', 'COMPOSITE_XOR', 'ChiralType', 'ClearMolSubstanceGroups', 'CompositeQueryType', 'ComputedProps', 'Conformer', 'CoordsAsDouble', 'CreateMolDataSubstanceGroup', 'CreateMolSubstanceGroup', 'CreateStereoGroup', 'EditableMol', 'FixedMolSizeMolBundle', 'ForwardStereoGroupIds', 'GetAtomAlias', 'GetAtomRLabel', 'GetAtomValue', 'GetDefaultPickleProperties', 'GetMolSubstanceGroupWithIdx', 'GetMolSubstanceGroups', 'GetNumPiElectrons', 'GetPeriodicTable', 'GetSupplementalSmilesLabel', 'HybridizationType', 'KEKULE_ALL', 'KekulizeException', 'Mol', 'MolBundle', 'MolBundleCanSerialize', 'MolProps', 'MolSanitizeException', 'NoConformers', 'NoProps', 'PeriodicTable', 'PrivateProps', 'PropertyPickleOptions', 'QueryAtom', 'QueryAtomData', 'QueryBond', 'RWMol', 'ResonanceFlags', 'ResonanceMolSupplier', 'ResonanceMolSupplierCallback', 'RingInfo', 'STEREO_ABSOLUTE', 'STEREO_AND', 'STEREO_OR', 'SetAtomAlias', 'SetAtomRLabel', 'SetAtomValue', 'SetDefaultPickleProperties', 'SetSupplementalSmilesLabel', 'StereoDescriptor', 'StereoGroup', 'StereoGroupType', 'StereoGroup_vect', 'StereoInfo', 'StereoSpecified', 'StereoType', 'SubstanceGroup', 'SubstanceGroupAttach', 'SubstanceGroupCState', 'SubstanceGroup_VECT', 'SubstructMatchParameters', 'UNCONSTRAINED_ANIONS', 'UNCONSTRAINED_CATIONS', 'tossit']
class Atom(Boost.Python.instance):
    """
    The class to store Atoms.
    Note that, though it is possible to create one, having an Atom on its own
    (i.e not associated with a molecule) is not particularly useful.
    """
    __instance_size__: typing.ClassVar[int] = 96
    @staticmethod
    def HasValenceViolation(arg1: Atom) -> bool:
        """
            Returns whether the atom has a valence violation or not.
            
            
        
            C++ signature :
                bool HasValenceViolation(RDKit::Atom {lvalue})
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def ClearProp(self, key: str) -> None:
        """
            Removes a particular property from an Atom (does nothing if not already set).
            
              ARGUMENTS:
                - key: the name of the property to be removed.
            
        
            C++ signature :
                void ClearProp(RDKit::Atom const*,std::string)
        """
    def DescribeQuery(self) -> str:
        """
            returns a text description of the query. Primarily intended for debugging purposes.
            
            
        
            C++ signature :
                std::string DescribeQuery(RDKit::Atom const*)
        """
    def GetAtomMapNum(self) -> int:
        """
            Gets the atoms map number, returns 0 if not set
        
            C++ signature :
                int GetAtomMapNum(RDKit::Atom {lvalue})
        """
    def GetAtomicNum(self) -> int:
        """
            Returns the atomic number.
        
            C++ signature :
                int GetAtomicNum(RDKit::Atom {lvalue})
        """
    def GetBonds(self) -> tuple:
        """
            Returns a read-only sequence of the atom's bonds
            
        
            C++ signature :
                boost::python::tuple GetBonds(RDKit::Atom*)
        """
    def GetBoolProp(self, key: str) -> bool:
        """
            Returns the value of the property.
            
              ARGUMENTS:
                - key: the name of the property to return (a bool).
            
              RETURNS: a bool
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                bool GetBoolProp(RDKit::Atom const*,std::string)
        """
    def GetChiralTag(self) -> ChiralType:
        """
            C++ signature :
                RDKit::Atom::ChiralType GetChiralTag(RDKit::Atom {lvalue})
        """
    def GetDegree(self) -> int:
        """
            Returns the degree of the atom in the molecule.
            
              The degree of an atom is defined to be its number of
              directly-bonded neighbors.
              The degree is independent of bond orders, but is dependent
                on whether or not Hs are explicit in the graph.
            
        
            C++ signature :
                unsigned int GetDegree(RDKit::Atom {lvalue})
        """
    def GetDoubleProp(self, key: str) -> float:
        """
            Returns the value of the property.
            
              ARGUMENTS:
                - key: the name of the property to return (a double).
            
              RETURNS: a double
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                double GetDoubleProp(RDKit::Atom const*,std::string)
        """
    def GetExplicitBitVectProp(self, key: str) -> ExplicitBitVect:
        """
            Returns the value of the property.
            
              ARGUMENTS:
                - key: the name of the property to return (a ExplicitBitVect).
            
              RETURNS: an ExplicitBitVect 
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                ExplicitBitVect GetExplicitBitVectProp(RDKit::Atom const*,std::string)
        """
    def GetExplicitValence(self) -> int:
        """
            Returns the explicit valence of the atom.
            
        
            C++ signature :
                int GetExplicitValence(RDKit::Atom {lvalue})
        """
    def GetFormalCharge(self) -> int:
        """
            C++ signature :
                int GetFormalCharge(RDKit::Atom {lvalue})
        """
    def GetHybridization(self) -> HybridizationType:
        """
            Returns the atom's hybridization.
            
        
            C++ signature :
                RDKit::Atom::HybridizationType GetHybridization(RDKit::Atom {lvalue})
        """
    def GetIdx(self) -> int:
        """
            Returns the atom's index (ordering in the molecule)
            
        
            C++ signature :
                unsigned int GetIdx(RDKit::Atom {lvalue})
        """
    def GetImplicitValence(self) -> int:
        """
            Returns the number of implicit Hs on the atom.
            
        
            C++ signature :
                int GetImplicitValence(RDKit::Atom {lvalue})
        """
    def GetIntProp(self, key: str) -> int:
        """
            Returns the value of the property.
            
              ARGUMENTS:
                - key: the name of the property to return (an int).
            
              RETURNS: an int
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                int GetIntProp(RDKit::Atom const*,std::string)
        """
    def GetIsAromatic(self) -> bool:
        """
            C++ signature :
                bool GetIsAromatic(RDKit::Atom {lvalue})
        """
    def GetIsotope(self) -> int:
        """
            C++ signature :
                unsigned int GetIsotope(RDKit::Atom {lvalue})
        """
    def GetMass(self) -> float:
        """
            C++ signature :
                double GetMass(RDKit::Atom {lvalue})
        """
    def GetMonomerInfo(self) -> AtomMonomerInfo:
        """
            Returns the atom's MonomerInfo object, if there is one.
            
            
        
            C++ signature :
                RDKit::AtomMonomerInfo* GetMonomerInfo(RDKit::Atom*)
        """
    def GetNeighbors(self) -> tuple:
        """
            Returns a read-only sequence of the atom's neighbors
            
        
            C++ signature :
                boost::python::tuple GetNeighbors(RDKit::Atom*)
        """
    def GetNoImplicit(self) -> bool:
        """
            Returns whether or not the atom is *allowed* to have implicit Hs.
            
        
            C++ signature :
                bool GetNoImplicit(RDKit::Atom {lvalue})
        """
    def GetNumExplicitHs(self) -> int:
        """
            C++ signature :
                unsigned int GetNumExplicitHs(RDKit::Atom {lvalue})
        """
    def GetNumImplicitHs(self) -> int:
        """
            Returns the total number of implicit Hs on the atom.
            
        
            C++ signature :
                unsigned int GetNumImplicitHs(RDKit::Atom {lvalue})
        """
    def GetNumRadicalElectrons(self) -> int:
        """
            C++ signature :
                unsigned int GetNumRadicalElectrons(RDKit::Atom {lvalue})
        """
    def GetOwningMol(self) -> Mol:
        """
            Returns the Mol that owns this atom.
            
        
            C++ signature :
                RDKit::ROMol {lvalue} GetOwningMol(RDKit::Atom {lvalue})
        """
    def GetPDBResidueInfo(self) -> AtomPDBResidueInfo:
        """
            Returns the atom's MonomerInfo object, if there is one.
            
            
        
            C++ signature :
                RDKit::AtomPDBResidueInfo* GetPDBResidueInfo(RDKit::Atom*)
        """
    def GetProp(self, key: str, autoConvert: bool = False) -> typing.Any:
        """
            Returns the value of the property.
            
              ARGUMENTS:
                - key: the name of the property to return (a string).
            
                - autoConvert: if True attempt to convert the property into a python object
            
              RETURNS: a string
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                boost::python::api::object GetProp(RDKit::Atom const*,std::string [,bool=False])
        """
    def GetPropNames(self, includePrivate: bool = False, includeComputed: bool = False) -> _vectSs:
        """
            Returns a list of the properties set on the Atom.
            
            
        
            C++ signature :
                std::vector<std::string, std::allocator<std::string> > GetPropNames(RDKit::Atom {lvalue} [,bool=False [,bool=False]])
        """
    def GetPropsAsDict(self, includePrivate: bool = True, includeComputed: bool = True, autoConvertStrings: bool = True) -> dict:
        """
            Returns a dictionary of the properties set on the Atom.
             n.b. some properties cannot be converted to python types.
            
        
            C++ signature :
                boost::python::dict GetPropsAsDict(RDKit::Atom [,bool=True [,bool=True [,bool=True]]])
        """
    def GetQueryType(self) -> str:
        """
            C++ signature :
                std::string GetQueryType(RDKit::Atom {lvalue})
        """
    def GetSmarts(self, doKekule: bool = False, allHsExplicit: bool = False, isomericSmiles: bool = True) -> str:
        """
            returns the SMARTS (or SMILES) string for an Atom
            
            
        
            C++ signature :
                std::string GetSmarts(RDKit::Atom const* [,bool=False [,bool=False [,bool=True]]])
        """
    def GetSymbol(self) -> str:
        """
            Returns the atomic symbol (a string)
            
        
            C++ signature :
                std::string GetSymbol(RDKit::Atom {lvalue})
        """
    def GetTotalDegree(self) -> int:
        """
            Returns the degree of the atom in the molecule including Hs.
            
              The degree of an atom is defined to be its number of
              directly-bonded neighbors.
              The degree is independent of bond orders.
            
        
            C++ signature :
                unsigned int GetTotalDegree(RDKit::Atom {lvalue})
        """
    def GetTotalNumHs(self, includeNeighbors: bool = False) -> int:
        """
            Returns the total number of Hs (explicit and implicit) on the atom.
            
              ARGUMENTS:
            
                - includeNeighbors: (optional) toggles inclusion of neighboring H atoms in the sum.
                  Defaults to 0.
            
        
            C++ signature :
                unsigned int GetTotalNumHs(RDKit::Atom {lvalue} [,bool=False])
        """
    def GetTotalValence(self) -> int:
        """
            Returns the total valence (explicit + implicit) of the atom.
            
            
        
            C++ signature :
                unsigned int GetTotalValence(RDKit::Atom {lvalue})
        """
    def GetUnsignedProp(self, key: str) -> int:
        """
            Returns the value of the property.
            
              ARGUMENTS:
                - key: the name of the property to return (an unsigned integer).
            
              RETURNS: an integer (Python has no unsigned type)
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                unsigned int GetUnsignedProp(RDKit::Atom const*,std::string)
        """
    def HasOwningMol(self) -> bool:
        """
            Returns whether or not this instance belongs to a molecule.
            
        
            C++ signature :
                bool HasOwningMol(RDKit::Atom {lvalue})
        """
    def HasProp(self, key: str) -> int:
        """
            Queries a Atom to see if a particular property has been assigned.
            
              ARGUMENTS:
                - key: the name of the property to check for (a string).
            
        
            C++ signature :
                int HasProp(RDKit::Atom const*,std::string)
        """
    def HasQuery(self) -> bool:
        """
            Returns whether or not the atom has an associated query
            
            
        
            C++ signature :
                bool HasQuery(RDKit::Atom {lvalue})
        """
    def InvertChirality(self) -> bool:
        """
            C++ signature :
                bool InvertChirality(RDKit::Atom {lvalue})
        """
    def IsInRing(self) -> bool:
        """
            Returns whether or not the atom is in a ring
            
            
        
            C++ signature :
                bool IsInRing(RDKit::Atom const*)
        """
    def IsInRingSize(self, size: int) -> bool:
        """
            Returns whether or not the atom is in a ring of a particular size.
            
              ARGUMENTS:
                - size: the ring size to look for
            
        
            C++ signature :
                bool IsInRingSize(RDKit::Atom const*,int)
        """
    def Match(self, what: Atom) -> bool:
        """
            Returns whether or not this atom matches another Atom.
            
              Each Atom (or query Atom) has a query function which is
              used for this type of matching.
            
              ARGUMENTS:
                - other: the other Atom to which to compare
            
        
            C++ signature :
                bool Match(RDKit::Atom {lvalue},RDKit::Atom const*)
        """
    def NeedsUpdatePropertyCache(self) -> bool:
        """
            Returns true or false depending on whether implicit and explicit valence of the molecule have already been calculated.
            
            
        
            C++ signature :
                bool NeedsUpdatePropertyCache(RDKit::Atom {lvalue})
        """
    def SetAtomMapNum(self, mapno: int, strict: bool = False) -> None:
        """
            Sets the atoms map number, a value of 0 clears the atom map
        
            C++ signature :
                void SetAtomMapNum(RDKit::Atom {lvalue},int [,bool=False])
        """
    def SetAtomicNum(self, newNum: int) -> None:
        """
            Sets the atomic number, takes an integer value as an argument
        
            C++ signature :
                void SetAtomicNum(RDKit::Atom {lvalue},int)
        """
    def SetBoolProp(self, key: str, val: bool) -> None:
        """
            Sets an atomic property
            
              ARGUMENTS:
                - key: the name of the property to be set (a bool).
                - value: the property value (a bool).
            
            
        
            C++ signature :
                void SetBoolProp(RDKit::Atom const*,std::string,bool)
        """
    def SetChiralTag(self, what: ChiralType) -> None:
        """
            C++ signature :
                void SetChiralTag(RDKit::Atom {lvalue},RDKit::Atom::ChiralType)
        """
    def SetDoubleProp(self, key: str, val: float) -> None:
        """
            Sets an atomic property
            
              ARGUMENTS:
                - key: the name of the property to be set (a double).
                - value: the property value (a double).
            
            
        
            C++ signature :
                void SetDoubleProp(RDKit::Atom const*,std::string,double)
        """
    def SetExplicitBitVectProp(self, key: str, val: ExplicitBitVect) -> None:
        """
            Sets an atomic property
            
              ARGUMENTS:
                - key: the name of the property to be set (an ExplicitBitVect).
                - value: the property value (an ExplicitBitVect).
            
            
        
            C++ signature :
                void SetExplicitBitVectProp(RDKit::Atom const*,std::string,ExplicitBitVect)
        """
    def SetFormalCharge(self, what: int) -> None:
        """
            C++ signature :
                void SetFormalCharge(RDKit::Atom {lvalue},int)
        """
    def SetHybridization(self, what: HybridizationType) -> None:
        """
            Sets the hybridization of the atom.
              The argument should be a HybridizationType
            
        
            C++ signature :
                void SetHybridization(RDKit::Atom {lvalue},RDKit::Atom::HybridizationType)
        """
    def SetIntProp(self, key: str, val: int) -> None:
        """
            Sets an atomic property
            
              ARGUMENTS:
                - key: the name of the property to be set (a int).
                - value: the property value (a int).
            
            
        
            C++ signature :
                void SetIntProp(RDKit::Atom const*,std::string,int)
        """
    def SetIsAromatic(self, what: bool) -> None:
        """
            C++ signature :
                void SetIsAromatic(RDKit::Atom {lvalue},bool)
        """
    def SetIsotope(self, what: int) -> None:
        """
            C++ signature :
                void SetIsotope(RDKit::Atom {lvalue},unsigned int)
        """
    def SetMonomerInfo(self, info: AtomMonomerInfo) -> None:
        """
            Sets the atom's MonomerInfo object.
            
            
        
            C++ signature :
                void SetMonomerInfo(RDKit::Atom*,RDKit::AtomMonomerInfo const*)
        """
    def SetNoImplicit(self, what: bool) -> None:
        """
            Sets a marker on the atom that *disallows* implicit Hs.
              This holds even if the atom would otherwise have implicit Hs added.
            
        
            C++ signature :
                void SetNoImplicit(RDKit::Atom {lvalue},bool)
        """
    def SetNumExplicitHs(self, what: int) -> None:
        """
            C++ signature :
                void SetNumExplicitHs(RDKit::Atom {lvalue},unsigned int)
        """
    def SetNumRadicalElectrons(self, num: int) -> None:
        """
            C++ signature :
                void SetNumRadicalElectrons(RDKit::Atom {lvalue},unsigned int)
        """
    def SetPDBResidueInfo(self, info: AtomMonomerInfo) -> None:
        """
            Sets the atom's MonomerInfo object.
            
            
        
            C++ signature :
                void SetPDBResidueInfo(RDKit::Atom*,RDKit::AtomMonomerInfo const*)
        """
    def SetProp(self, key: str, val: str) -> None:
        """
            Sets an atomic property
            
              ARGUMENTS:
                - key: the name of the property to be set (a string).
                - value: the property value (a string).
            
            
        
            C++ signature :
                void SetProp(RDKit::Atom const*,std::string,std::string)
        """
    def SetUnsignedProp(self, key: str, val: int) -> None:
        """
            Sets an atomic property
            
              ARGUMENTS:
                - key: the name of the property to be set (an unsigned integer).
                - value: the property value (a int >= 0).
            
            
        
            C++ signature :
                void SetUnsignedProp(RDKit::Atom const*,std::string,unsigned int)
        """
    def UpdatePropertyCache(self, strict: bool = True) -> None:
        """
            Regenerates computed properties like implicit valence and ring information.
            
            
        
            C++ signature :
                void UpdatePropertyCache(RDKit::Atom {lvalue} [,bool=True])
        """
    def __copy__(self) -> Atom:
        """
            Create a copy of the atom
        
            C++ signature :
                RDKit::Atom* __copy__(RDKit::Atom {lvalue})
        """
    @typing.overload
    def __init__(self, what: str) -> None:
        """
            C++ signature :
                void __init__(_object*,std::string)
        """
    @typing.overload
    def __init__(self, other: Atom) -> None:
        """
            C++ signature :
                void __init__(_object*,RDKit::Atom)
        """
    @typing.overload
    def __init__(self, num: int) -> None:
        """
            Constructor, takes the atomic number
        
            C++ signature :
                void __init__(_object*,unsigned int)
        """
class AtomKekulizeException(AtomSanitizeException):
    pass
class AtomMonomerInfo(Boost.Python.instance):
    """
    The class to store monomer information attached to Atoms
    """
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def GetMonomerType(self) -> AtomMonomerType:
        """
            C++ signature :
                RDKit::AtomMonomerInfo::AtomMonomerType GetMonomerType(RDKit::AtomMonomerInfo {lvalue})
        """
    def GetName(self) -> str:
        """
            C++ signature :
                std::string GetName(RDKit::AtomMonomerInfo {lvalue})
        """
    def SetMonomerType(self, typ: AtomMonomerType) -> None:
        """
            C++ signature :
                void SetMonomerType(RDKit::AtomMonomerInfo {lvalue},RDKit::AtomMonomerInfo::AtomMonomerType)
        """
    def SetName(self, nm: str) -> None:
        """
            C++ signature :
                void SetName(RDKit::AtomMonomerInfo {lvalue},std::string)
        """
    @typing.overload
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    @typing.overload
    def __init__(self, type: AtomMonomerType, name: str = '') -> None:
        """
            C++ signature :
                void __init__(_object*,RDKit::AtomMonomerInfo::AtomMonomerType [,std::string=''])
        """
class AtomMonomerType(Boost.Python.enum):
    OTHER: typing.ClassVar[AtomMonomerType]  # value = rdkit.Chem.rdchem.AtomMonomerType.OTHER
    PDBRESIDUE: typing.ClassVar[AtomMonomerType]  # value = rdkit.Chem.rdchem.AtomMonomerType.PDBRESIDUE
    UNKNOWN: typing.ClassVar[AtomMonomerType]  # value = rdkit.Chem.rdchem.AtomMonomerType.UNKNOWN
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'UNKNOWN': rdkit.Chem.rdchem.AtomMonomerType.UNKNOWN, 'PDBRESIDUE': rdkit.Chem.rdchem.AtomMonomerType.PDBRESIDUE, 'OTHER': rdkit.Chem.rdchem.AtomMonomerType.OTHER}
    values: typing.ClassVar[dict]  # value = {0: rdkit.Chem.rdchem.AtomMonomerType.UNKNOWN, 1: rdkit.Chem.rdchem.AtomMonomerType.PDBRESIDUE, 2: rdkit.Chem.rdchem.AtomMonomerType.OTHER}
class AtomPDBResidueInfo(AtomMonomerInfo):
    """
    The class to store PDB residue information attached to Atoms
    """
    __instance_size__: typing.ClassVar[int] = 128
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def GetAltLoc(self) -> str:
        """
            C++ signature :
                std::string GetAltLoc(RDKit::AtomPDBResidueInfo {lvalue})
        """
    def GetChainId(self) -> str:
        """
            C++ signature :
                std::string GetChainId(RDKit::AtomPDBResidueInfo {lvalue})
        """
    def GetInsertionCode(self) -> str:
        """
            C++ signature :
                std::string GetInsertionCode(RDKit::AtomPDBResidueInfo {lvalue})
        """
    def GetIsHeteroAtom(self) -> bool:
        """
            C++ signature :
                bool GetIsHeteroAtom(RDKit::AtomPDBResidueInfo {lvalue})
        """
    def GetOccupancy(self) -> float:
        """
            C++ signature :
                double GetOccupancy(RDKit::AtomPDBResidueInfo {lvalue})
        """
    def GetResidueName(self) -> str:
        """
            C++ signature :
                std::string GetResidueName(RDKit::AtomPDBResidueInfo {lvalue})
        """
    def GetResidueNumber(self) -> int:
        """
            C++ signature :
                int GetResidueNumber(RDKit::AtomPDBResidueInfo {lvalue})
        """
    def GetSecondaryStructure(self) -> int:
        """
            C++ signature :
                unsigned int GetSecondaryStructure(RDKit::AtomPDBResidueInfo {lvalue})
        """
    def GetSegmentNumber(self) -> int:
        """
            C++ signature :
                unsigned int GetSegmentNumber(RDKit::AtomPDBResidueInfo {lvalue})
        """
    def GetSerialNumber(self) -> int:
        """
            C++ signature :
                int GetSerialNumber(RDKit::AtomPDBResidueInfo {lvalue})
        """
    def GetTempFactor(self) -> float:
        """
            C++ signature :
                double GetTempFactor(RDKit::AtomPDBResidueInfo {lvalue})
        """
    def SetAltLoc(self, val: str) -> None:
        """
            C++ signature :
                void SetAltLoc(RDKit::AtomPDBResidueInfo {lvalue},std::string)
        """
    def SetChainId(self, val: str) -> None:
        """
            C++ signature :
                void SetChainId(RDKit::AtomPDBResidueInfo {lvalue},std::string)
        """
    def SetInsertionCode(self, val: str) -> None:
        """
            C++ signature :
                void SetInsertionCode(RDKit::AtomPDBResidueInfo {lvalue},std::string)
        """
    def SetIsHeteroAtom(self, val: bool) -> None:
        """
            C++ signature :
                void SetIsHeteroAtom(RDKit::AtomPDBResidueInfo {lvalue},bool)
        """
    def SetOccupancy(self, val: float) -> None:
        """
            C++ signature :
                void SetOccupancy(RDKit::AtomPDBResidueInfo {lvalue},double)
        """
    def SetResidueName(self, val: str) -> None:
        """
            C++ signature :
                void SetResidueName(RDKit::AtomPDBResidueInfo {lvalue},std::string)
        """
    def SetResidueNumber(self, val: int) -> None:
        """
            C++ signature :
                void SetResidueNumber(RDKit::AtomPDBResidueInfo {lvalue},int)
        """
    def SetSecondaryStructure(self, val: int) -> None:
        """
            C++ signature :
                void SetSecondaryStructure(RDKit::AtomPDBResidueInfo {lvalue},unsigned int)
        """
    def SetSegmentNumber(self, val: int) -> None:
        """
            C++ signature :
                void SetSegmentNumber(RDKit::AtomPDBResidueInfo {lvalue},unsigned int)
        """
    def SetSerialNumber(self, val: int) -> None:
        """
            C++ signature :
                void SetSerialNumber(RDKit::AtomPDBResidueInfo {lvalue},int)
        """
    def SetTempFactor(self, val: float) -> None:
        """
            C++ signature :
                void SetTempFactor(RDKit::AtomPDBResidueInfo {lvalue},double)
        """
    @typing.overload
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    @typing.overload
    def __init__(self, atomName: str, serialNumber: int = 1, altLoc: str = '', residueName: str = '', residueNumber: int = 0, chainId: str = '', insertionCode: str = '', occupancy: float = 1.0, tempFactor: float = 0.0, isHeteroAtom: bool = False, secondaryStructure: int = 0, segmentNumber: int = 0) -> None:
        """
            C++ signature :
                void __init__(_object*,std::string [,int=1 [,std::string='' [,std::string='' [,int=0 [,std::string='' [,std::string='' [,double=1.0 [,double=0.0 [,bool=False [,unsigned int=0 [,unsigned int=0]]]]]]]]]]])
        """
class AtomSanitizeException(MolSanitizeException):
    pass
class AtomValenceException(AtomSanitizeException):
    pass
class Bond(Boost.Python.instance):
    """
    The class to store Bonds.
    Note: unlike Atoms, is it currently impossible to construct Bonds from
    Python.
    """
    @staticmethod
    def GetSmarts(bond: Bond, allBondsExplicit: bool = False) -> str:
        """
            returns the SMARTS (or SMILES) string for a Bond
        
            C++ signature :
                std::string GetSmarts(RDKit::Bond const* [,bool=False])
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
    def ClearProp(self, key: str) -> None:
        """
            Removes a particular property from an Bond (does nothing if not already set).
            
              ARGUMENTS:
                - key: the name of the property to be removed.
            
        
            C++ signature :
                void ClearProp(RDKit::Bond const*,char const*)
        """
    def DescribeQuery(self) -> str:
        """
            returns a text description of the query. Primarily intended for debugging purposes.
            
            
        
            C++ signature :
                std::string DescribeQuery(RDKit::Bond const*)
        """
    def GetBeginAtom(self) -> Atom:
        """
            Returns the bond's first atom.
            
        
            C++ signature :
                RDKit::Atom* GetBeginAtom(RDKit::Bond {lvalue})
        """
    def GetBeginAtomIdx(self) -> int:
        """
            Returns the index of the bond's first atom.
            
        
            C++ signature :
                unsigned int GetBeginAtomIdx(RDKit::Bond {lvalue})
        """
    def GetBondDir(self) -> BondDir:
        """
            Returns the type of the bond as a BondDir
            
        
            C++ signature :
                RDKit::Bond::BondDir GetBondDir(RDKit::Bond {lvalue})
        """
    def GetBondType(self) -> BondType:
        """
            Returns the type of the bond as a BondType
            
        
            C++ signature :
                RDKit::Bond::BondType GetBondType(RDKit::Bond {lvalue})
        """
    def GetBondTypeAsDouble(self) -> float:
        """
            Returns the type of the bond as a double (i.e. 1.0 for SINGLE, 1.5 for AROMATIC, 2.0 for DOUBLE)
            
        
            C++ signature :
                double GetBondTypeAsDouble(RDKit::Bond {lvalue})
        """
    def GetBoolProp(self, key: str) -> bool:
        """
            Returns the value of the property.
            
              ARGUMENTS:
                - key: the name of the property to return (a boolean).
            
              RETURNS: a boolean
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                bool GetBoolProp(RDKit::Bond const*,std::string)
        """
    def GetDoubleProp(self, key: str) -> float:
        """
            Returns the value of the property.
            
              ARGUMENTS:
                - key: the name of the property to return (a double).
            
              RETURNS: a double
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                double GetDoubleProp(RDKit::Bond const*,std::string)
        """
    def GetEndAtom(self) -> Atom:
        """
            Returns the bond's second atom.
            
        
            C++ signature :
                RDKit::Atom* GetEndAtom(RDKit::Bond {lvalue})
        """
    def GetEndAtomIdx(self) -> int:
        """
            Returns the index of the bond's first atom.
            
        
            C++ signature :
                unsigned int GetEndAtomIdx(RDKit::Bond {lvalue})
        """
    def GetIdx(self) -> int:
        """
            Returns the bond's index (ordering in the molecule)
            
        
            C++ signature :
                unsigned int GetIdx(RDKit::Bond {lvalue})
        """
    def GetIntProp(self, key: str) -> int:
        """
            Returns the value of the property.
            
              ARGUMENTS:
                - key: the name of the property to return (an int).
            
              RETURNS: an int
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                int GetIntProp(RDKit::Bond const*,std::string)
        """
    def GetIsAromatic(self) -> bool:
        """
            C++ signature :
                bool GetIsAromatic(RDKit::Bond {lvalue})
        """
    def GetIsConjugated(self) -> bool:
        """
            Returns whether or not the bond is considered to be conjugated.
        
            C++ signature :
                bool GetIsConjugated(RDKit::Bond {lvalue})
        """
    def GetOtherAtom(self, what: Atom) -> Atom:
        """
            Given one of the bond's atoms, returns the other one.
            
        
            C++ signature :
                RDKit::Atom* GetOtherAtom(RDKit::Bond {lvalue},RDKit::Atom const*)
        """
    def GetOtherAtomIdx(self, thisIdx: int) -> int:
        """
            Given the index of one of the bond's atoms, returns the
            index of the other.
            
        
            C++ signature :
                unsigned int GetOtherAtomIdx(RDKit::Bond {lvalue},unsigned int)
        """
    def GetOwningMol(self) -> Mol:
        """
            Returns the Mol that owns this bond.
            
        
            C++ signature :
                RDKit::ROMol {lvalue} GetOwningMol(RDKit::Bond {lvalue})
        """
    def GetProp(self, key: str, autoConvert: bool = False) -> typing.Any:
        """
            Returns the value of the property.
            
              ARGUMENTS:
                - key: the name of the property to return (a string).
            
                - autoConvert: if True attempt to convert the property into a python object
            
              RETURNS: a string
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                boost::python::api::object GetProp(RDKit::Bond const*,std::string [,bool=False])
        """
    def GetPropNames(self, includePrivate: bool = False, includeComputed: bool = False) -> _vectSs:
        """
            Returns a list of the properties set on the Bond.
            
            
        
            C++ signature :
                std::vector<std::string, std::allocator<std::string> > GetPropNames(RDKit::Bond {lvalue} [,bool=False [,bool=False]])
        """
    def GetPropsAsDict(self, includePrivate: bool = True, includeComputed: bool = True, autoConvertStrings: bool = True) -> dict:
        """
            Returns a dictionary of the properties set on the Bond.
             n.b. some properties cannot be converted to python types.
            
        
            C++ signature :
                boost::python::dict GetPropsAsDict(RDKit::Bond [,bool=True [,bool=True [,bool=True]]])
        """
    def GetStereo(self) -> BondStereo:
        """
            Returns the stereo configuration of the bond as a BondStereo
            
        
            C++ signature :
                RDKit::Bond::BondStereo GetStereo(RDKit::Bond {lvalue})
        """
    def GetStereoAtoms(self) -> typing.Sequence[int]:
        """
            Returns the indices of the atoms setting this bond's stereochemistry.
            
        
            C++ signature :
                std::vector<int, std::allocator<int> > GetStereoAtoms(RDKit::Bond const*)
        """
    def GetUnsignedProp(self, key: str) -> int:
        """
            Returns the value of the property.
            
              ARGUMENTS:
                - key: the name of the property to return (an unsigned integer).
            
              RETURNS: an int (Python has no unsigned type)
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                unsigned int GetUnsignedProp(RDKit::Bond const*,std::string)
        """
    def GetValenceContrib(self, at: Atom) -> float:
        """
            Returns the contribution of the bond to the valence of an Atom.
            
              ARGUMENTS:
            
                - atom: the Atom to consider.
            
        
            C++ signature :
                double GetValenceContrib(RDKit::Bond {lvalue},RDKit::Atom const*)
        """
    def HasOwningMol(self) -> bool:
        """
            Returns whether or not this instance belongs to a molecule.
            
        
            C++ signature :
                bool HasOwningMol(RDKit::Bond {lvalue})
        """
    def HasProp(self, key: str) -> int:
        """
            Queries a Bond to see if a particular property has been assigned.
            
              ARGUMENTS:
                - key: the name of the property to check for (a string).
            
        
            C++ signature :
                int HasProp(RDKit::Bond const*,char const*)
        """
    def HasQuery(self) -> bool:
        """
            Returns whether or not the bond has an associated query
            
            
        
            C++ signature :
                bool HasQuery(RDKit::Bond {lvalue})
        """
    def IsInRing(self) -> bool:
        """
            Returns whether or not the bond is in a ring of any size.
            
            
        
            C++ signature :
                bool IsInRing(RDKit::Bond const*)
        """
    def IsInRingSize(self, size: int) -> bool:
        """
            Returns whether or not the bond is in a ring of a particular size.
            
              ARGUMENTS:
                - size: the ring size to look for
            
        
            C++ signature :
                bool IsInRingSize(RDKit::Bond const*,int)
        """
    def Match(self, what: Bond) -> bool:
        """
            Returns whether or not this bond matches another Bond.
            
              Each Bond (or query Bond) has a query function which is
              used for this type of matching.
            
              ARGUMENTS:
                - other: the other Bond to which to compare
            
        
            C++ signature :
                bool Match(RDKit::Bond {lvalue},RDKit::Bond const*)
        """
    def SetBondDir(self, what: BondDir) -> None:
        """
            Set the type of the bond as a BondDir
            
        
            C++ signature :
                void SetBondDir(RDKit::Bond {lvalue},RDKit::Bond::BondDir)
        """
    def SetBondType(self, bT: BondType) -> None:
        """
            Set the type of the bond as a BondType
            
        
            C++ signature :
                void SetBondType(RDKit::Bond {lvalue},RDKit::Bond::BondType)
        """
    def SetBoolProp(self, key: str, val: bool) -> None:
        """
            Sets a bond property
            
              ARGUMENTS:
                - key: the name of the property to be set (a string).
                - value: the property value (a boolean).
            
            
        
            C++ signature :
                void SetBoolProp(RDKit::Bond const*,char const*,bool)
        """
    def SetDoubleProp(self, key: str, val: float) -> None:
        """
            Sets a bond property
            
              ARGUMENTS:
                - key: the name of the property to be set (a string).
                - value: the property value (a double).
            
            
        
            C++ signature :
                void SetDoubleProp(RDKit::Bond const*,char const*,double)
        """
    def SetIntProp(self, key: str, val: int) -> None:
        """
            Sets a bond property
            
              ARGUMENTS:
                - key: the name of the property to be set (a string).
                - value: the property value (an int).
            
            
        
            C++ signature :
                void SetIntProp(RDKit::Bond const*,char const*,int)
        """
    def SetIsAromatic(self, what: bool) -> None:
        """
            C++ signature :
                void SetIsAromatic(RDKit::Bond {lvalue},bool)
        """
    def SetIsConjugated(self, what: bool) -> None:
        """
            C++ signature :
                void SetIsConjugated(RDKit::Bond {lvalue},bool)
        """
    def SetProp(self, key: str, val: str) -> None:
        """
            Sets a bond property
            
              ARGUMENTS:
                - key: the name of the property to be set (a string).
                - value: the property value (a string).
            
            
        
            C++ signature :
                void SetProp(RDKit::Bond const*,char const*,std::string)
        """
    def SetStereo(self, what: BondStereo) -> None:
        """
            Set the stereo configuration of the bond as a BondStereo
            
        
            C++ signature :
                void SetStereo(RDKit::Bond {lvalue},RDKit::Bond::BondStereo)
        """
    def SetStereoAtoms(self, bgnIdx: int, endIdx: int) -> None:
        """
            Set the indices of the atoms setting this bond's stereochemistry.
            
        
            C++ signature :
                void SetStereoAtoms(RDKit::Bond {lvalue},unsigned int,unsigned int)
        """
    def SetUnsignedProp(self, key: str, val: int) -> None:
        """
            Sets a bond property
            
              ARGUMENTS:
                - key: the name of the property to be set (a string).
                - value: the property value (an int >= 0).
            
            
        
            C++ signature :
                void SetUnsignedProp(RDKit::Bond const*,char const*,unsigned int)
        """
class BondDir(Boost.Python.enum):
    BEGINDASH: typing.ClassVar[BondDir]  # value = rdkit.Chem.rdchem.BondDir.BEGINDASH
    BEGINWEDGE: typing.ClassVar[BondDir]  # value = rdkit.Chem.rdchem.BondDir.BEGINWEDGE
    EITHERDOUBLE: typing.ClassVar[BondDir]  # value = rdkit.Chem.rdchem.BondDir.EITHERDOUBLE
    ENDDOWNRIGHT: typing.ClassVar[BondDir]  # value = rdkit.Chem.rdchem.BondDir.ENDDOWNRIGHT
    ENDUPRIGHT: typing.ClassVar[BondDir]  # value = rdkit.Chem.rdchem.BondDir.ENDUPRIGHT
    NONE: typing.ClassVar[BondDir]  # value = rdkit.Chem.rdchem.BondDir.NONE
    UNKNOWN: typing.ClassVar[BondDir]  # value = rdkit.Chem.rdchem.BondDir.UNKNOWN
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'NONE': rdkit.Chem.rdchem.BondDir.NONE, 'BEGINWEDGE': rdkit.Chem.rdchem.BondDir.BEGINWEDGE, 'BEGINDASH': rdkit.Chem.rdchem.BondDir.BEGINDASH, 'ENDDOWNRIGHT': rdkit.Chem.rdchem.BondDir.ENDDOWNRIGHT, 'ENDUPRIGHT': rdkit.Chem.rdchem.BondDir.ENDUPRIGHT, 'EITHERDOUBLE': rdkit.Chem.rdchem.BondDir.EITHERDOUBLE, 'UNKNOWN': rdkit.Chem.rdchem.BondDir.UNKNOWN}
    values: typing.ClassVar[dict]  # value = {0: rdkit.Chem.rdchem.BondDir.NONE, 1: rdkit.Chem.rdchem.BondDir.BEGINWEDGE, 2: rdkit.Chem.rdchem.BondDir.BEGINDASH, 3: rdkit.Chem.rdchem.BondDir.ENDDOWNRIGHT, 4: rdkit.Chem.rdchem.BondDir.ENDUPRIGHT, 5: rdkit.Chem.rdchem.BondDir.EITHERDOUBLE, 6: rdkit.Chem.rdchem.BondDir.UNKNOWN}
class BondStereo(Boost.Python.enum):
    STEREOANY: typing.ClassVar[BondStereo]  # value = rdkit.Chem.rdchem.BondStereo.STEREOANY
    STEREOATROPCCW: typing.ClassVar[BondStereo]  # value = rdkit.Chem.rdchem.BondStereo.STEREOATROPCCW
    STEREOATROPCW: typing.ClassVar[BondStereo]  # value = rdkit.Chem.rdchem.BondStereo.STEREOATROPCW
    STEREOCIS: typing.ClassVar[BondStereo]  # value = rdkit.Chem.rdchem.BondStereo.STEREOCIS
    STEREOE: typing.ClassVar[BondStereo]  # value = rdkit.Chem.rdchem.BondStereo.STEREOE
    STEREONONE: typing.ClassVar[BondStereo]  # value = rdkit.Chem.rdchem.BondStereo.STEREONONE
    STEREOTRANS: typing.ClassVar[BondStereo]  # value = rdkit.Chem.rdchem.BondStereo.STEREOTRANS
    STEREOZ: typing.ClassVar[BondStereo]  # value = rdkit.Chem.rdchem.BondStereo.STEREOZ
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'STEREONONE': rdkit.Chem.rdchem.BondStereo.STEREONONE, 'STEREOANY': rdkit.Chem.rdchem.BondStereo.STEREOANY, 'STEREOZ': rdkit.Chem.rdchem.BondStereo.STEREOZ, 'STEREOE': rdkit.Chem.rdchem.BondStereo.STEREOE, 'STEREOCIS': rdkit.Chem.rdchem.BondStereo.STEREOCIS, 'STEREOTRANS': rdkit.Chem.rdchem.BondStereo.STEREOTRANS, 'STEREOATROPCW': rdkit.Chem.rdchem.BondStereo.STEREOATROPCW, 'STEREOATROPCCW': rdkit.Chem.rdchem.BondStereo.STEREOATROPCCW}
    values: typing.ClassVar[dict]  # value = {0: rdkit.Chem.rdchem.BondStereo.STEREONONE, 1: rdkit.Chem.rdchem.BondStereo.STEREOANY, 2: rdkit.Chem.rdchem.BondStereo.STEREOZ, 3: rdkit.Chem.rdchem.BondStereo.STEREOE, 4: rdkit.Chem.rdchem.BondStereo.STEREOCIS, 5: rdkit.Chem.rdchem.BondStereo.STEREOTRANS, 6: rdkit.Chem.rdchem.BondStereo.STEREOATROPCW, 7: rdkit.Chem.rdchem.BondStereo.STEREOATROPCCW}
class BondType(Boost.Python.enum):
    AROMATIC: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.AROMATIC
    DATIVE: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.DATIVE
    DATIVEL: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.DATIVEL
    DATIVEONE: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.DATIVEONE
    DATIVER: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.DATIVER
    DOUBLE: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.DOUBLE
    FIVEANDAHALF: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.FIVEANDAHALF
    FOURANDAHALF: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.FOURANDAHALF
    HEXTUPLE: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.HEXTUPLE
    HYDROGEN: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.HYDROGEN
    IONIC: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.IONIC
    ONEANDAHALF: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.ONEANDAHALF
    OTHER: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.OTHER
    QUADRUPLE: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.QUADRUPLE
    QUINTUPLE: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.QUINTUPLE
    SINGLE: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.SINGLE
    THREEANDAHALF: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.THREEANDAHALF
    THREECENTER: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.THREECENTER
    TRIPLE: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.TRIPLE
    TWOANDAHALF: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.TWOANDAHALF
    UNSPECIFIED: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.UNSPECIFIED
    ZERO: typing.ClassVar[BondType]  # value = rdkit.Chem.rdchem.BondType.ZERO
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'UNSPECIFIED': rdkit.Chem.rdchem.BondType.UNSPECIFIED, 'SINGLE': rdkit.Chem.rdchem.BondType.SINGLE, 'DOUBLE': rdkit.Chem.rdchem.BondType.DOUBLE, 'TRIPLE': rdkit.Chem.rdchem.BondType.TRIPLE, 'QUADRUPLE': rdkit.Chem.rdchem.BondType.QUADRUPLE, 'QUINTUPLE': rdkit.Chem.rdchem.BondType.QUINTUPLE, 'HEXTUPLE': rdkit.Chem.rdchem.BondType.HEXTUPLE, 'ONEANDAHALF': rdkit.Chem.rdchem.BondType.ONEANDAHALF, 'TWOANDAHALF': rdkit.Chem.rdchem.BondType.TWOANDAHALF, 'THREEANDAHALF': rdkit.Chem.rdchem.BondType.THREEANDAHALF, 'FOURANDAHALF': rdkit.Chem.rdchem.BondType.FOURANDAHALF, 'FIVEANDAHALF': rdkit.Chem.rdchem.BondType.FIVEANDAHALF, 'AROMATIC': rdkit.Chem.rdchem.BondType.AROMATIC, 'IONIC': rdkit.Chem.rdchem.BondType.IONIC, 'HYDROGEN': rdkit.Chem.rdchem.BondType.HYDROGEN, 'THREECENTER': rdkit.Chem.rdchem.BondType.THREECENTER, 'DATIVEONE': rdkit.Chem.rdchem.BondType.DATIVEONE, 'DATIVE': rdkit.Chem.rdchem.BondType.DATIVE, 'DATIVEL': rdkit.Chem.rdchem.BondType.DATIVEL, 'DATIVER': rdkit.Chem.rdchem.BondType.DATIVER, 'OTHER': rdkit.Chem.rdchem.BondType.OTHER, 'ZERO': rdkit.Chem.rdchem.BondType.ZERO}
    values: typing.ClassVar[dict]  # value = {0: rdkit.Chem.rdchem.BondType.UNSPECIFIED, 1: rdkit.Chem.rdchem.BondType.SINGLE, 2: rdkit.Chem.rdchem.BondType.DOUBLE, 3: rdkit.Chem.rdchem.BondType.TRIPLE, 4: rdkit.Chem.rdchem.BondType.QUADRUPLE, 5: rdkit.Chem.rdchem.BondType.QUINTUPLE, 6: rdkit.Chem.rdchem.BondType.HEXTUPLE, 7: rdkit.Chem.rdchem.BondType.ONEANDAHALF, 8: rdkit.Chem.rdchem.BondType.TWOANDAHALF, 9: rdkit.Chem.rdchem.BondType.THREEANDAHALF, 10: rdkit.Chem.rdchem.BondType.FOURANDAHALF, 11: rdkit.Chem.rdchem.BondType.FIVEANDAHALF, 12: rdkit.Chem.rdchem.BondType.AROMATIC, 13: rdkit.Chem.rdchem.BondType.IONIC, 14: rdkit.Chem.rdchem.BondType.HYDROGEN, 15: rdkit.Chem.rdchem.BondType.THREECENTER, 16: rdkit.Chem.rdchem.BondType.DATIVEONE, 17: rdkit.Chem.rdchem.BondType.DATIVE, 18: rdkit.Chem.rdchem.BondType.DATIVEL, 19: rdkit.Chem.rdchem.BondType.DATIVER, 20: rdkit.Chem.rdchem.BondType.OTHER, 21: rdkit.Chem.rdchem.BondType.ZERO}
class ChiralType(Boost.Python.enum):
    CHI_ALLENE: typing.ClassVar[ChiralType]  # value = rdkit.Chem.rdchem.ChiralType.CHI_ALLENE
    CHI_OCTAHEDRAL: typing.ClassVar[ChiralType]  # value = rdkit.Chem.rdchem.ChiralType.CHI_OCTAHEDRAL
    CHI_OTHER: typing.ClassVar[ChiralType]  # value = rdkit.Chem.rdchem.ChiralType.CHI_OTHER
    CHI_SQUAREPLANAR: typing.ClassVar[ChiralType]  # value = rdkit.Chem.rdchem.ChiralType.CHI_SQUAREPLANAR
    CHI_TETRAHEDRAL: typing.ClassVar[ChiralType]  # value = rdkit.Chem.rdchem.ChiralType.CHI_TETRAHEDRAL
    CHI_TETRAHEDRAL_CCW: typing.ClassVar[ChiralType]  # value = rdkit.Chem.rdchem.ChiralType.CHI_TETRAHEDRAL_CCW
    CHI_TETRAHEDRAL_CW: typing.ClassVar[ChiralType]  # value = rdkit.Chem.rdchem.ChiralType.CHI_TETRAHEDRAL_CW
    CHI_TRIGONALBIPYRAMIDAL: typing.ClassVar[ChiralType]  # value = rdkit.Chem.rdchem.ChiralType.CHI_TRIGONALBIPYRAMIDAL
    CHI_UNSPECIFIED: typing.ClassVar[ChiralType]  # value = rdkit.Chem.rdchem.ChiralType.CHI_UNSPECIFIED
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'CHI_UNSPECIFIED': rdkit.Chem.rdchem.ChiralType.CHI_UNSPECIFIED, 'CHI_TETRAHEDRAL_CW': rdkit.Chem.rdchem.ChiralType.CHI_TETRAHEDRAL_CW, 'CHI_TETRAHEDRAL_CCW': rdkit.Chem.rdchem.ChiralType.CHI_TETRAHEDRAL_CCW, 'CHI_OTHER': rdkit.Chem.rdchem.ChiralType.CHI_OTHER, 'CHI_TETRAHEDRAL': rdkit.Chem.rdchem.ChiralType.CHI_TETRAHEDRAL, 'CHI_ALLENE': rdkit.Chem.rdchem.ChiralType.CHI_ALLENE, 'CHI_SQUAREPLANAR': rdkit.Chem.rdchem.ChiralType.CHI_SQUAREPLANAR, 'CHI_TRIGONALBIPYRAMIDAL': rdkit.Chem.rdchem.ChiralType.CHI_TRIGONALBIPYRAMIDAL, 'CHI_OCTAHEDRAL': rdkit.Chem.rdchem.ChiralType.CHI_OCTAHEDRAL}
    values: typing.ClassVar[dict]  # value = {0: rdkit.Chem.rdchem.ChiralType.CHI_UNSPECIFIED, 1: rdkit.Chem.rdchem.ChiralType.CHI_TETRAHEDRAL_CW, 2: rdkit.Chem.rdchem.ChiralType.CHI_TETRAHEDRAL_CCW, 3: rdkit.Chem.rdchem.ChiralType.CHI_OTHER, 4: rdkit.Chem.rdchem.ChiralType.CHI_TETRAHEDRAL, 5: rdkit.Chem.rdchem.ChiralType.CHI_ALLENE, 6: rdkit.Chem.rdchem.ChiralType.CHI_SQUAREPLANAR, 7: rdkit.Chem.rdchem.ChiralType.CHI_TRIGONALBIPYRAMIDAL, 8: rdkit.Chem.rdchem.ChiralType.CHI_OCTAHEDRAL}
class CompositeQueryType(Boost.Python.enum):
    COMPOSITE_AND: typing.ClassVar[CompositeQueryType]  # value = rdkit.Chem.rdchem.CompositeQueryType.COMPOSITE_AND
    COMPOSITE_OR: typing.ClassVar[CompositeQueryType]  # value = rdkit.Chem.rdchem.CompositeQueryType.COMPOSITE_OR
    COMPOSITE_XOR: typing.ClassVar[CompositeQueryType]  # value = rdkit.Chem.rdchem.CompositeQueryType.COMPOSITE_XOR
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'COMPOSITE_AND': rdkit.Chem.rdchem.CompositeQueryType.COMPOSITE_AND, 'COMPOSITE_OR': rdkit.Chem.rdchem.CompositeQueryType.COMPOSITE_OR, 'COMPOSITE_XOR': rdkit.Chem.rdchem.CompositeQueryType.COMPOSITE_XOR}
    values: typing.ClassVar[dict]  # value = {0: rdkit.Chem.rdchem.CompositeQueryType.COMPOSITE_AND, 1: rdkit.Chem.rdchem.CompositeQueryType.COMPOSITE_OR, 2: rdkit.Chem.rdchem.CompositeQueryType.COMPOSITE_XOR}
class Conformer(Boost.Python.instance):
    """
    The class to store 2D or 3D conformation of a molecule
    """
    __instance_size__: typing.ClassVar[int] = 40
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def ClearComputedProps(self) -> None:
        """
            Removes all computed properties from the conformer.
            
            
        
            C++ signature :
                void ClearComputedProps(RDKit::Conformer)
        """
    def ClearProp(self, key: str) -> None:
        """
            Removes a property from the conformer.
            
              ARGUMENTS:
                - key: the name of the property to clear (a string).
            
        
            C++ signature :
                void ClearProp(RDKit::Conformer,std::string)
        """
    def GetAtomPosition(self, aid: int) -> Point3D:
        """
            Get the posistion of an atom
            
        
            C++ signature :
                RDGeom::Point3D GetAtomPosition(RDKit::Conformer const*,unsigned int)
        """
    def GetBoolProp(self, key: str) -> bool:
        """
            Returns the Bool value of the property if possible.
            
              ARGUMENTS:
                - key: the name of the property to return (a string).
            
              RETURNS: a bool
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                bool GetBoolProp(RDKit::Conformer const*,std::string)
        """
    def GetDoubleProp(self, key: str) -> float:
        """
            Returns the double value of the property if possible.
            
              ARGUMENTS:
                - key: the name of the property to return (a string).
            
              RETURNS: a double
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                double GetDoubleProp(RDKit::Conformer const*,std::string)
        """
    def GetId(self) -> int:
        """
            Get the ID of the conformer
        
            C++ signature :
                unsigned int GetId(RDKit::Conformer {lvalue})
        """
    def GetIntProp(self, key: str) -> int:
        """
            Returns the integer value of the property if possible.
            
              ARGUMENTS:
                - key: the name of the property to return (a string).
            
              RETURNS: an integer
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                int GetIntProp(RDKit::Conformer const*,std::string)
        """
    def GetNumAtoms(self) -> int:
        """
            Get the number of atoms in the conformer
            
        
            C++ signature :
                unsigned int GetNumAtoms(RDKit::Conformer {lvalue})
        """
    def GetOwningMol(self) -> Mol:
        """
            Get the owning molecule
            
        
            C++ signature :
                RDKit::ROMol {lvalue} GetOwningMol(RDKit::Conformer {lvalue})
        """
    def GetPositions(self) -> typing.Any:
        """
            Get positions of all the atoms
            
        
            C++ signature :
                _object* GetPositions(RDKit::Conformer const*)
        """
    def GetProp(self, key: str, autoConvert: bool = False) -> typing.Any:
        """
            Returns the value of the property.
            
              ARGUMENTS:
                - key: the name of the property to return (a string).
            
                - autoConvert: if True attempt to convert the property into a python object
            
              RETURNS: a string
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                boost::python::api::object GetProp(RDKit::Conformer const*,std::string [,bool=False])
        """
    def GetPropNames(self, includePrivate: bool = False, includeComputed: bool = False) -> _vectSs:
        """
            Returns a tuple with all property names for this conformer.
            
              ARGUMENTS:
                - includePrivate: (optional) toggles inclusion of private properties in the result set.
                                  Defaults to 0.
                - includeComputed: (optional) toggles inclusion of computed properties in the result set.
                                  Defaults to 0.
            
              RETURNS: a tuple of strings
            
        
            C++ signature :
                std::vector<std::string, std::allocator<std::string> > GetPropNames(RDKit::Conformer {lvalue} [,bool=False [,bool=False]])
        """
    def GetPropsAsDict(self, includePrivate: bool = False, includeComputed: bool = False, autoConvertStrings: bool = True) -> dict:
        """
            Returns a dictionary populated with the conformer's properties.
             n.b. Some properties are not able to be converted to python types.
            
              ARGUMENTS:
                - includePrivate: (optional) toggles inclusion of private properties in the result set.
                                  Defaults to False.
                - includeComputed: (optional) toggles inclusion of computed properties in the result set.
                                  Defaults to False.
            
              RETURNS: a dictionary
            
        
            C++ signature :
                boost::python::dict GetPropsAsDict(RDKit::Conformer [,bool=False [,bool=False [,bool=True]]])
        """
    def GetUnsignedProp(self, key: str) -> int:
        """
            Returns the unsigned int value of the property if possible.
            
              ARGUMENTS:
                - key: the name of the property to return (a string).
            
              RETURNS: an unsigned integer
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                unsigned int GetUnsignedProp(RDKit::Conformer const*,std::string)
        """
    def HasOwningMol(self) -> bool:
        """
            Returns whether or not this instance belongs to a molecule.
            
        
            C++ signature :
                bool HasOwningMol(RDKit::Conformer {lvalue})
        """
    def HasProp(self, key: str) -> int:
        """
            Queries a conformer to see if a particular property has been assigned.
            
              ARGUMENTS:
                - key: the name of the property to check for (a string).
            
        
            C++ signature :
                int HasProp(RDKit::Conformer,std::string)
        """
    def Is3D(self) -> bool:
        """
            returns the 3D flag of the conformer
            
        
            C++ signature :
                bool Is3D(RDKit::Conformer {lvalue})
        """
    def Set3D(self, v: bool) -> None:
        """
            Set the 3D flag of the conformer
            
        
            C++ signature :
                void Set3D(RDKit::Conformer {lvalue},bool)
        """
    @typing.overload
    def SetAtomPosition(self, aid: int, loc: typing.Any) -> None:
        """
            Set the position of the specified atom
            
        
            C++ signature :
                void SetAtomPosition(RDKit::Conformer*,unsigned int,boost::python::api::object)
        """
    @typing.overload
    def SetAtomPosition(self, atomId: int, position: Point3D) -> None:
        """
            Set the position of the specified atom
            
        
            C++ signature :
                void SetAtomPosition(RDKit::Conformer {lvalue},unsigned int,RDGeom::Point3D)
        """
    def SetBoolProp(self, key: str, val: bool, computed: bool = False) -> None:
        """
            Sets a boolean valued molecular property
            
              ARGUMENTS:
                - key: the name of the property to be set (a string).
                - value: the property value as a bool.
                - computed: (optional) marks the property as being computed.
                            Defaults to False.
            
            
        
            C++ signature :
                void SetBoolProp(RDKit::Conformer,std::string,bool [,bool=False])
        """
    def SetDoubleProp(self, key: str, val: float, computed: bool = False) -> None:
        """
            Sets a double valued molecular property
            
              ARGUMENTS:
                - key: the name of the property to be set (a string).
                - value: the property value as a double.
                - computed: (optional) marks the property as being computed.
                            Defaults to 0.
            
            
        
            C++ signature :
                void SetDoubleProp(RDKit::Conformer,std::string,double [,bool=False])
        """
    def SetId(self, id: int) -> None:
        """
            Set the ID of the conformer
            
        
            C++ signature :
                void SetId(RDKit::Conformer {lvalue},unsigned int)
        """
    def SetIntProp(self, key: str, val: int, computed: bool = False) -> None:
        """
            Sets an integer valued molecular property
            
              ARGUMENTS:
                - key: the name of the property to be set (an unsigned number).
                - value: the property value as an integer.
                - computed: (optional) marks the property as being computed.
                            Defaults to False.
            
            
        
            C++ signature :
                void SetIntProp(RDKit::Conformer,std::string,int [,bool=False])
        """
    def SetPositions(self, positions: typing.Any) -> None:
        """
            Set positions of all the atoms given a 2D or 3D numpy array of type double
            
        
            C++ signature :
                void SetPositions(RDKit::Conformer*,boost::python::numpy::ndarray)
        """
    def SetProp(self, key: str, val: str, computed: bool = False) -> None:
        """
            Sets a molecular property
            
              ARGUMENTS:
                - key: the name of the property to be set (a string).
                - value: the property value (a string).
                - computed: (optional) marks the property as being computed.
                            Defaults to False.
            
            
        
            C++ signature :
                void SetProp(RDKit::Conformer,std::string,std::string [,bool=False])
        """
    def SetUnsignedProp(self, key: str, val: int, computed: bool = False) -> None:
        """
            Sets an unsigned integer valued molecular property
            
              ARGUMENTS:
                - key: the name of the property to be set (a string).
                - value: the property value as an unsigned integer.
                - computed: (optional) marks the property as being computed.
                            Defaults to False.
            
            
        
            C++ signature :
                void SetUnsignedProp(RDKit::Conformer,std::string,unsigned int [,bool=False])
        """
    @typing.overload
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    @typing.overload
    def __init__(self, numAtoms: int) -> None:
        """
            Constructor with the number of atoms specified
        
            C++ signature :
                void __init__(_object*,unsigned int)
        """
    @typing.overload
    def __init__(self, other: Conformer) -> None:
        """
            C++ signature :
                void __init__(_object*,RDKit::Conformer)
        """
class EditableMol(Boost.Python.instance):
    """
    an editable molecule class
    """
    __instance_size__: typing.ClassVar[int] = 32
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def AddAtom(self, atom: Atom) -> int:
        """
            add an atom, returns the index of the newly added atom
        
            C++ signature :
                int AddAtom(RDKit::(anonymous namespace)::EditableMol {lvalue},RDKit::Atom*)
        """
    def AddBond(self, beginAtomIdx: int, endAtomIdx: int, order: BondType = ...) -> int:
        """
            add a bond, returns the total number of bonds
        
            C++ signature :
                int AddBond(RDKit::(anonymous namespace)::EditableMol {lvalue},unsigned int,unsigned int [,RDKit::Bond::BondType=rdkit.Chem.rdchem.BondType.UNSPECIFIED])
        """
    def BeginBatchEdit(self) -> None:
        """
            starts batch editing
        
            C++ signature :
                void BeginBatchEdit(RDKit::(anonymous namespace)::EditableMol {lvalue})
        """
    def CommitBatchEdit(self) -> None:
        """
            finishes batch editing and makes the actual edits
        
            C++ signature :
                void CommitBatchEdit(RDKit::(anonymous namespace)::EditableMol {lvalue})
        """
    def GetMol(self) -> Mol:
        """
            Returns a Mol (a normal molecule)
        
            C++ signature :
                RDKit::ROMol* GetMol(RDKit::(anonymous namespace)::EditableMol {lvalue})
        """
    def RemoveAtom(self, idx: int) -> None:
        """
            Remove the specified atom from the molecule
        
            C++ signature :
                void RemoveAtom(RDKit::(anonymous namespace)::EditableMol {lvalue},unsigned int)
        """
    def RemoveBond(self, idx1: int, idx2: int) -> None:
        """
            Remove the specified bond from the molecule
        
            C++ signature :
                void RemoveBond(RDKit::(anonymous namespace)::EditableMol {lvalue},unsigned int,unsigned int)
        """
    def ReplaceAtom(self, index: int, newAtom: Atom, updateLabel: bool = False, preserveProps: bool = False) -> None:
        """
            replaces the specified atom with the provided one
            If updateLabel is True, the new atom becomes the active atom
            If preserveProps is True preserve keep the existing props unless explicit set on the new atom
        
            C++ signature :
                void ReplaceAtom(RDKit::(anonymous namespace)::EditableMol {lvalue},unsigned int,RDKit::Atom* [,bool=False [,bool=False]])
        """
    def ReplaceBond(self, index: int, newBond: Bond, preserveProps: bool = False) -> None:
        """
            replaces the specified bond with the provided one.
            If preserveProps is True preserve keep the existing props unless explicit set on the new bond
        
            C++ signature :
                void ReplaceBond(RDKit::(anonymous namespace)::EditableMol {lvalue},unsigned int,RDKit::Bond* [,bool=False])
        """
    def RollbackBatchEdit(self) -> None:
        """
            cancels batch editing
        
            C++ signature :
                void RollbackBatchEdit(RDKit::(anonymous namespace)::EditableMol {lvalue})
        """
    def __init__(self, m: Mol) -> None:
        """
            Construct from a Mol
        
            C++ signature :
                void __init__(_object*,RDKit::ROMol)
        """
class FixedMolSizeMolBundle(MolBundle):
    """
    A class for storing groups of related molecules.
        Here related means that the molecules have to have the same number of atoms.
    
    """
    __instance_size__: typing.ClassVar[int] = 88
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
class HybridizationType(Boost.Python.enum):
    OTHER: typing.ClassVar[HybridizationType]  # value = rdkit.Chem.rdchem.HybridizationType.OTHER
    S: typing.ClassVar[HybridizationType]  # value = rdkit.Chem.rdchem.HybridizationType.S
    SP: typing.ClassVar[HybridizationType]  # value = rdkit.Chem.rdchem.HybridizationType.SP
    SP2: typing.ClassVar[HybridizationType]  # value = rdkit.Chem.rdchem.HybridizationType.SP2
    SP2D: typing.ClassVar[HybridizationType]  # value = rdkit.Chem.rdchem.HybridizationType.SP2D
    SP3: typing.ClassVar[HybridizationType]  # value = rdkit.Chem.rdchem.HybridizationType.SP3
    SP3D: typing.ClassVar[HybridizationType]  # value = rdkit.Chem.rdchem.HybridizationType.SP3D
    SP3D2: typing.ClassVar[HybridizationType]  # value = rdkit.Chem.rdchem.HybridizationType.SP3D2
    UNSPECIFIED: typing.ClassVar[HybridizationType]  # value = rdkit.Chem.rdchem.HybridizationType.UNSPECIFIED
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'UNSPECIFIED': rdkit.Chem.rdchem.HybridizationType.UNSPECIFIED, 'S': rdkit.Chem.rdchem.HybridizationType.S, 'SP': rdkit.Chem.rdchem.HybridizationType.SP, 'SP2': rdkit.Chem.rdchem.HybridizationType.SP2, 'SP3': rdkit.Chem.rdchem.HybridizationType.SP3, 'SP2D': rdkit.Chem.rdchem.HybridizationType.SP2D, 'SP3D': rdkit.Chem.rdchem.HybridizationType.SP3D, 'SP3D2': rdkit.Chem.rdchem.HybridizationType.SP3D2, 'OTHER': rdkit.Chem.rdchem.HybridizationType.OTHER}
    values: typing.ClassVar[dict]  # value = {0: rdkit.Chem.rdchem.HybridizationType.UNSPECIFIED, 1: rdkit.Chem.rdchem.HybridizationType.S, 2: rdkit.Chem.rdchem.HybridizationType.SP, 3: rdkit.Chem.rdchem.HybridizationType.SP2, 4: rdkit.Chem.rdchem.HybridizationType.SP3, 5: rdkit.Chem.rdchem.HybridizationType.SP2D, 6: rdkit.Chem.rdchem.HybridizationType.SP3D, 7: rdkit.Chem.rdchem.HybridizationType.SP3D2, 8: rdkit.Chem.rdchem.HybridizationType.OTHER}
class KekulizeException(MolSanitizeException):
    pass
class Mol(Boost.Python.instance):
    """
    The Molecule class.
    
      In addition to the expected Atoms and Bonds, molecules contain:
        - a collection of Atom and Bond bookmarks indexed with integers
            that can be used to flag and retrieve particular Atoms or Bonds
            using the {get|set}{Atom|Bond}Bookmark() methods.
    
        - a set of string-valued properties. These can have arbitrary string
            labels and can be set and retrieved using the {set|get}Prop() methods
            Molecular properties can be tagged as being *computed*, in which case
              they will be automatically cleared under certain circumstances (when the
              molecule itself is modified, for example).
            Molecules also have the concept of *private* properties, which are tagged
              by beginning the property name with an underscore (_).
    """
    __getstate_manages_dict__: typing.ClassVar[bool] = True
    __instance_size__: typing.ClassVar[int] = 40
    __safe_for_unpickling__: typing.ClassVar[bool] = True
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def AddConformer(self, conf: Conformer, assignId: bool = False) -> int:
        """
            Add a conformer to the molecule and return the conformer ID
        
            C++ signature :
                unsigned int AddConformer(RDKit::ROMol {lvalue},RDKit::Conformer* [,bool=False])
        """
    def ClearComputedProps(self, includeRings: bool = True) -> None:
        """
            Removes all computed properties from the molecule.
            
            
        
            C++ signature :
                void ClearComputedProps(RDKit::ROMol [,bool=True])
        """
    def ClearProp(self, key: str) -> None:
        """
            Removes a property from the molecule.
            
              ARGUMENTS:
                - key: the name of the property to clear (a string).
            
        
            C++ signature :
                void ClearProp(RDKit::ROMol,std::string)
        """
    def Debug(self, useStdout: bool = True) -> None:
        """
            Prints debugging information about the molecule.
            
        
            C++ signature :
                void Debug(RDKit::ROMol [,bool=True])
        """
    def GetAromaticAtoms(self) -> typing.Sequence[rdkit.Chem.QueryAtom]:
        """
            Returns a read-only sequence containing all of the molecule's aromatic Atoms.
            
        
            C++ signature :
                RDKit::ReadOnlySeq<RDKit::QueryAtomIterator_<RDKit::Atom, RDKit::ROMol>, RDKit::Atom*, RDKit::AtomCountFunctor>* GetAromaticAtoms(boost::shared_ptr<RDKit::ROMol>)
        """
    def GetAtomWithIdx(self, idx: int) -> Atom:
        """
            Returns a particular Atom.
            
              ARGUMENTS:
                - idx: which Atom to return
            
              NOTE: atom indices start at 0
            
        
            C++ signature :
                RDKit::Atom* GetAtomWithIdx(RDKit::ROMol {lvalue},unsigned int)
        """
    def GetAtoms(self):
        """
        returns an iterator over the atoms in the molecule
        """
    def GetAtomsMatchingQuery(self, qa: QueryAtom) -> typing.Sequence[rdkit.Chem.QueryAtom]:
        """
            Returns a read-only sequence containing all of the atoms in a molecule that match the query atom. Atom query options are defined in the rdkit.Chem.rdqueries module.
            
        
            C++ signature :
                RDKit::ReadOnlySeq<RDKit::QueryAtomIterator_<RDKit::Atom, RDKit::ROMol>, RDKit::Atom*, RDKit::AtomCountFunctor>* GetAtomsMatchingQuery(boost::shared_ptr<RDKit::ROMol>,RDKit::QueryAtom*)
        """
    def GetBondBetweenAtoms(self, idx1: int, idx2: int) -> Bond:
        """
            Returns the bond between two atoms, if there is one.
            
              ARGUMENTS:
                - idx1,idx2: the Atom indices
            
              Returns:
                The Bond between the two atoms, if such a bond exists.
                If there is no Bond between the atoms, None is returned instead.
            
              NOTE: bond indices start at 0
            
        
            C++ signature :
                RDKit::Bond* GetBondBetweenAtoms(RDKit::ROMol {lvalue},unsigned int,unsigned int)
        """
    def GetBondWithIdx(self, idx: int) -> Bond:
        """
            Returns a particular Bond.
            
              ARGUMENTS:
                - idx: which Bond to return
            
              NOTE: bond indices start at 0
            
        
            C++ signature :
                RDKit::Bond* GetBondWithIdx(RDKit::ROMol {lvalue},unsigned int)
        """
    def GetBonds(self):
        """
        returns an iterator over the bonds in the molecule
        """
    def GetBoolProp(self, key: str) -> bool:
        """
            Returns the Bool value of the property if possible.
            
              ARGUMENTS:
                - key: the name of the property to return (a string).
            
              RETURNS: a bool
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                bool GetBoolProp(RDKit::ROMol const*,std::string)
        """
    def GetConformer(self, id: int = -1) -> Conformer:
        """
            Get the conformer with a specified ID
        
            C++ signature :
                RDKit::Conformer* GetConformer(RDKit::ROMol {lvalue} [,int=-1])
        """
    def GetConformers(self) -> typing.Sequence[rdkit.Chem.Conformer]:
        """
            Returns a read-only sequence containing all of the molecule's Conformers.
        
            C++ signature :
                RDKit::ReadOnlySeq<std::_List_iterator<boost::shared_ptr<RDKit::Conformer> >, boost::shared_ptr<RDKit::Conformer>&, RDKit::ConformerCountFunctor>* GetConformers(boost::shared_ptr<RDKit::ROMol>)
        """
    def GetDoubleProp(self, key: str) -> float:
        """
            Returns the double value of the property if possible.
            
              ARGUMENTS:
                - key: the name of the property to return (a string).
            
              RETURNS: a double
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                double GetDoubleProp(RDKit::ROMol const*,std::string)
        """
    def GetIntProp(self, key: str) -> int:
        """
            Returns the integer value of the property if possible.
            
              ARGUMENTS:
                - key: the name of the property to return (a string).
            
              RETURNS: an integer
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                int GetIntProp(RDKit::ROMol const*,std::string)
        """
    def GetNumAtoms(self, onlyHeavy: int = -1, onlyExplicit: bool = True) -> int:
        """
            Returns the number of atoms in the molecule.
            
              ARGUMENTS:
                - onlyExplicit: (optional) include only explicit atoms (atoms in the molecular graph)
                                defaults to 1.
              NOTE: the onlyHeavy argument is deprecated
            
        
            C++ signature :
                int GetNumAtoms(RDKit::ROMol [,int=-1 [,bool=True]])
        """
    def GetNumBonds(self, onlyHeavy: bool = True) -> int:
        """
            Returns the number of Bonds in the molecule.
            
              ARGUMENTS:
                - onlyHeavy: (optional) include only bonds to heavy atoms (not Hs)
                              defaults to 1.
            
        
            C++ signature :
                unsigned int GetNumBonds(RDKit::ROMol {lvalue} [,bool=True])
        """
    def GetNumConformers(self) -> int:
        """
            Return the number of conformations on the molecule
        
            C++ signature :
                unsigned int GetNumConformers(RDKit::ROMol {lvalue})
        """
    def GetNumHeavyAtoms(self) -> int:
        """
            Returns the number of heavy atoms (atomic number >1) in the molecule.
            
            
        
            C++ signature :
                unsigned int GetNumHeavyAtoms(RDKit::ROMol {lvalue})
        """
    def GetProp(self, key: str, autoConvert: bool = False) -> typing.Any:
        """
            Returns the value of the property.
            
              ARGUMENTS:
                - key: the name of the property to return (a string).
            
                - autoConvert: if True attempt to convert the property into a python object
            
              RETURNS: a string
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                boost::python::api::object GetProp(RDKit::ROMol const*,std::string [,bool=False])
        """
    def GetPropNames(self, includePrivate: bool = False, includeComputed: bool = False) -> _vectSs:
        """
            Returns a tuple with all property names for this molecule.
            
              ARGUMENTS:
                - includePrivate: (optional) toggles inclusion of private properties in the result set.
                                  Defaults to 0.
                - includeComputed: (optional) toggles inclusion of computed properties in the result set.
                                  Defaults to 0.
            
              RETURNS: a tuple of strings
            
        
            C++ signature :
                std::vector<std::string, std::allocator<std::string> > GetPropNames(RDKit::ROMol {lvalue} [,bool=False [,bool=False]])
        """
    def GetPropsAsDict(self, includePrivate: bool = False, includeComputed: bool = False, autoConvertStrings: bool = True) -> dict:
        """
            Returns a dictionary populated with the molecules properties.
             n.b. Some properties are not able to be converted to python types.
            
              ARGUMENTS:
                - includePrivate: (optional) toggles inclusion of private properties in the result set.
                                  Defaults to False.
                - includeComputed: (optional) toggles inclusion of computed properties in the result set.
                                  Defaults to False.
            
              RETURNS: a dictionary
            
        
            C++ signature :
                boost::python::dict GetPropsAsDict(RDKit::ROMol [,bool=False [,bool=False [,bool=True]]])
        """
    def GetRingInfo(self) -> RingInfo:
        """
            Returns the number of molecule's RingInfo object.
            
            
        
            C++ signature :
                RDKit::RingInfo* GetRingInfo(RDKit::ROMol {lvalue})
        """
    def GetStereoGroups(self) -> StereoGroup_vect:
        """
            Returns a list of StereoGroups defining the relative stereochemistry of the atoms.
            
        
            C++ signature :
                std::vector<RDKit::StereoGroup, std::allocator<RDKit::StereoGroup> > GetStereoGroups(RDKit::ROMol {lvalue})
        """
    @typing.overload
    def GetSubstructMatch(self, query: Mol, useChirality: bool = False, useQueryQueryMatches: bool = False) -> typing.Any:
        """
            Returns the indices of the molecule's atoms that match a substructure query.
            
              ARGUMENTS:
                - query: a Molecule
            
                - useChirality: enables the use of stereochemistry in the matching
            
                - useQueryQueryMatches: use query-query matching logic
            
              RETURNS: a tuple of integers
            
              NOTES:
                 - only a single match is returned
                 - the ordering of the indices corresponds to the atom ordering
                     in the query. For example, the first index is for the atom in
                     this molecule that matches the first atom in the query.
            
        
            C++ signature :
                _object* GetSubstructMatch(RDKit::ROMol,RDKit::ROMol [,bool=False [,bool=False]])
        """
    @typing.overload
    def GetSubstructMatch(self, query: MolBundle, useChirality: bool = False, useQueryQueryMatches: bool = False) -> typing.Any:
        """
            C++ signature :
                _object* GetSubstructMatch(RDKit::ROMol,RDKit::MolBundle [,bool=False [,bool=False]])
        """
    @typing.overload
    def GetSubstructMatch(self, query: Mol, params: SubstructMatchParameters) -> typing.Any:
        """
            Returns the indices of the molecule's atoms that match a substructure query.
            
              ARGUMENTS:
                - query: a Molecule
            
                - params: parameters controlling the substructure match
            
              RETURNS: a tuple of integers
            
              NOTES:
                 - only a single match is returned
                 - the ordering of the indices corresponds to the atom ordering
                     in the query. For example, the first index is for the atom in
                     this molecule that matches the first atom in the query.
            
        
            C++ signature :
                _object* GetSubstructMatch(RDKit::ROMol,RDKit::ROMol,RDKit::SubstructMatchParameters)
        """
    @typing.overload
    def GetSubstructMatch(self, query: MolBundle, params: SubstructMatchParameters) -> typing.Any:
        """
            C++ signature :
                _object* GetSubstructMatch(RDKit::ROMol,RDKit::MolBundle,RDKit::SubstructMatchParameters)
        """
    @typing.overload
    def GetSubstructMatches(self, query: Mol, uniquify: bool = True, useChirality: bool = False, useQueryQueryMatches: bool = False, maxMatches: int = 1000) -> typing.Any:
        """
            Returns tuples of the indices of the molecule's atoms that match a substructure query.
            
              ARGUMENTS:
                - query: a Molecule.
                - uniquify: (optional) determines whether or not the matches are uniquified.
                            Defaults to 1.
            
                - useChirality: enables the use of stereochemistry in the matching
            
                - useQueryQueryMatches: use query-query matching logic
            
                - maxMatches: The maximum number of matches that will be returned.
                              In high-symmetry cases with medium-sized molecules, it is
                              very easy to end up with a combinatorial explosion in the
                              number of possible matches. This argument prevents that from
                              having unintended consequences
            
              RETURNS: a tuple of tuples of integers
            
              NOTE:
                 - the ordering of the indices corresponds to the atom ordering
                     in the query. For example, the first index is for the atom in
                     this molecule that matches the first atom in the query.
            
        
            C++ signature :
                _object* GetSubstructMatches(RDKit::ROMol,RDKit::ROMol [,bool=True [,bool=False [,bool=False [,unsigned int=1000]]]])
        """
    @typing.overload
    def GetSubstructMatches(self, query: MolBundle, uniquify: bool = True, useChirality: bool = False, useQueryQueryMatches: bool = False, maxMatches: int = 1000) -> typing.Any:
        """
            C++ signature :
                _object* GetSubstructMatches(RDKit::ROMol,RDKit::MolBundle [,bool=True [,bool=False [,bool=False [,unsigned int=1000]]]])
        """
    @typing.overload
    def GetSubstructMatches(self, query: Mol, params: SubstructMatchParameters) -> typing.Any:
        """
            Returns tuples of the indices of the molecule's atoms that match a substructure query.
            
              ARGUMENTS:
                - query: a Molecule.
                - params: parameters controlling the substructure match
            
              RETURNS: a tuple of tuples of integers
            
              NOTE:
                 - the ordering of the indices corresponds to the atom ordering
                     in the query. For example, the first index is for the atom in
                     this molecule that matches the first atom in the query.
            
        
            C++ signature :
                _object* GetSubstructMatches(RDKit::ROMol,RDKit::ROMol,RDKit::SubstructMatchParameters)
        """
    @typing.overload
    def GetSubstructMatches(self, query: MolBundle, params: SubstructMatchParameters) -> typing.Any:
        """
            C++ signature :
                _object* GetSubstructMatches(RDKit::ROMol,RDKit::MolBundle,RDKit::SubstructMatchParameters)
        """
    def GetUnsignedProp(self, key: str) -> int:
        """
            Returns the unsigned int value of the property if possible.
            
              ARGUMENTS:
                - key: the name of the property to return (a string).
            
              RETURNS: an unsigned integer
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                unsigned int GetUnsignedProp(RDKit::ROMol const*,std::string)
        """
    def HasProp(self, key: str) -> int:
        """
            Queries a molecule to see if a particular property has been assigned.
            
              ARGUMENTS:
                - key: the name of the property to check for (a string).
            
        
            C++ signature :
                int HasProp(RDKit::ROMol,std::string)
        """
    def HasQuery(self) -> bool:
        """
            Returns if any atom or bond in molecule has a query
        
            C++ signature :
                bool HasQuery(RDKit::ROMol {lvalue})
        """
    @typing.overload
    def HasSubstructMatch(self, query: Mol, recursionPossible: bool = True, useChirality: bool = False, useQueryQueryMatches: bool = False) -> bool:
        """
            Queries whether or not the molecule contains a particular substructure.
            
              ARGUMENTS:
                - query: a Molecule
            
                - recursionPossible: (optional)
            
                - useChirality: enables the use of stereochemistry in the matching
            
                - useQueryQueryMatches: use query-query matching logic
            
              RETURNS: True or False
            
        
            C++ signature :
                bool HasSubstructMatch(RDKit::ROMol,RDKit::ROMol [,bool=True [,bool=False [,bool=False]]])
        """
    @typing.overload
    def HasSubstructMatch(self, query: MolBundle, recursionPossible: bool = True, useChirality: bool = False, useQueryQueryMatches: bool = False) -> bool:
        """
            C++ signature :
                bool HasSubstructMatch(RDKit::ROMol,RDKit::MolBundle [,bool=True [,bool=False [,bool=False]]])
        """
    @typing.overload
    def HasSubstructMatch(self, query: Mol, params: SubstructMatchParameters) -> bool:
        """
            Queries whether or not the molecule contains a particular substructure.
            
              ARGUMENTS:
                - query: a Molecule
            
                - params: parameters controlling the substructure match
            
              RETURNS: True or False
            
        
            C++ signature :
                bool HasSubstructMatch(RDKit::ROMol,RDKit::ROMol,RDKit::SubstructMatchParameters)
        """
    @typing.overload
    def HasSubstructMatch(self, query: MolBundle, params: SubstructMatchParameters = True) -> bool:
        """
            C++ signature :
                bool HasSubstructMatch(RDKit::ROMol,RDKit::MolBundle [,RDKit::SubstructMatchParameters=True])
        """
    def NeedsUpdatePropertyCache(self) -> bool:
        """
            Returns true or false depending on whether implicit and explicit valence of the molecule have already been calculated.
            
            
        
            C++ signature :
                bool NeedsUpdatePropertyCache(RDKit::ROMol {lvalue})
        """
    def RemoveAllConformers(self) -> None:
        """
            Remove all the conformations on the molecule
        
            C++ signature :
                void RemoveAllConformers(RDKit::ROMol {lvalue})
        """
    def RemoveConformer(self, id: int) -> None:
        """
            Remove the conformer with the specified ID
        
            C++ signature :
                void RemoveConformer(RDKit::ROMol {lvalue},unsigned int)
        """
    def SetBoolProp(self, key: str, val: bool, computed: bool = False) -> None:
        """
            Sets a boolean valued molecular property
            
              ARGUMENTS:
                - key: the name of the property to be set (a string).
                - value: the property value as a bool.
                - computed: (optional) marks the property as being computed.
                            Defaults to False.
            
            
        
            C++ signature :
                void SetBoolProp(RDKit::ROMol,std::string,bool [,bool=False])
        """
    def SetDoubleProp(self, key: str, val: float, computed: bool = False) -> None:
        """
            Sets a double valued molecular property
            
              ARGUMENTS:
                - key: the name of the property to be set (a string).
                - value: the property value as a double.
                - computed: (optional) marks the property as being computed.
                            Defaults to 0.
            
            
        
            C++ signature :
                void SetDoubleProp(RDKit::ROMol,std::string,double [,bool=False])
        """
    def SetIntProp(self, key: str, val: int, computed: bool = False) -> None:
        """
            Sets an integer valued molecular property
            
              ARGUMENTS:
                - key: the name of the property to be set (an unsigned number).
                - value: the property value as an integer.
                - computed: (optional) marks the property as being computed.
                            Defaults to False.
            
            
        
            C++ signature :
                void SetIntProp(RDKit::ROMol,std::string,int [,bool=False])
        """
    def SetProp(self, key: str, val: str, computed: bool = False) -> None:
        """
            Sets a molecular property
            
              ARGUMENTS:
                - key: the name of the property to be set (a string).
                - value: the property value (a string).
                - computed: (optional) marks the property as being computed.
                            Defaults to False.
            
            
        
            C++ signature :
                void SetProp(RDKit::ROMol,std::string,std::string [,bool=False])
        """
    def SetUnsignedProp(self, key: str, val: int, computed: bool = False) -> None:
        """
            Sets an unsigned integer valued molecular property
            
              ARGUMENTS:
                - key: the name of the property to be set (a string).
                - value: the property value as an unsigned integer.
                - computed: (optional) marks the property as being computed.
                            Defaults to False.
            
            
        
            C++ signature :
                void SetUnsignedProp(RDKit::ROMol,std::string,unsigned int [,bool=False])
        """
    @typing.overload
    def ToBinary(self) -> typing.Any:
        """
            Returns a binary string representation of the molecule.
            
        
            C++ signature :
                boost::python::api::object ToBinary(RDKit::ROMol)
        """
    @typing.overload
    def ToBinary(self, propertyFlags: int) -> typing.Any:
        """
            Returns a binary string representation of the molecule pickling the specified properties.
            
        
            C++ signature :
                boost::python::api::object ToBinary(RDKit::ROMol,unsigned int)
        """
    def UpdatePropertyCache(self, strict: bool = True) -> None:
        """
            Regenerates computed properties like implicit valence and ring information.
            
            
        
            C++ signature :
                void UpdatePropertyCache(RDKit::ROMol {lvalue} [,bool=True])
        """
    def __copy__(self) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __copy__(boost::python::api::object)
        """
    def __deepcopy__(self, memo: dict) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __deepcopy__(boost::python::api::object,boost::python::dict)
        """
    def __getinitargs__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getinitargs__(RDKit::ROMol)
        """
    def __getstate__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getstate__(boost::python::api::object)
        """
    @typing.overload
    def __init__(self) -> None:
        """
            Constructor, takes no arguments
        
            C++ signature :
                void __init__(_object*)
        """
    @typing.overload
    def __init__(self, pklString: str) -> None:
        """
            C++ signature :
                void __init__(_object*,std::string)
        """
    @typing.overload
    def __init__(self, pklString: str, propertyFlags: int) -> None:
        """
            C++ signature :
                void __init__(_object*,std::string,unsigned int)
        """
    @typing.overload
    def __init__(self, mol: Mol, quickCopy: bool = False, confId: int = -1) -> None:
        """
            C++ signature :
                void __init__(_object*,RDKit::ROMol [,bool=False [,int=-1]])
        """
    def __setstate__(self, data: tuple) -> None:
        """
            C++ signature :
                void __setstate__(boost::python::api::object,boost::python::tuple)
        """
class MolBundle(Boost.Python.instance):
    """
    A class for storing groups of related molecules.
    
    """
    __getstate_manages_dict__: typing.ClassVar[bool] = True
    __instance_size__: typing.ClassVar[int] = 88
    __safe_for_unpickling__: typing.ClassVar[bool] = True
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def AddMol(self, nmol: Mol) -> int:
        """
            C++ signature :
                unsigned long AddMol(RDKit::MolBundle {lvalue},boost::shared_ptr<RDKit::ROMol>)
        """
    def GetMol(self, idx: int) -> Mol:
        """
            C++ signature :
                boost::shared_ptr<RDKit::ROMol> GetMol(RDKit::MolBundle {lvalue},unsigned long)
        """
    @typing.overload
    def GetSubstructMatch(self, query: Mol, useChirality: bool = False, useQueryQueryMatches: bool = False) -> typing.Any:
        """
            Returns the indices of the atoms from the first molecule in a bundle that matches a substructure query.
            
              ARGUMENTS:
                - query: a Molecule
            
                - useChirality: enables the use of stereochemistry in the matching
            
                - useQueryQueryMatches: use query-query matching logic
            
              RETURNS: a tuple of integers
            
              NOTES:
                 - only a single match is returned
                 - the ordering of the indices corresponds to the atom ordering
                     in the query. For example, the first index is for the atom in
                     this molecule that matches the first atom in the query.
            
        
            C++ signature :
                _object* GetSubstructMatch(RDKit::MolBundle,RDKit::ROMol [,bool=False [,bool=False]])
        """
    @typing.overload
    def GetSubstructMatch(self, query: MolBundle, useChirality: bool = False, useQueryQueryMatches: bool = False) -> typing.Any:
        """
            Returns the indices of the atoms from the first molecule in a bundle that matches a substructure query from a bundle.
            
              ARGUMENTS:
                - query: a MolBundle
            
                - useChirality: enables the use of stereochemistry in the matching
            
                - useQueryQueryMatches: use query-query matching logic
            
              RETURNS: a tuple of integers
            
              NOTES:
                 - only a single match is returned
                 - the ordering of the indices corresponds to the atom ordering
                     in the query. For example, the first index is for the atom in
                     this molecule that matches the first atom in the query.
            
        
            C++ signature :
                _object* GetSubstructMatch(RDKit::MolBundle,RDKit::MolBundle [,bool=False [,bool=False]])
        """
    @typing.overload
    def GetSubstructMatch(self, query: Mol, params: SubstructMatchParameters) -> typing.Any:
        """
            Returns the indices of the atoms from the first molecule in a bundle that matches a substructure query.
            
              ARGUMENTS:
                - query: a Molecule
            
                - params: parameters controlling the substructure match
            
              RETURNS: a tuple of integers
            
              NOTES:
                 - only a single match is returned
                 - the ordering of the indices corresponds to the atom ordering
                     in the query. For example, the first index is for the atom in
                     this molecule that matches the first atom in the query.
            
        
            C++ signature :
                _object* GetSubstructMatch(RDKit::MolBundle,RDKit::ROMol,RDKit::SubstructMatchParameters)
        """
    @typing.overload
    def GetSubstructMatch(self, query: MolBundle, params: SubstructMatchParameters) -> typing.Any:
        """
            Returns the indices of the atoms from the first molecule in a bundle that matches a substructure query from a bundle.
            
              ARGUMENTS:
                - query: a MolBundle
            
                - params: parameters controlling the substructure match
            
              RETURNS: a tuple of integers
            
              NOTES:
                 - only a single match is returned
                 - the ordering of the indices corresponds to the atom ordering
                     in the query. For example, the first index is for the atom in
                     this molecule that matches the first atom in the query.
            
        
            C++ signature :
                _object* GetSubstructMatch(RDKit::MolBundle,RDKit::MolBundle,RDKit::SubstructMatchParameters)
        """
    @typing.overload
    def GetSubstructMatches(self, query: Mol, uniquify: bool = True, useChirality: bool = False, useQueryQueryMatches: bool = False, maxMatches: int = 1000) -> typing.Any:
        """
            Returns tuple of all indices of the atoms from the first molecule in a bundle that matches a substructure query.
            
              ARGUMENTS:
                - query: a molecule.
                - uniquify: (optional) determines whether or not the matches are uniquified.
                            Defaults to 1.
            
                - useChirality: enables the use of stereochemistry in the matching
            
                - useQueryQueryMatches: use query-query matching logic
            
                - maxMatches: The maximum number of matches that will be returned.
                              In high-symmetry cases with medium-sized molecules, it is
                              very easy to end up with a combinatorial explosion in the
                              number of possible matches. This argument prevents that from
                              having unintended consequences
            
              RETURNS: a tuple of tuples of integers
            
              NOTE:
                 - the ordering of the indices corresponds to the atom ordering
                     in the query. For example, the first index is for the atom in
                     this molecule that matches the first atom in the query.
            
        
            C++ signature :
                _object* GetSubstructMatches(RDKit::MolBundle,RDKit::ROMol [,bool=True [,bool=False [,bool=False [,unsigned int=1000]]]])
        """
    @typing.overload
    def GetSubstructMatches(self, query: MolBundle, uniquify: bool = True, useChirality: bool = False, useQueryQueryMatches: bool = False, maxMatches: int = 1000) -> typing.Any:
        """
            Returns tuple of all indices of the atoms from the first molecule in a bundle that matches a substructure query from the second bundle.
            
              ARGUMENTS:
                - query: a MolBundle.
                - uniquify: (optional) determines whether or not the matches are uniquified.
                            Defaults to 1.
            
                - useChirality: enables the use of stereochemistry in the matching
            
                - useQueryQueryMatches: use query-query matching logic
            
                - maxMatches: The maximum number of matches that will be returned.
                              In high-symmetry cases with medium-sized molecules, it is
                              very easy to end up with a combinatorial explosion in the
                              number of possible matches. This argument prevents that from
                              having unintended consequences
            
              RETURNS: a tuple of tuples of integers
            
              NOTE:
                 - the ordering of the indices corresponds to the atom ordering
                     in the query. For example, the first index is for the atom in
                     this molecule that matches the first atom in the query.
            
        
            C++ signature :
                _object* GetSubstructMatches(RDKit::MolBundle,RDKit::MolBundle [,bool=True [,bool=False [,bool=False [,unsigned int=1000]]]])
        """
    @typing.overload
    def GetSubstructMatches(self, query: Mol, params: SubstructMatchParameters) -> typing.Any:
        """
            Returns tuple of all indices of the atoms from the first molecule in a bundle that matches a substructure query.
            
              ARGUMENTS:
                - query: a molecule.
                - params: parameters controlling the substructure match
            
              RETURNS: a tuple of tuples of integers
            
              NOTE:
                 - the ordering of the indices corresponds to the atom ordering
                     in the query. For example, the first index is for the atom in
                     this molecule that matches the first atom in the query.
            
        
            C++ signature :
                _object* GetSubstructMatches(RDKit::MolBundle,RDKit::ROMol,RDKit::SubstructMatchParameters)
        """
    @typing.overload
    def GetSubstructMatches(self, query: MolBundle, params: SubstructMatchParameters) -> typing.Any:
        """
            Returns tuple of all indices of the atoms from the first molecule in a bundle that matches a substructure query from the second bundle.
            
              ARGUMENTS:
                - query: a MolBundle.
                - params: parameters controlling the substructure match
            
              RETURNS: a tuple of tuples of integers
            
              NOTE:
                 - the ordering of the indices corresponds to the atom ordering
                     in the query. For example, the first index is for the atom in
                     this molecule that matches the first atom in the query.
            
        
            C++ signature :
                _object* GetSubstructMatches(RDKit::MolBundle,RDKit::MolBundle,RDKit::SubstructMatchParameters)
        """
    @typing.overload
    def HasSubstructMatch(self, query: Mol, recursionPossible: bool = True, useChirality: bool = False, useQueryQueryMatches: bool = False) -> bool:
        """
            Queries whether or not any molecule in the bundle contains a particular substructure.
            
              ARGUMENTS:
                - query: a Molecule
            
                - recursionPossible: (optional)
            
                - useChirality: enables the use of stereochemistry in the matching
            
                - useQueryQueryMatches: use query-query matching logic
            
              RETURNS: True or False
            
        
            C++ signature :
                bool HasSubstructMatch(RDKit::MolBundle,RDKit::ROMol [,bool=True [,bool=False [,bool=False]]])
        """
    @typing.overload
    def HasSubstructMatch(self, query: MolBundle, recursionPossible: bool = True, useChirality: bool = False, useQueryQueryMatches: bool = False) -> bool:
        """
            Queries whether or not any molecule in the first bundle matches any molecule in the second bundle.
            
              ARGUMENTS:
                - query: a MolBundle
            
                - recursionPossible: (optional)
            
                - useChirality: enables the use of stereochemistry in the matching
            
                - useQueryQueryMatches: use query-query matching logic
            
              RETURNS: True or False
            
        
            C++ signature :
                bool HasSubstructMatch(RDKit::MolBundle,RDKit::MolBundle [,bool=True [,bool=False [,bool=False]]])
        """
    @typing.overload
    def HasSubstructMatch(self, query: Mol, params: SubstructMatchParameters) -> bool:
        """
            Queries whether or not any molecule in the bundle contains a particular substructure.
            
              ARGUMENTS:
                - query: a Molecule
            
                - params: parameters controlling the substructure match
            
            matching
            
                - useQueryQueryMatches: use query-query matching logic
            
              RETURNS: True or False
            
        
            C++ signature :
                bool HasSubstructMatch(RDKit::MolBundle,RDKit::ROMol,RDKit::SubstructMatchParameters)
        """
    @typing.overload
    def HasSubstructMatch(self, query: MolBundle, params: SubstructMatchParameters) -> bool:
        """
            Queries whether or not any molecule in the first bundle matches any molecule in the second bundle.
            
              ARGUMENTS:
                - query: a MolBundle
            
                - params: parameters controlling the substructure match
            
              RETURNS: True or False
            
        
            C++ signature :
                bool HasSubstructMatch(RDKit::MolBundle,RDKit::MolBundle,RDKit::SubstructMatchParameters)
        """
    def Size(self) -> int:
        """
            C++ signature :
                unsigned long Size(RDKit::MolBundle {lvalue})
        """
    def ToBinary(self) -> typing.Any:
        """
            Returns a binary string representation of the MolBundle.
            
        
            C++ signature :
                boost::python::api::object ToBinary(RDKit::MolBundle)
        """
    def __getinitargs__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getinitargs__(RDKit::MolBundle)
        """
    def __getitem__(self, idx: int) -> Mol:
        """
            C++ signature :
                boost::shared_ptr<RDKit::ROMol> __getitem__(RDKit::MolBundle {lvalue},unsigned long)
        """
    def __getstate__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getstate__(boost::python::api::object)
        """
    @typing.overload
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    @typing.overload
    def __init__(self, pkl: str) -> None:
        """
            C++ signature :
                void __init__(_object*,std::string)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(RDKit::MolBundle {lvalue})
        """
    def __setstate__(self, data: tuple) -> None:
        """
            C++ signature :
                void __setstate__(boost::python::api::object,boost::python::tuple)
        """
class MolSanitizeException(ValueError):
    pass
class PeriodicTable(Boost.Python.instance):
    """
    A class which stores information from the Periodic Table.
    
      It is not possible to create a PeriodicTable object directly from Python,
      use GetPeriodicTable() to get the global table.
    
      The PeriodicTable object can be queried for a variety of properties:
    
        - GetAtomicWeight
    
        - GetAtomicNumber
    
        - GetElementSymbol
    
        - GetElementName
    
        - GetRow
    
        - GetRvdw (van der Waals radius)
    
        - GetRCovalent (covalent radius)
    
        - GetDefaultValence
    
        - GetValenceList
    
        - GetNOuterElecs (number of valence electrons)
    
        - GetMostCommonIsotope
    
        - GetMostCommonIsotopeMass
    
        - GetRb0
    
        - GetAbundanceForIsotope
    
        - GetMassForIsotope
    
      When it makes sense, these can be queried using either an atomic number (integer)
      or an atomic symbol (string)
    
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
    @typing.overload
    def GetAbundanceForIsotope(self, atomicNumber: int, isotope: int) -> float:
        """
            C++ signature :
                double GetAbundanceForIsotope(RDKit::PeriodicTable {lvalue},unsigned int,unsigned int)
        """
    @typing.overload
    def GetAbundanceForIsotope(self, elementSymbol: str, isotope: int) -> float:
        """
            C++ signature :
                double GetAbundanceForIsotope(RDKit::PeriodicTable {lvalue},std::string,unsigned int)
        """
    def GetAtomicNumber(self, elementSymbol: str) -> int:
        """
            C++ signature :
                int GetAtomicNumber(RDKit::PeriodicTable {lvalue},std::string)
        """
    @typing.overload
    def GetAtomicWeight(self, atomicNumber: int) -> float:
        """
            C++ signature :
                double GetAtomicWeight(RDKit::PeriodicTable {lvalue},unsigned int)
        """
    @typing.overload
    def GetAtomicWeight(self, elementSymbol: str) -> float:
        """
            C++ signature :
                double GetAtomicWeight(RDKit::PeriodicTable {lvalue},std::string)
        """
    @typing.overload
    def GetDefaultValence(self, atomicNumber: int) -> int:
        """
            C++ signature :
                int GetDefaultValence(RDKit::PeriodicTable {lvalue},unsigned int)
        """
    @typing.overload
    def GetDefaultValence(self, elementSymbol: str) -> int:
        """
            C++ signature :
                int GetDefaultValence(RDKit::PeriodicTable {lvalue},std::string)
        """
    def GetElementName(self, atomicNumber: int) -> str:
        """
            C++ signature :
                std::string GetElementName(RDKit::PeriodicTable {lvalue},unsigned int)
        """
    def GetElementSymbol(self, atomicNumber: int) -> str:
        """
            C++ signature :
                std::string GetElementSymbol(RDKit::PeriodicTable {lvalue},unsigned int)
        """
    @typing.overload
    def GetMassForIsotope(self, atomicNumber: int, isotope: int) -> float:
        """
            C++ signature :
                double GetMassForIsotope(RDKit::PeriodicTable {lvalue},unsigned int,unsigned int)
        """
    @typing.overload
    def GetMassForIsotope(self, elementSymbol: str, isotope: int) -> float:
        """
            C++ signature :
                double GetMassForIsotope(RDKit::PeriodicTable {lvalue},std::string,unsigned int)
        """
    def GetMaxAtomicNumber(self) -> int:
        """
            C++ signature :
                unsigned int GetMaxAtomicNumber(RDKit::PeriodicTable {lvalue})
        """
    @typing.overload
    def GetMostCommonIsotope(self, atomicNumber: int) -> int:
        """
            C++ signature :
                int GetMostCommonIsotope(RDKit::PeriodicTable {lvalue},unsigned int)
        """
    @typing.overload
    def GetMostCommonIsotope(self, elementSymbol: str) -> int:
        """
            C++ signature :
                int GetMostCommonIsotope(RDKit::PeriodicTable {lvalue},std::string)
        """
    @typing.overload
    def GetMostCommonIsotopeMass(self, atomicNumber: int) -> float:
        """
            C++ signature :
                double GetMostCommonIsotopeMass(RDKit::PeriodicTable {lvalue},unsigned int)
        """
    @typing.overload
    def GetMostCommonIsotopeMass(self, elementSymbol: str) -> float:
        """
            C++ signature :
                double GetMostCommonIsotopeMass(RDKit::PeriodicTable {lvalue},std::string)
        """
    @typing.overload
    def GetNOuterElecs(self, atomicNumber: int) -> int:
        """
            C++ signature :
                int GetNOuterElecs(RDKit::PeriodicTable {lvalue},unsigned int)
        """
    @typing.overload
    def GetNOuterElecs(self, elementSymbol: str) -> int:
        """
            C++ signature :
                int GetNOuterElecs(RDKit::PeriodicTable {lvalue},std::string)
        """
    @typing.overload
    def GetRb0(self, atomicNumber: int) -> float:
        """
            C++ signature :
                double GetRb0(RDKit::PeriodicTable {lvalue},unsigned int)
        """
    @typing.overload
    def GetRb0(self, elementSymbol: str) -> float:
        """
            C++ signature :
                double GetRb0(RDKit::PeriodicTable {lvalue},std::string)
        """
    @typing.overload
    def GetRcovalent(self, atomicNumber: int) -> float:
        """
            C++ signature :
                double GetRcovalent(RDKit::PeriodicTable {lvalue},unsigned int)
        """
    @typing.overload
    def GetRcovalent(self, elementSymbol: str) -> float:
        """
            C++ signature :
                double GetRcovalent(RDKit::PeriodicTable {lvalue},std::string)
        """
    @typing.overload
    def GetRow(self, atomicNumber: int) -> int:
        """
            C++ signature :
                unsigned int GetRow(RDKit::PeriodicTable {lvalue},unsigned int)
        """
    @typing.overload
    def GetRow(self, elementSymbol: str) -> int:
        """
            C++ signature :
                unsigned int GetRow(RDKit::PeriodicTable {lvalue},std::string)
        """
    @typing.overload
    def GetRvdw(self, atomicNumber: int) -> float:
        """
            C++ signature :
                double GetRvdw(RDKit::PeriodicTable {lvalue},unsigned int)
        """
    @typing.overload
    def GetRvdw(self, elementSymbol: str) -> float:
        """
            C++ signature :
                double GetRvdw(RDKit::PeriodicTable {lvalue},std::string)
        """
    @typing.overload
    def GetValenceList(self, atomicNumber: int) -> typing.Sequence[int]:
        """
            C++ signature :
                std::vector<int, std::allocator<int> > GetValenceList(RDKit::PeriodicTable {lvalue},unsigned int)
        """
    @typing.overload
    def GetValenceList(self, elementSymbol: str) -> typing.Sequence[int]:
        """
            C++ signature :
                std::vector<int, std::allocator<int> > GetValenceList(RDKit::PeriodicTable {lvalue},std::string)
        """
class PropertyPickleOptions(Boost.Python.enum):
    AllProps: typing.ClassVar[PropertyPickleOptions]  # value = rdkit.Chem.rdchem.PropertyPickleOptions.AllProps
    AtomProps: typing.ClassVar[PropertyPickleOptions]  # value = rdkit.Chem.rdchem.PropertyPickleOptions.AtomProps
    BondProps: typing.ClassVar[PropertyPickleOptions]  # value = rdkit.Chem.rdchem.PropertyPickleOptions.BondProps
    ComputedProps: typing.ClassVar[PropertyPickleOptions]  # value = rdkit.Chem.rdchem.PropertyPickleOptions.ComputedProps
    CoordsAsDouble: typing.ClassVar[PropertyPickleOptions]  # value = rdkit.Chem.rdchem.PropertyPickleOptions.CoordsAsDouble
    MolProps: typing.ClassVar[PropertyPickleOptions]  # value = rdkit.Chem.rdchem.PropertyPickleOptions.MolProps
    NoConformers: typing.ClassVar[PropertyPickleOptions]  # value = rdkit.Chem.rdchem.PropertyPickleOptions.NoConformers
    NoProps: typing.ClassVar[PropertyPickleOptions]  # value = rdkit.Chem.rdchem.PropertyPickleOptions.NoProps
    PrivateProps: typing.ClassVar[PropertyPickleOptions]  # value = rdkit.Chem.rdchem.PropertyPickleOptions.PrivateProps
    QueryAtomData: typing.ClassVar[PropertyPickleOptions]  # value = rdkit.Chem.rdchem.PropertyPickleOptions.QueryAtomData
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'NoProps': rdkit.Chem.rdchem.PropertyPickleOptions.NoProps, 'MolProps': rdkit.Chem.rdchem.PropertyPickleOptions.MolProps, 'AtomProps': rdkit.Chem.rdchem.PropertyPickleOptions.AtomProps, 'BondProps': rdkit.Chem.rdchem.PropertyPickleOptions.BondProps, 'QueryAtomData': rdkit.Chem.rdchem.PropertyPickleOptions.QueryAtomData, 'PrivateProps': rdkit.Chem.rdchem.PropertyPickleOptions.PrivateProps, 'ComputedProps': rdkit.Chem.rdchem.PropertyPickleOptions.ComputedProps, 'AllProps': rdkit.Chem.rdchem.PropertyPickleOptions.AllProps, 'CoordsAsDouble': rdkit.Chem.rdchem.PropertyPickleOptions.CoordsAsDouble, 'NoConformers': rdkit.Chem.rdchem.PropertyPickleOptions.NoConformers}
    values: typing.ClassVar[dict]  # value = {0: rdkit.Chem.rdchem.PropertyPickleOptions.NoProps, 1: rdkit.Chem.rdchem.PropertyPickleOptions.MolProps, 2: rdkit.Chem.rdchem.PropertyPickleOptions.QueryAtomData, 4: rdkit.Chem.rdchem.PropertyPickleOptions.BondProps, 16: rdkit.Chem.rdchem.PropertyPickleOptions.PrivateProps, 32: rdkit.Chem.rdchem.PropertyPickleOptions.ComputedProps, 65535: rdkit.Chem.rdchem.PropertyPickleOptions.AllProps, 65536: rdkit.Chem.rdchem.PropertyPickleOptions.CoordsAsDouble, 131072: rdkit.Chem.rdchem.PropertyPickleOptions.NoConformers}
class QueryAtom(Atom):
    """
    The class to store QueryAtoms.
    These cannot currently be constructed directly from Python
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
    def ExpandQuery(self, other: QueryAtom, how: CompositeQueryType = ..., maintainOrder: bool = True) -> None:
        """
            combines the query from other with ours
        
            C++ signature :
                void ExpandQuery(RDKit::QueryAtom*,RDKit::QueryAtom const* [,Queries::CompositeQueryType=rdkit.Chem.rdchem.CompositeQueryType.COMPOSITE_AND [,bool=True]])
        """
    def SetQuery(self, other: QueryAtom) -> None:
        """
            Replace our query with a copy of the other query
        
            C++ signature :
                void SetQuery(RDKit::QueryAtom*,RDKit::QueryAtom const*)
        """
class QueryBond(Bond):
    """
    The class to store QueryBonds.
    These cannot currently be constructed directly from Python
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
    def ExpandQuery(self, other: QueryBond, how: CompositeQueryType = ..., maintainOrder: bool = True) -> None:
        """
            combines the query from other with ours
        
            C++ signature :
                void ExpandQuery(RDKit::QueryBond*,RDKit::QueryBond const* [,Queries::CompositeQueryType=rdkit.Chem.rdchem.CompositeQueryType.COMPOSITE_AND [,bool=True]])
        """
    def SetQuery(self, other: QueryBond) -> None:
        """
            Replace our query with a copy of the other query
        
            C++ signature :
                void SetQuery(RDKit::QueryBond*,RDKit::QueryBond const*)
        """
class RWMol(Mol):
    """
    The RW molecule class (read/write)
    
      This class is a more-performant version of the EditableMolecule class in that
      it is a 'live' molecule and shares the interface from the Mol class.
      All changes are performed without the need to create a copy of the
      molecule using GetMol() (this is still available, however).
      
      n.b. Eventually this class may become a direct replacement for EditableMol
    """
    __getstate_manages_dict__: typing.ClassVar[bool] = True
    __instance_size__: typing.ClassVar[int] = 320
    __safe_for_unpickling__: typing.ClassVar[bool] = True
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def AddAtom(self, atom: Atom) -> int:
        """
            add an atom, returns the index of the newly added atom
        
            C++ signature :
                int AddAtom(RDKit::ReadWriteMol {lvalue},RDKit::Atom*)
        """
    def AddBond(self, beginAtomIdx: int, endAtomIdx: int, order: BondType = ...) -> int:
        """
            add a bond, returns the new number of bonds
        
            C++ signature :
                int AddBond(RDKit::ReadWriteMol {lvalue},unsigned int,unsigned int [,RDKit::Bond::BondType=rdkit.Chem.rdchem.BondType.UNSPECIFIED])
        """
    def BeginBatchEdit(self) -> None:
        """
            starts batch editing
        
            C++ signature :
                void BeginBatchEdit(RDKit::ReadWriteMol {lvalue})
        """
    def CommitBatchEdit(self) -> None:
        """
            finishes batch editing and makes the actual changes
        
            C++ signature :
                void CommitBatchEdit(RDKit::ReadWriteMol {lvalue})
        """
    def GetMol(self) -> Mol:
        """
            Returns a Mol (a normal molecule)
        
            C++ signature :
                RDKit::ROMol* GetMol(RDKit::ReadWriteMol {lvalue})
        """
    def InsertMol(self, mol: Mol) -> None:
        """
            Insert (add) the given molecule into this one
        
            C++ signature :
                void InsertMol(RDKit::ReadWriteMol {lvalue},RDKit::ROMol)
        """
    def RemoveAtom(self, idx: int) -> None:
        """
            Remove the specified atom from the molecule
        
            C++ signature :
                void RemoveAtom(RDKit::ReadWriteMol {lvalue},unsigned int)
        """
    def RemoveBond(self, idx1: int, idx2: int) -> None:
        """
            Remove the specified bond from the molecule
        
            C++ signature :
                void RemoveBond(RDKit::ReadWriteMol {lvalue},unsigned int,unsigned int)
        """
    def ReplaceAtom(self, index: int, newAtom: Atom, updateLabel: bool = False, preserveProps: bool = False) -> None:
        """
            replaces the specified atom with the provided one
            If updateLabel is True, the new atom becomes the active atom
            If preserveProps is True preserve keep the existing props unless explicit set on the new atom
        
            C++ signature :
                void ReplaceAtom(RDKit::ReadWriteMol {lvalue},unsigned int,RDKit::Atom* [,bool=False [,bool=False]])
        """
    def ReplaceBond(self, index: int, newBond: Bond, preserveProps: bool = False, keepSGroups: bool = True) -> None:
        """
            replaces the specified bond with the provided one.
            If preserveProps is True preserve keep the existing props unless explicit set on the new bond. If keepSGroups is False, allSubstance Groups referencing the bond will be dropped.
        
            C++ signature :
                void ReplaceBond(RDKit::ReadWriteMol {lvalue},unsigned int,RDKit::Bond* [,bool=False [,bool=True]])
        """
    def RollbackBatchEdit(self) -> None:
        """
            cancels batch editing
        
            C++ signature :
                void RollbackBatchEdit(RDKit::ReadWriteMol {lvalue})
        """
    def SetStereoGroups(self, stereo_groups: list) -> None:
        """
            Set the stereo groups
        
            C++ signature :
                void SetStereoGroups(RDKit::ReadWriteMol {lvalue},boost::python::list {lvalue})
        """
    def __copy__(self) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __copy__(boost::python::api::object)
        """
    def __deepcopy__(self, memo: dict) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __deepcopy__(boost::python::api::object,boost::python::dict)
        """
    def __enter__(self) -> RWMol:
        """
            C++ signature :
                RDKit::ReadWriteMol* __enter__(RDKit::ReadWriteMol {lvalue})
        """
    def __exit__(self, exc_type: typing.Any, exc_value: typing.Any, traceback: typing.Any) -> bool:
        """
            C++ signature :
                bool __exit__(RDKit::ReadWriteMol {lvalue},boost::python::api::object,boost::python::api::object,boost::python::api::object)
        """
    def __getinitargs__(self: Mol) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getinitargs__(RDKit::ROMol)
        """
    def __getstate__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getstate__(boost::python::api::object)
        """
    @typing.overload
    def __init__(self, m: Mol) -> None:
        """
            Construct from a Mol
        
            C++ signature :
                void __init__(_object*,RDKit::ROMol)
        """
    @typing.overload
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    @typing.overload
    def __init__(self, pklString: str) -> None:
        """
            C++ signature :
                void __init__(_object*,std::string)
        """
    @typing.overload
    def __init__(self, pklString: str, propertyFlags: int) -> None:
        """
            C++ signature :
                void __init__(_object*,std::string,unsigned int)
        """
    @typing.overload
    def __init__(self, mol: Mol, quickCopy: bool = False, confId: int = -1) -> None:
        """
            C++ signature :
                void __init__(_object*,RDKit::ROMol [,bool=False [,int=-1]])
        """
    def __setstate__(self, data: tuple) -> None:
        """
            C++ signature :
                void __setstate__(boost::python::api::object,boost::python::tuple)
        """
class ResonanceFlags(Boost.Python.enum):
    ALLOW_CHARGE_SEPARATION: typing.ClassVar[ResonanceFlags]  # value = rdkit.Chem.rdchem.ResonanceFlags.ALLOW_CHARGE_SEPARATION
    ALLOW_INCOMPLETE_OCTETS: typing.ClassVar[ResonanceFlags]  # value = rdkit.Chem.rdchem.ResonanceFlags.ALLOW_INCOMPLETE_OCTETS
    KEKULE_ALL: typing.ClassVar[ResonanceFlags]  # value = rdkit.Chem.rdchem.ResonanceFlags.KEKULE_ALL
    UNCONSTRAINED_ANIONS: typing.ClassVar[ResonanceFlags]  # value = rdkit.Chem.rdchem.ResonanceFlags.UNCONSTRAINED_ANIONS
    UNCONSTRAINED_CATIONS: typing.ClassVar[ResonanceFlags]  # value = rdkit.Chem.rdchem.ResonanceFlags.UNCONSTRAINED_CATIONS
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'ALLOW_INCOMPLETE_OCTETS': rdkit.Chem.rdchem.ResonanceFlags.ALLOW_INCOMPLETE_OCTETS, 'ALLOW_CHARGE_SEPARATION': rdkit.Chem.rdchem.ResonanceFlags.ALLOW_CHARGE_SEPARATION, 'KEKULE_ALL': rdkit.Chem.rdchem.ResonanceFlags.KEKULE_ALL, 'UNCONSTRAINED_CATIONS': rdkit.Chem.rdchem.ResonanceFlags.UNCONSTRAINED_CATIONS, 'UNCONSTRAINED_ANIONS': rdkit.Chem.rdchem.ResonanceFlags.UNCONSTRAINED_ANIONS}
    values: typing.ClassVar[dict]  # value = {1: rdkit.Chem.rdchem.ResonanceFlags.ALLOW_INCOMPLETE_OCTETS, 2: rdkit.Chem.rdchem.ResonanceFlags.ALLOW_CHARGE_SEPARATION, 4: rdkit.Chem.rdchem.ResonanceFlags.KEKULE_ALL, 8: rdkit.Chem.rdchem.ResonanceFlags.UNCONSTRAINED_CATIONS, 16: rdkit.Chem.rdchem.ResonanceFlags.UNCONSTRAINED_ANIONS}
class ResonanceMolSupplier(Boost.Python.instance):
    """
    A class which supplies resonance structures (as mols) from a mol.
    
      Usage examples:
    
        1) Lazy evaluation: the resonance structures are not constructed
           until we ask for them:
    
           >>> suppl = ResonanceMolSupplier(mol)
           >>> for resMol in suppl:
           ...    resMol.GetNumAtoms()
    
        2) Lazy evaluation 2:
    
           >>> suppl = ResonanceMolSupplier(mol)
           >>> resMol1 = next(suppl)
           >>> resMol2 = next(suppl)
           >>> suppl.reset()
           >>> resMol3 = next(suppl)
           # resMol3 and resMol1 are the same: 
           >>> MolToSmiles(resMol3)==MolToSmiles(resMol1)
    
        3) Random Access:
    
           >>> suppl = ResonanceMolSupplier(mol)
           >>> resMol1 = suppl[0] 
           >>> resMol2 = suppl[1] 
    
           NOTE: this will generate an IndexError if the supplier doesn't have that many
           molecules.
    
        4) Random Access 2: looping over all resonance structures
           >>> suppl = ResonanceMolSupplier(mol)
           >>> nResMols = len(suppl)
           >>> for i in range(nResMols):
           ...   suppl[i].GetNumAtoms()
    
    """
    __instance_size__: typing.ClassVar[int] = 168
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def Enumerate(self) -> None:
        """
            Ask ResonanceMolSupplier to enumerate resonance structures(automatically done as soon as any attempt to access them is made).
            
        
            C++ signature :
                void Enumerate(RDKit::ResonanceMolSupplier {lvalue})
        """
    def GetAtomConjGrpIdx(self, ai: int) -> int:
        """
            Given an atom index, it returns the index of the conjugated groupthe atom belongs to, or -1 if it is not conjugated.
            
        
            C++ signature :
                unsigned int GetAtomConjGrpIdx(RDKit::ResonanceMolSupplier {lvalue},unsigned int)
        """
    def GetBondConjGrpIdx(self, bi: int) -> int:
        """
            Given a bond index, it returns the index of the conjugated groupthe bond belongs to, or -1 if it is not conjugated.
            
        
            C++ signature :
                unsigned int GetBondConjGrpIdx(RDKit::ResonanceMolSupplier {lvalue},unsigned int)
        """
    def GetIsEnumerated(self) -> bool:
        """
            Returns true if resonance structure enumeration has already happened.
            
        
            C++ signature :
                bool GetIsEnumerated(RDKit::ResonanceMolSupplier {lvalue})
        """
    def GetNumConjGrps(self) -> int:
        """
            Returns the number of individual conjugated groups in the molecule.
            
        
            C++ signature :
                unsigned int GetNumConjGrps(RDKit::ResonanceMolSupplier {lvalue})
        """
    def GetProgressCallback(self) -> typing.Any:
        """
            Get the ResonanceMolSupplierCallback subclass instance,
            or None if none was set.
            
        
            C++ signature :
                boost::python::api::object GetProgressCallback(RDKit::ResonanceMolSupplier)
        """
    def GetSubstructMatch(self, query: Mol, useChirality: bool = False, useQueryQueryMatches: bool = False) -> typing.Any:
        """
            Returns the indices of the molecule's atoms that match a substructure query,
            taking into account all resonance structures in ResonanceMolSupplier.
            
              ARGUMENTS:
                - query: a Molecule
            
                - useChirality: enables the use of stereochemistry in the matching
            
                - useQueryQueryMatches: use query-query matching logic
            
              RETURNS: a tuple of integers
            
              NOTES:
                 - only a single match is returned
                 - the ordering of the indices corresponds to the atom ordering
                     in the query. For example, the first index is for the atom in
                     this molecule that matches the first atom in the query.
            
        
            C++ signature :
                _object* GetSubstructMatch(RDKit::ResonanceMolSupplier {lvalue},RDKit::ROMol [,bool=False [,bool=False]])
        """
    def GetSubstructMatches(self, query: Mol, uniquify: bool = False, useChirality: bool = False, useQueryQueryMatches: bool = False, maxMatches: int = 1000, numThreads: int = 1) -> typing.Any:
        """
            Returns tuples of the indices of the molecule's atoms that match a substructure query,
            taking into account all resonance structures in ResonanceMolSupplier.
            
              ARGUMENTS:
                - query: a Molecule.
                - uniquify: (optional) determines whether or not the matches are uniquified.
                            Defaults to 1.
            
                - useChirality: enables the use of stereochemistry in the matching
            
                - useQueryQueryMatches: use query-query matching logic
            
                - maxMatches: The maximum number of matches that will be returned.
                              In high-symmetry cases with medium-sized molecules, it is
                              very easy to end up with a combinatorial explosion in the
                              number of possible matches. This argument prevents that from
                              having unintended consequences
            
                - numThreads: The number of threads to be used (defaults to 1; 0 selects the
                              number of concurrent threads supported by the hardware; negative
                              values are added to the number of concurrent threads supported
                              by the hardware).
            
              RETURNS: a tuple of tuples of integers
            
              NOTE:
                 - the ordering of the indices corresponds to the atom ordering
                     in the query. For example, the first index is for the atom in
                     this molecule that matches the first atom in the query.
            
        
            C++ signature :
                _object* GetSubstructMatches(RDKit::ResonanceMolSupplier {lvalue},RDKit::ROMol [,bool=False [,bool=False [,bool=False [,unsigned int=1000 [,int=1]]]]])
        """
    def SetNumThreads(self, numThreads: int) -> None:
        """
            Sets the number of threads to be used to enumerate resonance
            structures (defaults to 1; 0 selects the number of concurrent
            threads supported by the hardware; negative values are added
            to the number of concurrent threads supported by the hardware).
            
        
            C++ signature :
                void SetNumThreads(RDKit::ResonanceMolSupplier {lvalue},unsigned int)
        """
    def SetProgressCallback(self, callback: typing.Any) -> None:
        """
            Pass an instance of a class derived from
            ResonanceMolSupplierCallback, which must implement the
            __call__() method.
            
        
            C++ signature :
                void SetProgressCallback(RDKit::ResonanceMolSupplier {lvalue},_object*)
        """
    def WasCanceled(self) -> bool:
        """
            Returns True if the resonance structure generation was canceled.
            
        
            C++ signature :
                bool WasCanceled(RDKit::ResonanceMolSupplier {lvalue})
        """
    def __getitem__(self, idx: int) -> Mol:
        """
            C++ signature :
                RDKit::ROMol* __getitem__(RDKit::ResonanceMolSupplier*,int)
        """
    def __init__(self, mol: Mol, flags: int = 0, maxStructs: int = 1000) -> None:
        """
            C++ signature :
                void __init__(_object*,RDKit::ROMol {lvalue} [,unsigned int=0 [,unsigned int=1000]])
        """
    def __iter__(self) -> ResonanceMolSupplier:
        """
            C++ signature :
                RDKit::ResonanceMolSupplier* __iter__(RDKit::ResonanceMolSupplier*)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned int __len__(RDKit::ResonanceMolSupplier {lvalue})
        """
    def __next__(self) -> Mol:
        """
            Returns the next resonance structure in the supplier. Raises _StopIteration_ on end.
            
        
            C++ signature :
                RDKit::ROMol* __next__(RDKit::ResonanceMolSupplier*)
        """
    def atEnd(self) -> bool:
        """
            Returns whether or not we have hit the end of the resonance structure supplier.
            
        
            C++ signature :
                bool atEnd(RDKit::ResonanceMolSupplier {lvalue})
        """
    def reset(self) -> None:
        """
            Resets our position in the resonance structure supplier to the beginning.
            
        
            C++ signature :
                void reset(RDKit::ResonanceMolSupplier {lvalue})
        """
class ResonanceMolSupplierCallback(Boost.Python.instance):
    """
    Create a derived class from this abstract base class and
        implement the __call__() method.
        The __call__() method is called at each iteration of the
        algorithm, and provides a mechanism to monitor or stop
        its progress.
    
        To have your callback called, pass an instance of your
        derived class to ResonanceMolSupplier.SetProgressCallback()
    """
    __instance_size__: typing.ClassVar[int] = 88
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def GetMaxStructures(self) -> int:
        """
            Get the number of conjugated groups this molecule has.
            
        
            C++ signature :
                unsigned long GetMaxStructures(RDKit::PyResonanceMolSupplierCallback {lvalue})
        """
    def GetNumConjGrps(self) -> int:
        """
            Returns the number of individual conjugated groups in the molecule.
            
        
            C++ signature :
                unsigned int GetNumConjGrps(RDKit::PyResonanceMolSupplierCallback {lvalue})
        """
    def GetNumDiverseStructures(self, conjGrpIdx: int) -> int:
        """
            Get the number of non-degenrate resonance structures generated so far for the passed conjugated group index.
            
        
            C++ signature :
                unsigned long GetNumDiverseStructures(RDKit::PyResonanceMolSupplierCallback {lvalue},unsigned int)
        """
    def GetNumStructures(self, conjGrpIdx: int) -> int:
        """
            Get the number of resonance structures generated so far for the passed conjugated group index.
            
        
            C++ signature :
                unsigned long GetNumStructures(RDKit::PyResonanceMolSupplierCallback {lvalue},unsigned int)
        """
    @typing.overload
    def __call__(self) -> bool:
        """
            This must be implemented in the derived class. Return True if the resonance structure generation should continue; False if the resonance structure generation should stop.
            
        
            C++ signature :
                bool __call__(RDKit::PyResonanceMolSupplierCallback {lvalue})
        """
    @typing.overload
    def __call__(self) -> None:
        """
            C++ signature :
                void __call__(RDKit::PyResonanceMolSupplierCallback {lvalue})
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
class RingInfo(Boost.Python.instance):
    """
    contains information about a molecule's rings
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
    def AddRing(self, atomIds: typing.Any, bondIds: typing.Any) -> None:
        """
            Adds a ring to the set. Be very careful with this operation.
        
            C++ signature :
                void AddRing(RDKit::RingInfo*,boost::python::api::object,boost::python::api::object)
        """
    def AreAtomsInSameRing(self, idx1: int, idx2: int) -> bool:
        """
            C++ signature :
                bool AreAtomsInSameRing(RDKit::RingInfo {lvalue},unsigned int,unsigned int)
        """
    def AreAtomsInSameRingOfSize(self, idx1: int, idx2: int, size: int) -> bool:
        """
            C++ signature :
                bool AreAtomsInSameRingOfSize(RDKit::RingInfo {lvalue},unsigned int,unsigned int,unsigned int)
        """
    def AreBondsInSameRing(self, idx1: int, idx2: int) -> bool:
        """
            C++ signature :
                bool AreBondsInSameRing(RDKit::RingInfo {lvalue},unsigned int,unsigned int)
        """
    def AreBondsInSameRingOfSize(self, idx1: int, idx2: int, size: int) -> bool:
        """
            C++ signature :
                bool AreBondsInSameRingOfSize(RDKit::RingInfo {lvalue},unsigned int,unsigned int,unsigned int)
        """
    def AreRingFamiliesInitialized(self) -> bool:
        """
            C++ signature :
                bool AreRingFamiliesInitialized(RDKit::RingInfo {lvalue})
        """
    def AreRingsFused(self, ring1Idx: int, ring2Idx: int) -> bool:
        """
            C++ signature :
                bool AreRingsFused(RDKit::RingInfo {lvalue},unsigned int,unsigned int)
        """
    def AtomMembers(self, idx: int) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object AtomMembers(RDKit::RingInfo const*,unsigned int)
        """
    def AtomRingFamilies(self) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object AtomRingFamilies(RDKit::RingInfo const*)
        """
    def AtomRingSizes(self, idx: int) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object AtomRingSizes(RDKit::RingInfo const*,unsigned int)
        """
    def AtomRings(self) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object AtomRings(RDKit::RingInfo const*)
        """
    def BondMembers(self, idx: int) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object BondMembers(RDKit::RingInfo const*,unsigned int)
        """
    def BondRingFamilies(self) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object BondRingFamilies(RDKit::RingInfo const*)
        """
    def BondRingSizes(self, idx: int) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object BondRingSizes(RDKit::RingInfo const*,unsigned int)
        """
    def BondRings(self) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object BondRings(RDKit::RingInfo const*)
        """
    def IsAtomInRingOfSize(self, idx: int, size: int) -> bool:
        """
            C++ signature :
                bool IsAtomInRingOfSize(RDKit::RingInfo {lvalue},unsigned int,unsigned int)
        """
    def IsBondInRingOfSize(self, idx: int, size: int) -> bool:
        """
            C++ signature :
                bool IsBondInRingOfSize(RDKit::RingInfo {lvalue},unsigned int,unsigned int)
        """
    def IsRingFused(self, ringIdx: int) -> bool:
        """
            C++ signature :
                bool IsRingFused(RDKit::RingInfo {lvalue},unsigned int)
        """
    def MinAtomRingSize(self, idx: int) -> int:
        """
            C++ signature :
                unsigned int MinAtomRingSize(RDKit::RingInfo {lvalue},unsigned int)
        """
    def MinBondRingSize(self, idx: int) -> int:
        """
            C++ signature :
                unsigned int MinBondRingSize(RDKit::RingInfo {lvalue},unsigned int)
        """
    def NumAtomRings(self, idx: int) -> int:
        """
            C++ signature :
                unsigned int NumAtomRings(RDKit::RingInfo {lvalue},unsigned int)
        """
    def NumBondRings(self, idx: int) -> int:
        """
            C++ signature :
                unsigned int NumBondRings(RDKit::RingInfo {lvalue},unsigned int)
        """
    def NumFusedBonds(self, ringIdx: int) -> int:
        """
            C++ signature :
                unsigned int NumFusedBonds(RDKit::RingInfo {lvalue},unsigned int)
        """
    def NumRelevantCycles(self) -> int:
        """
            C++ signature :
                unsigned int NumRelevantCycles(RDKit::RingInfo {lvalue})
        """
    def NumRingFamilies(self) -> int:
        """
            C++ signature :
                unsigned int NumRingFamilies(RDKit::RingInfo {lvalue})
        """
    def NumRings(self) -> int:
        """
            C++ signature :
                unsigned int NumRings(RDKit::RingInfo {lvalue})
        """
class StereoDescriptor(Boost.Python.enum):
    Bond_Cis: typing.ClassVar[StereoDescriptor]  # value = rdkit.Chem.rdchem.StereoDescriptor.Bond_Cis
    Bond_Trans: typing.ClassVar[StereoDescriptor]  # value = rdkit.Chem.rdchem.StereoDescriptor.Bond_Trans
    NoValue: typing.ClassVar[StereoDescriptor]  # value = rdkit.Chem.rdchem.StereoDescriptor.NoValue
    Tet_CCW: typing.ClassVar[StereoDescriptor]  # value = rdkit.Chem.rdchem.StereoDescriptor.Tet_CCW
    Tet_CW: typing.ClassVar[StereoDescriptor]  # value = rdkit.Chem.rdchem.StereoDescriptor.Tet_CW
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'NoValue': rdkit.Chem.rdchem.StereoDescriptor.NoValue, 'Tet_CW': rdkit.Chem.rdchem.StereoDescriptor.Tet_CW, 'Tet_CCW': rdkit.Chem.rdchem.StereoDescriptor.Tet_CCW, 'Bond_Cis': rdkit.Chem.rdchem.StereoDescriptor.Bond_Cis, 'Bond_Trans': rdkit.Chem.rdchem.StereoDescriptor.Bond_Trans}
    values: typing.ClassVar[dict]  # value = {0: rdkit.Chem.rdchem.StereoDescriptor.NoValue, 1: rdkit.Chem.rdchem.StereoDescriptor.Tet_CW, 2: rdkit.Chem.rdchem.StereoDescriptor.Tet_CCW, 3: rdkit.Chem.rdchem.StereoDescriptor.Bond_Cis, 4: rdkit.Chem.rdchem.StereoDescriptor.Bond_Trans}
class StereoGroup(Boost.Python.instance):
    """
    A collection of atoms with a defined stereochemical relationship.
    
    Used to help represent a sample with unknown stereochemistry, or that is a mix
    of diastereomers.
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
    def GetAtoms(self) -> typing.Any:
        """
            access the atoms in the StereoGroup.
            
        
            C++ signature :
                boost::python::api::object GetAtoms(RDKit::StereoGroup {lvalue})
        """
    def GetGroupType(self) -> StereoGroupType:
        """
            Returns the StereoGroupType.
            
        
            C++ signature :
                RDKit::StereoGroupType GetGroupType(RDKit::StereoGroup {lvalue})
        """
    def GetReadId(self) -> int:
        """
            return the StereoGroup's original ID.
            Note that the ID only makes sense for AND/OR groups.
            
        
            C++ signature :
                unsigned int GetReadId(RDKit::StereoGroup {lvalue})
        """
    def GetWriteId(self) -> int:
        """
            return the StereoGroup's ID that will be exported.
            Note that the ID only makes sense for AND/OR groups.
            
        
            C++ signature :
                unsigned int GetWriteId(RDKit::StereoGroup {lvalue})
        """
    def SetWriteId(self, id: int) -> None:
        """
            return the StereoGroup's ID that will be exported.
            Note that the ID only makes sense for AND/OR groups.
            
        
            C++ signature :
                void SetWriteId(RDKit::StereoGroup {lvalue},unsigned int)
        """
class StereoGroupType(Boost.Python.enum):
    STEREO_ABSOLUTE: typing.ClassVar[StereoGroupType]  # value = rdkit.Chem.rdchem.StereoGroupType.STEREO_ABSOLUTE
    STEREO_AND: typing.ClassVar[StereoGroupType]  # value = rdkit.Chem.rdchem.StereoGroupType.STEREO_AND
    STEREO_OR: typing.ClassVar[StereoGroupType]  # value = rdkit.Chem.rdchem.StereoGroupType.STEREO_OR
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'STEREO_ABSOLUTE': rdkit.Chem.rdchem.StereoGroupType.STEREO_ABSOLUTE, 'STEREO_OR': rdkit.Chem.rdchem.StereoGroupType.STEREO_OR, 'STEREO_AND': rdkit.Chem.rdchem.StereoGroupType.STEREO_AND}
    values: typing.ClassVar[dict]  # value = {0: rdkit.Chem.rdchem.StereoGroupType.STEREO_ABSOLUTE, 1: rdkit.Chem.rdchem.StereoGroupType.STEREO_OR, 2: rdkit.Chem.rdchem.StereoGroupType.STEREO_AND}
class StereoGroup_vect(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<RDKit::StereoGroup, std::allocator<RDKit::StereoGroup> > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<RDKit::StereoGroup, std::allocator<RDKit::StereoGroup> > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<RDKit::StereoGroup, std::allocator<RDKit::StereoGroup> >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __iter__(self) -> typing.Any:
        """
            C++ signature :
                boost::python::objects::iterator_range<boost::python::return_internal_reference<1ul, boost::python::default_call_policies>, __gnu_cxx::__normal_iterator<RDKit::StereoGroup*, std::vector<RDKit::StereoGroup, std::allocator<RDKit::StereoGroup> > > > __iter__(boost::python::back_reference<std::vector<RDKit::StereoGroup, std::allocator<RDKit::StereoGroup> >&>)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<RDKit::StereoGroup, std::allocator<RDKit::StereoGroup> > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<RDKit::StereoGroup, std::allocator<RDKit::StereoGroup> > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<RDKit::StereoGroup, std::allocator<RDKit::StereoGroup> > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<RDKit::StereoGroup, std::allocator<RDKit::StereoGroup> > {lvalue},boost::python::api::object)
        """
class StereoInfo(Boost.Python.instance):
    """
    Class describing stereochemistry
    """
    NOATOM: typing.ClassVar[int] = 4294967295
    __instance_size__: typing.ClassVar[int] = 72
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    @property
    def centeredOn(*args, **kwargs):
        """
        index of the item the stereo concerns
        """
    @centeredOn.setter
    def centeredOn(*args, **kwargs):
        ...
    @property
    def controllingAtoms(*args, **kwargs):
        """
        indices of the atoms controlling the stereo
        """
    @property
    def descriptor(*args, **kwargs):
        """
        stereo descriptor
        """
    @descriptor.setter
    def descriptor(*args, **kwargs):
        ...
    @property
    def permutation(*args, **kwargs):
        """
        permutation index (used for non-tetrahedral chirality)
        """
    @permutation.setter
    def permutation(*args, **kwargs):
        ...
    @property
    def specified(*args, **kwargs):
        """
        whether or not it is specified
        """
    @specified.setter
    def specified(*args, **kwargs):
        ...
    @property
    def type(*args, **kwargs):
        """
        the type of stereo
        """
    @type.setter
    def type(*args, **kwargs):
        ...
class StereoSpecified(Boost.Python.enum):
    Specified: typing.ClassVar[StereoSpecified]  # value = rdkit.Chem.rdchem.StereoSpecified.Specified
    Unknown: typing.ClassVar[StereoSpecified]  # value = rdkit.Chem.rdchem.StereoSpecified.Unknown
    Unspecified: typing.ClassVar[StereoSpecified]  # value = rdkit.Chem.rdchem.StereoSpecified.Unspecified
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'Unspecified': rdkit.Chem.rdchem.StereoSpecified.Unspecified, 'Specified': rdkit.Chem.rdchem.StereoSpecified.Specified, 'Unknown': rdkit.Chem.rdchem.StereoSpecified.Unknown}
    values: typing.ClassVar[dict]  # value = {0: rdkit.Chem.rdchem.StereoSpecified.Unspecified, 1: rdkit.Chem.rdchem.StereoSpecified.Specified, 2: rdkit.Chem.rdchem.StereoSpecified.Unknown}
class StereoType(Boost.Python.enum):
    Atom_Octahedral: typing.ClassVar[StereoType]  # value = rdkit.Chem.rdchem.StereoType.Atom_Octahedral
    Atom_SquarePlanar: typing.ClassVar[StereoType]  # value = rdkit.Chem.rdchem.StereoType.Atom_SquarePlanar
    Atom_Tetrahedral: typing.ClassVar[StereoType]  # value = rdkit.Chem.rdchem.StereoType.Atom_Tetrahedral
    Atom_TrigonalBipyramidal: typing.ClassVar[StereoType]  # value = rdkit.Chem.rdchem.StereoType.Atom_TrigonalBipyramidal
    Bond_Atropisomer: typing.ClassVar[StereoType]  # value = rdkit.Chem.rdchem.StereoType.Bond_Atropisomer
    Bond_Cumulene_Even: typing.ClassVar[StereoType]  # value = rdkit.Chem.rdchem.StereoType.Bond_Cumulene_Even
    Bond_Double: typing.ClassVar[StereoType]  # value = rdkit.Chem.rdchem.StereoType.Bond_Double
    Unspecified: typing.ClassVar[StereoType]  # value = rdkit.Chem.rdchem.StereoType.Unspecified
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'Unspecified': rdkit.Chem.rdchem.StereoType.Unspecified, 'Atom_Tetrahedral': rdkit.Chem.rdchem.StereoType.Atom_Tetrahedral, 'Atom_SquarePlanar': rdkit.Chem.rdchem.StereoType.Atom_SquarePlanar, 'Atom_TrigonalBipyramidal': rdkit.Chem.rdchem.StereoType.Atom_TrigonalBipyramidal, 'Atom_Octahedral': rdkit.Chem.rdchem.StereoType.Atom_Octahedral, 'Bond_Double': rdkit.Chem.rdchem.StereoType.Bond_Double, 'Bond_Cumulene_Even': rdkit.Chem.rdchem.StereoType.Bond_Cumulene_Even, 'Bond_Atropisomer': rdkit.Chem.rdchem.StereoType.Bond_Atropisomer}
    values: typing.ClassVar[dict]  # value = {0: rdkit.Chem.rdchem.StereoType.Unspecified, 1: rdkit.Chem.rdchem.StereoType.Atom_Tetrahedral, 2: rdkit.Chem.rdchem.StereoType.Atom_SquarePlanar, 3: rdkit.Chem.rdchem.StereoType.Atom_TrigonalBipyramidal, 4: rdkit.Chem.rdchem.StereoType.Atom_Octahedral, 5: rdkit.Chem.rdchem.StereoType.Bond_Double, 6: rdkit.Chem.rdchem.StereoType.Bond_Cumulene_Even, 7: rdkit.Chem.rdchem.StereoType.Bond_Atropisomer}
class SubstanceGroup(Boost.Python.instance):
    """
    A collection of atoms and bonds with associated properties
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
    def AddAtomWithBookmark(self, mark: int) -> None:
        """
            C++ signature :
                void AddAtomWithBookmark(RDKit::SubstanceGroup {lvalue},int)
        """
    def AddAtomWithIdx(self, idx: int) -> None:
        """
            C++ signature :
                void AddAtomWithIdx(RDKit::SubstanceGroup {lvalue},unsigned int)
        """
    def AddAttachPoint(self, aIdx: int, lvIdx: int, idStr: str) -> None:
        """
            C++ signature :
                void AddAttachPoint(RDKit::SubstanceGroup {lvalue},unsigned int,int,std::string)
        """
    def AddBondWithBookmark(self, mark: int) -> None:
        """
            C++ signature :
                void AddBondWithBookmark(RDKit::SubstanceGroup {lvalue},int)
        """
    def AddBondWithIdx(self, idx: int) -> None:
        """
            C++ signature :
                void AddBondWithIdx(RDKit::SubstanceGroup {lvalue},unsigned int)
        """
    def AddBracket(self, pts: typing.Any) -> None:
        """
            C++ signature :
                void AddBracket(RDKit::SubstanceGroup {lvalue},boost::python::api::object)
        """
    def AddCState(self, bondIdx: int, vector: Point3D) -> None:
        """
            C++ signature :
                void AddCState(RDKit::SubstanceGroup {lvalue},unsigned int,RDGeom::Point3D)
        """
    def AddParentAtomWithBookmark(self, mark: int) -> None:
        """
            C++ signature :
                void AddParentAtomWithBookmark(RDKit::SubstanceGroup {lvalue},int)
        """
    def AddParentAtomWithIdx(self, idx: int) -> None:
        """
            C++ signature :
                void AddParentAtomWithIdx(RDKit::SubstanceGroup {lvalue},unsigned int)
        """
    def ClearAttachPoints(self) -> None:
        """
            C++ signature :
                void ClearAttachPoints(RDKit::SubstanceGroup {lvalue})
        """
    def ClearBrackets(self) -> None:
        """
            C++ signature :
                void ClearBrackets(RDKit::SubstanceGroup {lvalue})
        """
    def ClearCStates(self) -> None:
        """
            C++ signature :
                void ClearCStates(RDKit::SubstanceGroup {lvalue})
        """
    def ClearProp(self, key: str) -> None:
        """
            Removes a particular property (does nothing if not set).
            
            
        
            C++ signature :
                void ClearProp(RDKit::SubstanceGroup {lvalue},std::string)
        """
    def GetAtoms(self) -> typing.Sequence[int]:
        """
            returns a list of the indices of the atoms in this SubstanceGroup
        
            C++ signature :
                std::vector<unsigned int, std::allocator<unsigned int> > GetAtoms(RDKit::SubstanceGroup {lvalue})
        """
    def GetAttachPoints(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple GetAttachPoints(RDKit::SubstanceGroup)
        """
    def GetBonds(self) -> typing.Sequence[int]:
        """
            returns a list of the indices of the bonds in this SubstanceGroup
        
            C++ signature :
                std::vector<unsigned int, std::allocator<unsigned int> > GetBonds(RDKit::SubstanceGroup {lvalue})
        """
    def GetBoolProp(self, key: str) -> bool:
        """
            returns the value of a particular property
        
            C++ signature :
                bool GetBoolProp(RDKit::SubstanceGroup {lvalue},std::string)
        """
    def GetBrackets(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple GetBrackets(RDKit::SubstanceGroup)
        """
    def GetCStates(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple GetCStates(RDKit::SubstanceGroup)
        """
    def GetDoubleProp(self, key: str) -> float:
        """
            returns the value of a particular property
        
            C++ signature :
                double GetDoubleProp(RDKit::SubstanceGroup {lvalue},std::string)
        """
    def GetIndexInMol(self) -> int:
        """
            returns the index of this SubstanceGroup in the owning molecule's list.
        
            C++ signature :
                unsigned int GetIndexInMol(RDKit::SubstanceGroup {lvalue})
        """
    def GetIntProp(self, key: str) -> int:
        """
            returns the value of a particular property
        
            C++ signature :
                int GetIntProp(RDKit::SubstanceGroup {lvalue},std::string)
        """
    def GetOwningMol(self) -> Mol:
        """
            returns the molecule owning this SubstanceGroup
        
            C++ signature :
                RDKit::ROMol {lvalue} GetOwningMol(RDKit::SubstanceGroup {lvalue})
        """
    def GetParentAtoms(self) -> typing.Sequence[int]:
        """
            returns a list of the indices of the parent atoms in this SubstanceGroup
        
            C++ signature :
                std::vector<unsigned int, std::allocator<unsigned int> > GetParentAtoms(RDKit::SubstanceGroup {lvalue})
        """
    def GetProp(self, key: str, autoConvert: bool = False) -> typing.Any:
        """
            Returns the value of the property.
            
              ARGUMENTS:
                - key: the name of the property to return (a string).
            
                - autoConvert: if True attempt to convert the property into a python object
            
              RETURNS: a string
            
              NOTE:
                - If the property has not been set, a KeyError exception will be raised.
            
        
            C++ signature :
                boost::python::api::object GetProp(RDKit::SubstanceGroup const*,std::string [,bool=False])
        """
    def GetPropNames(self, includePrivate: bool = False, includeComputed: bool = False) -> _vectSs:
        """
            Returns a list of the properties set on the SubstanceGroup.
            
            
        
            C++ signature :
                std::vector<std::string, std::allocator<std::string> > GetPropNames(RDKit::SubstanceGroup {lvalue} [,bool=False [,bool=False]])
        """
    def GetPropsAsDict(self, includePrivate: bool = True, includeComputed: bool = True, autoConvertStrings: bool = True) -> dict:
        """
            Returns a dictionary of the properties set on the SubstanceGroup.
             n.b. some properties cannot be converted to python types.
            
        
            C++ signature :
                boost::python::dict GetPropsAsDict(RDKit::SubstanceGroup [,bool=True [,bool=True [,bool=True]]])
        """
    def GetStringVectProp(self, key: str) -> _vectSs:
        """
            returns the value of a particular property
        
            C++ signature :
                std::vector<std::string, std::allocator<std::string> > GetStringVectProp(RDKit::SubstanceGroup {lvalue},std::string)
        """
    def GetUnsignedProp(self, key: str) -> int:
        """
            returns the value of a particular property
        
            C++ signature :
                unsigned int GetUnsignedProp(RDKit::SubstanceGroup {lvalue},std::string)
        """
    def GetUnsignedVectProp(self, key: str) -> typing.Sequence[int]:
        """
            returns the value of a particular property
        
            C++ signature :
                std::vector<unsigned int, std::allocator<unsigned int> > GetUnsignedVectProp(RDKit::SubstanceGroup {lvalue},std::string)
        """
    def HasProp(self, key: str) -> bool:
        """
            returns whether or not a particular property exists
        
            C++ signature :
                bool HasProp(RDKit::SubstanceGroup {lvalue},std::string)
        """
    def SetAtoms(self, iterable: typing.Any) -> None:
        """
            Set the list of the indices of the atoms in this SubstanceGroup.
            Note that this does not update properties, CStates or Attachment Points.
        
            C++ signature :
                void SetAtoms(RDKit::SubstanceGroup {lvalue},boost::python::api::object)
        """
    def SetBonds(self, iterable: typing.Any) -> None:
        """
            Set the list of the indices of the bonds in this SubstanceGroup.
            Note that this does not update properties, CStates or Attachment Points.
        
            C++ signature :
                void SetBonds(RDKit::SubstanceGroup {lvalue},boost::python::api::object)
        """
    def SetBoolProp(self, key: str, val: bool, computed: bool = False) -> None:
        """
            sets the value of a particular property
        
            C++ signature :
                void SetBoolProp(RDKit::SubstanceGroup {lvalue},std::string,bool [,bool=False])
        """
    def SetDoubleProp(self, key: str, val: float, computed: bool = False) -> None:
        """
            sets the value of a particular property
        
            C++ signature :
                void SetDoubleProp(RDKit::SubstanceGroup {lvalue},std::string,double [,bool=False])
        """
    def SetIntProp(self, key: str, val: int, computed: bool = False) -> None:
        """
            sets the value of a particular property
        
            C++ signature :
                void SetIntProp(RDKit::SubstanceGroup {lvalue},std::string,int [,bool=False])
        """
    def SetParentAtoms(self, iterable: typing.Any) -> None:
        """
            Set the list of the indices of the parent atoms in this SubstanceGroup.
            Note that this does not update properties, CStates or Attachment Points.
        
            C++ signature :
                void SetParentAtoms(RDKit::SubstanceGroup {lvalue},boost::python::api::object)
        """
    def SetProp(self, key: str, val: str, computed: bool = False) -> None:
        """
            sets the value of a particular property
        
            C++ signature :
                void SetProp(RDKit::SubstanceGroup {lvalue},std::string,std::string [,bool=False])
        """
    def SetUnsignedProp(self, key: str, val: int, computed: bool = False) -> None:
        """
            sets the value of a particular property
        
            C++ signature :
                void SetUnsignedProp(RDKit::SubstanceGroup {lvalue},std::string,unsigned int [,bool=False])
        """
class SubstanceGroupAttach(Boost.Python.instance):
    """
    AttachPoint for a SubstanceGroup
    """
    __instance_size__: typing.ClassVar[int] = 40
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    @property
    def aIdx(*args, **kwargs):
        """
        attachment index
        """
    @property
    def id(*args, **kwargs):
        """
        attachment id
        """
    @property
    def lvIdx(*args, **kwargs):
        """
        leaving atom or index (0 for implied)
        """
class SubstanceGroupCState(Boost.Python.instance):
    """
    CSTATE for a SubstanceGroup
    """
    __instance_size__: typing.ClassVar[int] = 40
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    @property
    def bondIdx(*args, **kwargs):
        ...
    @property
    def vector(*args, **kwargs):
        ...
class SubstanceGroup_VECT(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<RDKit::SubstanceGroup, std::allocator<RDKit::SubstanceGroup> > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<RDKit::SubstanceGroup, std::allocator<RDKit::SubstanceGroup> > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<RDKit::SubstanceGroup, std::allocator<RDKit::SubstanceGroup> >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __iter__(self) -> typing.Any:
        """
            C++ signature :
                boost::python::objects::iterator_range<boost::python::return_internal_reference<1ul, boost::python::default_call_policies>, __gnu_cxx::__normal_iterator<RDKit::SubstanceGroup*, std::vector<RDKit::SubstanceGroup, std::allocator<RDKit::SubstanceGroup> > > > __iter__(boost::python::back_reference<std::vector<RDKit::SubstanceGroup, std::allocator<RDKit::SubstanceGroup> >&>)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<RDKit::SubstanceGroup, std::allocator<RDKit::SubstanceGroup> > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<RDKit::SubstanceGroup, std::allocator<RDKit::SubstanceGroup> > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<RDKit::SubstanceGroup, std::allocator<RDKit::SubstanceGroup> > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<RDKit::SubstanceGroup, std::allocator<RDKit::SubstanceGroup> > {lvalue},boost::python::api::object)
        """
class SubstructMatchParameters(Boost.Python.instance):
    """
    Parameters controlling substructure matching
    """
    __instance_size__: typing.ClassVar[int] = 128
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def setExtraFinalCheck(self, func: typing.Any) -> None:
        """
            allows you to provide a function that will be called
                           with the molecule
                       and a vector of atom IDs containing a potential match.
                       The function should return true or false indicating whether or not
                       that match should be accepted.
        
            C++ signature :
                void setExtraFinalCheck(RDKit::SubstructMatchParameters {lvalue},boost::python::api::object)
        """
    @property
    def aromaticMatchesConjugated(*args, **kwargs):
        """
        aromatic and conjugated bonds match each other
        """
    @aromaticMatchesConjugated.setter
    def aromaticMatchesConjugated(*args, **kwargs):
        ...
    @property
    def atomProperties(*args, **kwargs):
        """
        atom properties that must be equivalent in order to match.
        """
    @atomProperties.setter
    def atomProperties(*args, **kwargs):
        ...
    @property
    def bondProperties(*args, **kwargs):
        """
        bond properties that must be equivalent in order to match.
        """
    @bondProperties.setter
    def bondProperties(*args, **kwargs):
        ...
    @property
    def maxMatches(*args, **kwargs):
        """
        maximum number of matches to return
        """
    @maxMatches.setter
    def maxMatches(*args, **kwargs):
        ...
    @property
    def maxRecursiveMatches(*args, **kwargs):
        """
        maximum number of recursive matches to find
        """
    @maxRecursiveMatches.setter
    def maxRecursiveMatches(*args, **kwargs):
        ...
    @property
    def numThreads(*args, **kwargs):
        """
        number of threads to use when multi-threading is possible.0 selects the number of concurrent threads supported by thehardware. negative values are added to the number of concurrentthreads supported by the hardware.
        """
    @numThreads.setter
    def numThreads(*args, **kwargs):
        ...
    @property
    def recursionPossible(*args, **kwargs):
        """
        Allow recursive queries
        """
    @recursionPossible.setter
    def recursionPossible(*args, **kwargs):
        ...
    @property
    def specifiedStereoQueryMatchesUnspecified(*args, **kwargs):
        """
        If set, query atoms and bonds with specified stereochemistry will match atoms and bonds with unspecified stereochemistry.
        """
    @specifiedStereoQueryMatchesUnspecified.setter
    def specifiedStereoQueryMatchesUnspecified(*args, **kwargs):
        ...
    @property
    def uniquify(*args, **kwargs):
        """
        uniquify (by atom index) match results
        """
    @uniquify.setter
    def uniquify(*args, **kwargs):
        ...
    @property
    def useChirality(*args, **kwargs):
        """
        Use chirality in determining whether or not atoms/bonds match
        """
    @useChirality.setter
    def useChirality(*args, **kwargs):
        ...
    @property
    def useEnhancedStereo(*args, **kwargs):
        """
        take enhanced stereochemistry into account while doing the match. This only has an effect if useChirality is also True.
        """
    @useEnhancedStereo.setter
    def useEnhancedStereo(*args, **kwargs):
        ...
    @property
    def useGenericMatchers(*args, **kwargs):
        """
        use generic groups (=homology groups) as a post-filtering step (if any are present in the molecule)
        """
    @useGenericMatchers.setter
    def useGenericMatchers(*args, **kwargs):
        ...
    @property
    def useQueryQueryMatches(*args, **kwargs):
        """
        Consider query-query matches, not just simple matches
        """
    @useQueryQueryMatches.setter
    def useQueryQueryMatches(*args, **kwargs):
        ...
class _ROConformerSeq(Boost.Python.instance):
    """
    Read-only sequence of conformers, not constructible from Python.
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
    def __getitem__(self, i: int) -> Conformer:
        """
            C++ signature :
                RDKit::Conformer* __getitem__(RDKit::ReadOnlySeq<std::_List_iterator<boost::shared_ptr<RDKit::Conformer> >, boost::shared_ptr<RDKit::Conformer>&, RDKit::ConformerCountFunctor> {lvalue},int)
        """
    def __iter__(self) -> typing.Sequence[rdkit.Chem.Conformer]:
        """
            C++ signature :
                RDKit::ReadOnlySeq<std::_List_iterator<boost::shared_ptr<RDKit::Conformer> >, boost::shared_ptr<RDKit::Conformer>&, RDKit::ConformerCountFunctor>* __iter__(RDKit::ReadOnlySeq<std::_List_iterator<boost::shared_ptr<RDKit::Conformer> >, boost::shared_ptr<RDKit::Conformer>&, RDKit::ConformerCountFunctor> {lvalue})
        """
    def __len__(self) -> int:
        """
            C++ signature :
                int __len__(RDKit::ReadOnlySeq<std::_List_iterator<boost::shared_ptr<RDKit::Conformer> >, boost::shared_ptr<RDKit::Conformer>&, RDKit::ConformerCountFunctor> {lvalue})
        """
    def __next__(self) -> Conformer:
        """
            C++ signature :
                RDKit::Conformer* __next__(RDKit::ReadOnlySeq<std::_List_iterator<boost::shared_ptr<RDKit::Conformer> >, boost::shared_ptr<RDKit::Conformer>&, RDKit::ConformerCountFunctor> {lvalue})
        """
class _ROQAtomSeq(Boost.Python.instance):
    """
    Read-only sequence of atoms matching a query, not constructible from Python.
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
    def __getitem__(self, which: int) -> Atom:
        """
            C++ signature :
                RDKit::Atom* __getitem__(RDKit::ReadOnlySeq<RDKit::QueryAtomIterator_<RDKit::Atom, RDKit::ROMol>, RDKit::Atom*, RDKit::AtomCountFunctor> {lvalue},int)
        """
    def __iter__(self) -> typing.Sequence[rdkit.Chem.QueryAtom]:
        """
            C++ signature :
                RDKit::ReadOnlySeq<RDKit::QueryAtomIterator_<RDKit::Atom, RDKit::ROMol>, RDKit::Atom*, RDKit::AtomCountFunctor>* __iter__(RDKit::ReadOnlySeq<RDKit::QueryAtomIterator_<RDKit::Atom, RDKit::ROMol>, RDKit::Atom*, RDKit::AtomCountFunctor> {lvalue})
        """
    def __len__(self) -> int:
        """
            C++ signature :
                int __len__(RDKit::ReadOnlySeq<RDKit::QueryAtomIterator_<RDKit::Atom, RDKit::ROMol>, RDKit::Atom*, RDKit::AtomCountFunctor> {lvalue})
        """
    def __next__(self) -> Atom:
        """
            C++ signature :
                RDKit::Atom* __next__(RDKit::ReadOnlySeq<RDKit::QueryAtomIterator_<RDKit::Atom, RDKit::ROMol>, RDKit::Atom*, RDKit::AtomCountFunctor> {lvalue})
        """
class _cppAtomKekulizeException(_cppMolSanitizeException):
    """
    exception arising from sanitization
    """
    @staticmethod
    def GetAtomIndices(arg1: _cppAtomKekulizeException) -> tuple:
        """
            C++ signature :
                boost::python::tuple GetAtomIndices(RDKit::KekulizeException)
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
class _cppAtomSanitizeException(_cppMolSanitizeException):
    """
    exception arising from sanitization
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
    def GetAtomIdx(self) -> int:
        """
            C++ signature :
                unsigned int GetAtomIdx(RDKit::AtomSanitizeException {lvalue})
        """
class _cppAtomValenceException(_cppAtomSanitizeException):
    """
    exception arising from sanitization
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
class _cppMolSanitizeException(Boost.Python.instance):
    """
    exception arising from sanitization
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
    def GetType(self) -> str:
        """
            C++ signature :
                std::string GetType(RDKit::MolSanitizeException {lvalue})
        """
    def Message(self) -> str:
        """
            C++ signature :
                char const* Message(RDKit::MolSanitizeException {lvalue})
        """
class _listN5boost10shared_ptrIN5RDKit9ConformerEEE(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 40
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::list<boost::shared_ptr<RDKit::Conformer>, std::allocator<boost::shared_ptr<RDKit::Conformer> > > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::list<boost::shared_ptr<RDKit::Conformer>, std::allocator<boost::shared_ptr<RDKit::Conformer> > > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::list<boost::shared_ptr<RDKit::Conformer>, std::allocator<boost::shared_ptr<RDKit::Conformer> > >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __iter__(self) -> typing.Any:
        """
            C++ signature :
                boost::python::objects::iterator_range<boost::python::return_internal_reference<1ul, boost::python::default_call_policies>, std::_List_iterator<boost::shared_ptr<RDKit::Conformer> > > __iter__(boost::python::back_reference<std::list<boost::shared_ptr<RDKit::Conformer>, std::allocator<boost::shared_ptr<RDKit::Conformer> > >&>)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::list<boost::shared_ptr<RDKit::Conformer>, std::allocator<boost::shared_ptr<RDKit::Conformer> > > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::list<boost::shared_ptr<RDKit::Conformer>, std::allocator<boost::shared_ptr<RDKit::Conformer> > > {lvalue},_object*,_object*)
        """
class _listPN5RDKit4AtomE(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 40
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::list<RDKit::Atom*, std::allocator<RDKit::Atom*> > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::list<RDKit::Atom*, std::allocator<RDKit::Atom*> > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::list<RDKit::Atom*, std::allocator<RDKit::Atom*> >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __iter__(self) -> typing.Any:
        """
            C++ signature :
                boost::python::objects::iterator_range<boost::python::return_value_policy<boost::python::return_by_value, boost::python::default_call_policies>, std::_List_iterator<RDKit::Atom*> > __iter__(boost::python::back_reference<std::list<RDKit::Atom*, std::allocator<RDKit::Atom*> >&>)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::list<RDKit::Atom*, std::allocator<RDKit::Atom*> > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::list<RDKit::Atom*, std::allocator<RDKit::Atom*> > {lvalue},_object*,_object*)
        """
class _listPN5RDKit4BondE(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 40
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::list<RDKit::Bond*, std::allocator<RDKit::Bond*> > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::list<RDKit::Bond*, std::allocator<RDKit::Bond*> > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::list<RDKit::Bond*, std::allocator<RDKit::Bond*> >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __iter__(self) -> typing.Any:
        """
            C++ signature :
                boost::python::objects::iterator_range<boost::python::return_value_policy<boost::python::return_by_value, boost::python::default_call_policies>, std::_List_iterator<RDKit::Bond*> > __iter__(boost::python::back_reference<std::list<RDKit::Bond*, std::allocator<RDKit::Bond*> >&>)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::list<RDKit::Bond*, std::allocator<RDKit::Bond*> > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::list<RDKit::Bond*, std::allocator<RDKit::Bond*> > {lvalue},_object*,_object*)
        """
def AddMolSubstanceGroup(mol: Mol, sgroup: SubstanceGroup) -> SubstanceGroup:
    """
        adds a copy of a SubstanceGroup to a molecule, returns the new SubstanceGroup
    
        C++ signature :
            RDKit::SubstanceGroup* AddMolSubstanceGroup(RDKit::ROMol {lvalue},RDKit::SubstanceGroup)
    """
def ClearMolSubstanceGroups(mol: Mol) -> None:
    """
        removes all SubstanceGroups from a molecule (if any)
    
        C++ signature :
            void ClearMolSubstanceGroups(RDKit::ROMol {lvalue})
    """
def CreateMolDataSubstanceGroup(mol: Mol, fieldName: str, value: str) -> SubstanceGroup:
    """
        creates a new DATA SubstanceGroup associated with a molecule, returns the new SubstanceGroup
    
        C++ signature :
            RDKit::SubstanceGroup* CreateMolDataSubstanceGroup(RDKit::ROMol {lvalue},std::string,std::string)
    """
def CreateMolSubstanceGroup(mol: Mol, type: str) -> SubstanceGroup:
    """
        creates a new SubstanceGroup associated with a molecule, returns the new SubstanceGroup
    
        C++ signature :
            RDKit::SubstanceGroup* CreateMolSubstanceGroup(RDKit::ROMol {lvalue},std::string)
    """
def CreateStereoGroup(stereoGroupType: StereoGroupType, mol: Mol, atomIds: typing.Any, readId: int = 0) -> StereoGroup:
    """
        creates a StereoGroup associated with a molecule from a list of atom Ids
    
        C++ signature :
            RDKit::StereoGroup* CreateStereoGroup(RDKit::StereoGroupType,RDKit::ROMol {lvalue},boost::python::api::object [,unsigned int=0])
    """
def ForwardStereoGroupIds(mol: Mol) -> None:
    """
        Forward the original Stereo Group IDs when exporting the Mol.
    
        C++ signature :
            void ForwardStereoGroupIds(RDKit::ROMol {lvalue})
    """
def GetAtomAlias(atom: Atom) -> str:
    """
        Returns the atom's MDL alias text
    
        C++ signature :
            std::string GetAtomAlias(RDKit::Atom const*)
    """
def GetAtomRLabel(atom: Atom) -> int:
    """
        Returns the atom's MDL AtomRLabel (this is an integer from 0 to 99)
    
        C++ signature :
            int GetAtomRLabel(RDKit::Atom const*)
    """
def GetAtomValue(atom: Atom) -> str:
    """
        Returns the atom's MDL alias text
    
        C++ signature :
            std::string GetAtomValue(RDKit::Atom const*)
    """
def GetDefaultPickleProperties() -> int:
    """
        Get the current global mol pickler options.
    
        C++ signature :
            unsigned int GetDefaultPickleProperties()
    """
def GetMolSubstanceGroupWithIdx(mol: Mol, idx: int) -> SubstanceGroup:
    """
        returns a particular SubstanceGroup from the molecule
    
        C++ signature :
            RDKit::SubstanceGroup* GetMolSubstanceGroupWithIdx(RDKit::ROMol {lvalue},unsigned int)
    """
def GetMolSubstanceGroups(mol: Mol) -> SubstanceGroup_VECT:
    """
        returns a copy of the molecule's SubstanceGroups (if any)
    
        C++ signature :
            std::vector<RDKit::SubstanceGroup, std::allocator<RDKit::SubstanceGroup> > GetMolSubstanceGroups(RDKit::ROMol {lvalue})
    """
def GetNumPiElectrons(atom: Atom) -> int:
    """
        Returns the number of electrons an atom is using for pi bonding
    
        C++ signature :
            unsigned int GetNumPiElectrons(RDKit::Atom)
    """
def GetPeriodicTable() -> PeriodicTable:
    """
        Returns the application's PeriodicTable instance.
        
        
    
        C++ signature :
            RDKit::PeriodicTable* GetPeriodicTable()
    """
def GetSupplementalSmilesLabel(atom: Atom) -> str:
    """
        Gets the supplemental smiles label on an atom, returns an empty string if not present.
    
        C++ signature :
            std::string GetSupplementalSmilesLabel(RDKit::Atom const*)
    """
def MolBundleCanSerialize() -> bool:
    """
        Returns True if the MolBundle is serializable (requires boost serialization
    
        C++ signature :
            bool MolBundleCanSerialize()
    """
def SetAtomAlias(atom: Atom, rlabel: str) -> None:
    """
        Sets the atom's MDL alias text.
        Setting to an empty string clears the alias.
    
        C++ signature :
            void SetAtomAlias(RDKit::Atom*,std::string)
    """
def SetAtomRLabel(atom: Atom, rlabel: int) -> None:
    """
        Sets the atom's MDL RLabel (this is an integer from 0 to 99).
        Setting to 0 clears the rlabel.
    
        C++ signature :
            void SetAtomRLabel(RDKit::Atom*,int)
    """
def SetAtomValue(atom: Atom, rlabel: str) -> None:
    """
        Sets the atom's MDL alias text.
        Setting to an empty string clears the alias.
    
        C++ signature :
            void SetAtomValue(RDKit::Atom*,std::string)
    """
def SetDefaultPickleProperties(arg1: int) -> None:
    """
        Set the current global mol pickler options.
    
        C++ signature :
            void SetDefaultPickleProperties(unsigned int)
    """
def SetSupplementalSmilesLabel(atom: Atom, label: str) -> None:
    """
        Sets a supplemental label on an atom that is written to the smiles string.
        
        >>> m = Chem.MolFromSmiles("C")
        >>> Chem.SetSupplementalSmilesLabel(m.GetAtomWithIdx(0), '<xxx>')
        >>> Chem.MolToSmiles(m)
        'C<xxx>'
        
    
        C++ signature :
            void SetSupplementalSmilesLabel(RDKit::Atom*,std::string)
    """
def _HasSubstructMatchStr(pkl: str, query: Mol, recursionPossible: bool = True, useChirality: bool = False, useQueryQueryMatches: bool = False) -> bool:
    """
        This function is included to speed substructure queries from databases, 
        it's probably not of
        general interest.
        
          ARGUMENTS:
            - pkl: a Molecule pickle
        
            - query: a Molecule
        
            - recursionPossible: (optional)
        
            - useChirality: (optional)
        
            - useQueryQueryMatches: use query-query matching logic
        
          RETURNS: True or False
        
    
        C++ signature :
            bool _HasSubstructMatchStr(std::string,RDKit::ROMol [,bool=True [,bool=False [,bool=False]]])
    """
def tossit() -> None:
    """
        C++ signature :
            void tossit()
    """
ALLOW_CHARGE_SEPARATION: ResonanceFlags  # value = rdkit.Chem.rdchem.ResonanceFlags.ALLOW_CHARGE_SEPARATION
ALLOW_INCOMPLETE_OCTETS: ResonanceFlags  # value = rdkit.Chem.rdchem.ResonanceFlags.ALLOW_INCOMPLETE_OCTETS
AllProps: PropertyPickleOptions  # value = rdkit.Chem.rdchem.PropertyPickleOptions.AllProps
AtomProps: PropertyPickleOptions  # value = rdkit.Chem.rdchem.PropertyPickleOptions.AtomProps
BondProps: PropertyPickleOptions  # value = rdkit.Chem.rdchem.PropertyPickleOptions.BondProps
CHI_ALLENE: ChiralType  # value = rdkit.Chem.rdchem.ChiralType.CHI_ALLENE
CHI_OCTAHEDRAL: ChiralType  # value = rdkit.Chem.rdchem.ChiralType.CHI_OCTAHEDRAL
CHI_OTHER: ChiralType  # value = rdkit.Chem.rdchem.ChiralType.CHI_OTHER
CHI_SQUAREPLANAR: ChiralType  # value = rdkit.Chem.rdchem.ChiralType.CHI_SQUAREPLANAR
CHI_TETRAHEDRAL: ChiralType  # value = rdkit.Chem.rdchem.ChiralType.CHI_TETRAHEDRAL
CHI_TETRAHEDRAL_CCW: ChiralType  # value = rdkit.Chem.rdchem.ChiralType.CHI_TETRAHEDRAL_CCW
CHI_TETRAHEDRAL_CW: ChiralType  # value = rdkit.Chem.rdchem.ChiralType.CHI_TETRAHEDRAL_CW
CHI_TRIGONALBIPYRAMIDAL: ChiralType  # value = rdkit.Chem.rdchem.ChiralType.CHI_TRIGONALBIPYRAMIDAL
CHI_UNSPECIFIED: ChiralType  # value = rdkit.Chem.rdchem.ChiralType.CHI_UNSPECIFIED
COMPOSITE_AND: CompositeQueryType  # value = rdkit.Chem.rdchem.CompositeQueryType.COMPOSITE_AND
COMPOSITE_OR: CompositeQueryType  # value = rdkit.Chem.rdchem.CompositeQueryType.COMPOSITE_OR
COMPOSITE_XOR: CompositeQueryType  # value = rdkit.Chem.rdchem.CompositeQueryType.COMPOSITE_XOR
ComputedProps: PropertyPickleOptions  # value = rdkit.Chem.rdchem.PropertyPickleOptions.ComputedProps
CoordsAsDouble: PropertyPickleOptions  # value = rdkit.Chem.rdchem.PropertyPickleOptions.CoordsAsDouble
KEKULE_ALL: ResonanceFlags  # value = rdkit.Chem.rdchem.ResonanceFlags.KEKULE_ALL
MolProps: PropertyPickleOptions  # value = rdkit.Chem.rdchem.PropertyPickleOptions.MolProps
NoConformers: PropertyPickleOptions  # value = rdkit.Chem.rdchem.PropertyPickleOptions.NoConformers
NoProps: PropertyPickleOptions  # value = rdkit.Chem.rdchem.PropertyPickleOptions.NoProps
PrivateProps: PropertyPickleOptions  # value = rdkit.Chem.rdchem.PropertyPickleOptions.PrivateProps
QueryAtomData: PropertyPickleOptions  # value = rdkit.Chem.rdchem.PropertyPickleOptions.QueryAtomData
STEREO_ABSOLUTE: StereoGroupType  # value = rdkit.Chem.rdchem.StereoGroupType.STEREO_ABSOLUTE
STEREO_AND: StereoGroupType  # value = rdkit.Chem.rdchem.StereoGroupType.STEREO_AND
STEREO_OR: StereoGroupType  # value = rdkit.Chem.rdchem.StereoGroupType.STEREO_OR
UNCONSTRAINED_ANIONS: ResonanceFlags  # value = rdkit.Chem.rdchem.ResonanceFlags.UNCONSTRAINED_ANIONS
UNCONSTRAINED_CATIONS: ResonanceFlags  # value = rdkit.Chem.rdchem.ResonanceFlags.UNCONSTRAINED_CATIONS
