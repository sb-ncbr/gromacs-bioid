"""
Module containing implementation of SynthonSpace search of Synthon-based chemical libraries such as Enamine REAL.  NOTE: This functionality is experimental and the API and/or results may change in future releases.
"""
from __future__ import annotations
import typing
__all__ = ['SubstructureResult', 'SynthonSpace', 'SynthonSpaceSearchParams']
class SubstructureResult(Boost.Python.instance):
    """
    Used to return results of SynthonSpace searches.
    """
    @staticmethod
    def GetCancelled(arg1: SubstructureResult) -> bool:
        """
            Returns whether the search was cancelled or not.
        
            C++ signature :
                bool GetCancelled(RDKit::SynthonSpaceSearch::SearchResults {lvalue})
        """
    @staticmethod
    def GetMaxNumResults(arg1: SubstructureResult) -> int:
        """
            The upper bound on number of results possible.  There may be fewer than this in practice for several reasons such as duplicate reagent sets being removed or the final product not matching the query even though the synthons suggested they would.
        
            C++ signature :
                unsigned long GetMaxNumResults(RDKit::SynthonSpaceSearch::SearchResults {lvalue})
        """
    @staticmethod
    def GetTimedOut(arg1: SubstructureResult) -> bool:
        """
            Returns whether the search timed out or not.
        
            C++ signature :
                bool GetTimedOut(RDKit::SynthonSpaceSearch::SearchResults {lvalue})
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
    def GetHitMolecules(self) -> list:
        """
            A function returning hits from the search
        
            C++ signature :
                boost::python::list GetHitMolecules(RDKit::SynthonSpaceSearch::SearchResults)
        """
class SynthonSpace(Boost.Python.instance):
    """
    SynthonSpaceSearch object.
    """
    __instance_size__: typing.ClassVar[int] = 88
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def BuildSynthonFingerprints(self, fingerprintGenerator: typing.Any) -> None:
        """
            Build the synthon fingerprints ready for similarity searching.  This is done automatically when the first similarity search is done, but if converting a text file to binary format it might need to be done explicitly.
        
            C++ signature :
                void BuildSynthonFingerprints(RDKit::SynthonSpaceSearch::SynthonSpace {lvalue},RDKit::FingerprintGenerator<unsigned long>)
        """
    def FingerprintSearch(self, query: Mol, fingerprintGenerator: typing.Any, params: typing.Any = None) -> SubstructureResult:
        """
            Does a fingerprint search in the SynthonSpace using the FingerprintGenerator passed in.
        
            C++ signature :
                RDKit::SynthonSpaceSearch::SearchResults FingerprintSearch(RDKit::SynthonSpaceSearch::SynthonSpace {lvalue},RDKit::ROMol,boost::python::api::object [,boost::python::api::object=None])
        """
    def GetNumProducts(self) -> int:
        """
            Returns number of products in the SynthonSpace, with multiple counting of any duplicates.
        
            C++ signature :
                long GetNumProducts(RDKit::SynthonSpaceSearch::SynthonSpace {lvalue})
        """
    def GetNumReactions(self) -> int:
        """
            Returns number of reactions in the SynthonSpace.
        
            C++ signature :
                unsigned long GetNumReactions(RDKit::SynthonSpaceSearch::SynthonSpace {lvalue})
        """
    def ReadDBFile(self, inFile: str) -> None:
        """
            Reads binary database file.
        
            C++ signature :
                void ReadDBFile(RDKit::SynthonSpaceSearch::SynthonSpace {lvalue},std::string)
        """
    def ReadTextFile(self, inFile: str) -> None:
        """
            Reads text file of the sort used by ChemSpace/Enamine.
        
            C++ signature :
                void ReadTextFile(RDKit::SynthonSpaceSearch::SynthonSpace {lvalue},std::string)
        """
    def SubstructureSearch(self, query: Mol, params: typing.Any = None) -> SubstructureResult:
        """
            Does a substructure search in the SynthonSpace.
        
            C++ signature :
                RDKit::SynthonSpaceSearch::SearchResults SubstructureSearch(RDKit::SynthonSpaceSearch::SynthonSpace {lvalue},RDKit::ROMol [,boost::python::api::object=None])
        """
    def Summarise(self) -> None:
        """
            Writes a summary of the SynthonSpace to stdout.
        
            C++ signature :
                void Summarise(RDKit::SynthonSpaceSearch::SynthonSpace)
        """
    def WriteDBFile(self, outFile: str) -> None:
        """
            Writes binary database file.
        
            C++ signature :
                void WriteDBFile(RDKit::SynthonSpaceSearch::SynthonSpace {lvalue},std::string)
        """
    def WriteEnumeratedFile(self, outFile: str) -> None:
        """
            Writes enumerated library to file.
        
            C++ signature :
                void WriteEnumeratedFile(RDKit::SynthonSpaceSearch::SynthonSpace {lvalue},std::string)
        """
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
class SynthonSpaceSearchParams(Boost.Python.instance):
    """
    SynthonSpaceSearch parameters.
    """
    __instance_size__: typing.ClassVar[int] = 104
    @staticmethod
    def __reduce__(*args, **kwargs):
        ...
    def __init__(self) -> None:
        """
            C++ signature :
                void __init__(_object*)
        """
    @property
    def approxSimilarityAdjuster(*args, **kwargs):
        """
        The fingerprint search uses an approximate similarity method before building a product and doing a final check.  The similarityCutoff is reduced by this value for the approximate check.  A lower value will give faster run times at the risk of missing some hits.  The value you use should have a positive correlation with your FOMO.  The default of 0.1 is appropriate for Morgan fingerprints.  With RDKit fingerprints, 0.05 is adequate, and higher than that has been seen to produce long run times.
        """
    @approxSimilarityAdjuster.setter
    def approxSimilarityAdjuster(*args, **kwargs):
        ...
    @property
    def buildHits(*args, **kwargs):
        """
        If false, reports the maximum number of hits that the search could produce, but doesn't return them.
        """
    @buildHits.setter
    def buildHits(*args, **kwargs):
        ...
    @property
    def fragSimilarityAdjuster(*args, **kwargs):
        """
        Similarities of fragments are generally low due to low bit densities.  For the fragment matching, reduce the similarity cutoff off by this amount.  Default=0.1.
        """
    @fragSimilarityAdjuster.setter
    def fragSimilarityAdjuster(*args, **kwargs):
        ...
    @property
    def hitStart(*args, **kwargs):
        """
        The sequence number of the hit to start from.  So that you can return the next N hits of a search having already obtained N-1.  Default=0
        """
    @hitStart.setter
    def hitStart(*args, **kwargs):
        ...
    @property
    def maxBondSplits(*args, **kwargs):
        """
        The maximum number of bonds to break in the query.  It should be between 1 and 4 and will be constrained to be so.  Default=4.
        """
    @maxBondSplits.setter
    def maxBondSplits(*args, **kwargs):
        ...
    @property
    def maxHits(*args, **kwargs):
        """
        The maximum number of hits to return.  Default=1000.Use -1 for no maximum.
        """
    @maxHits.setter
    def maxHits(*args, **kwargs):
        ...
    @property
    def maxNumFrags(*args, **kwargs):
        """
        The maximum number of fragments the query can be broken into.  Big molecules will create huge numbers of fragments that may cause excessive memory use.  If the number of fragments hits this number, fragmentation stops and the search results will likely be incomplete.  Default=100000.
        """
    @maxNumFrags.setter
    def maxNumFrags(*args, **kwargs):
        ...
    @property
    def numRandomSweeps(*args, **kwargs):
        """
        The random sampling doesn't always produce the required number of hits in 1 go.  This parameter controls how many loops it makes to try and get the hits before giving up.  Default=10.
        """
    @numRandomSweeps.setter
    def numRandomSweeps(*args, **kwargs):
        ...
    @property
    def randomSample(*args, **kwargs):
        """
        If True, returns a random sample of the hits, up to maxHits in number.  Default=False.
        """
    @randomSample.setter
    def randomSample(*args, **kwargs):
        ...
    @property
    def randomSeed(*args, **kwargs):
        """
        If using randomSample, this seeds the random number generator so as to give reproducible results.  Default=-1 means use a random seed.
        """
    @randomSeed.setter
    def randomSeed(*args, **kwargs):
        ...
    @property
    def similarityCutoff(*args, **kwargs):
        """
        Similarity cutoff for returning hits by fingerprint similarity.  At present the fp is hard-coded to be Morgan, bits, radius=2.  Default=0.5.
        """
    @similarityCutoff.setter
    def similarityCutoff(*args, **kwargs):
        ...
    @property
    def timeOut(*args, **kwargs):
        """
        Time limit for search, in seconds.  Default is 600s, 0 means no timeout.  Requires an integer
        """
    @timeOut.setter
    def timeOut(*args, **kwargs):
        ...
