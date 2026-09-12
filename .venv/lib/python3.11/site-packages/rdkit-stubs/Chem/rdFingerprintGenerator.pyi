from __future__ import annotations
import typing
__all__ = ['AdditionalOutput', 'AtomInvariantsGenerator', 'AtomPairFP', 'AtomPairFingerprintOptions', 'BondInvariantsGenerator', 'FPType', 'FingerprintGenerator32', 'FingerprintGenerator64', 'FingerprintOptions', 'GetAtomPairAtomInvGen', 'GetAtomPairGenerator', 'GetCountFPs', 'GetFPs', 'GetMorganAtomInvGen', 'GetMorganBondInvGen', 'GetMorganFeatureAtomInvGen', 'GetMorganGenerator', 'GetRDKitAtomInvGen', 'GetRDKitFPGenerator', 'GetSparseCountFPs', 'GetSparseFPs', 'GetTopologicalTorsionGenerator', 'MorganFP', 'MorganFingerprintOptions', 'RDKitFP', 'RDKitFingerprintOptions', 'TopologicalTorsionFP', 'TopologicalTorsionFingerprintOptions']
class AdditionalOutput(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 88
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def AllocateAtomCounts(self) -> None:
        """
            synonym for CollectAtomCounts()
        
            C++ signature :
                void AllocateAtomCounts(RDKit::AdditionalOutput {lvalue})
        """
    def AllocateAtomToBits(self) -> None:
        """
            synonym for CollectAtomToBits()
        
            C++ signature :
                void AllocateAtomToBits(RDKit::AdditionalOutput {lvalue})
        """
    def AllocateBitInfoMap(self) -> None:
        """
            synonym for CollectBitInfoMap()
        
            C++ signature :
                void AllocateBitInfoMap(RDKit::AdditionalOutput {lvalue})
        """
    def AllocateBitPaths(self) -> None:
        """
            synonym for CollectBitPaths()
        
            C++ signature :
                void AllocateBitPaths(RDKit::AdditionalOutput {lvalue})
        """
    def CollectAtomCounts(self) -> None:
        """
            toggles collection of information about the number of bits each atom is involved in
        
            C++ signature :
                void CollectAtomCounts(RDKit::AdditionalOutput {lvalue})
        """
    def CollectAtomToBits(self) -> None:
        """
            toggle collection of information mapping each atom to the bits it is involved in.
        
            C++ signature :
                void CollectAtomToBits(RDKit::AdditionalOutput {lvalue})
        """
    def CollectBitInfoMap(self) -> None:
        """
            toggles collection of information mapping each atom to more detail about the atom environment (not available from all fingerprints)
        
            C++ signature :
                void CollectBitInfoMap(RDKit::AdditionalOutput {lvalue})
        """
    def CollectBitPaths(self) -> None:
        """
            toggles collection of information matching each atom to information about the paths it is involved in (not available from all fingerprints).
        
            C++ signature :
                void CollectBitPaths(RDKit::AdditionalOutput {lvalue})
        """
    def GetAtomCounts(self) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object GetAtomCounts(RDKit::AdditionalOutput)
        """
    def GetAtomToBits(self) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object GetAtomToBits(RDKit::AdditionalOutput)
        """
    def GetBitInfoMap(self) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object GetBitInfoMap(RDKit::AdditionalOutput)
        """
    def GetBitPaths(self) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object GetBitPaths(RDKit::AdditionalOutput)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
class AtomInvariantsGenerator(Boost.Python.instance):
    @staticmethod
    def __init__(*args, **kwargs):
        """
        Raises an exception
        This class cannot be instantiated from Python
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
class AtomPairFingerprintOptions(FingerprintOptions):
    @staticmethod
    def __init__(*args, **kwargs):
        """
        Raises an exception
        This class cannot be instantiated from Python
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    @property
    def maxDistance(*args, **kwargs):
        """
        maximum distance to be included
        """
    @maxDistance.setter
    def maxDistance(*args, **kwargs):
        ...
    @property
    def minDistance(*args, **kwargs):
        """
        minimum distance to be included
        """
    @minDistance.setter
    def minDistance(*args, **kwargs):
        ...
    @property
    def use2D(*args, **kwargs):
        """
        use 2D distances
        """
    @use2D.setter
    def use2D(*args, **kwargs):
        ...
class BondInvariantsGenerator(Boost.Python.instance):
    @staticmethod
    def __init__(*args, **kwargs):
        """
        Raises an exception
        This class cannot be instantiated from Python
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
class FPType(Boost.Python.enum):
    AtomPairFP: typing.ClassVar[FPType]  # value = rdkit.Chem.rdFingerprintGenerator.FPType.AtomPairFP
    MorganFP: typing.ClassVar[FPType]  # value = rdkit.Chem.rdFingerprintGenerator.FPType.MorganFP
    RDKitFP: typing.ClassVar[FPType]  # value = rdkit.Chem.rdFingerprintGenerator.FPType.RDKitFP
    TopologicalTorsionFP: typing.ClassVar[FPType]  # value = rdkit.Chem.rdFingerprintGenerator.FPType.TopologicalTorsionFP
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'RDKitFP': rdkit.Chem.rdFingerprintGenerator.FPType.RDKitFP, 'MorganFP': rdkit.Chem.rdFingerprintGenerator.FPType.MorganFP, 'AtomPairFP': rdkit.Chem.rdFingerprintGenerator.FPType.AtomPairFP, 'TopologicalTorsionFP': rdkit.Chem.rdFingerprintGenerator.FPType.TopologicalTorsionFP}
    values: typing.ClassVar[dict]  # value = {2: rdkit.Chem.rdFingerprintGenerator.FPType.RDKitFP, 1: rdkit.Chem.rdFingerprintGenerator.FPType.MorganFP, 0: rdkit.Chem.rdFingerprintGenerator.FPType.AtomPairFP, 3: rdkit.Chem.rdFingerprintGenerator.FPType.TopologicalTorsionFP}
