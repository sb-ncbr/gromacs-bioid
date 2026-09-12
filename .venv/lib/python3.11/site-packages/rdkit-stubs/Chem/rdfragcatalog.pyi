from __future__ import annotations
import rdkit.Chem
import typing
__all__ = ['FragCatGenerator', 'FragCatParams', 'FragCatalog', 'FragFPGenerator']
class FragCatGenerator(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 32
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def AddFragsFromMol(self, mol: Mol, fcat: FragCatalog) -> int:
        """
            C++ signature :
                unsigned int AddFragsFromMol(RDKit::FragCatGenerator {lvalue},RDKit::ROMol,RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int>*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
class FragCatParams(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 80
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def GetFuncGroup(self, fid: int) -> rdkit.Chem.Mol:
        """
            C++ signature :
                RDKit::ROMol const* GetFuncGroup(RDKit::FragCatParams {lvalue},int)
        """
    def GetLowerFragLength(self) -> int:
        """
            C++ signature :
                unsigned int GetLowerFragLength(RDKit::FragCatParams {lvalue})
        """
    def GetNumFuncGroups(self) -> int:
        """
            C++ signature :
                unsigned int GetNumFuncGroups(RDKit::FragCatParams {lvalue})
        """
    def GetTolerance(self) -> float:
        """
            C++ signature :
                double GetTolerance(RDKit::FragCatParams {lvalue})
        """
    def GetTypeString(self) -> str:
        """
            C++ signature :
                std::string GetTypeString(RDKit::FragCatParams {lvalue})
        """
    def GetUpperFragLength(self) -> int:
        """
            C++ signature :
                unsigned int GetUpperFragLength(RDKit::FragCatParams {lvalue})
        """
    def Serialize(self) -> str:
        """
            C++ signature :
                std::string Serialize(RDKit::FragCatParams {lvalue})
        """
    def __init__(self, lLen: int, uLen: int, fgroupFilename: str, tol: float = 1e-08) -> None:
        """
            C++ signature :
                void __init__(_object*,int,int,std::string [,double=1e-08])
        """
class FragCatalog(Boost.Python.instance):
    __getstate_manages_dict__: typing.ClassVar[bool] = True
    __instance_size__: typing.ClassVar[int] = 144
    __safe_for_unpickling__: typing.ClassVar[bool] = True
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def GetBitDescription(self, idx: int) -> str:
        """
            C++ signature :
                std::string GetBitDescription(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int> const*,unsigned int)
        """
    def GetBitDiscrims(self, idx: int) -> typing.Sequence[double]:
        """
            C++ signature :
                std::vector<double, std::allocator<double> > GetBitDiscrims(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int> const*,unsigned int)
        """
    def GetBitEntryId(self, idx: int) -> int:
        """
            C++ signature :
                unsigned int GetBitEntryId(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int> const*,unsigned int)
        """
    def GetBitFuncGroupIds(self, idx: int) -> typing.Sequence[int]:
        """
            C++ signature :
                std::vector<int, std::allocator<int> > GetBitFuncGroupIds(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int> const*,unsigned int)
        """
    def GetBitOrder(self, idx: int) -> int:
        """
            C++ signature :
                unsigned int GetBitOrder(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int> const*,unsigned int)
        """
    def GetCatalogParams(self) -> FragCatParams:
        """
            C++ signature :
                RDKit::FragCatParams* GetCatalogParams(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int> {lvalue})
        """
    def GetEntryBitId(self, idx: int) -> int:
        """
            C++ signature :
                unsigned int GetEntryBitId(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int> const*,unsigned int)
        """
    def GetEntryDescription(self, idx: int) -> str:
        """
            C++ signature :
                std::string GetEntryDescription(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int> const*,unsigned int)
        """
    def GetEntryDownIds(self, idx: int) -> typing.Sequence[int]:
        """
            C++ signature :
                std::vector<int, std::allocator<int> > GetEntryDownIds(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int> const*,unsigned int)
        """
    def GetEntryFuncGroupIds(self, idx: int) -> typing.Sequence[int]:
        """
            C++ signature :
                std::vector<int, std::allocator<int> > GetEntryFuncGroupIds(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int> const*,unsigned int)
        """
    def GetEntryOrder(self, idx: int) -> int:
        """
            C++ signature :
                unsigned int GetEntryOrder(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int> const*,unsigned int)
        """
    def GetFPLength(self) -> int:
        """
            C++ signature :
                unsigned int GetFPLength(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int> {lvalue})
        """
    def GetNumEntries(self) -> int:
        """
            C++ signature :
                unsigned int GetNumEntries(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int> {lvalue})
        """
    def Serialize(self) -> str:
        """
            C++ signature :
                std::string Serialize(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int> {lvalue})
        """
    def __getinitargs__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getinitargs__(RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int>)
        """
    def __getstate__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getstate__(boost::python::api::object)
        """
    @typing.overload
    def __init__(self, params: FragCatParams) -> None:
        """
            C++ signature :
                void __init__(_object*,RDKit::FragCatParams*)
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
class FragFPGenerator(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 32
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def GetFPForMol(self, mol: Mol, fcat: FragCatalog) -> ExplicitBitVect:
        """
            C++ signature :
                ExplicitBitVect* GetFPForMol(RDKit::FragFPGenerator {lvalue},RDKit::ROMol,RDCatalog::HierarchCatalog<RDKit::FragCatalogEntry, RDKit::FragCatParams, int>)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
