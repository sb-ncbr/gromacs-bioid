"""DEPRECATED (frozen 2026-10) — superseded by src_new/loader/. See src/loader/README.md."""
import logging
import warnings
from enum import Enum

import MDAnalysis # type: ignore
from MDAnalysis import Universe, AtomGroup
from .. import core_config
from .universe_loader import load
from .results_file import ResultsFile
from .repair_fragment import estimate_elements_from_mass, estimate_elements_from_names, estimate_elements_multi, fix_names as repair_fix_names
from ..constants import KNOWN_RESIDUE_CODES, KNOWN_NUCLEIC_ACIDS_CODES

logger = logging.getLogger("base")

ERROR_SIM_NOT_LOADED = "The simulation is not loaded!"
ERROR_SEGMENT_NOT_PRESENT = "The requested segment is not present within the simulation (or has been filtered out)"

class SegmentSupports(Enum):
    ELEMENTS = 1
    MASSES = 2
    POSITIONS = 3
    NAMES = 4
    AMINO_ACID_RESIDUE_NAMES = 5
    NUCLEIC_ACID_RESIDUE_NAMES = 6
    NAMES_UNIQUE = 7
    MULTI_ATOM_RESIDUES = 8

def supports_flag(fragment: MDAnalysis.AtomGroup, flag: SegmentSupports) -> bool:
    """
    Calculates whether specific segment (represented by a fragment) supports specific flag
    :param fragment: representing the segment
    :param flag: to be checked
    :raises RuntimeError: if the flag is not recognized
    :return: True if flag is supported
    """

    match flag:
        case SegmentSupports.ELEMENTS:
            return hasattr(fragment, "elements") and all(e for e in fragment.elements)
        case SegmentSupports.MASSES:
            return hasattr(fragment, "masses") and all(x > 0 for x in fragment.masses)
        case SegmentSupports.POSITIONS:
            return hasattr(fragment.atoms, "positions")
        case SegmentSupports.NAMES:
            return hasattr(fragment.atoms, "names")
        case SegmentSupports.NAMES_UNIQUE:
            if not hasattr(fragment.atoms, "names"):
                return False
            for resid in fragment.residues.resnums:
                residue: AtomGroup = fragment.select_atoms(f"resid {resid}")
                if len(residue.atoms.names) != len(set(residue.atoms.names)):
                    return False
            return True
        case SegmentSupports.AMINO_ACID_RESIDUE_NAMES:
            return (hasattr(fragment.atoms, "resnames")
                    and all(residue_name.upper() in KNOWN_RESIDUE_CODES for residue_name in fragment.resnames))
        case SegmentSupports.NUCLEIC_ACID_RESIDUE_NAMES:
            return (hasattr(fragment.atoms, "resnames")
                    and all(residue_name.upper() in KNOWN_NUCLEIC_ACIDS_CODES for residue_name in fragment.resnames))
        case SegmentSupports.MULTI_ATOM_RESIDUES:
            residue_ids: list[int] = fragment.residues.resids
            residue_atoms: list[int] = [len(fragment.select_atoms(f"resid {resid}").atoms) for resid in residue_ids]
            return any(cnt > 1 for cnt in residue_atoms)
        case _:
            raise RuntimeError(f"Unknown flag '{flag}'")


class SimulationParameter(Enum):
    ATOM_COUNT = 1
    RESIDUE_COUNT = 2
    SEGMENT_COUNT = 3
    FRAGMENT_COUNT = 4