class FingerprintGenerator32(Boost.Python.instance):
    @staticmethod
    def __init__(*args, **kwargs):
        """
        Raises an exception
        This class cannot be instantiated from Python
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def GetCountFingerprint(self, mol: Mol, fromAtoms: typing.Any = [], ignoreAtoms: typing.Any = [], confId: int = -1, customAtomInvariants: typing.Any = [], customBondInvariants: typing.Any = [], additionalOutput: typing.Any = None) -> UIntSparseIntVect:
        """
            Generates a count fingerprint
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - fromAtoms: indices of atoms to use while generating the fingerprint
                - ignoreAtoms: indices of atoms to exclude while generating the fingerprint
                - confId: 3D confirmation to use, only used by AtomPair fingerprint
                - customAtomInvariants: custom atom invariants to be used, overrides invariants from the invariant generator
                - customBondInvariants: custom bond invariants to be used, overrides invariants from the invariant generator
            
                - additionalOutput: AdditionalOutput instance used to return extra information about the bits
            
              RETURNS: a SparseIntVect containing fingerprint
            
            
        
            C++ signature :
                RDKit::SparseIntVect<unsigned int>* GetCountFingerprint(RDKit::FingerprintGenerator<unsigned int> const*,RDKit::ROMol [,boost::python::api::object=[] [,boost::python::api::object=[] [,int=-1 [,boost::python::api::object=[] [,boost::python::api::object=[] [,boost::python::api::object=None]]]]]])
        """
    def GetCountFingerprintAsNumPy(self, mol: Mol, fromAtoms: typing.Any = [], ignoreAtoms: typing.Any = [], confId: int = -1, customAtomInvariants: typing.Any = [], customBondInvariants: typing.Any = [], additionalOutput: typing.Any = None) -> typing.Any:
        """
            Generates a count fingerprint
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - fromAtoms: indices of atoms to use while generating the fingerprint
                - ignoreAtoms: indices of atoms to exclude while generating the fingerprint
                - confId: 3D confirmation to use, only used by AtomPair fingerprint
                - customAtomInvariants: custom atom invariants to be used, overrides invariants from the invariant generator
                - customBondInvariants: custom bond invariants to be used, overrides invariants from the invariant generator
            
                - additionalOutput: AdditionalOutput instance used to return extra information about the bits
            
              RETURNS: a numpy array containing the fingerprint
            
            
        
            C++ signature :
                boost::python::api::object GetCountFingerprintAsNumPy(RDKit::FingerprintGenerator<unsigned int> const*,RDKit::ROMol [,boost::python::api::object=[] [,boost::python::api::object=[] [,int=-1 [,boost::python::api::object=[] [,boost::python::api::object=[] [,boost::python::api::object=None]]]]]])
        """
    def GetCountFingerprints(self, mols: typing.Any, numThreads: int = 1) -> tuple:
        """
            Generates count fingerprints for a sequence of molecules
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - numThreads: number of threads to use
            
              RETURNS: a tuple of SparseIntVects
            
            
        
            C++ signature :
                boost::python::tuple GetCountFingerprints(RDKit::FingerprintGenerator<unsigned int> const*,boost::python::api::object [,int=1])
        """
    def GetFingerprint(self, mol: Mol, fromAtoms: typing.Any = [], ignoreAtoms: typing.Any = [], confId: int = -1, customAtomInvariants: typing.Any = [], customBondInvariants: typing.Any = [], additionalOutput: typing.Any = None) -> ExplicitBitVect:
        """
            Generates a fingerprint
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - fromAtoms: indices of atoms to use while generating the fingerprint
                - ignoreAtoms: indices of atoms to exclude while generating the fingerprint
                - confId: 3D confirmation to use, only used by AtomPair fingerprint
                - customAtomInvariants: custom atom invariants to be used, overrides invariants from the invariant generator
                - customBondInvariants: custom bond invariants to be used, overrides invariants from the invariant generator
            
                - additionalOutput: AdditionalOutput instance used to return extra information about the bits
            
              RETURNS: a ExplicitBitVect containing fingerprint
            
            
        
            C++ signature :
                ExplicitBitVect* GetFingerprint(RDKit::FingerprintGenerator<unsigned int> const*,RDKit::ROMol [,boost::python::api::object=[] [,boost::python::api::object=[] [,int=-1 [,boost::python::api::object=[] [,boost::python::api::object=[] [,boost::python::api::object=None]]]]]])
        """
    def GetFingerprintAsNumPy(self, mol: Mol, fromAtoms: typing.Any = [], ignoreAtoms: typing.Any = [], confId: int = -1, customAtomInvariants: typing.Any = [], customBondInvariants: typing.Any = [], additionalOutput: typing.Any = None) -> typing.Any:
        """
            Generates a fingerprint
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - fromAtoms: indices of atoms to use while generating the fingerprint
                - ignoreAtoms: indices of atoms to exclude while generating the fingerprint
                - confId: 3D confirmation to use, only used by AtomPair fingerprint
                - customAtomInvariants: custom atom invariants to be used, overrides invariants from the invariant generator
                - customBondInvariants: custom bond invariants to be used, overrides invariants from the invariant generator
            
                - additionalOutput: AdditionalOutput instance used to return extra information about the bits
            
              RETURNS: a numpy array containing the fingerprint
            
            
        
            C++ signature :
                boost::python::api::object GetFingerprintAsNumPy(RDKit::FingerprintGenerator<unsigned int> const*,RDKit::ROMol [,boost::python::api::object=[] [,boost::python::api::object=[] [,int=-1 [,boost::python::api::object=[] [,boost::python::api::object=[] [,boost::python::api::object=None]]]]]])
        """
    def GetFingerprints(self, mols: typing.Any, numThreads: int = 1) -> tuple:
        """
            Generates fingerprints for a sequence of molecules
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - numThreads: number of threads to use
            
              RETURNS: a tuple of ExplicitBitVects
            
            
        
            C++ signature :
                boost::python::tuple GetFingerprints(RDKit::FingerprintGenerator<unsigned int> const*,boost::python::api::object [,int=1])
        """
    def GetInfoString(self) -> str:
        """
            Returns a string containing information about the fingerprint generator
            
              RETURNS: an information string
            
            
        
            C++ signature :
                std::string GetInfoString(RDKit::FingerprintGenerator<unsigned int> const*)
        """
    def GetOptions(self) -> FingerprintOptions:
        """
            return the fingerprint options object
        
            C++ signature :
                RDKit::FingerprintArguments* GetOptions(RDKit::FingerprintGenerator<unsigned int>*)
        """
    def GetSparseCountFingerprint(self, mol: Mol, fromAtoms: typing.Any = [], ignoreAtoms: typing.Any = [], confId: int = -1, customAtomInvariants: typing.Any = [], customBondInvariants: typing.Any = [], additionalOutput: typing.Any = None) -> UIntSparseIntVect:
        """
            Generates a sparse count fingerprint
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - fromAtoms: indices of atoms to use while generating the fingerprint
                - ignoreAtoms: indices of atoms to exclude while generating the fingerprint
                - confId: 3D confirmation to use, only used by AtomPair fingerprint
                - customAtomInvariants: custom atom invariants to be used, overrides invariants from the invariant generator
                - customBondInvariants: custom bond invariants to be used, overrides invariants from the invariant generator
            
                - additionalOutput: AdditionalOutput instance used to return extra information about the bits
            
              RETURNS: a SparseIntVect containing fingerprint
            
            
        
            C++ signature :
                RDKit::SparseIntVect<unsigned int>* GetSparseCountFingerprint(RDKit::FingerprintGenerator<unsigned int> const*,RDKit::ROMol [,boost::python::api::object=[] [,boost::python::api::object=[] [,int=-1 [,boost::python::api::object=[] [,boost::python::api::object=[] [,boost::python::api::object=None]]]]]])
        """
    def GetSparseCountFingerprints(self, mols: typing.Any, numThreads: int = 1) -> tuple:
        """
            Generates sparse count fingerprints for a sequence of molecules
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - numThreads: number of threads to use
            
              RETURNS: a tuple of SparseIntVects
            
            
        
            C++ signature :
                boost::python::tuple GetSparseCountFingerprints(RDKit::FingerprintGenerator<unsigned int> const*,boost::python::api::object [,int=1])
        """
    def GetSparseFingerprint(self, mol: Mol, fromAtoms: typing.Any = [], ignoreAtoms: typing.Any = [], confId: int = -1, customAtomInvariants: typing.Any = [], customBondInvariants: typing.Any = [], additionalOutput: typing.Any = None) -> SparseBitVect:
        """
            Generates a sparse fingerprint
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - fromAtoms: indices of atoms to use while generating the fingerprint
                - ignoreAtoms: indices of atoms to exclude while generating the fingerprint
                - confId: 3D confirmation to use, only used by AtomPair fingerprint
                - customAtomInvariants: custom atom invariants to be used, overrides invariants from the invariant generator
                - customBondInvariants: custom bond invariants to be used, overrides invariants from the invariant generator
            
                - additionalOutput: AdditionalOutput instance used to return extra information about the bits
            
              RETURNS: a SparseBitVect containing fingerprint
            
            
        
            C++ signature :
                SparseBitVect* GetSparseFingerprint(RDKit::FingerprintGenerator<unsigned int> const*,RDKit::ROMol [,boost::python::api::object=[] [,boost::python::api::object=[] [,int=-1 [,boost::python::api::object=[] [,boost::python::api::object=[] [,boost::python::api::object=None]]]]]])
        """
    def GetSparseFingerprints(self, mols: typing.Any, numThreads: int = 1) -> tuple:
        """
            Generates sparse fingerprints for a sequence of molecules
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - numThreads: number of threads to use
            
              RETURNS: a tuple of SparseBitVects
            
            
        
            C++ signature :
                boost::python::tuple GetSparseFingerprints(RDKit::FingerprintGenerator<unsigned int> const*,boost::python::api::object [,int=1])
        """
class FingerprintGenerator64(Boost.Python.instance):
    @staticmethod
    def __init__(*args, **kwargs):
        """
        Raises an exception
        This class cannot be instantiated from Python
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def GetCountFingerprint(self, mol: Mol, fromAtoms: typing.Any = [], ignoreAtoms: typing.Any = [], confId: int = -1, customAtomInvariants: typing.Any = [], customBondInvariants: typing.Any = [], additionalOutput: typing.Any = None) -> UIntSparseIntVect:
        """
            Generates a count fingerprint
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - fromAtoms: indices of atoms to use while generating the fingerprint
                - ignoreAtoms: indices of atoms to exclude while generating the fingerprint
                - confId: 3D confirmation to use, only used by AtomPair fingerprint
                - customAtomInvariants: custom atom invariants to be used, overrides invariants from the invariant generator
                - customBondInvariants: custom bond invariants to be used, overrides invariants from the invariant generator
            
                - additionalOutput: AdditionalOutput instance used to return extra information about the bits
            
              RETURNS: a SparseIntVect containing fingerprint
            
            
        
            C++ signature :
                RDKit::SparseIntVect<unsigned int>* GetCountFingerprint(RDKit::FingerprintGenerator<unsigned long> const*,RDKit::ROMol [,boost::python::api::object=[] [,boost::python::api::object=[] [,int=-1 [,boost::python::api::object=[] [,boost::python::api::object=[] [,boost::python::api::object=None]]]]]])
        """
    def GetCountFingerprintAsNumPy(self, mol: Mol, fromAtoms: typing.Any = [], ignoreAtoms: typing.Any = [], confId: int = -1, customAtomInvariants: typing.Any = [], customBondInvariants: typing.Any = [], additionalOutput: typing.Any = None) -> typing.Any:
        """
            Generates a count fingerprint
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - fromAtoms: indices of atoms to use while generating the fingerprint
                - ignoreAtoms: indices of atoms to exclude while generating the fingerprint
                - confId: 3D confirmation to use, only used by AtomPair fingerprint
                - customAtomInvariants: custom atom invariants to be used, overrides invariants from the invariant generator
                - customBondInvariants: custom bond invariants to be used, overrides invariants from the invariant generator
            
                - additionalOutput: AdditionalOutput instance used to return extra information about the bits
            
              RETURNS: a numpy array containing the fingerprint
            
            
        
            C++ signature :
                boost::python::api::object GetCountFingerprintAsNumPy(RDKit::FingerprintGenerator<unsigned long> const*,RDKit::ROMol [,boost::python::api::object=[] [,boost::python::api::object=[] [,int=-1 [,boost::python::api::object=[] [,boost::python::api::object=[] [,boost::python::api::object=None]]]]]])
        """
    def GetCountFingerprints(self, mols: typing.Any, numThreads: int = 1) -> tuple:
        """
            Generates count fingerprints for a sequence of molecules
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - numThreads: number of threads to use
            
              RETURNS: a tuple of SparseIntVects
            
            
        
            C++ signature :
                boost::python::tuple GetCountFingerprints(RDKit::FingerprintGenerator<unsigned long> const*,boost::python::api::object [,int=1])
        """
    def GetFingerprint(self, mol: Mol, fromAtoms: typing.Any = [], ignoreAtoms: typing.Any = [], confId: int = -1, customAtomInvariants: typing.Any = [], customBondInvariants: typing.Any = [], additionalOutput: typing.Any = None) -> ExplicitBitVect:
        """
            Generates a fingerprint
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - fromAtoms: indices of atoms to use while generating the fingerprint
                - ignoreAtoms: indices of atoms to exclude while generating the fingerprint
                - confId: 3D confirmation to use, only used by AtomPair fingerprint
                - customAtomInvariants: custom atom invariants to be used, overrides invariants from the invariant generator
                - customBondInvariants: custom bond invariants to be used, overrides invariants from the invariant generator
            
                - additionalOutput: AdditionalOutput instance used to return extra information about the bits
            
              RETURNS: a ExplicitBitVect containing fingerprint
            
            
        
            C++ signature :
                ExplicitBitVect* GetFingerprint(RDKit::FingerprintGenerator<unsigned long> const*,RDKit::ROMol [,boost::python::api::object=[] [,boost::python::api::object=[] [,int=-1 [,boost::python::api::object=[] [,boost::python::api::object=[] [,boost::python::api::object=None]]]]]])
        """
    def GetFingerprintAsNumPy(self, mol: Mol, fromAtoms: typing.Any = [], ignoreAtoms: typing.Any = [], confId: int = -1, customAtomInvariants: typing.Any = [], customBondInvariants: typing.Any = [], additionalOutput: typing.Any = None) -> typing.Any:
        """
            Generates a fingerprint
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - fromAtoms: indices of atoms to use while generating the fingerprint
                - ignoreAtoms: indices of atoms to exclude while generating the fingerprint
                - confId: 3D confirmation to use, only used by AtomPair fingerprint
                - customAtomInvariants: custom atom invariants to be used, overrides invariants from the invariant generator
                - customBondInvariants: custom bond invariants to be used, overrides invariants from the invariant generator
            
                - additionalOutput: AdditionalOutput instance used to return extra information about the bits
            
              RETURNS: a numpy array containing the fingerprint
            
            
        
            C++ signature :
                boost::python::api::object GetFingerprintAsNumPy(RDKit::FingerprintGenerator<unsigned long> const*,RDKit::ROMol [,boost::python::api::object=[] [,boost::python::api::object=[] [,int=-1 [,boost::python::api::object=[] [,boost::python::api::object=[] [,boost::python::api::object=None]]]]]])
        """
    def GetFingerprints(self, mols: typing.Any, numThreads: int = 1) -> tuple:
        """
            Generates fingerprints for a sequence of molecules
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - numThreads: number of threads to use
            
              RETURNS: a tuple of ExplicitBitVects
            
            
        
            C++ signature :
                boost::python::tuple GetFingerprints(RDKit::FingerprintGenerator<unsigned long> const*,boost::python::api::object [,int=1])
        """
    def GetInfoString(self) -> str:
        """
            Returns a string containing information about the fingerprint generator
            
              RETURNS: an information string
            
            
        
            C++ signature :
                std::string GetInfoString(RDKit::FingerprintGenerator<unsigned long> const*)
        """
    def GetOptions(self) -> FingerprintOptions:
        """
            return the fingerprint options object
        
            C++ signature :
                RDKit::FingerprintArguments* GetOptions(RDKit::FingerprintGenerator<unsigned long>*)
        """
    def GetSparseCountFingerprint(self, mol: Mol, fromAtoms: typing.Any = [], ignoreAtoms: typing.Any = [], confId: int = -1, customAtomInvariants: typing.Any = [], customBondInvariants: typing.Any = [], additionalOutput: typing.Any = None) -> ULongSparseIntVect:
        """
            Generates a sparse count fingerprint
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - fromAtoms: indices of atoms to use while generating the fingerprint
                - ignoreAtoms: indices of atoms to exclude while generating the fingerprint
                - confId: 3D confirmation to use, only used by AtomPair fingerprint
                - customAtomInvariants: custom atom invariants to be used, overrides invariants from the invariant generator
                - customBondInvariants: custom bond invariants to be used, overrides invariants from the invariant generator
            
                - additionalOutput: AdditionalOutput instance used to return extra information about the bits
            
              RETURNS: a SparseIntVect containing fingerprint
            
            
        
            C++ signature :
                RDKit::SparseIntVect<unsigned long>* GetSparseCountFingerprint(RDKit::FingerprintGenerator<unsigned long> const*,RDKit::ROMol [,boost::python::api::object=[] [,boost::python::api::object=[] [,int=-1 [,boost::python::api::object=[] [,boost::python::api::object=[] [,boost::python::api::object=None]]]]]])
        """
    def GetSparseCountFingerprints(self, mols: typing.Any, numThreads: int = 1) -> tuple:
        """
            Generates sparse count fingerprints for a sequence of molecules
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - numThreads: number of threads to use
            
              RETURNS: a tuple of SparseIntVects
            
            
        
            C++ signature :
                boost::python::tuple GetSparseCountFingerprints(RDKit::FingerprintGenerator<unsigned long> const*,boost::python::api::object [,int=1])
        """
    def GetSparseFingerprint(self, mol: Mol, fromAtoms: typing.Any = [], ignoreAtoms: typing.Any = [], confId: int = -1, customAtomInvariants: typing.Any = [], customBondInvariants: typing.Any = [], additionalOutput: typing.Any = None) -> SparseBitVect:
        """
            Generates a sparse fingerprint
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - fromAtoms: indices of atoms to use while generating the fingerprint
                - ignoreAtoms: indices of atoms to exclude while generating the fingerprint
                - confId: 3D confirmation to use, only used by AtomPair fingerprint
                - customAtomInvariants: custom atom invariants to be used, overrides invariants from the invariant generator
                - customBondInvariants: custom bond invariants to be used, overrides invariants from the invariant generator
            
                - additionalOutput: AdditionalOutput instance used to return extra information about the bits
            
              RETURNS: a SparseBitVect containing fingerprint
            
            
        
            C++ signature :
                SparseBitVect* GetSparseFingerprint(RDKit::FingerprintGenerator<unsigned long> const*,RDKit::ROMol [,boost::python::api::object=[] [,boost::python::api::object=[] [,int=-1 [,boost::python::api::object=[] [,boost::python::api::object=[] [,boost::python::api::object=None]]]]]])
        """
    def GetSparseFingerprints(self, mols: typing.Any, numThreads: int = 1) -> tuple:
        """
            Generates sparse fingerprints for a sequence of molecules
            
              ARGUMENTS:
                - mol: molecule to be fingerprinted
                - numThreads: number of threads to use
            
              RETURNS: a tuple of SparseBitVects
            
            
        
            C++ signature :
                boost::python::tuple GetSparseFingerprints(RDKit::FingerprintGenerator<unsigned long> const*,boost::python::api::object [,int=1])
        """
