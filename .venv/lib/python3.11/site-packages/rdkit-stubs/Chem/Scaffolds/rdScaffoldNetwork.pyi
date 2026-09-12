"""
Module containing functions for creating a Scaffold Network
"""
from __future__ import annotations
import typing
__all__ = ['BRICSScaffoldParams', 'CreateScaffoldNetwork', 'EdgeType', 'NetworkEdge', 'NetworkEdge_VECT', 'ScaffoldNetwork', 'ScaffoldNetworkParams', 'UpdateScaffoldNetwork']
class EdgeType(Boost.Python.enum):
    Fragment: typing.ClassVar[EdgeType]  # value = rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.Fragment
    Generic: typing.ClassVar[EdgeType]  # value = rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.Generic
    GenericBond: typing.ClassVar[EdgeType]  # value = rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.GenericBond
    Initialize: typing.ClassVar[EdgeType]  # value = rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.Initialize
    RemoveAttachment: typing.ClassVar[EdgeType]  # value = rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.RemoveAttachment
    __slots__: typing.ClassVar[tuple] = tuple()
    names: typing.ClassVar[dict]  # value = {'Fragment': rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.Fragment, 'Generic': rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.Generic, 'GenericBond': rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.GenericBond, 'RemoveAttachment': rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.RemoveAttachment, 'Initialize': rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.Initialize}
    values: typing.ClassVar[dict]  # value = {1: rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.Fragment, 2: rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.Generic, 3: rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.GenericBond, 4: rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.RemoveAttachment, 5: rdkit.Chem.Scaffolds.rdScaffoldNetwork.EdgeType.Initialize}
class NetworkEdge(Boost.Python.instance):
    """
    A scaffold network edge
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
    def __str__(self) -> typing.Any:
        """
            C++ signature :
                _object* __str__(RDKit::ScaffoldNetwork::NetworkEdge {lvalue})
        """
    @property
    def beginIdx(*args, **kwargs):
        """
        index of the begin node in node list
        """
    @property
    def endIdx(*args, **kwargs):
        """
        index of the end node in node list
        """
    @property
    def type(*args, **kwargs):
        """
        type of the edge
        """
class NetworkEdge_VECT(Boost.Python.instance):
    __instance_size__: typing.ClassVar[int] = 48
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __contains__(self, item: typing.Any) -> bool:
        """
            C++ signature :
                bool __contains__(std::vector<RDKit::ScaffoldNetwork::NetworkEdge, std::allocator<RDKit::ScaffoldNetwork::NetworkEdge> > {lvalue},_object*)
        """
    def __delitem__(self, item: typing.Any) -> None:
        """
            C++ signature :
                void __delitem__(std::vector<RDKit::ScaffoldNetwork::NetworkEdge, std::allocator<RDKit::ScaffoldNetwork::NetworkEdge> > {lvalue},_object*)
        """
    def __getitem__(self, item: typing.Any) -> typing.Any:
        """
            C++ signature :
                boost::python::api::object __getitem__(boost::python::back_reference<std::vector<RDKit::ScaffoldNetwork::NetworkEdge, std::allocator<RDKit::ScaffoldNetwork::NetworkEdge> >&>,_object*)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    def __iter__(self) -> typing.Any:
        """
            C++ signature :
                boost::python::objects::iterator_range<boost::python::return_internal_reference<1ul, boost::python::default_call_policies>, __gnu_cxx::__normal_iterator<RDKit::ScaffoldNetwork::NetworkEdge*, std::vector<RDKit::ScaffoldNetwork::NetworkEdge, std::allocator<RDKit::ScaffoldNetwork::NetworkEdge> > > > __iter__(boost::python::back_reference<std::vector<RDKit::ScaffoldNetwork::NetworkEdge, std::allocator<RDKit::ScaffoldNetwork::NetworkEdge> >&>)
        """
    def __len__(self) -> int:
        """
            C++ signature :
                unsigned long __len__(std::vector<RDKit::ScaffoldNetwork::NetworkEdge, std::allocator<RDKit::ScaffoldNetwork::NetworkEdge> > {lvalue})
        """
    def __setitem__(self, item: typing.Any, value: typing.Any) -> None:
        """
            C++ signature :
                void __setitem__(std::vector<RDKit::ScaffoldNetwork::NetworkEdge, std::allocator<RDKit::ScaffoldNetwork::NetworkEdge> > {lvalue},_object*,_object*)
        """
    def append(self, item: typing.Any) -> None:
        """
            C++ signature :
                void append(std::vector<RDKit::ScaffoldNetwork::NetworkEdge, std::allocator<RDKit::ScaffoldNetwork::NetworkEdge> > {lvalue},boost::python::api::object)
        """
    def extend(self, other: typing.Any) -> None:
        """
            C++ signature :
                void extend(std::vector<RDKit::ScaffoldNetwork::NetworkEdge, std::allocator<RDKit::ScaffoldNetwork::NetworkEdge> > {lvalue},boost::python::api::object)
        """
