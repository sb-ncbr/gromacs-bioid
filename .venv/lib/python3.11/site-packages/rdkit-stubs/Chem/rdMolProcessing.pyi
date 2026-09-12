"""
Module containing functions for working with groups of molecules
"""
from __future__ import annotations
import typing
__all__ = ['GetFingerprintsForMolsInFile', 'SupplierOptions']
class SupplierOptions(Boost.Python.instance):
    """
    Supplier Options
    """
    __instance_size__: typing.ClassVar[int] = 80
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    @property
    def confId2D(*args, **kwargs):
        """
        used for TDT files
        """
    @confId2D.setter
    def confId2D(*args, **kwargs):
        ...
    @property
    def confId3D(*args, **kwargs):
        """
        used for TDT files
        """
    @confId3D.setter
    def confId3D(*args, **kwargs):
        ...
    @property
    def delimiter(*args, **kwargs):
        """
        used for SMILES files
        """
    @delimiter.setter
    def delimiter(*args, **kwargs):
        ...
    @property
    def nameColumn(*args, **kwargs):
        """
        used for SMILES files
        """
    @nameColumn.setter
    def nameColumn(*args, **kwargs):
        ...
    @property
    def nameRecord(*args, **kwargs):
        """
        used for TDT files
        """
    @nameRecord.setter
    def nameRecord(*args, **kwargs):
        ...
    @property
    def numThreads(*args, **kwargs):
        """
        the number of threads to use while working
        """
    @numThreads.setter
    def numThreads(*args, **kwargs):
        ...
    @property
    def removeHs(*args, **kwargs):
        ...
    @removeHs.setter
    def removeHs(*args, **kwargs):
        ...
    @property
    def sanitize(*args, **kwargs):
        ...
    @sanitize.setter
    def sanitize(*args, **kwargs):
        ...
    @property
    def smilesColumn(*args, **kwargs):
        """
        used for SMILES files
        """
    @smilesColumn.setter
    def smilesColumn(*args, **kwargs):
        ...
    @property
    def strictParsing(*args, **kwargs):
        ...
    @strictParsing.setter
    def strictParsing(*args, **kwargs):
        ...
    @property
    def titleLine(*args, **kwargs):
        """
        used for SMILES files
        """
    @titleLine.setter
    def titleLine(*args, **kwargs):
        ...
@typing.overload
def GetFingerprintsForMolsInFile(filename: str, generator: typing.Any = None, options: SupplierOptions = ...) -> tuple:
    """
        returns the fingerprints for the molecules in a file (32 bit version)
    
        C++ signature :
            boost::python::tuple GetFingerprintsForMolsInFile(std::string [,boost::python::api::object=None [,RDKit::GeneralMolSupplier::SupplierOptions=<rdkit.Chem.rdMolProcessing.SupplierOptions object at 0x7f26dbe3c180>]])
    """
@typing.overload
def GetFingerprintsForMolsInFile(filename: str, generator: typing.Any = None, options: SupplierOptions = ...) -> tuple:
    """
        returns the fingerprints for the molecules in a file (64 bit version)
    
        C++ signature :
            boost::python::tuple GetFingerprintsForMolsInFile(std::string [,boost::python::api::object=None [,RDKit::GeneralMolSupplier::SupplierOptions=<rdkit.Chem.rdMolProcessing.SupplierOptions object at 0x7f26cbc0b060>]])
    """