class FingerprintOptions(Boost.Python.instance):
    @staticmethod
    def __init__(*args, **kwargs):
        """
        Raises an exception
        This class cannot be instantiated from Python
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def SetCountBounds(self, bounds: typing.Any) -> None:
        """
            set the bins for the count bounds
        
            C++ signature :
                void SetCountBounds(RDKit::FingerprintArguments {lvalue},boost::python::api::object)
        """
    @property
    def countSimulation(*args, **kwargs):
        """
        use count simulation
        """
    @countSimulation.setter
    def countSimulation(*args, **kwargs):
        ...
    @property
    def fpSize(*args, **kwargs):
        """
        size of the fingerprints created
        """
    @fpSize.setter
    def fpSize(*args, **kwargs):
        ...
    @property
    def includeChirality(*args, **kwargs):
        """
        include chirality in atom invariants (not for all fingerprints)
        """
    @includeChirality.setter
    def includeChirality(*args, **kwargs):
        ...
    @property
    def numBitsPerFeature(*args, **kwargs):
        """
        number of bits to set for each feature
        """
    @numBitsPerFeature.setter
    def numBitsPerFeature(*args, **kwargs):
        ...
class MorganFingerprintOptions(FingerprintOptions):
    @staticmethod
    def __init__(*args, **kwargs):
        """
        Raises an exception
        This class cannot be instantiated from Python
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    @property
    def includeRedundantEnvironments(*args, **kwargs):
        """
        include redundant environments in the fingerprint
        """
    @includeRedundantEnvironments.setter
    def includeRedundantEnvironments(*args, **kwargs):
        ...
    @property
    def onlyNonzeroInvariants(*args, **kwargs):
        """
        use include atoms which have nonzero invariants
        """
    @onlyNonzeroInvariants.setter
    def onlyNonzeroInvariants(*args, **kwargs):
        ...
    @property
    def radius(*args, **kwargs):
        """
        the radius of the fingerprints to generate
        """
    @radius.setter
    def radius(*args, **kwargs):
        ...
