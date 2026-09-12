from __future__ import annotations
import typing
__all__ = ['AlignMol', 'FloatVector', 'PrepareConformer', 'ShapeInput']
class FloatVector(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<float, std::allocator<float> > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<float, std::allocator<float> > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<float, std::allocator<float> >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __iter__(self) -> typing.Any:
        """
            C++ signature :
                boost::python::objects::iterator_range<boost::python::return_value_policy<boost::python::return_by_value, boost::python::default_call_policies>, __gnu_cxx::__normal_iterator<float*, std::vector<float, std::allocator<float> > > > __iter__(boost::python::back_reference<std::vector<float, std::allocator<float> >&>)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<float, std::allocator<float> > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<float, std::allocator<float> > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<float, std::allocator<float> > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<float, std::allocator<float> > {lvalue},boost::python::api::object)
        """
class ShapeInput(Boost.Python.instance):
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
    def alpha_vector(*args, **kwargs):
        ...
    @alpha_vector.setter
    def alpha_vector(*args, **kwargs):
        ...
    @property
    def atom_type_vector(*args, **kwargs):
        ...
    @atom_type_vector.setter
    def atom_type_vector(*args, **kwargs):
        ...
    @property
    def coord(*args, **kwargs):
        ...
    @coord.setter
    def coord(*args, **kwargs):
        ...
    @property
    def shift(*args, **kwargs):
        ...
    @shift.setter
    def shift(*args, **kwargs):
        ...
    @property
    def sof(*args, **kwargs):
        ...
    @sof.setter
    def sof(*args, **kwargs):
        ...
    @property
    def sov(*args, **kwargs):
        ...
    @sov.setter
    def sov(*args, **kwargs):
        ...
    @property
    def volumeAtomIndexVector(*args, **kwargs):
        ...
    @volumeAtomIndexVector.setter
    def volumeAtomIndexVector(*args, **kwargs):
        ...
@typing.overload
def AlignMol(ref: Mol, probe: Mol, refConfId: int = -1, probeConfId: int = -1, useColors: bool = True, opt_param: float = 1.0, max_preiters: int = 10, max_postiters: int = 30) -> tuple:
    """
        Aligns a probe molecule to a reference molecule. The probe is modified.
        
        Parameters
        ----------
        ref : RDKit.ROMol
            Reference molecule
        probe : RDKit.ROMol
            Probe molecule
        refConfId : int, optional
            Reference conformer ID (default is -1)
        probeConfId : int, optional
            Probe conformer ID (default is -1)
        useColors : bool, optional
            Whether or not to use colors in the scoring (default is True)
        opt_param : float, optional
        max_preiters : int, optional
        max_postiters : int, optional
        
        
        Returns
        -------
         2-tuple of doubles
            The results are (shape_score, color_score)
            The color_score is zero if useColors is False
    
        C++ signature :
            boost::python::tuple AlignMol(RDKit::ROMol,RDKit::ROMol {lvalue} [,int=-1 [,int=-1 [,bool=True [,double=1.0 [,unsigned int=10 [,unsigned int=30]]]]]])
    """
@typing.overload
def AlignMol(refShape: ShapeInput, probe: Mol, probeConfId: int = -1, useColors: bool = True, opt_param: float = 1.0, max_preiters: int = 10, max_postiters: int = 30) -> tuple:
    """
        Aligns a probe molecule to a reference shape. The probe is modified.
        
        Parameters
        ----------
        refShape : ShapeInput
            Reference molecule
        probe : RDKit.ROMol
            Probe molecule
        probeConfId : int, optional
            Probe conformer ID (default is -1)
        useColors : bool, optional
            Whether or not to use colors in the scoring (default is True)
        optParam : float, optional
        max_preiters : int, optional
        max_postiters : int, optional
        
        
        Returns
        -------
         2-tuple of doubles
            The results are (shape_score, color_score)
            The color_score is zero if useColors is False
    
        C++ signature :
            boost::python::tuple AlignMol(ShapeInput,RDKit::ROMol {lvalue} [,int=-1 [,bool=True [,double=1.0 [,unsigned int=10 [,unsigned int=30]]]]])
    """
def PrepareConformer(mol: Mol, confId: int = -1, useColors: bool = True) -> ShapeInput:
    """
        Generates a ShapeInput object for a molecule
        
        Parameters
        ----------
        mol : RDKit.ROMol
            Reference molecule
        confId : int, optional
            Conformer ID to use (default is -1)
        useColors : bool, optional
            Whether or not to assign chemical features (colors) (default is True)
        
        Returns
        -------
         a ShapeInput for the molecule
    
        C++ signature :
            ShapeInput* PrepareConformer(RDKit::ROMol [,int=-1 [,bool=True]])
    """