class ScaffoldNetwork(Boost.Python.instance):
    """
    A scaffold network
    """
    __getstate_manages_dict__: typing.ClassVar[bool] = True
    __instance_size__: typing.ClassVar[int] = 120
    __safe_for_unpickling__: typing.ClassVar[bool] = True
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __getinitargs__(self) -> tuple:
        """
            C++ signature :
                boost::python::tuple __getinitargs__(RDKit::ScaffoldNetwork::ScaffoldNetwork)
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
    def __setstate__(self, data: tuple) -> None:
        """
            C++ signature :
                void __setstate__(boost::python::api::object,boost::python::tuple)
        """
    @property
    def counts(*args, **kwargs):
        """
        the number of times each node was encountered while building the network.
        """
    @property
    def edges(*args, **kwargs):
        """
        the sequence of network edges
        """
    @property
    def molCounts(*args, **kwargs):
        """
        the number of moleclues each node was found in.
        """
    @property
    def nodes(*args, **kwargs):
        """
        the sequence of SMILES defining the nodes
        """
class ScaffoldNetworkParams(Boost.Python.instance):
    """
    Scaffold network parameters
    """
    __instance_size__: typing.ClassVar[int] = 64
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    @typing.overload
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    @typing.overload
    def __init__(self, bondBreakerSmartsList: _vectSs) -> None:
        """
            Constructor taking a list of Reaction SMARTS for the fragmentation reactions
        
            C++ signature :
                void __init__(_object*,std::vector<std::string, std::allocator<std::string> >)
        """
    @property
    def collectMolCounts(*args, **kwargs):
        """
        keep track of the number of molecules each scaffold was found in
        """
    @collectMolCounts.setter
    def collectMolCounts(*args, **kwargs):
        ...
    @property
    def flattenChirality(*args, **kwargs):
        """
        remove chirality and bond stereo when flattening
        """
    @flattenChirality.setter
    def flattenChirality(*args, **kwargs):
        ...
    @property
    def flattenIsotopes(*args, **kwargs):
        """
        remove isotopes when flattening
        """
    @flattenIsotopes.setter
    def flattenIsotopes(*args, **kwargs):
        ...
    @property
    def flattenKeepLargest(*args, **kwargs):
        """
        keep only the largest fragment when doing flattening
        """
    @flattenKeepLargest.setter
    def flattenKeepLargest(*args, **kwargs):
        ...
    @property
    def includeGenericBondScaffolds(*args, **kwargs):
        """
        include scaffolds with all bonds replaced by single bonds
        """
    @includeGenericBondScaffolds.setter
    def includeGenericBondScaffolds(*args, **kwargs):
        ...
    @property
    def includeGenericScaffolds(*args, **kwargs):
        """
        include scaffolds with all atoms replaced by dummies
        """
    @includeGenericScaffolds.setter
    def includeGenericScaffolds(*args, **kwargs):
        ...
    @property
    def includeNames(*args, **kwargs):
        """
        Include molecules names of the input molecules
        """
    @includeNames.setter
    def includeNames(*args, **kwargs):
        ...
    @property
    def includeScaffoldsWithAttachments(*args, **kwargs):
        """
        Include the version of the scaffold with attachment points
        """
    @includeScaffoldsWithAttachments.setter
    def includeScaffoldsWithAttachments(*args, **kwargs):
        ...
    @property
    def includeScaffoldsWithoutAttachments(*args, **kwargs):
        """
        remove attachment points from scaffolds and include the result
        """
    @includeScaffoldsWithoutAttachments.setter
    def includeScaffoldsWithoutAttachments(*args, **kwargs):
        ...
    @property
    def keepOnlyFirstFragment(*args, **kwargs):
        """
        keep only the first fragment from the bond breaking rule
        """
    @keepOnlyFirstFragment.setter
    def keepOnlyFirstFragment(*args, **kwargs):
        ...
    @property
    def pruneBeforeFragmenting(*args, **kwargs):
        """
        Do a pruning/flattening step before starting fragmenting
        """
    @pruneBeforeFragmenting.setter
    def pruneBeforeFragmenting(*args, **kwargs):
        ...
def BRICSScaffoldParams() -> ScaffoldNetworkParams:
    """
        Returns parameters for generating scaffolds using BRICS fragmentation rules
    
        C++ signature :
            RDKit::ScaffoldNetwork::ScaffoldNetworkParams* BRICSScaffoldParams()
    """
def CreateScaffoldNetwork(mols: typing.Any, params: ScaffoldNetworkParams) -> ScaffoldNetwork:
    """
        create (and return) a new network from a sequence of molecules
    
        C++ signature :
            RDKit::ScaffoldNetwork::ScaffoldNetwork* CreateScaffoldNetwork(boost::python::api::object,RDKit::ScaffoldNetwork::ScaffoldNetworkParams)
    """
def UpdateScaffoldNetwork(mols: typing.Any, network: ScaffoldNetwork, params: ScaffoldNetworkParams) -> None:
    """
        update an existing network by adding molecules
    
        C++ signature :
            void UpdateScaffoldNetwork(boost::python::api::object,RDKit::ScaffoldNetwork::ScaffoldNetwork {lvalue},RDKit::ScaffoldNetwork::ScaffoldNetworkParams)
    """