class RDKitFingerprintOptions(FingerprintOptions):
    @staticmethod
    def __init__(*args, **kwargs):
        """
        Raises an exception
        This class cannot be instantiated from Python
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    @property
    def branchedPaths(*args, **kwargs):
        """
        generate branched subgraphs, not just linear ones
        """
    @branchedPaths.setter
    def branchedPaths(*args, **kwargs):
        ...
    @property
    def maxPath(*args, **kwargs):
        """
        maximum path length (in bonds) to be included
        """
    @maxPath.setter
    def maxPath(*args, **kwargs):
        ...
    @property
    def minPath(*args, **kwargs):
        """
        minimum path length (in bonds) to be included
        """
    @minPath.setter
    def minPath(*args, **kwargs):
        ...
    @property
    def useBondOrder(*args, **kwargs):
        """
        include bond orders in the path hashes
        """
    @useBondOrder.setter
    def useBondOrder(*args, **kwargs):
        ...
    @property
    def useHs(*args, **kwargs):
        """
        use explicit Hs in the paths (if molecule has explicit Hs)
        """
    @useHs.setter
    def useHs(*args, **kwargs):
        ...
class TopologicalTorsionFingerprintOptions(FingerprintOptions):
    @staticmethod
    def __init__(*args, **kwargs):
        """
        Raises an exception
        This class cannot be instantiated from Python
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    @property
    def onlyShortestPaths(*args, **kwargs):
        """
        whether or not to only include paths which are the shortest path between the start and end atoms
        """
    @onlyShortestPaths.setter
    def onlyShortestPaths(*args, **kwargs):
        ...
    @property
    def torsionAtomCount(*args, **kwargs):
        """
        number of atoms to be included in the paths
        """
    @torsionAtomCount.setter
    def torsionAtomCount(*args, **kwargs):
        ...
