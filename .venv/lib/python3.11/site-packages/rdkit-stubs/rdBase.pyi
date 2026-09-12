"""
Module containing basic definitions for wrapped C++ code

"""
from __future__ import annotations
import typing
__all__ = ['AttachFileToLog', 'BlockLogs', 'DisableLog', 'EnableLog', 'LogDebugMsg', 'LogErrorMsg', 'LogInfoMsg', 'LogMessage', 'LogStatus', 'LogToCppStreams', 'LogToPythonLogger', 'LogToPythonStderr', 'LogWarningMsg', 'MatchTypeVect', 'SeedRandomNumberGenerator', 'UnsignedLong_Vect', 'VectorOfStringVectors', 'WrapLogs', 'boostVersion', 'ostream', 'rdkitBuild', 'rdkitVersion', 'std_ostream', 'streambuf']
class BlockLogs(Boost.Python.instance):
    """
    Temporarily block logs from outputting while this instance is in scope.
    """
    __instance_size__: typing.ClassVar[int] = 32
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __enter__(self) -> BlockLogs:
        """
            C++ signature :
                BlockLogs* __enter__(BlockLogs {lvalue})
        """
    def __exit__(self, exc_type: typing.Any, exc_value: typing.Any, traceback: typing.Any) -> None:
        """
            C++ signature :
                void __exit__(BlockLogs {lvalue},boost::python::api::object,boost::python::api::object,boost::python::api::object)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
class MatchTypeVect(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __iter__(vect):
        ...
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<std::pair<int, int>, std::allocator<std::pair<int, int> > > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<std::pair<int, int>, std::allocator<std::pair<int, int> > > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<std::pair<int, int>, std::allocator<std::pair<int, int> > >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<std::pair<int, int>, std::allocator<std::pair<int, int> > > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<std::pair<int, int>, std::allocator<std::pair<int, int> > > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<std::pair<int, int>, std::allocator<std::pair<int, int> > > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<std::pair<int, int>, std::allocator<std::pair<int, int> > > {lvalue},boost::python::api::object)
        """
class UnsignedLong_Vect(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __iter__(vect):
        ...
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<unsigned long, std::allocator<unsigned long> > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<unsigned long, std::allocator<unsigned long> > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<unsigned long, std::allocator<unsigned long> >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<unsigned long, std::allocator<unsigned long> > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<unsigned long, std::allocator<unsigned long> > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<unsigned long, std::allocator<unsigned long> > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<unsigned long, std::allocator<unsigned long> > {lvalue},boost::python::api::object)
        """
class VectorOfStringVectors(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __iter__(vect):
        ...
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<std::vector<std::string, std::allocator<std::string> >, std::allocator<std::vector<std::string, std::allocator<std::string> > > > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<std::vector<std::string, std::allocator<std::string> >, std::allocator<std::vector<std::string, std::allocator<std::string> > > > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<std::vector<std::string, std::allocator<std::string> >, std::allocator<std::vector<std::string, std::allocator<std::string> > > >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<std::vector<std::string, std::allocator<std::string> >, std::allocator<std::vector<std::string, std::allocator<std::string> > > > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<std::vector<std::string, std::allocator<std::string> >, std::allocator<std::vector<std::string, std::allocator<std::string> > > > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<std::vector<std::string, std::allocator<std::string> >, std::allocator<std::vector<std::string, std::allocator<std::string> > > > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<std::vector<std::string, std::allocator<std::string> >, std::allocator<std::vector<std::string, std::allocator<std::string> > > > {lvalue},boost::python::api::object)
        """
class _listSt6vectorIiSaIiEE(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 40
    @staticmethod
    def __iter__(vect):
        ...
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::list<std::vector<int, std::allocator<int> >, std::allocator<std::vector<int, std::allocator<int> > > > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::list<std::vector<int, std::allocator<int> >, std::allocator<std::vector<int, std::allocator<int> > > > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::list<std::vector<int, std::allocator<int> >, std::allocator<std::vector<int, std::allocator<int> > > >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::list<std::vector<int, std::allocator<int> >, std::allocator<std::vector<int, std::allocator<int> > > > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::list<std::vector<int, std::allocator<int> >, std::allocator<std::vector<int, std::allocator<int> > > > {lvalue},_object*,_object*)
        """
class _listSt6vectorIjSaIjEE(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 40
    @staticmethod
    def __iter__(vect):
        ...
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::list<std::vector<unsigned int, std::allocator<unsigned int> >, std::allocator<std::vector<unsigned int, std::allocator<unsigned int> > > > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::list<std::vector<unsigned int, std::allocator<unsigned int> >, std::allocator<std::vector<unsigned int, std::allocator<unsigned int> > > > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::list<std::vector<unsigned int, std::allocator<unsigned int> >, std::allocator<std::vector<unsigned int, std::allocator<unsigned int> > > >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::list<std::vector<unsigned int, std::allocator<unsigned int> >, std::allocator<std::vector<unsigned int, std::allocator<unsigned int> > > > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::list<std::vector<unsigned int, std::allocator<unsigned int> >, std::allocator<std::vector<unsigned int, std::allocator<unsigned int> > > > {lvalue},_object*,_object*)
        """
