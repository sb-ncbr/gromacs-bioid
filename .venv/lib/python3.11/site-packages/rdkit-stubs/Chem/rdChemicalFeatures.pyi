"""
Module containing free chemical feature functionality
     These are features that are not associated with molecules. They are 
     typically derived from pharmacophores and site-maps.
"""
from __future__ import annotations
import typing
__all__ = ['FreeChemicalFeature']
class FreeChemicalFeature(Boost.Python.instance):
    """
    Class to represent free chemical features.
        These chemical features are not associated with a molecule, though they can be matched 
        to molecular features
    """
    __getstate_manages_dict__: typing.ClassVar[bool] = True
    __instance_size__: typing.ClassVar[int] = 88
    __safe_for_unpickling__: typing.ClassVar[bool] = True
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def GetFamily(self) -> str:
        """
            Get the family of the feature
        
            C++ signature :
                std::string GetFamily(ChemicalFeatures::FreeChemicalFeature {lvalue})
        """
    def GetId(self) -> int:
        """
            Get the id of the feature
        
            C++ signature :
                int GetId(ChemicalFeatures::FreeChemicalFeature {lvalue})
        """
    def GetPos(self) -> Point3D:
        """
            Get the position of the feature
        
            C++ signature :
                RDGeom::Point3D GetPos(ChemicalFeatures::FreeChemicalFeature {lvalue})
        """
    def GetType(self) -> str:
        """
            Get the sepcific type for the feature
        
            C++ signature :
                std::string GetType(ChemicalFeatures::FreeChemicalFeature {lvalue})
        """
    def SetFamily(self, family: str) -> None:
        """
            Set the family of the feature
        
            C++ signature :
                void SetFamily(ChemicalFeatures::FreeChemicalFeature {lvalue},std::string)
        """
    def SetId(self, id: int) -> None:
        """
            Set the id of the feature
        
            C++ signature :
                void SetId(ChemicalFeatures::FreeChemicalFeature {lvalue},int)
        """
    def SetPos(self, loc: Point3D) -> None:
        """
            Set the feature position
        
            C++ signature :
                void SetPos(ChemicalFeatures::FreeChemicalFeature {lvalue},RDGeom::Point3D)
        """
    def SetType(self, type: str) -> None:
        """
            Set the sepcific type for the feature
        
            C++ signature :
                void SetType(ChemicalFeatures::FreeChemicalFeature {lvalue},std::string)
        """
    def __getinitargs__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getinitargs__(ChemicalFeatures::FreeChemicalFeature)
        """
    def __getstate__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getstate__(boost::python::api::object)
        """
    @typing.overload
    def __init__(self, pickle: str) -> None:
        """
            C++ signature :
                void __init__(_object*,std::string)
        """
    @typing.overload
    def __init__(self) -> None:
        """
            Default Constructor
        
            C++ signature :
                void __init__(_object*)
        """
    @typing.overload
    def __init__(self, family: str, type: str, loc: Point3D, id: int = -1) -> None:
        """
            Constructor with family, type and location specified
        
            C++ signature :
                void __init__(_object*,std::string,std::string,RDGeom::Point3D [,int=-1])
        """
    @typing.overload
    def __init__(self, family: str, loc: Point3D) -> None:
        """
            constructor with family and location specified, empty type and id
        
            C++ signature :
                void __init__(_object*,std::string,RDGeom::Point3D)
        """
    def __setstate__(self, data: tuple) -> None:
        """
            C++ signature :
                void __setstate__(boost::python::api::object,boost::python::tuple)
        """