def GetAtomPairAtomInvGen(includeChirality: bool = False) -> AtomInvariantsGenerator:
    """
        Get an atom pair atom-invariant generator
        
          ARGUMENTS:
            - includeChirality: if set, chirality will be taken into account for invariants
          RETURNS: AtomInvariantsGenerator
        
        
    
        C++ signature :
            RDKit::AtomInvariantsGenerator* GetAtomPairAtomInvGen([ bool=False])
    """
def GetAtomPairGenerator(minDistance: int = 1, maxDistance: int = 30, includeChirality: bool = False, use2D: bool = True, countSimulation: bool = True, countBounds: typing.Any = None, fpSize: int = 2048, atomInvariantsGenerator: typing.Any = None) -> FingerprintGenerator64:
    """
        Get an atom pair fingerprint generator
        
          ARGUMENTS:
            - minDistance: minimum distance between atoms to be considered in a pair, default is 1 bond
            - maxDistance: maximum distance between atoms to be considered in a pair, default is maxPathLen-1 bonds
            - includeChirality: if set, chirality will be used in the atom  invariants, this is ignored if atomInvariantsGenerator is provided
            - use2D: if set, the 2D (topological) distance matrix  will be used
            - countSimulation:  if set, use count simulation while  generating the fingerprint
            - countBounds: boundaries for count simulation, corresponding bit will be  set if the count is higher than the number provided for that spot
            - fpSize: size of the generated fingerprint, does not affect the sparse versions
            - atomInvariantsGenerator: atom invariants to be used during fingerprint generation
        
        This generator supports the following AdditionalOutput types:
            - atomToBits: which bits each atom is involved in
            - atomCounts: how many bits each atom sets
            - bitInfoMap: map from bitId to (atomId, radius) pairs
        
          RETURNS: FingerprintGenerator
        
        
    
        C++ signature :
            RDKit::FingerprintGenerator<unsigned long>* GetAtomPairGenerator([ unsigned int=1 [,unsigned int=30 [,bool=False [,bool=True [,bool=True [,boost::python::api::object {lvalue}=None [,unsigned int=2048 [,boost::python::api::object {lvalue}=None]]]]]]]])
    """
