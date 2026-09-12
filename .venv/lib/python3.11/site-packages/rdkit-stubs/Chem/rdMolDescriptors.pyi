"""
Module containing functions to compute molecular descriptors
"""
from __future__ import annotations
import rdkit.rdBase
import typing
__all__ = ['AtomPairsParameters', 'BCUT2D', 'CalcAUTOCORR2D', 'CalcAUTOCORR3D', 'CalcAsphericity', 'CalcChi0n', 'CalcChi0v', 'CalcChi1n', 'CalcChi1v', 'CalcChi2n', 'CalcChi2v', 'CalcChi3n', 'CalcChi3v', 'CalcChi4n', 'CalcChi4v', 'CalcChiNn', 'CalcChiNv', 'CalcCoulombMat', 'CalcCrippenDescriptors', 'CalcEEMcharges', 'CalcEccentricity', 'CalcExactMolWt', 'CalcFractionCSP3', 'CalcGETAWAY', 'CalcHallKierAlpha', 'CalcInertialShapeFactor', 'CalcKappa1', 'CalcKappa2', 'CalcKappa3', 'CalcLabuteASA', 'CalcMORSE', 'CalcMolFormula', 'CalcNPR1', 'CalcNPR2', 'CalcNumAliphaticCarbocycles', 'CalcNumAliphaticHeterocycles', 'CalcNumAliphaticRings', 'CalcNumAmideBonds', 'CalcNumAromaticCarbocycles', 'CalcNumAromaticHeterocycles', 'CalcNumAromaticRings', 'CalcNumAtomStereoCenters', 'CalcNumAtoms', 'CalcNumBridgeheadAtoms', 'CalcNumHBA', 'CalcNumHBD', 'CalcNumHeavyAtoms', 'CalcNumHeteroatoms', 'CalcNumHeterocycles', 'CalcNumLipinskiHBA', 'CalcNumLipinskiHBD', 'CalcNumRings', 'CalcNumRotatableBonds', 'CalcNumSaturatedCarbocycles', 'CalcNumSaturatedHeterocycles', 'CalcNumSaturatedRings', 'CalcNumSpiroAtoms', 'CalcNumUnspecifiedAtomStereoCenters', 'CalcOxidationNumbers', 'CalcPBF', 'CalcPMI1', 'CalcPMI2', 'CalcPMI3', 'CalcPhi', 'CalcRDF', 'CalcRadiusOfGyration', 'CalcSpherocityIndex', 'CalcTPSA', 'CalcWHIM', 'CustomProp_VSA_', 'DoubleCubicLatticeVolume', 'GetAtomFeatures', 'GetAtomPairAtomCode', 'GetAtomPairCode', 'GetAtomPairFingerprint', 'GetConnectivityInvariants', 'GetFeatureInvariants', 'GetHashedAtomPairFingerprint', 'GetHashedAtomPairFingerprintAsBitVect', 'GetHashedMorganFingerprint', 'GetHashedTopologicalTorsionFingerprint', 'GetHashedTopologicalTorsionFingerprintAsBitVect', 'GetMACCSKeysFingerprint', 'GetMorganFingerprint', 'GetMorganFingerprintAsBitVect', 'GetTopologicalTorsionFingerprint', 'GetUSR', 'GetUSRCAT', 'GetUSRDistributions', 'GetUSRDistributionsFromPoints', 'GetUSRFromDistributions', 'GetUSRScore', 'MQNs_', 'MakePropertyRangeQuery', 'NumRotatableBondsOptions', 'PEOE_VSA_', 'Properties', 'PropertyFunctor', 'PropertyRangeQuery', 'PythonPropertyFunctor', 'SMR_VSA_', 'SlogP_VSA_']
class AtomPairsParameters(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 32
    atomTypes: typing.ClassVar[rdkit.rdBase._vectj]  # value = <rdkit.rdBase._vectj object>
    codeSize: typing.ClassVar[int] = 9
    numAtomPairFingerprintBits: typing.ClassVar[int] = 23
    numBranchBits: typing.ClassVar[int] = 3
    numChiralBits: typing.ClassVar[int] = 2
    numPathBits: typing.ClassVar[int] = 5
    numPiBits: typing.ClassVar[int] = 2
    numTypeBits: typing.ClassVar[int] = 4
    version: typing.ClassVar[str] = '1.1.0'
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
class DoubleCubicLatticeVolume(Boost.Python.instance):
    """
    Class for the Double Cubic Lattice Volume method
    """
    __instance_size__: typing.ClassVar[int] = 64
    @staticmethod
    def GetCompactness(arg1: DoubleCubicLatticeVolume) -> float:
        """
            Get the Compactness of the Protein
        
            C++ signature :
                double GetCompactness(RDKit::Descriptors::DoubleCubicLatticeVolume {lvalue})
        """
    @staticmethod
    def GetPackingDensity(arg1: DoubleCubicLatticeVolume) -> float:
        """
            Get the PackingDensity of the Protein
        
            C++ signature :
                double GetPackingDensity(RDKit::Descriptors::DoubleCubicLatticeVolume {lvalue})
        """
    @staticmethod
    def GetSurfaceArea(arg1: DoubleCubicLatticeVolume) -> float:
        """
            Get the Surface Area of the Molecule or Protein
        
            C++ signature :
                double GetSurfaceArea(RDKit::Descriptors::DoubleCubicLatticeVolume {lvalue})
        """
    @staticmethod
    def GetVDWVolume(arg1: DoubleCubicLatticeVolume) -> float:
        """
            Get the van der Waals Volume of the Molecule or Protein
        
            C++ signature :
                double GetVDWVolume(RDKit::Descriptors::DoubleCubicLatticeVolume {lvalue})
        """
    @staticmethod
    def GetVolume(arg1: DoubleCubicLatticeVolume) -> float:
        """
            Get the Total Volume of the Molecule or Protein
        
            C++ signature :
                double GetVolume(RDKit::Descriptors::DoubleCubicLatticeVolume {lvalue})
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __init__(self, mol: Mol, isProtein: bool = False, includeLigand: bool = True, probeRadius: float = 1.2, depth: int = 4, dotDensity: int = 0) -> None:
        """
            ARGUMENTS:
                  "   - mol: molecule or protein under consideration
                  "   - isProtein: flag to indicate if the input is a protein (default=False, free ligand).
                  "   - includeLigand: flag to include or exclude a bound ligand when input is a protein (default=True)
                  "   - probeRadius: radius of the solvent probe (default=1.2)
                  "   - depth: control of number of dots per atom (default=4)
                  "   - dotDensity: control of accuracy (default=0)
                  "
        
            C++ signature :
                void __init__(_object*,RDKit::ROMol [,bool=False [,bool=True [,double=1.2 [,int=4 [,int=0]]]]])
        """
class NumRotatableBondsOptions(Boost.Python.enum):
    """
    Options for generating rotatable bonds
     NonStrict - standard loose definitions
     Strict - stricter definition excluding amides, esters, etc
     StrictLinkages - adds rotors between rotatable bonds
     Default - Current RDKit default
    """
    Default: typing.ClassVar[NumRotatableBondsOptions]  # value = rdkit.Chem.rdMolDescriptors.NumRotatableBondsOptions.Default
    NonStrict: typing.ClassVar[NumRotatableBondsOptions]  # value = rdkit.Chem.rdMolDescriptors.NumRotatableBondsOptions.NonStrict
    Strict: typing.ClassVar[NumRotatableBondsOptions]  # value = rdkit.Chem.rdMolDescriptors.NumRotatableBondsOptions.Strict
    StrictLinkages: typing.ClassVar[NumRotatableBondsOptions]  # value = rdkit.Chem.rdMolDescriptors.NumRotatableBondsOptions.StrictLinkages
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'NonStrict': rdkit.Chem.rdMolDescriptors.NumRotatableBondsOptions.NonStrict, 'Strict': rdkit.Chem.rdMolDescriptors.NumRotatableBondsOptions.Strict, 'StrictLinkages': rdkit.Chem.rdMolDescriptors.NumRotatableBondsOptions.StrictLinkages, 'Default': rdkit.Chem.rdMolDescriptors.NumRotatableBondsOptions.Default}
    values: typing.ClassVar[dict]  # value = {0: rdkit.Chem.rdMolDescriptors.NumRotatableBondsOptions.NonStrict, 1: rdkit.Chem.rdMolDescriptors.NumRotatableBondsOptions.Strict, 2: rdkit.Chem.rdMolDescriptors.NumRotatableBondsOptions.StrictLinkages, -1: rdkit.Chem.rdMolDescriptors.NumRotatableBondsOptions.Default}
class Properties(Boost.Python.instance):
    """
    Property computation and registry system.  To compute all registered properties:
    mol = Chem.MolFromSmiles('c1ccccc1')
    properties = rdMolDescriptors.Properties()
    for name, value in zip(properties.GetPropertyNames(), properties.ComputeProperties(mol)):
      print(name, value)
    
    To compute a subset
    properties = rdMolDescriptors.Properties(['exactmw', 'lipinskiHBA'])
    for name, value in zip(properties.GetPropertyNames(), properties.ComputeProperties(mol)):
      print(name, value)
    
    """
    __instance_size__: typing.ClassVar[int] = 40
    @staticmethod
    def GetAvailableProperties() -> _vectSs:
        """
            Return all available property names that can be computed
        
            C++ signature :
                std::vector<std::string, std::allocator<std::string> > GetAvailableProperties()
        """
    @staticmethod
    def GetProperty(propName: str) -> PropertyFunctor:
        """
            Return the named property if it exists
        
            C++ signature :
                boost::shared_ptr<RDKit::Descriptors::PropertyFunctor> GetProperty(std::string)
        """
    @staticmethod
    def RegisterProperty(propertyFunctor: AtomPairsParameters) -> int:
        """
            Register a new property object (not thread safe)
        
            C++ signature :
                int RegisterProperty(boost::python::api::object)
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def AnnotateProperties(self, mol: Mol) -> None:
        """
            Annotate the molecule with the computed properties.  These properties will be available as SDData or from mol.GetProp(prop)
        
            C++ signature :
                void AnnotateProperties(RDKit::Descriptors::Properties {lvalue},RDKit::ROMol {lvalue})
        """
    def ComputeProperties(self, mol: Mol, annotateMol: bool = False) -> typing.Sequence[double]:
        """
            Return a list of computed properties, if annotateMol==True, annotate the molecule with the computed properties.
        
            C++ signature :
                std::vector<double, std::allocator<double> > ComputeProperties(RDKit::Descriptors::Properties {lvalue},RDKit::ROMol [,bool=False])
        """
    def GetPropertyNames(self) -> _vectSs:
        """
            Return the property names computed by this instance
        
            C++ signature :
                std::vector<std::string, std::allocator<std::string> > GetPropertyNames(RDKit::Descriptors::Properties {lvalue})
        """
    @typing.overload
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    @typing.overload
    def __init__(self, propNames: _vectSs) -> None:
        """
            C++ signature :
                void __init__(_object*,std::vector<std::string, std::allocator<std::string> >)
        """
class PropertyFunctor(Boost.Python.instance):
    """
    Property computation class stored in the property registry.
    See rdkit.Chem.rdMolDescriptor.Properties.GetProperty and 
    rdkit.Chem.Descriptor.Properties.PropertyFunctor for creating new ones
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
    def GetName(self) -> str:
        """
            Return the name of the property to calculate
        
            C++ signature :
                std::string GetName(RDKit::Descriptors::PropertyFunctor {lvalue})
        """
    def GetVersion(self) -> str:
        """
            Return the version of the calculated property
        
            C++ signature :
                std::string GetVersion(RDKit::Descriptors::PropertyFunctor {lvalue})
        """
    def __call__(self, mol: Mol) -> float:
        """
            Compute the property for the specified molecule
        
            C++ signature :
                double __call__(RDKit::Descriptors::PropertyFunctor {lvalue},RDKit::ROMol)
        """
class PropertyRangeQuery(Boost.Python.instance):
    """
    Property Range Query for a molecule.  Match(mol) -> true if in range
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
    def Match(self, what: Mol) -> bool:
        """
            C++ signature :
                bool Match(Queries::RangeQuery<double, RDKit::ROMol const&, true> {lvalue},RDKit::ROMol)
        """
class PythonPropertyFunctor(PropertyFunctor):
    """
    """
    __instance_size__: typing.ClassVar[int] = 64
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __call__(self, mol: Mol) -> float:
        """
            Compute the property for the specified molecule
        
            C++ signature :
                double __call__((anonymous namespace)::PythonPropertyFunctor {lvalue},RDKit::ROMol)
        """
    def __init__(self, callback: typing.Any, name: str, version: str) -> None:
        """
            C++ signature :
                void __init__(_object*,_object*,std::string,std::string)
        """
@typing.overload
def BCUT2D(mol: Mol) -> list:
    """
        Implements BCUT descriptors From J. Chem. Inf. Comput. Sci., Vol. 39, No. 1, 1999Diagonal elements are (currently) atomic mass, gasteiger charge,crippen logP and crippen MRReturns the 2D BCUT2D descriptors vector as described in
        returns [mass eigen value high, mass eigen value low,
                 gasteiger charge eigenvalue high, gasteiger charge low,
                 crippen lowgp  eigenvalue high, crippen lowgp  low,
                 crippen mr eigenvalue high, crippen mr low]
        
    
        C++ signature :
            boost::python::list BCUT2D(RDKit::ROMol)
    """
@typing.overload
def BCUT2D(mol: Mol, atom_props: list) -> tuple:
    """
        Returns a 2D BCUT (eigen value hi, eigenvalue low) given the molecule and the specified atom props
         atom_props must be a list or tuple of floats equal in size to the number of atoms in mol
    
        C++ signature :
            std::pair<double, double> BCUT2D(RDKit::ROMol,boost::python::list)
    """
@typing.overload
def BCUT2D(mol: Mol, atom_props: tuple) -> tuple:
    """
        Returns a 2D BCUT (eigen value hi, eigenvalue low) given the molecule and the specified atom props
         atom_props must be a list or tuple of floats equal in size to the number of atoms in mol
    
        C++ signature :
            std::pair<double, double> BCUT2D(RDKit::ROMol,boost::python::tuple)
    """
@typing.overload
def BCUT2D(mol: Mol, atom_propname: str) -> tuple:
    """
        Returns a 2D BCUT (eigen value high, eigen value low) given the molecule and the specified atom prop name
        atom_propname must exist on each atom and be convertible to a float
    
        C++ signature :
            std::pair<double, double> BCUT2D(RDKit::ROMol,std::string)
    """
def CalcAUTOCORR2D(mol: Mol, CustomAtomProperty: str = '') -> list:
    """
        Returns 2D Autocorrelation descriptors vector
    
        C++ signature :
            boost::python::list CalcAUTOCORR2D(RDKit::ROMol [,std::string=''])
    """
def CalcAUTOCORR3D(mol: Mol, confId: int = -1, CustomAtomProperty: str = '') -> list:
    """
        Returns 3D Autocorrelation descriptors vector
    
        C++ signature :
            boost::python::list CalcAUTOCORR3D(RDKit::ROMol [,int=-1 [,std::string='']])
    """
def CalcAsphericity(mol: Mol, confId: int = -1, useAtomicMasses: bool = True, force: bool = True) -> float:
    """
        C++ signature :
            double CalcAsphericity(RDKit::ROMol [,int=-1 [,bool=True [,bool=True]]])
    """
def CalcChi0n(mol: Mol, force: bool = False) -> float:
    """
        C++ signature :
            double CalcChi0n(RDKit::ROMol [,bool=False])
    """
def CalcChi0v(mol: Mol, force: bool = False) -> float:
    """
        C++ signature :
            double CalcChi0v(RDKit::ROMol [,bool=False])
    """
def CalcChi1n(mol: Mol, force: bool = False) -> float:
    """
        C++ signature :
            double CalcChi1n(RDKit::ROMol [,bool=False])
    """
def CalcChi1v(mol: Mol, force: bool = False) -> float:
    """
        C++ signature :
            double CalcChi1v(RDKit::ROMol [,bool=False])
    """
def CalcChi2n(mol: Mol, force: bool = False) -> float:
    """
        C++ signature :
            double CalcChi2n(RDKit::ROMol [,bool=False])
    """
def CalcChi2v(mol: Mol, force: bool = False) -> float:
    """
        C++ signature :
            double CalcChi2v(RDKit::ROMol [,bool=False])
    """
def CalcChi3n(mol: Mol, force: bool = False) -> float:
    """
        C++ signature :
            double CalcChi3n(RDKit::ROMol [,bool=False])
    """
def CalcChi3v(mol: Mol, force: bool = False) -> float:
    """
        C++ signature :
            double CalcChi3v(RDKit::ROMol [,bool=False])
    """
def CalcChi4n(mol: Mol, force: bool = False) -> float:
    """
        C++ signature :
            double CalcChi4n(RDKit::ROMol [,bool=False])
    """
def CalcChi4v(mol: Mol, force: bool = False) -> float:
    """
        C++ signature :
            double CalcChi4v(RDKit::ROMol [,bool=False])
    """
def CalcChiNn(mol: Mol, n: int, force: bool = False) -> float:
    """
        C++ signature :
            double CalcChiNn(RDKit::ROMol,unsigned int [,bool=False])
    """
def CalcChiNv(mol: Mol, n: int, force: bool = False) -> float:
    """
        C++ signature :
            double CalcChiNv(RDKit::ROMol,unsigned int [,bool=False])
    """
def CalcCoulombMat(mol: Mol, confId: int = -1) -> tuple:
    """
        Returns severals Coulomb randomized matrices
    
        C++ signature :
            boost::python::tuple CalcCoulombMat(RDKit::ROMol [,int=-1])
    """
def CalcCrippenDescriptors(mol: Mol, includeHs: bool = True, force: bool = False) -> tuple:
    """
        returns a 2-tuple with the Wildman-Crippen logp,mr values
    
        C++ signature :
            boost::python::tuple CalcCrippenDescriptors(RDKit::ROMol [,bool=True [,bool=False]])
    """
def CalcEEMcharges(mol: Mol, confId: int = -1) -> list:
    """
        Returns EEM atomic partial charges
    
        C++ signature :
            boost::python::list CalcEEMcharges(RDKit::ROMol {lvalue} [,int=-1])
    """
def CalcEccentricity(mol: Mol, confId: int = -1, useAtomicMasses: bool = True, force: bool = True) -> float:
    """
        C++ signature :
            double CalcEccentricity(RDKit::ROMol [,int=-1 [,bool=True [,bool=True]]])
    """
def CalcExactMolWt(mol: Mol, onlyHeavy: bool = False) -> float:
    """
        returns the molecule's exact molecular weight
    
        C++ signature :
            double CalcExactMolWt(RDKit::ROMol [,bool=False])
    """
def CalcFractionCSP3(mol: Mol) -> float:
    """
        returns the fraction of C atoms that are SP3 hybridized
    
        C++ signature :
            double CalcFractionCSP3(RDKit::ROMol)
    """
def CalcGETAWAY(mol: Mol, confId: int = -1, precision: float = 2, CustomAtomProperty: str = '') -> list:
    """
        Returns the GETAWAY descriptors vector
    
        C++ signature :
            boost::python::list CalcGETAWAY(RDKit::ROMol [,int=-1 [,double=2 [,std::string='']]])
    """
def CalcHallKierAlpha(mol: Mol, atomContribs: AtomPairsParameters = None) -> float:
    """
        C++ signature :
            double CalcHallKierAlpha(RDKit::ROMol [,boost::python::api::object=None])
    """
def CalcInertialShapeFactor(mol: Mol, confId: int = -1, useAtomicMasses: bool = True, force: bool = True) -> float:
    """
        C++ signature :
            double CalcInertialShapeFactor(RDKit::ROMol [,int=-1 [,bool=True [,bool=True]]])
    """
def CalcKappa1(mol: Mol) -> float:
    """
        C++ signature :
            double CalcKappa1(RDKit::ROMol)
    """
def CalcKappa2(mol: Mol) -> float:
    """
        C++ signature :
            double CalcKappa2(RDKit::ROMol)
    """
def CalcKappa3(mol: Mol) -> float:
    """
        C++ signature :
            double CalcKappa3(RDKit::ROMol)
    """
def CalcLabuteASA(mol: Mol, includeHs: bool = True, force: bool = False) -> float:
    """
        returns the Labute ASA value for a molecule
    
        C++ signature :
            double CalcLabuteASA(RDKit::ROMol [,bool=True [,bool=False]])
    """
def CalcMORSE(mol: Mol, confId: int = -1, CustomAtomProperty: str = '') -> list:
    """
        Returns Molecule Representation of Structures based on Electron diffraction descriptors
    
        C++ signature :
            boost::python::list CalcMORSE(RDKit::ROMol [,int=-1 [,std::string='']])
    """
def CalcMolFormula(mol: Mol, separateIsotopes: bool = False, abbreviateHIsotopes: bool = True) -> str:
    """
        returns the molecule's formula
    
        C++ signature :
            std::string CalcMolFormula(RDKit::ROMol [,bool=False [,bool=True]])
    """
def CalcNPR1(mol: Mol, confId: int = -1, useAtomicMasses: bool = True, force: bool = True) -> float:
    """
        C++ signature :
            double CalcNPR1(RDKit::ROMol [,int=-1 [,bool=True [,bool=True]]])
    """
def CalcNPR2(mol: Mol, confId: int = -1, useAtomicMasses: bool = True, force: bool = True) -> float:
    """
        C++ signature :
            double CalcNPR2(RDKit::ROMol [,int=-1 [,bool=True [,bool=True]]])
    """
def CalcNumAliphaticCarbocycles(mol: Mol) -> int:
    """
        returns the number of aliphatic (containing at least one non-aromatic bond) carbocycles for a molecule
    
        C++ signature :
            unsigned int CalcNumAliphaticCarbocycles(RDKit::ROMol)
    """
def CalcNumAliphaticHeterocycles(mol: Mol) -> int:
    """
        returns the number of aliphatic (containing at least one non-aromatic bond) heterocycles for a molecule
    
        C++ signature :
            unsigned int CalcNumAliphaticHeterocycles(RDKit::ROMol)
    """
def CalcNumAliphaticRings(mol: Mol) -> int:
    """
        returns the number of aliphatic (containing at least one non-aromatic bond) rings for a molecule
    
        C++ signature :
            unsigned int CalcNumAliphaticRings(RDKit::ROMol)
    """
def CalcNumAmideBonds(mol: Mol) -> int:
    """
        returns the number of amide bonds in a molecule
    
        C++ signature :
            unsigned int CalcNumAmideBonds(RDKit::ROMol)
    """
def CalcNumAromaticCarbocycles(mol: Mol) -> int:
    """
        returns the number of aromatic carbocycles for a molecule
    
        C++ signature :
            unsigned int CalcNumAromaticCarbocycles(RDKit::ROMol)
    """
def CalcNumAromaticHeterocycles(mol: Mol) -> int:
    """
        returns the number of aromatic heterocycles for a molecule
    
        C++ signature :
            unsigned int CalcNumAromaticHeterocycles(RDKit::ROMol)
    """
def CalcNumAromaticRings(mol: Mol) -> int:
    """
        returns the number of aromatic rings for a molecule
    
        C++ signature :
            unsigned int CalcNumAromaticRings(RDKit::ROMol)
    """
def CalcNumAtomStereoCenters(mol: Mol) -> int:
    """
        Returns the total number of atomic stereocenters (specified and unspecified)
    
        C++ signature :
            unsigned int CalcNumAtomStereoCenters(RDKit::ROMol)
    """
def CalcNumAtoms(mol: Mol) -> int:
    """
        returns the total number of atoms for a molecule
    
        C++ signature :
            unsigned int CalcNumAtoms(RDKit::ROMol)
    """
def CalcNumBridgeheadAtoms(mol: Mol, atoms: AtomPairsParameters = None) -> int:
    """
        Returns the number of bridgehead atoms (atoms shared between rings that share at least two bonds)
    
        C++ signature :
            unsigned int CalcNumBridgeheadAtoms(RDKit::ROMol [,boost::python::api::object=None])
    """
def CalcNumHBA(mol: Mol) -> int:
    """
        returns the number of H-bond acceptors for a molecule
    
        C++ signature :
            unsigned int CalcNumHBA(RDKit::ROMol)
    """
def CalcNumHBD(mol: Mol) -> int:
    """
        returns the number of H-bond donors for a molecule
    
        C++ signature :
            unsigned int CalcNumHBD(RDKit::ROMol)
    """
def CalcNumHeavyAtoms(mol: Mol) -> int:
    """
        returns the number of heavy atoms for a molecule
    
        C++ signature :
            unsigned int CalcNumHeavyAtoms(RDKit::ROMol)
    """
def CalcNumHeteroatoms(mol: Mol) -> int:
    """
        returns the number of heteroatoms for a molecule
    
        C++ signature :
            unsigned int CalcNumHeteroatoms(RDKit::ROMol)
    """
def CalcNumHeterocycles(mol: Mol) -> int:
    """
        returns the number of heterocycles for a molecule
    
        C++ signature :
            unsigned int CalcNumHeterocycles(RDKit::ROMol)
    """
def CalcNumLipinskiHBA(mol: Mol) -> int:
    """
        returns the number of Lipinski H-bond acceptors for a molecule
    
        C++ signature :
            unsigned int CalcNumLipinskiHBA(RDKit::ROMol)
    """
def CalcNumLipinskiHBD(mol: Mol) -> int:
    """
        returns the number of Lipinski H-bond donors for a molecule
    
        C++ signature :
            unsigned int CalcNumLipinskiHBD(RDKit::ROMol)
    """
def CalcNumRings(mol: Mol) -> int:
    """
        returns the number of rings for a molecule
    
        C++ signature :
            unsigned int CalcNumRings(RDKit::ROMol)
    """
@typing.overload
def CalcNumRotatableBonds(mol: Mol, strict: bool) -> int:
    """
        returns the number of rotatable bonds for a molecule.
           strict = NumRotatableBondsOptions.NonStrict - Simple rotatable bond definition.
           strict = NumRotatableBondsOptions.Strict - (default) does not count things like
                    amide or ester bonds
           strict = NumRotatableBondsOptions.StrictLinkages - handles linkages between ring
              systems.
              - Single bonds between aliphatic ring Cs are always rotatable. This
                means that the central bond in CC1CCCC(C)C1-C1C(C)CCCC1C is now 
                considered rotatable; it was not before
              - Heteroatoms in the linked rings no longer affect whether or not
                the linking bond is rotatable
              - the linking bond in systems like Cc1cccc(C)c1-c1c(C)cccc1 is now
                 considered non-rotatable
    
        C++ signature :
            unsigned int CalcNumRotatableBonds(RDKit::ROMol,bool)
    """
@typing.overload
def CalcNumRotatableBonds(mol: Mol, strict: NumRotatableBondsOptions = ...) -> int:
    """
        returns the number of rotatable bonds for a molecule.
           strict = NumRotatableBondsOptions.NonStrict - Simple rotatable bond definition.
           strict = NumRotatableBondsOptions.Strict - (default) does not count things like
                    amide or ester bonds
           strict = NumRotatableBondsOptions.StrictLinkages - handles linkages between ring
              systems.
              - Single bonds between aliphatic ring Cs are always rotatable. This
                means that the central bond in CC1CCCC(C)C1-C1C(C)CCCC1C is now 
                considered rotatable; it was not before
              - Heteroatoms in the linked rings no longer affect whether or not
                the linking bond is rotatable
              - the linking bond in systems like Cc1cccc(C)c1-c1c(C)cccc1 is now
                 considered non-rotatable
    
        C++ signature :
            unsigned int CalcNumRotatableBonds(RDKit::ROMol [,RDKit::Descriptors::NumRotatableBondsOptions=rdkit.Chem.rdMolDescriptors.NumRotatableBondsOptions.Default])
    """
def CalcNumSaturatedCarbocycles(mol: Mol) -> int:
    """
        returns the number of saturated carbocycles for a molecule
    
        C++ signature :
            unsigned int CalcNumSaturatedCarbocycles(RDKit::ROMol)
    """
def CalcNumSaturatedHeterocycles(mol: Mol) -> int:
    """
        returns the number of saturated heterocycles for a molecule
    
        C++ signature :
            unsigned int CalcNumSaturatedHeterocycles(RDKit::ROMol)
    """
def CalcNumSaturatedRings(mol: Mol) -> int:
    """
        returns the number of saturated rings for a molecule
    
        C++ signature :
            unsigned int CalcNumSaturatedRings(RDKit::ROMol)
    """
def CalcNumSpiroAtoms(mol: Mol, atoms: AtomPairsParameters = None) -> int:
    """
        Returns the number of spiro atoms (atoms shared between rings that share exactly one atom)
    
        C++ signature :
            unsigned int CalcNumSpiroAtoms(RDKit::ROMol [,boost::python::api::object=None])
    """
def CalcNumUnspecifiedAtomStereoCenters(mol: Mol) -> int:
    """
        Returns the number of unspecified atomic stereocenters
    
        C++ signature :
            unsigned int CalcNumUnspecifiedAtomStereoCenters(RDKit::ROMol)
    """
def CalcOxidationNumbers(mol: Mol) -> None:
    """
        Adds the oxidation number/state to the atoms of a molecule as property OxidationNumber on each atom.  Use Pauling electronegativities.  This is experimental code, still under development.
    
        C++ signature :
            void CalcOxidationNumbers(RDKit::ROMol)
    """
def CalcPBF(mol: Mol, confId: int = -1) -> float:
    """
        Returns the PBF (plane of best fit) descriptor (https://doi.org/10.1021/ci300293f)
    
        C++ signature :
            double CalcPBF(RDKit::ROMol [,int=-1])
    """
def CalcPMI1(mol: Mol, confId: int = -1, useAtomicMasses: bool = True, force: bool = True) -> float:
    """
        C++ signature :
            double CalcPMI1(RDKit::ROMol [,int=-1 [,bool=True [,bool=True]]])
    """
def CalcPMI2(mol: Mol, confId: int = -1, useAtomicMasses: bool = True, force: bool = True) -> float:
    """
        C++ signature :
            double CalcPMI2(RDKit::ROMol [,int=-1 [,bool=True [,bool=True]]])
    """
def CalcPMI3(mol: Mol, confId: int = -1, useAtomicMasses: bool = True, force: bool = True) -> float:
    """
        C++ signature :
            double CalcPMI3(RDKit::ROMol [,int=-1 [,bool=True [,bool=True]]])
    """
def CalcPhi(mol: Mol) -> float:
    """
        C++ signature :
            double CalcPhi(RDKit::ROMol)
    """
def CalcRDF(mol: Mol, confId: int = -1, CustomAtomProperty: str = '') -> list:
    """
        Returns radial distribution fonction descriptors (RDF)
    
        C++ signature :
            boost::python::list CalcRDF(RDKit::ROMol [,int=-1 [,std::string='']])
    """
def CalcRadiusOfGyration(mol: Mol, confId: int = -1, useAtomicMasses: bool = True, force: bool = True) -> float:
    """
        C++ signature :
            double CalcRadiusOfGyration(RDKit::ROMol [,int=-1 [,bool=True [,bool=True]]])
    """
def CalcSpherocityIndex(mol: Mol, confId: int = -1, force: bool = True) -> float:
    """
        C++ signature :
            double CalcSpherocityIndex(RDKit::ROMol [,int=-1 [,bool=True]])
    """
def CalcTPSA(mol: Mol, force: bool = False, includeSandP: bool = False) -> float:
    """
        returns the TPSA value for a molecule
    
        C++ signature :
            double CalcTPSA(RDKit::ROMol [,bool=False [,bool=False]])
    """
def CalcWHIM(mol: Mol, confId: int = -1, thresh: float = 0.001, CustomAtomProperty: str = '') -> list:
    """
        Returns the WHIM descriptors vector
    
        C++ signature :
            boost::python::list CalcWHIM(RDKit::ROMol [,int=-1 [,double=0.001 [,std::string='']]])
    """
def CustomProp_VSA_(mol: Mol, customPropName: str, bins: AtomPairsParameters, force: bool = False) -> list:
    """
        C++ signature :
            boost::python::list CustomProp_VSA_(RDKit::ROMol,std::string,boost::python::api::object [,bool=False])
    """
def GetAtomFeatures(mol: Mol, atomid: int, addchiral: bool = False) -> list:
    """
        Returns the Atom Features vector
    
        C++ signature :
            boost::python::list GetAtomFeatures(RDKit::ROMol,int [,bool=False])
    """
def GetAtomPairAtomCode(atom: Atom, branchSubtract: int = 0, includeChirality: bool = False) -> int:
    """
        Returns the atom code (hash) for an atom
    
        C++ signature :
            unsigned int GetAtomPairAtomCode(RDKit::Atom const* [,unsigned int=0 [,bool=False]])
    """
def GetAtomPairCode(atom1Code: int, atom2Code: int, distance: int, includeChirality: bool = False) -> int:
    """
        Returns the atom-pair code (hash) for a pair of atoms separated by a certain number of bonds
    
        C++ signature :
            unsigned int GetAtomPairCode(unsigned int,unsigned int,unsigned int [,bool=False])
    """
def GetAtomPairFingerprint(mol: Mol, minLength: int = 1, maxLength: int = 30, fromAtoms: AtomPairsParameters = 0, ignoreAtoms: AtomPairsParameters = 0, atomInvariants: AtomPairsParameters = 0, includeChirality: bool = False, use2D: bool = True, confId: int = -1) -> IntSparseIntVect:
    """
        Returns the atom-pair fingerprint for a molecule as an IntSparseIntVect
    
        C++ signature :
            RDKit::SparseIntVect<int>* GetAtomPairFingerprint(RDKit::ROMol [,unsigned int=1 [,unsigned int=30 [,boost::python::api::object=0 [,boost::python::api::object=0 [,boost::python::api::object=0 [,bool=False [,bool=True [,int=-1]]]]]]]])
    """
def GetConnectivityInvariants(mol: Mol, includeRingMembership: bool = True) -> list:
    """
        Returns connectivity invariants (ECFP-like) for a molecule.
    
        C++ signature :
            boost::python::list GetConnectivityInvariants(RDKit::ROMol [,bool=True])
    """
def GetFeatureInvariants(mol: Mol) -> list:
    """
        Returns feature invariants (FCFP-like) for a molecule.
    
        C++ signature :
            boost::python::list GetFeatureInvariants(RDKit::ROMol)
    """
def GetHashedAtomPairFingerprint(mol: Mol, nBits: int = 2048, minLength: int = 1, maxLength: int = 30, fromAtoms: AtomPairsParameters = 0, ignoreAtoms: AtomPairsParameters = 0, atomInvariants: AtomPairsParameters = 0, includeChirality: bool = False, use2D: bool = True, confId: int = -1) -> IntSparseIntVect:
    """
        Returns the hashed atom-pair fingerprint for a molecule as an IntSparseIntVect
    
        C++ signature :
            RDKit::SparseIntVect<int>* GetHashedAtomPairFingerprint(RDKit::ROMol [,unsigned int=2048 [,unsigned int=1 [,unsigned int=30 [,boost::python::api::object=0 [,boost::python::api::object=0 [,boost::python::api::object=0 [,bool=False [,bool=True [,int=-1]]]]]]]]])
    """
def GetHashedAtomPairFingerprintAsBitVect(mol: Mol, nBits: int = 2048, minLength: int = 1, maxLength: int = 30, fromAtoms: AtomPairsParameters = 0, ignoreAtoms: AtomPairsParameters = 0, atomInvariants: AtomPairsParameters = 0, nBitsPerEntry: int = 4, includeChirality: bool = False, use2D: bool = True, confId: int = -1) -> ExplicitBitVect:
    """
        Returns the atom-pair fingerprint for a molecule as an ExplicitBitVect
    
        C++ signature :
            ExplicitBitVect* GetHashedAtomPairFingerprintAsBitVect(RDKit::ROMol [,unsigned int=2048 [,unsigned int=1 [,unsigned int=30 [,boost::python::api::object=0 [,boost::python::api::object=0 [,boost::python::api::object=0 [,unsigned int=4 [,bool=False [,bool=True [,int=-1]]]]]]]]]])
    """
def GetHashedMorganFingerprint(mol: Mol, radius: int, nBits: int = 2048, invariants: AtomPairsParameters = [], fromAtoms: AtomPairsParameters = [], useChirality: bool = False, useBondTypes: bool = True, useFeatures: bool = False, bitInfo: AtomPairsParameters = None, includeRedundantEnvironments: bool = False) -> UIntSparseIntVect:
    """
        Returns a hashed Morgan fingerprint for a molecule
    
        C++ signature :
            RDKit::SparseIntVect<unsigned int>* GetHashedMorganFingerprint(RDKit::ROMol,unsigned int [,unsigned int=2048 [,boost::python::api::object=[] [,boost::python::api::object=[] [,bool=False [,bool=True [,bool=False [,boost::python::api::object=None [,bool=False]]]]]]]])
    """
def GetHashedTopologicalTorsionFingerprint(mol: Mol, nBits: int = 2048, targetSize: int = 4, fromAtoms: AtomPairsParameters = 0, ignoreAtoms: AtomPairsParameters = 0, atomInvariants: AtomPairsParameters = 0, includeChirality: bool = False) -> LongSparseIntVect:
    """
        Returns the hashed topological-torsion fingerprint for a molecule as a LongIntSparseIntVect
    
        C++ signature :
            RDKit::SparseIntVect<long>* GetHashedTopologicalTorsionFingerprint(RDKit::ROMol [,unsigned int=2048 [,unsigned int=4 [,boost::python::api::object=0 [,boost::python::api::object=0 [,boost::python::api::object=0 [,bool=False]]]]]])
    """
def GetHashedTopologicalTorsionFingerprintAsBitVect(mol: Mol, nBits: int = 2048, targetSize: int = 4, fromAtoms: AtomPairsParameters = 0, ignoreAtoms: AtomPairsParameters = 0, atomInvariants: AtomPairsParameters = 0, nBitsPerEntry: int = 4, includeChirality: bool = False) -> ExplicitBitVect:
    """
        Returns the topological-torsion fingerprint for a molecule as an ExplicitBitVect
    
        C++ signature :
            ExplicitBitVect* GetHashedTopologicalTorsionFingerprintAsBitVect(RDKit::ROMol [,unsigned int=2048 [,unsigned int=4 [,boost::python::api::object=0 [,boost::python::api::object=0 [,boost::python::api::object=0 [,unsigned int=4 [,bool=False]]]]]]])
    """
def GetMACCSKeysFingerprint(mol: Mol) -> ExplicitBitVect:
    """
        Returns the MACCS keys for a molecule as an ExplicitBitVect
    
        C++ signature :
            ExplicitBitVect* GetMACCSKeysFingerprint(RDKit::ROMol)
    """
def GetMorganFingerprint(mol: Mol, radius: int, invariants: AtomPairsParameters = [], fromAtoms: AtomPairsParameters = [], useChirality: bool = False, useBondTypes: bool = True, useFeatures: bool = False, useCounts: bool = True, bitInfo: AtomPairsParameters = None, includeRedundantEnvironments: bool = False) -> UIntSparseIntVect:
    """
        Returns a Morgan fingerprint for a molecule
    
        C++ signature :
            RDKit::SparseIntVect<unsigned int>* GetMorganFingerprint(RDKit::ROMol,unsigned int [,boost::python::api::object=[] [,boost::python::api::object=[] [,bool=False [,bool=True [,bool=False [,bool=True [,boost::python::api::object=None [,bool=False]]]]]]]])
    """
def GetMorganFingerprintAsBitVect(mol: Mol, radius: int, nBits: int = 2048, invariants: AtomPairsParameters = [], fromAtoms: AtomPairsParameters = [], useChirality: bool = False, useBondTypes: bool = True, useFeatures: bool = False, bitInfo: AtomPairsParameters = None, includeRedundantEnvironments: bool = False) -> ExplicitBitVect:
    """
        Returns a Morgan fingerprint for a molecule as a bit vector
    
        C++ signature :
            ExplicitBitVect* GetMorganFingerprintAsBitVect(RDKit::ROMol,unsigned int [,unsigned int=2048 [,boost::python::api::object=[] [,boost::python::api::object=[] [,bool=False [,bool=True [,bool=False [,boost::python::api::object=None [,bool=False]]]]]]]])
    """
def GetTopologicalTorsionFingerprint(mol: Mol, targetSize: int = 4, fromAtoms: AtomPairsParameters = 0, ignoreAtoms: AtomPairsParameters = 0, atomInvariants: AtomPairsParameters = 0, includeChirality: bool = False) -> LongSparseIntVect:
    """
        Returns the topological-torsion fingerprint for a molecule as a LongIntSparseIntVect
    
        C++ signature :
            RDKit::SparseIntVect<long>* GetTopologicalTorsionFingerprint(RDKit::ROMol [,unsigned int=4 [,boost::python::api::object=0 [,boost::python::api::object=0 [,boost::python::api::object=0 [,bool=False]]]]])
    """
def GetUSR(mol: Mol, confId: int = -1) -> list:
    """
        Returns a USR descriptor for one conformer of a molecule
    
        C++ signature :
            boost::python::list GetUSR(RDKit::ROMol [,int=-1])
    """
def GetUSRCAT(mol: Mol, atomSelections: AtomPairsParameters = None, confId: int = -1) -> list:
    """
        Returns a USRCAT descriptor for one conformer of a molecule
    
        C++ signature :
            boost::python::list GetUSRCAT(RDKit::ROMol [,boost::python::api::object=None [,int=-1]])
    """
def GetUSRDistributions(coords: AtomPairsParameters, points: AtomPairsParameters = None) -> list:
    """
        Returns the four USR distance distributions for a set of coordinates
    
        C++ signature :
            boost::python::list GetUSRDistributions(boost::python::api::object [,boost::python::api::object=None])
    """
def GetUSRDistributionsFromPoints(coords: AtomPairsParameters, points: AtomPairsParameters) -> list:
    """
        Returns the USR distance distributions for a set of coordinates and points
    
        C++ signature :
            boost::python::list GetUSRDistributionsFromPoints(boost::python::api::object,boost::python::api::object)
    """
def GetUSRFromDistributions(distances: AtomPairsParameters) -> list:
    """
        Returns the USR descriptor from a set of distance distributions
    
        C++ signature :
            boost::python::list GetUSRFromDistributions(boost::python::api::object)
    """
def GetUSRScore(descriptor1: AtomPairsParameters, descriptor2: AtomPairsParameters, weights: AtomPairsParameters = []) -> float:
    """
        Returns the USR score for two USR or USRCAT descriptors
    
        C++ signature :
            double GetUSRScore(boost::python::api::object,boost::python::api::object [,boost::python::api::object=[]])
    """
def MQNs_(mol: Mol, force: bool = False) -> list:
    """
        C++ signature :
            boost::python::list MQNs_(RDKit::ROMol [,bool=False])
    """
def MakePropertyRangeQuery(name: str, min: float, max: float) -> PropertyRangeQuery:
    """
        Generates a Range property for the specified property, between min and max
        query = MakePropertyRangeQuery('exactmw', 0, 500)
        query.Match( mol )
    
        C++ signature :
            Queries::RangeQuery<double, RDKit::ROMol const&, true>* MakePropertyRangeQuery(std::string,double,double)
    """
def PEOE_VSA_(mol: Mol, bins: AtomPairsParameters = [], force: bool = False) -> list:
    """
        C++ signature :
            boost::python::list PEOE_VSA_(RDKit::ROMol [,boost::python::api::object=[] [,bool=False]])
    """
def SMR_VSA_(mol: Mol, bins: AtomPairsParameters = [], force: bool = False) -> list:
    """
        C++ signature :
            boost::python::list SMR_VSA_(RDKit::ROMol [,boost::python::api::object=[] [,bool=False]])
    """
def SlogP_VSA_(mol: Mol, bins: AtomPairsParameters = [], force: bool = False) -> list:
    """
        C++ signature :
            boost::python::list SlogP_VSA_(RDKit::ROMol [,boost::python::api::object=[] [,bool=False]])
    """
def _CalcCrippenContribs(mol: Mol, force: bool = False, atomTypes: list = [], atomTypeLabels: list = []) -> list:
    """
        returns (as a list of 2-tuples) the contributions of each atom to
        the Wildman-Cripppen logp and mr value
    
        C++ signature :
            boost::python::list _CalcCrippenContribs(RDKit::ROMol [,bool=False [,boost::python::list=[] [,boost::python::list=[]]]])
    """
def _CalcLabuteASAContribs(mol: Mol, includeHs: bool = True, force: bool = False) -> tuple:
    """
        returns a list of atomic contributions to the Labute ASA
    
        C++ signature :
            boost::python::tuple _CalcLabuteASAContribs(RDKit::ROMol [,bool=True [,bool=False]])
    """
def _CalcMolWt(mol: Mol, onlyHeavy: bool = False) -> float:
    """
        returns the molecule's molecular weight
    
        C++ signature :
            double _CalcMolWt(RDKit::ROMol [,bool=False])
    """
def _CalcTPSAContribs(mol: Mol, force: bool = False, includeSandP: bool = False) -> tuple:
    """
        returns a list of atomic contributions to the TPSA
    
        C++ signature :
            boost::python::tuple _CalcTPSAContribs(RDKit::ROMol [,bool=False [,bool=False]])
    """
_BCUT2D_version: str = '1.0.0'
_CalcAUTOCORR2D_version: str = '1.0.0'
_CalcAUTOCORR3D_version: str = '1.0.0'
_CalcAsphericity_version: str = '1.0.0'
_CalcChi0n_version: str = '1.2.0'
_CalcChi0v_version: str = '1.2.0'
_CalcChi1n_version: str = '1.2.0'
_CalcChi1v_version: str = '1.2.0'
_CalcChi2n_version: str = '1.2.0'
_CalcChi2v_version: str = '1.2.0'
_CalcChi3n_version: str = '1.2.0'
_CalcChi3v_version: str = '1.2.0'
_CalcChi4n_version: str = '1.2.0'
_CalcChi4v_version: str = '1.2.0'
_CalcChiNn_version: str = '1.2.0'
_CalcChiNv_version: str = '1.2.0'
_CalcCoulombMat_version: str = '1.0.0'
_CalcCrippenDescriptors_version: str = '1.2.0'
_CalcEMMcharges_version: str = '1.0.0'
_CalcEccentricity_version: str = '1.0.0'
_CalcExactMolWt_version: str = '1.0.0'
_CalcFractionCSP3_version: str = '1.0.0'
_CalcGETAWAY_version: str = '1.0.0'
_CalcHallKierAlpha_version: str = '1.2.0'
_CalcInertialShapeFactor_version: str = '1.0.0'
_CalcKappa1_version: str = '1.1.0'
_CalcKappa2_version: str = '1.1.0'
_CalcKappa3_version: str = '1.1.0'
_CalcLabuteASA_version: str = '1.0.2'
_CalcMORSE_version: str = '1.0.0'
_CalcMolFormula_version: str = '1.3.0'
_CalcMolWt_version: str = '1.0.0'
_CalcNPR1_version: str = '1.0.0'
_CalcNPR2_version: str = '1.0.0'
_CalcNumAliphaticCarbocycles_version: str = '1.0.0'
_CalcNumAliphaticHeterocycles_version: str = '1.0.0'
_CalcNumAliphaticRings_version: str = '1.0.0'
_CalcNumAmideBonds_version: str = '1.0.0'
_CalcNumAromaticCarbocycles_version: str = '1.0.0'
_CalcNumAromaticHeterocycles_version: str = '1.0.0'
_CalcNumAromaticRings_version: str = '1.0.0'
_CalcNumAtomStereoCenters_version: str = '1.0.1'
_CalcNumAtoms_version: str = '1.0.0'
_CalcNumBridgeheadAtoms_version: str = '2.0.0'
_CalcNumHBA_version: str = '2.0.1'
_CalcNumHBD_version: str = '2.0.1'
_CalcNumHeavyAtoms_version: str = '1.0.0'
_CalcNumHeteroatoms_version: str = '1.0.1'
_CalcNumHeterocycles_version: str = '1.0.0'
_CalcNumLipinskiHBA_version: str = '1.0.0'
_CalcNumLipinskiHBD_version: str = '2.0.0'
_CalcNumRings_version: str = '1.0.1'
_CalcNumRotatableBonds_version: str = '3.1.0'
_CalcNumSaturatedCarbocycles_version: str = '1.0.0'
_CalcNumSaturatedHeterocycles_version: str = '1.0.0'
_CalcNumSaturatedRings_version: str = '1.0.0'
_CalcNumSpiroAtoms_version: str = '1.0.0'
_CalcNumUnspecifiedAtomStereoCenters_version: str = '1.0.1'
_CalcPBF_version: str = '1.0.0'
_CalcPMI1_version: str = '1.0.0'
_CalcPMI2_version: str = '1.0.0'
_CalcPMI3_version: str = '1.0.0'
_CalcPhi_version: str = '1.0.0'
_CalcRDF_version: str = '1.0.0'
_CalcRadiusOfGyration_version: str = '1.0.0'
_CalcSpherocityIndex_version: str = '1.0.0'
_CalcTPSA_version: str = '2.0.0'
_CalcWHIM_version: str = '1.0.0'
_ConnectivityInvariants_version: str = '1.0.0'
_FeatureInvariants_version: str = '0.1.0'
_GetAtomFeatures_version: str = '1.0.0'
_MorganFingerprint_version: str = '1.0.0'