class _listi(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 40
    @staticmethod
    def __iter__(vect):
        ...
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::list<int, std::allocator<int> > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::list<int, std::allocator<int> > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::list<int, std::allocator<int> >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::list<int, std::allocator<int> > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::list<int, std::allocator<int> > {lvalue},_object*,_object*)
        """
class _vectSs(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __iter__(vect):
        ...
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<std::string, std::allocator<std::string> > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<std::string, std::allocator<std::string> > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<std::string, std::allocator<std::string> >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<std::string, std::allocator<std::string> > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<std::string, std::allocator<std::string> > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<std::string, std::allocator<std::string> > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<std::string, std::allocator<std::string> > {lvalue},boost::python::api::object)
        """
class _vectSt6vectorIdSaIdEE(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __iter__(vect):
        ...
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<std::vector<double, std::allocator<double> >, std::allocator<std::vector<double, std::allocator<double> > > > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<std::vector<double, std::allocator<double> >, std::allocator<std::vector<double, std::allocator<double> > > > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<std::vector<double, std::allocator<double> >, std::allocator<std::vector<double, std::allocator<double> > > >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<std::vector<double, std::allocator<double> >, std::allocator<std::vector<double, std::allocator<double> > > > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<std::vector<double, std::allocator<double> >, std::allocator<std::vector<double, std::allocator<double> > > > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<std::vector<double, std::allocator<double> >, std::allocator<std::vector<double, std::allocator<double> > > > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<std::vector<double, std::allocator<double> >, std::allocator<std::vector<double, std::allocator<double> > > > {lvalue},boost::python::api::object)
        """
class _vectSt6vectorIiSaIiEE(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __iter__(vect):
        ...
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<std::vector<int, std::allocator<int> >, std::allocator<std::vector<int, std::allocator<int> > > > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<std::vector<int, std::allocator<int> >, std::allocator<std::vector<int, std::allocator<int> > > > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<std::vector<int, std::allocator<int> >, std::allocator<std::vector<int, std::allocator<int> > > >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<std::vector<int, std::allocator<int> >, std::allocator<std::vector<int, std::allocator<int> > > > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<std::vector<int, std::allocator<int> >, std::allocator<std::vector<int, std::allocator<int> > > > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<std::vector<int, std::allocator<int> >, std::allocator<std::vector<int, std::allocator<int> > > > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<std::vector<int, std::allocator<int> >, std::allocator<std::vector<int, std::allocator<int> > > > {lvalue},boost::python::api::object)
        """
class _vectSt6vectorIjSaIjEE(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __iter__(vect):
        ...
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<std::vector<unsigned int, std::allocator<unsigned int> >, std::allocator<std::vector<unsigned int, std::allocator<unsigned int> > > > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<std::vector<unsigned int, std::allocator<unsigned int> >, std::allocator<std::vector<unsigned int, std::allocator<unsigned int> > > > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<std::vector<unsigned int, std::allocator<unsigned int> >, std::allocator<std::vector<unsigned int, std::allocator<unsigned int> > > >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<std::vector<unsigned int, std::allocator<unsigned int> >, std::allocator<std::vector<unsigned int, std::allocator<unsigned int> > > > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<std::vector<unsigned int, std::allocator<unsigned int> >, std::allocator<std::vector<unsigned int, std::allocator<unsigned int> > > > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<std::vector<unsigned int, std::allocator<unsigned int> >, std::allocator<std::vector<unsigned int, std::allocator<unsigned int> > > > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<std::vector<unsigned int, std::allocator<unsigned int> >, std::allocator<std::vector<unsigned int, std::allocator<unsigned int> > > > {lvalue},boost::python::api::object)
        """
class _vectd(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __iter__(vect):
        ...
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<double, std::allocator<double> > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<double, std::allocator<double> > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<double, std::allocator<double> >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<double, std::allocator<double> > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<double, std::allocator<double> > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<double, std::allocator<double> > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<double, std::allocator<double> > {lvalue},boost::python::api::object)
        """