def GetCountFPs(molecules: list = [], fpType: FPType = ...) -> list:
    """
        C++ signature :
            boost::python::list GetCountFPs([ boost::python::list {lvalue}=[] [,RDKit::FPType=rdkit.Chem.rdFingerprintGenerator.FPType.MorganFP]])
    """
def GetFPs(molecules: list = [], fpType: FPType = ...) -> list:
    """
        C++ signature :
            boost::python::list GetFPs([ boost::python::list {lvalue}=[] [,RDKit::FPType=rdkit.Chem.rdFingerprintGenerator.FPType.MorganFP]])
    """
def GetMorganAtomInvGen(includeRingMembership: bool = False) -> AtomInvariantsGenerator:
    """
        Get a morgan atom invariants generator
        
          ARGUMENTS:
            - includeRingMembership: if set, whether or not the atom is in a ring will be used in the invariant list
        
          RETURNS: AtomInvariantsGenerator
        
        
    
        C++ signature :
            RDKit::AtomInvariantsGenerator* GetMorganAtomInvGen([ bool=False])
    """
def GetMorganBondInvGen(useBondTypes: bool = True, useChirality: bool = False) -> BondInvariantsGenerator:
    """
        Get a morgan bond invariants generator
        
          ARGUMENTS:
            - useBondTypes: if set, bond types will be included as a part of the bond invariants
            - useChirality: if set, chirality information will be included as a part of the bond invariants
        
          RETURNS: BondInvariantsGenerator
        
        
    
        C++ signature :
            RDKit::BondInvariantsGenerator* GetMorganBondInvGen([ bool=True [,bool=False]])
    """