class Simulation:

    def __init__(self, files_directory: str, results_path: str, log_handler: logging.FileHandler, log_path: str) -> None:
        """
        Initializes virtual representation of simulation, and its associated results
        :param files_directory: directory containing simulation files (.tpr, .gro, etc...)
        :param results_path: path where to save results
        :param log_handler: logging handler associated with this simulation analysis run
        :param log_path: path to log file
        """

        logger.info("Opening simulation handle for directory '%s'" % files_directory)

        self.simulation_directory: str = files_directory

        self.results_file_path: str = results_path
        self.results_file: ResultsFile = ResultsFile(results_path, log_handler)
        self.log_path: str = log_path

        self.filter_segments: set[str] = set()

        self._segments: set[str] = set()
        self._segment_flags: dict[str, dict[SegmentSupports, bool]] = {}

        self._active_simulation: Universe | None = None

    def get_results_handler(self) -> ResultsFile:
        """
        Provides results file handler associated with the simulation
        :return: ResultsFile instance
        """
        return self.results_file

    def set_segment_filter(self, reported_segments: set[str]) -> None:
        """
        Places a restriction on which segments will be reported by the simulation
        :param reported_segments: segment names to be allowed
        :return: None
        """
        self.filter_segments = reported_segments

    def load_simulation(self) -> None:
        """
        Loads the simulation into the RAM for immediate use. Also fetches all segments and their flags
        :raises RuntimeError: if simulation cannot be loaded
        :return: None
        """

        logger.info("Attempting to load simulation from '%s'" % self.simulation_directory)

        with warnings.catch_warnings(action="ignore"):
            self._active_simulation = load(self.simulation_directory,
                                           self.results_file)  # this can throw

        logger.info("Successfully loaded simulation from '%s'" % self.simulation_directory)

        self._segments = set(self._active_simulation.segments.segids)
        if self.filter_segments:
            self._segments = self._segments.intersection(self.filter_segments)

        for segment_name in self._segments:
            self._segment_flags[segment_name] = {}
            for flag in SegmentSupports:
                self._segment_flags[segment_name][flag] = supports_flag(self.get_fragment(segment_name),
                                                                        flag)
                self.results_file.set_item(f"simulation/segments/{segment_name}/flags/{flag.name}",
                                           self._segment_flags[segment_name][flag])

            self.results_file.set_item(f"simulation/segments/{segment_name}/atoms_molecule",
                                       len(self.get_fragment(segment_name).atoms))
            self.results_file.set_item(f"simulation/segments/{segment_name}/bonds_molecule",
                                       len(self.get_fragment(segment_name).bonds))

            self.results_file.set_item(f"simulation/segments/{segment_name}/atoms",
                                       len(self._active_simulation.atoms[self._active_simulation.atoms.segids == segment_name].atoms))
            self.results_file.set_item(f"simulation/segments/{segment_name}/bonds",
                                       len(self._active_simulation.atoms[self._active_simulation.atoms.segids == segment_name].bonds))
            self.results_file.set_item(f"simulation/segments/{segment_name}/molecules",
                                       len(self._active_simulation.atoms[self._active_simulation.atoms.segids == segment_name].fragments))

    def unload_simulation(self) -> None:
        """
        Unloads the simulation from RAM by giving it to the garbage collector
        :raises AssertionError: if the simulation is not loaded
        :return: None
        """
        assert self._active_simulation is not None, ERROR_SIM_NOT_LOADED
        self._active_simulation = None

    def get_simulation(self) -> Universe:
        """
        Provides raw simulation object
        :raises AssertionError: if the simulation is not loaded
        :return: simulation
        """
        assert self._active_simulation is not None, ERROR_SIM_NOT_LOADED
        return self._active_simulation

    def get_segments(self) -> set[str]:
        """
        Provides list of all segments (molecule types) within the simulation
        :raises AssertionError: if the simulation is not loaded
        :return: set of segment names
        """

        assert self._active_simulation is not None, ERROR_SIM_NOT_LOADED
        return self._segments

    def get_fragment(self, segment_name: str) -> MDAnalysis.AtomGroup:
        """
        Provides a molecule (fragment) given the segment name
        :param segment_name: of the molecule to be returned
        :raises AssertionError: if the simulation is not loaded, or the segment_name is not within the simulation,
                                or finally if the segment cannot be extracted
        :return: AtomGroup representing the fragment
        """
        assert self._active_simulation is not None, ERROR_SIM_NOT_LOADED
        assert segment_name in self._segments, ERROR_SEGMENT_NOT_PRESENT

        segment_atoms = self._active_simulation.atoms[self._active_simulation.atoms.segids == segment_name]
        fragments: list[MDAnalysis.AtomGroup] = segment_atoms.fragments
        assert fragments, "Fragment could not be retrieved, possibly whitespace in the name"
        return fragments[0]

    def get_simulation_parameter(self, kind: SimulationParameter) -> int:
        """
        Provides specific parameter of the simulation
        :param kind: type of parameter to be returned
        :raises AssertionError: if the simulation is not loaded
        :raises RuntimeError: if the parameter is not recognized
        :return: value of the parameter
        """
        assert self._active_simulation is not None, ERROR_SIM_NOT_LOADED
        match kind:
            case SimulationParameter.ATOM_COUNT:
                return int(self._active_simulation.atoms.n_atoms)
            case SimulationParameter.RESIDUE_COUNT:
                return int(self._active_simulation.atoms.n_residues)
            case SimulationParameter.SEGMENT_COUNT:
                return int(self._active_simulation.atoms.n_segments)
            case SimulationParameter.FRAGMENT_COUNT:
                return int(self._active_simulation.atoms.n_fragments)
            case _:
                raise RuntimeError(f"Unknown parameter '{kind}'")

    def get_segment_flag(self, segment_name: str, kind: SegmentSupports) -> bool:
        """
        Provides whether a specific segment supports a specific feature
        :param segment_name: of the segment to be checked
        :param kind: type of feature to be checked
        :raises AssertionError: if the simulation is not loaded, or the segment_name is not within the simulation
        :return: True if the segment supports the feature, False otherwise
        """
        assert self._active_simulation is not None, ERROR_SIM_NOT_LOADED
        assert segment_name in self._segments, ERROR_SEGMENT_NOT_PRESENT
        return self._segment_flags[segment_name].get(kind, False)

    def fix_missing_elements(self, segment_name: str, save_to: list[str] | None = None) -> bool:
        """
        Attempts to fix missing atomic element information in the simulation by determining them using atomic masses
        :param segment_name: for which to fix missing atomic elements
        :param save_to: list to store the names of the identified elements, if provided
        :return: True if fixing routine was successful, False otherwise
        """
        if save_to is None and self.get_segment_flag(segment_name, SegmentSupports.ELEMENTS):
            # bugfix: save_to overrides implicit return and forces determination of elements
            return True  # no action needed if elements are already present

        if (self.get_segment_flag(segment_name, SegmentSupports.MASSES)  # elements are estimated from masses
                and estimate_elements_from_mass(self._active_simulation, self.get_fragment(segment_name), save_to)):
            return True

        if (self.get_segment_flag(segment_name, SegmentSupports.NAMES)  # elements are estimated from masses
                and estimate_elements_from_names(self._active_simulation, self.get_fragment(segment_name),
                                                 use_types_not_names=False, save_to=save_to)):
            return True

        if (self.get_segment_flag(segment_name, SegmentSupports.NAMES)  # elements are estimated from masses
                and estimate_elements_from_names(self._active_simulation, self.get_fragment(segment_name),
                                                 use_types_not_names=True, save_to=save_to)):
            return True

        if (estimate_elements_multi(self._active_simulation, self.get_fragment(segment_name),
                                                 save_to=save_to)):
            return True

        return False

    def fix_names(self, segment_name: str) -> bool:
        """
        Attempts to fix missing/incorrect atomic name information in the fragment by assigning random ones
        :param segment_name: for which to fix missing atomic names
        :return: True if fixing routine was successful, False otherwise
        """
        return repair_fix_names(self._active_simulation, self.get_fragment(segment_name))