class _vecti(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __iter__(vect):
        ...
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<int, std::allocator<int> > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<int, std::allocator<int> > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<int, std::allocator<int> >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<int, std::allocator<int> > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<int, std::allocator<int> > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<int, std::allocator<int> > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<int, std::allocator<int> > {lvalue},boost::python::api::object)
        """
class _vectj(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __iter__(vect):
        ...
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<unsigned int, std::allocator<unsigned int> > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<unsigned int, std::allocator<unsigned int> > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<unsigned int, std::allocator<unsigned int> >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<unsigned int, std::allocator<unsigned int> > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<unsigned int, std::allocator<unsigned int> > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<unsigned int, std::allocator<unsigned int> > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<unsigned int, std::allocator<unsigned int> > {lvalue},boost::python::api::object)
        """
class ostream(std_ostream):
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __init__(self, python_file_obj: typing.Any, buffer_size: int = 0) -> None:
        """
            C++ signature :
                void __init__(_object*,boost::python::api::object {lvalue} [,unsigned long=0])
        """
class std_ostream(Boost.Python.instance):
    @staticmethod
    def __init__(*args, **kwargs):
        """
        Raises an exception
        This class cannot be instantiated from Python
        """
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
class streambuf(Boost.Python.instance):
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __init__(self, python_file_obj: typing.Any, buffer_size: int = 0) -> None:
        """
            documentation
        
            C++ signature :
                void __init__(_object*,boost::python::api::object {lvalue} [,unsigned long=0])
        """
def AttachFileToLog(spec: str, filename: str, delay: int = 100) -> None:
    """
        Causes the log to write to a file
    
        C++ signature :
            void AttachFileToLog(std::string,std::string [,int=100])
    """
def DisableLog(spec: str) -> None:
    """
        C++ signature :
            void DisableLog(std::string)
    """
def EnableLog(spec: str) -> None:
    """
        C++ signature :
            void EnableLog(std::string)
    """
def LogDebugMsg(msg: str) -> None:
    """
        Log a message to the RDKit debug logs
    
        C++ signature :
            void LogDebugMsg(std::string)
    """
def LogErrorMsg(msg: str) -> None:
    """
        Log a message to the RDKit error logs
    
        C++ signature :
            void LogErrorMsg(std::string)
    """
def LogInfoMsg(msg: str) -> None:
    """
        Log a message to the RDKit info logs
    
        C++ signature :
            void LogInfoMsg(std::string)
    """
def LogMessage(spec: str, msg: str) -> None:
    """
        Log a message to any rdApp.* log
    
        C++ signature :
            void LogMessage(std::string,std::string)
    """
def LogStatus() -> str:
    """
        C++ signature :
            std::string LogStatus()
    """
def LogToCppStreams() -> None:
    """
        Initialize RDKit logs with C++ streams
    
        C++ signature :
            void LogToCppStreams()
    """
def LogToPythonLogger() -> None:
    """
        Initialize RDKit logs with Python's logging module
    
        C++ signature :
            void LogToPythonLogger()
    """
def LogToPythonStderr() -> None:
    """
        Initialize RDKit logs with Python's stderr stream
    
        C++ signature :
            void LogToPythonStderr()
    """
def LogWarningMsg(msg: str) -> None:
    """
        Log a message to the RDKit warning logs
    
        C++ signature :
            void LogWarningMsg(std::string)
    """
def SeedRandomNumberGenerator(seed: int) -> None:
    """
        Provides a seed to the standard C random number generator
        This does not affect pure Python code, but is relevant to some of the RDKit C++ components.
    
        C++ signature :
            void SeedRandomNumberGenerator(unsigned int)
    """
def WrapLogs() -> None:
    """
        Tee the RDKit logs to Python's stderr stream
    
        C++ signature :
            void WrapLogs()
    """
def _version() -> str:
    """
        Deprecated, use the constant rdkitVersion instead
    
        C++ signature :
            std::string _version()
    """
_iostreamsEnabled: bool = True
_multithreadedEnabled: bool = True
_serializationEnabled: bool = True
boostVersion: str = '1_85'
rdkitBuild: str = 'Linux|6.8.0-1020-azure|UNIX|GNU|64-bit'
rdkitVersion: str = '2024.09.5'