def GetMorganFeatureAtomInvGen(patterns: typing.Any = None) -> AtomInvariantsGenerator:
    """
        Get a morgan feature atom invariants generator
        
          ARGUMENTS:
            - patterns: if provided should contain the queries used to assign atom-types. if not provided, feature definitions adapted from reference: Gobbi and Poppinger, Biotech. Bioeng. _61_ 47-54 (1998) will be used for Donor, Acceptor, Aromatic, Halogen, Basic, Acidic.
        
          RETURNS: AtomInvariantsGenerator
        
        
    
        C++ signature :
            RDKit::AtomInvariantsGenerator* GetMorganFeatureAtomInvGen([ boost::python::api::object {lvalue}=None])
    """
def GetMorganGenerator(radius: int = 3, countSimulation: bool = False, includeChirality: bool = False, useBondTypes: bool = True, onlyNonzeroInvariants: bool = False, includeRingMembership: bool = True, countBounds: typing.Any = None, fpSize: int = 2048, atomInvariantsGenerator: typing.Any = None, bondInvariantsGenerator: typing.Any = None, includeRedundantEnvironments: bool = False) -> FingerprintGenerator64:
    """
        Get a morgan fingerprint generator
        
          ARGUMENTS:
            - radius:  the number of iterations to grow the fingerprint
            - countSimulation: if set, use count simulation while generating the fingerprint
            - includeChirality: if set, chirality information will be added to the generated fingerprint
            - useBondTypes: if set, bond types will be included as a part of the default bond invariants
            - countBounds: boundaries for count simulation, corresponding bit will be  set if the count is higher than the number provided for that spot
            - fpSize: size of the generated fingerprint, does not affect the sparse versions
            - atomInvariantsGenerator: atom invariants to be used during fingerprint generation
        
        This generator supports the following AdditionalOutput types:
            - atomToBits: which bits each atom is the center of
            - atomCounts: how many bits each atom sets
            - bitInfoMap: map from bitId to (atomId1, radius) pairs
        
          RETURNS: FingerprintGenerator
        
        
    
        C++ signature :
            RDKit::FingerprintGenerator<unsigned long>* GetMorganGenerator([ unsigned int=3 [,bool=False [,bool=False [,bool=True [,bool=False [,bool=True [,boost::python::api::object {lvalue}=None [,unsigned int=2048 [,boost::python::api::object {lvalue}=None [,boost::python::api::object {lvalue}=None [,bool=False]]]]]]]]]]])
    """
