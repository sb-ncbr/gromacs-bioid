from __future__ import annotations
import rdkit.Chem
import typing
__all__ = ['CreateMolCatalog', 'MolCatalog', 'MolCatalogEntry']
class MolCatalog(Boost.Python.instance):
    __getstate_manages_dict__: typing.ClassVar[bool] = True
    __instance_size__: typing.ClassVar[int] = 144
    __safe_for_unpickling__: typing.ClassVar[bool] = True
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def AddEdge(self, id1: int, id2: int) -> None:
        """
            C++ signature :
                void AddEdge(RDCatalog::HierarchCatalog<RDKit::MolCatalogEntry, RDKit::MolCatalogParams, int> {lvalue},unsigned int,unsigned int)
        """
    def AddEntry(self, entry: MolCatalogEntry) -> int:
        """
            C++ signature :
                unsigned int AddEntry(RDCatalog::HierarchCatalog<RDKit::MolCatalogEntry, RDKit::MolCatalogParams, int>*,RDKit::MolCatalogEntry*)
        """
    def GetBitDescription(self, idx: int) -> str:
        """
            C++ signature :
                std::string GetBitDescription(RDCatalog::HierarchCatalog<RDKit::MolCatalogEntry, RDKit::MolCatalogParams, int> const*,unsigned int)
        """
    def GetBitEntryId(self, idx: int) -> int:
        """
            C++ signature :
                unsigned int GetBitEntryId(RDCatalog::HierarchCatalog<RDKit::MolCatalogEntry, RDKit::MolCatalogParams, int> const*,unsigned int)
        """
    def GetEntryBitId(self, idx: int) -> int:
        """
            C++ signature :
                unsigned int GetEntryBitId(RDCatalog::HierarchCatalog<RDKit::MolCatalogEntry, RDKit::MolCatalogParams, int> const*,unsigned int)
        """
    def GetEntryDescription(self, idx: int) -> str:
        """
            C++ signature :
                std::string GetEntryDescription(RDCatalog::HierarchCatalog<RDKit::MolCatalogEntry, RDKit::MolCatalogParams, int> const*,unsigned int)
        """
    def GetEntryDownIds(self, idx: int) -> typing.Sequence[int]:
        """
            C++ signature :
                std::vector<int, std::allocator<int> > GetEntryDownIds(RDCatalog::HierarchCatalog<RDKit::MolCatalogEntry, RDKit::MolCatalogParams, int> const*,unsigned int)
        """
    def GetFPLength(self) -> int:
        """
            C++ signature :
                unsigned int GetFPLength(RDCatalog::HierarchCatalog<RDKit::MolCatalogEntry, RDKit::MolCatalogParams, int> {lvalue})
        """
    def GetNumEntries(self) -> int:
        """
            C++ signature :
                unsigned int GetNumEntries(RDCatalog::HierarchCatalog<RDKit::MolCatalogEntry, RDKit::MolCatalogParams, int> {lvalue})
        """
    def Serialize(self) -> str:
        """
            C++ signature :
                std::string Serialize(RDCatalog::HierarchCatalog<RDKit::MolCatalogEntry, RDKit::MolCatalogParams, int> {lvalue})
        """
    def __getinitargs__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getinitargs__(RDCatalog::HierarchCatalog<RDKit::MolCatalogEntry, RDKit::MolCatalogParams, int>)
        """
    def __getstate__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getstate__(boost::python::api::object)
        """
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
class MolCatalogEntry(Boost.Python.instance):
    __getstate_manages_dict__: typing.ClassVar[bool] = True
    __instance_size__: typing.ClassVar[int] = 72
    __safe_for_unpickling__: typing.ClassVar[bool] = True
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def GetDescription(self) -> str:
        """
            C++ signature :
                std::string GetDescription(RDKit::MolCatalogEntry {lvalue})
        """
    def GetMol(self) -> rdkit.Chem.Mol:
        """
            C++ signature :
                RDKit::ROMol GetMol(RDKit::MolCatalogEntry {lvalue})
        """
    def GetOrder(self) -> int:
        """
            C++ signature :
                unsigned int GetOrder(RDKit::MolCatalogEntry {lvalue})
        """
    def SetDescription(self, val: str) -> None:
        """
            C++ signature :
                void SetDescription(RDKit::MolCatalogEntry {lvalue},std::string)
        """
    def SetMol(self, mol: Mol) -> None:
        """
            C++ signature :
                void SetMol(RDKit::MolCatalogEntry*,RDKit::ROMol const*)
        """
    def SetOrder(self, order: int) -> None:
        """
            C++ signature :
                void SetOrder(RDKit::MolCatalogEntry {lvalue},unsigned int)
        """
    def __getinitargs__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getinitargs__(RDKit::MolCatalogEntry)
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
def CreateMolCatalog() -> MolCatalog:
    """
        C++ signature :
            RDCatalog::HierarchCatalog<RDKit::MolCatalogEntry, RDKit::MolCatalogParams, int>* CreateMolCatalog()
    """
