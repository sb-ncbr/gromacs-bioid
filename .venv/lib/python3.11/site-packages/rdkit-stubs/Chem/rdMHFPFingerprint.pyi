from __future__ import annotations
import typing
__all__ = ['MHFPEncoder']
class MHFPEncoder(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 96
    @staticmethod
    def Distance(a: _vectj, b: _vectj) -> float:
        """
            C++ signature :
                double Distance(std::vector<unsigned int, std::allocator<unsigned int> >,std::vector<unsigned int, std::allocator<unsigned int> >)
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def CreateShinglingFromMol(self, mol: Mol, radius: int = 3, rings: bool = True, isomeric: bool = False, kekulize: bool = False, min_radius: int = 1) -> _vectSs:
        """
            Creates a shingling (a list of circular n-grams / substructures) from a RDKit Mol instance.
        
            C++ signature :
                std::vector<std::string, std::allocator<std::string> > CreateShinglingFromMol(RDKit::MHFPFingerprints::MHFPEncoder*,RDKit::ROMol [,unsigned char=3 [,bool=True [,bool=False [,bool=False [,unsigned char=1]]]]])
        """
    def CreateShinglingFromSmiles(self, smiles: str, radius: int = 3, rings: bool = True, isomeric: bool = False, kekulize: bool = False, min_radius: int = 1) -> _vectSs:
        """
            Creates a shingling (a list of circular n-grams / substructures) from a SMILES string.
        
            C++ signature :
                std::vector<std::string, std::allocator<std::string> > CreateShinglingFromSmiles(RDKit::MHFPFingerprints::MHFPEncoder*,std::string [,unsigned char=3 [,bool=True [,bool=False [,bool=False [,unsigned char=1]]]]])
        """
    def EncodeMol(self, mol: Mol, radius: int = 3, rings: bool = True, isomeric: bool = False, kekulize: bool = False, min_radius: int = 1) -> typing.Sequence[int]:
        """
            Creates a MHFP vector from an RDKit Mol instance.
        
            C++ signature :
                std::vector<unsigned int, std::allocator<unsigned int> > EncodeMol(RDKit::MHFPFingerprints::MHFPEncoder*,RDKit::ROMol [,unsigned char=3 [,bool=True [,bool=False [,bool=False [,unsigned char=1]]]]])
        """
    def EncodeMolsBulk(self, mols: list, radius: int = 3, rings: bool = True, isomeric: bool = False, kekulize: bool = False, min_radius: int = 1) -> typing.Sequence[typing.Sequence[int]]:
        """
            Creates a MHFP vector from a list of RDKit Mol instances.
        
            C++ signature :
                std::vector<std::vector<unsigned int, std::allocator<unsigned int> >, std::allocator<std::vector<unsigned int, std::allocator<unsigned int> > > > EncodeMolsBulk(RDKit::MHFPFingerprints::MHFPEncoder*,boost::python::list {lvalue} [,unsigned char=3 [,bool=True [,bool=False [,bool=False [,unsigned char=1]]]]])
        """
    def EncodeSECFPMol(self, smiles: Mol, radius: int = 3, rings: bool = True, isomeric: bool = False, kekulize: bool = False, min_radius: int = 1, length: int = 2048) -> ExplicitBitVect:
        """
            Creates a SECFP binary vector from an RDKit Mol instance.
        
            C++ signature :
                ExplicitBitVect EncodeSECFPMol(RDKit::MHFPFingerprints::MHFPEncoder*,RDKit::ROMol [,unsigned char=3 [,bool=True [,bool=False [,bool=False [,unsigned char=1 [,unsigned long=2048]]]]]])
        """
    def EncodeSECFPMolsBulk(self, smiles: list, radius: int = 3, rings: bool = True, isomeric: bool = False, kekulize: bool = False, min_radius: int = 1, length: int = 2048) -> typing.Any:
        """
            Creates a SECFP binary vector from a list of RDKit Mol instances.
        
            C++ signature :
                std::vector<ExplicitBitVect, std::allocator<ExplicitBitVect> > EncodeSECFPMolsBulk(RDKit::MHFPFingerprints::MHFPEncoder*,boost::python::list {lvalue} [,unsigned char=3 [,bool=True [,bool=False [,bool=False [,unsigned char=1 [,unsigned long=2048]]]]]])
        """
    def EncodeSECFPSmiles(self, smiles: str, radius: int = 3, rings: bool = True, isomeric: bool = False, kekulize: bool = False, min_radius: int = 1, length: int = 2048) -> ExplicitBitVect:
        """
            Creates a SECFP binary vector from a SMILES string.
        
            C++ signature :
                ExplicitBitVect EncodeSECFPSmiles(RDKit::MHFPFingerprints::MHFPEncoder*,std::string [,unsigned char=3 [,bool=True [,bool=False [,bool=False [,unsigned char=1 [,unsigned long=2048]]]]]])
        """
    def EncodeSECFPSmilesBulk(self, smiles: list, radius: int = 3, rings: bool = True, isomeric: bool = False, kekulize: bool = False, min_radius: int = 1, length: int = 2048) -> typing.Any:
        """
            Creates a SECFP binary vector from a list of SMILES strings.
        
            C++ signature :
                std::vector<ExplicitBitVect, std::allocator<ExplicitBitVect> > EncodeSECFPSmilesBulk(RDKit::MHFPFingerprints::MHFPEncoder*,boost::python::list {lvalue} [,unsigned char=3 [,bool=True [,bool=False [,bool=False [,unsigned char=1 [,unsigned long=2048]]]]]])
        """
    def EncodeSmiles(self, smiles: str, radius: int = 3, rings: bool = True, isomeric: bool = False, kekulize: bool = False, min_radius: int = 1) -> typing.Sequence[int]:
        """
            Creates a MHFP vector from a SMILES string.
        
            C++ signature :
                std::vector<unsigned int, std::allocator<unsigned int> > EncodeSmiles(RDKit::MHFPFingerprints::MHFPEncoder*,std::string [,unsigned char=3 [,bool=True [,bool=False [,bool=False [,unsigned char=1]]]]])
        """
    def EncodeSmilesBulk(self, smiles: list, radius: int = 3, rings: bool = True, isomeric: bool = False, kekulize: bool = False, min_radius: int = 1) -> typing.Sequence[typing.Sequence[int]]:
        """
            Creates a MHFP vector from a list of SMILES strings.
        
            C++ signature :
                std::vector<std::vector<unsigned int, std::allocator<unsigned int> >, std::allocator<std::vector<unsigned int, std::allocator<unsigned int> > > > EncodeSmilesBulk(RDKit::MHFPFingerprints::MHFPEncoder*,boost::python::list {lvalue} [,unsigned char=3 [,bool=True [,bool=False [,bool=False [,unsigned char=1]]]]])
        """
    def FromArray(self, vec: list) -> typing.Sequence[int]:
        """
            Creates a MHFP vector from a list of unsigned integers.
        
            C++ signature :
                std::vector<unsigned int, std::allocator<unsigned int> > FromArray(RDKit::MHFPFingerprints::MHFPEncoder*,boost::python::list {lvalue})
        """
    def FromStringArray(self, vec: list) -> typing.Sequence[int]:
        """
            Creates a MHFP vector from a list of arbitrary strings.
        
            C++ signature :
                std::vector<unsigned int, std::allocator<unsigned int> > FromStringArray(RDKit::MHFPFingerprints::MHFPEncoder*,boost::python::list {lvalue})
        """
    def __init__(self, n_permutations: int, seed: int) -> None:
        """
            C++ signature :
                void __init__(_object* [,unsigned int [,unsigned int]])
        """