def GetRDKitAtomInvGen() -> AtomInvariantsGenerator:
    """
        Get an RDKit atom invariants generator
        
          RETURNS: AtomInvariantsGenerator
        
        
    
        C++ signature :
            RDKit::AtomInvariantsGenerator* GetRDKitAtomInvGen()
    """
def GetRDKitFPGenerator(minPath: int = 1, maxPath: int = 7, useHs: bool = True, branchedPaths: bool = True, useBondOrder: bool = True, countSimulation: bool = False, countBounds: typing.Any = None, fpSize: int = 2048, numBitsPerFeature: int = 2, atomInvariantsGenerator: typing.Any = None) -> FingerprintGenerator64:
    """
        Get an RDKit fingerprint generator
        
          ARGUMENTS:
            - minPath: the minimum path length (in bonds) to be included
            - maxPath: the maximum path length (in bonds) to be included
            - useHs: toggles inclusion of Hs in paths (if the molecule has explicit Hs)
            - branchedPaths: toggles generation of branched subgraphs, not just linear paths
            - useBondOrder: toggles inclusion of bond orders in the path hashes
            - countSimulation:  if set, use count simulation while  generating the fingerprint
            - countBounds: boundaries for count simulation, corresponding bit will be  set if the count is higher than the number provided for that spot
            - fpSize: size of the generated fingerprint, does not affect the sparse versions
            - numBitsPerFeature: the number of bits set per path/subgraph found
            - atomInvariantsGenerator: atom invariants to be used during fingerprint generation
        
        This generator supports the following AdditionalOutput types:
            - atomToBits: which bits each atom is involved in
            - atomCounts: how many bits each atom sets
            - bitPaths: map from bitId to vectors of bond indices for the individual subgraphs
        
          RETURNS: FingerprintGenerator
        
        
    
        C++ signature :
            RDKit::FingerprintGenerator<unsigned long>* GetRDKitFPGenerator([ unsigned int=1 [,unsigned int=7 [,bool=True [,bool=True [,bool=True [,bool=False [,boost::python::api::object {lvalue}=None [,unsigned int=2048 [,unsigned int=2 [,boost::python::api::object {lvalue}=None]]]]]]]]]])
    """
def GetSparseCountFPs(molecules: list = [], fpType: FPType = ...) -> list:
    """
        C++ signature :
            boost::python::list GetSparseCountFPs([ boost::python::list {lvalue}=[] [,RDKit::FPType=rdkit.Chem.rdFingerprintGenerator.FPType.MorganFP]])
    """
def GetSparseFPs(molecules: list = [], fpType: FPType = ...) -> list:
    """
        C++ signature :
            boost::python::list GetSparseFPs([ boost::python::list {lvalue}=[] [,RDKit::FPType=rdkit.Chem.rdFingerprintGenerator.FPType.MorganFP]])
    """
def GetTopologicalTorsionGenerator(includeChirality: bool = False, torsionAtomCount: int = 4, countSimulation: bool = True, countBounds: typing.Any = None, fpSize: int = 2048, atomInvariantsGenerator: typing.Any = None) -> FingerprintGenerator64:
    """
        Get an atom pair fingerprint generator
        
          ARGUMENTS:
            - includeChirality: includeChirality argument for both the default atom invariants generator and the fingerprint arguments
            - torsionAtomCount: the number of atoms to include in the "torsions"
            - countSimulation:  if set, use count simulation while  generating the fingerprint
            - countBounds: boundaries for count simulation, corresponding bit will be  set if the count is higher than the number provided for that spot
            - fpSize: size of the generated fingerprint, does not affect the sparse versions
            - atomInvariantsGenerator: atom invariants to be used during fingerprint generation
        
        This generator supports the following AdditionalOutput types:
            - atomToBits: which bits each atom is involved in
            - atomCounts: how many bits each atom sets
            - bitPaths: map from bitId to vectors of atom indices
        
          RETURNS: FingerprintGenerator
        
        
    
        C++ signature :
            RDKit::FingerprintGenerator<unsigned long>* GetTopologicalTorsionGenerator([ bool=False [,unsigned int=4 [,bool=True [,boost::python::api::object {lvalue}=None [,unsigned int=2048 [,boost::python::api::object {lvalue}=None]]]]]])
    """
AtomPairFP: FPType  # value = rdkit.Chem.rdFingerprintGenerator.FPType.AtomPairFP
MorganFP: FPType  # value = rdkit.Chem.rdFingerprintGenerator.FPType.MorganFP
RDKitFP: FPType  # value = rdkit.Chem.rdFingerprintGenerator.FPType.RDKitFP
TopologicalTorsionFP: FPType  # value = rdkit.Chem.rdFingerprintGenerator.FPType.TopologicalTorsionFP
