"""DEPRECATED (frozen 2026-10) — legacy strategy loader, superseded by
src_new/loader/strategies.py + src_new/input/discovery.py (widened engine
matrix: CHARMM/LAMMPS support, atom-count probing, success gates).
Do not extend; see src/loader/README.md. Kept for the legacy api_endpoint
chain only.
"""
import logging
import json
import os
from contextlib import contextmanager
import tempfile
from enum import Enum
from rdkit import Chem
from rdkit.Chem import rdDetermineBonds
from .results_file import ResultsFile
from MDAnalysis import Universe # type: ignore
from ..utils.file_utils import list_files_in_directory, filter_files_by_extension
from ..constants import MDANALYSIS_GUESSER_VDWRADII

ERROR_STRATEGY_NOT_APPLICABLE: str = "Too many/non-present topology and coordinate files, cowardly exiting!"
LOAD_STRATEGY_PATH: str = "simulation/load_strategy"

logger = logging.getLogger("base")

def save_used_files(dir_path: str, files: list[str]) -> None:
    """
    Saves used files used for loading the simulation
    :param dir_path: to save used files to (used_files.txt)
    :param files: used to load the simulation
    :return: None (creates the file)
    """
    files = [os.path.basename(x) for x in files]

    with open(os.path.join(dir_path, "used_files.txt"), "w") as fd:
        json.dump(files, fd)

class LoadStrategy(Enum):
    ITP_GRO = "ITP_GRO"  # ITP-based topology and gro coords
    TOP_GRO = "TOP_GRO"  # TOP-based topology and gro coords
    TPR_GRO = "TPR_GRO"  # TRP-based topology and gro coords
    TPR     = "TPR"      # TRP-based topology w/o coords
    TOP     = "TOP"      # TOP-based topology w/o coords
    ITP     = "ITP"      # ITP-based topology w/o coords
    XTC     = "XTC"      # XTC-based topology
    PDB     = "PDB"      # PDB-based topology, with bonds inferrence


def load(simulation_directory: str, results_file: ResultsFile) -> Universe:
    """
    Attempts to load simulation into MDAnalysis' universe
    :param simulation_directory: directory containing simulation files
    :param results_file: results file related to the simulation
    :raises RuntimeError: if all load strategies fail
    :return: Universe
    """
    if results_file.item_exists(LOAD_STRATEGY_PATH):
        logger.info("Using existing load strategy '%s'"
                    % results_file.get_item_safe(LOAD_STRATEGY_PATH, required_type=str))

        return _load_using(simulation_directory,
                           results_file,
                           LoadStrategy(results_file.get_item_safe(LOAD_STRATEGY_PATH, required_type=str)))

    for strategy in LoadStrategy:
        try:
            return _load_using(simulation_directory, results_file, strategy)
        except Exception as exc:
            logger.info(f"... loading failed! {exc}")
            pass

    logger.fatal("No load strategy succeeded. Aborting. (Are all necessary files provided?)")
    raise RuntimeError(f"No load strategy is applicable for simulation in directory '{simulation_directory}'")


def _load_using(simulation_directory: str, results_file: ResultsFile, strategy: LoadStrategy) -> Universe:
    """
    Attempts to load simulation into MDAnalysis' universe using specified strategy
    :param simulation_directory: directory containing simulation files
    :param results_file: to save successful load strategy
    :raises RuntimeError: if strategy fails or is not applicable
    :return: Universe
    """
    simulation_files: list[str] = list_files_in_directory(simulation_directory)

    match strategy:
        case LoadStrategy.ITP_GRO:
            return _load_itp_gro(simulation_files, results_file, simulation_directory)
        case LoadStrategy.TOP_GRO:
            return _load_top_gro(simulation_files, results_file, simulation_directory)
        case LoadStrategy.TPR_GRO:
            return _load_tpr_gro(simulation_files, results_file, simulation_directory)
        case LoadStrategy.TPR:
            return _load_tpr(simulation_files, results_file, simulation_directory)
        case LoadStrategy.TOP:
            return _load_top(simulation_files, results_file, simulation_directory)
        case LoadStrategy.ITP:
            return _load_itp(simulation_files, results_file, simulation_directory)
        case LoadStrategy.PDB:
            return _load_pdb(simulation_files, results_file, simulation_directory)
        case LoadStrategy.XTC:
            return _load_xtc(simulation_files, results_file, simulation_directory)
        case _:
            raise RuntimeError("Unknown load strategy")


def _load_itp_gro(simulation_files: list[str], results_file: ResultsFile, simulation_directory: str) -> Universe:
    """
    Attempts to load simulation into MDAnalysis' universe using ITP topology and GRO coordinates
    :param simulation_files: files representing the simulation
    :param results_file: to save successful load strategy
    :raises RuntimeError: if strategy fails or is not applicable
    :return: Universe
    """
    logger.info("Loading using ITP topology and GRO coordinates...")

    top_files: list[str] = filter_files_by_extension(simulation_files, ['top'])
    gro_files: list[str] = filter_files_by_extension(simulation_files, ['gro'])

    if len(top_files) != 1 or len(gro_files) != 1:
        raise RuntimeError(ERROR_STRATEGY_NOT_APPLICABLE)

    universe: Universe = Universe(top_files[0],
                                  gro_files[0],
                                  tpr_resid_from_one=True,
                                  in_memory=True,
                                  topology_format='ITP',
                                  infer_system=True)

    results_file.set_item(LOAD_STRATEGY_PATH, LoadStrategy.ITP_GRO.value)
    save_used_files(simulation_directory, [top_files[0], gro_files[0]])
    return universe


def _load_top_gro(simulation_files: list[str], results_file: ResultsFile, simulation_directory: str) -> Universe:
    """
    Attempts to load simulation into MDAnalysis' universe using TOP topology and GRO coordinates
    :param simulation_files: files representing the simulation
    :param results_file: to save successful load strategy
    :raises RuntimeError: if strategy fails or is not applicable
    :return: Universe
    """
    logger.info("Loading using TOP topology and GRO coordinates...")

    top_files: list[str] = filter_files_by_extension(simulation_files, ['top'])
    gro_files: list[str] = filter_files_by_extension(simulation_files, ['gro'])

    if len(top_files) != 1 or len(gro_files) != 1:
        raise RuntimeError(ERROR_STRATEGY_NOT_APPLICABLE)
    universe: Universe = Universe(top_files[0],gro_files[0], tpr_resid_from_one=True, in_memory=True)
    results_file.set_item(LOAD_STRATEGY_PATH, LoadStrategy.TOP_GRO.value)
    save_used_files(simulation_directory, [top_files[0], gro_files[0]])
    return universe


def _load_tpr_gro(simulation_files: list[str], results_file: ResultsFile, simulation_directory: str) -> Universe:
    """
    Attempts to load simulation into MDAnalysis' universe using TPR topology and GRO coordinates
    :param simulation_files: files representing the simulation
    :param results_file: to save successful load strategy
    :raises RuntimeError: if strategy fails or is not applicable
    :return: Universe
    """
    logger.info("Loading using TPR topology and GRO coordinates...")

    top_files: list[str] = filter_files_by_extension(simulation_files, ['tpr'])
    gro_files: list[str] = filter_files_by_extension(simulation_files, ['gro'])

    if len(top_files) != 1 or len(gro_files) != 1:
        raise RuntimeError(ERROR_STRATEGY_NOT_APPLICABLE)

    universe: Universe = Universe(top_files[0],gro_files[0], tpr_resid_from_one=True, in_memory=True)
    results_file.set_item(LOAD_STRATEGY_PATH, LoadStrategy.TPR_GRO.value)
    save_used_files(simulation_directory, [top_files[0], gro_files[0]])
    return universe


def _load_tpr(simulation_files: list[str], results_file: ResultsFile, simulation_directory: str) -> Universe:
    """
    Attempts to load simulation into MDAnalysis' universe using TPR topology w/o coordinates
    :param simulation_files: files representing the simulation
    :param results_file: to save successful load strategy
    :raises RuntimeError: if strategy fails or is not applicable
    :return: Universe
    """
    logger.info("Loading using TPR topology only...")

    top_files: list[str] = filter_files_by_extension(simulation_files, ['tpr'])

    if len(top_files) != 1:
        raise RuntimeError(ERROR_STRATEGY_NOT_APPLICABLE)

    universe: Universe = Universe(top_files[0], tpr_resid_from_one=True, in_memory=True)
    results_file.set_item(LOAD_STRATEGY_PATH, LoadStrategy.TPR.value)
    save_used_files(simulation_directory, [top_files[0]])
    return universe


def _load_top(simulation_files: list[str], results_file: ResultsFile, simulation_directory: str) -> Universe:
    """
    Attempts to load simulation into MDAnalysis' universe using TOP topology w/o coordinates
    :param simulation_files: files representing the simulation
    :param results_file: to save successful load strategy
    :raises RuntimeError: if strategy fails or is not applicable
    :return: Universe
    """
    logger.info("Loading using TOP topology only...")

    top_files: list[str] = filter_files_by_extension(simulation_files, ['top'])

    if len(top_files) != 1:
        raise RuntimeError(ERROR_STRATEGY_NOT_APPLICABLE)

    universe: Universe = Universe(top_files[0], tpr_resid_from_one=True, in_memory=True)
    results_file.set_item(LOAD_STRATEGY_PATH, LoadStrategy.TOP.value)
    save_used_files(simulation_directory, [top_files[0]])
    return universe


def _load_itp(simulation_files: list[str], results_file: ResultsFile, simulation_directory: str) -> Universe:
    """
    Attempts to load simulation into MDAnalysis' universe using TOP topology w/o coordinates
    :param simulation_files: files representing the simulation
    :param results_file: to save successful load strategy
    :raises RuntimeError: if strategy fails or is not applicable
    :return: Universe
    """
    logger.info("Loading using ITP topology only...")

    top_files: list[str] = filter_files_by_extension(simulation_files, ['top'])

    if len(top_files) != 1:
        raise RuntimeError(ERROR_STRATEGY_NOT_APPLICABLE)

    universe: Universe = Universe(top_files[0],
                                  tpr_resid_from_one=True,
                                  in_memory=True,
                                  topology_format='ITP',
                                  infer_system=True)

    results_file.set_item(LOAD_STRATEGY_PATH, LoadStrategy.ITP.value)
    save_used_files(simulation_directory, [top_files[0]])
    return universe


def _load_xtc(simulation_files: list[str],results_file: ResultsFile, simulation_directory: str) -> Universe:
    """
    Attempts to load simulation into MDAnalysis' universe using PDB topology + coords
    :param simulation_files: files representing the simulation
    :param results_file: to save successful load strategy
    :raises RuntimeError: if strategy fails or is not applicable
    :return: Universe
    """
    logger.info("Loading using XTC...")

    xtc_files: list[str] = filter_files_by_extension(simulation_files, ['xtc'])

    if len(xtc_files) != 1:
        raise RuntimeError(ERROR_STRATEGY_NOT_APPLICABLE)

    universe: Universe = Universe(xtc_files[0],
                                  in_memory=True,
                                  infer_system=True)

    results_file.set_item(LOAD_STRATEGY_PATH, LoadStrategy.XTC.value)
    save_used_files(simulation_directory, [xtc_files[0]])
    return universe


@contextmanager
def fix_pdb(pdb_path: str, clear_bonds: bool = True):
    tmp_names: list[str] = []
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdb")
        tmp_names.append(tmp.name)
        with open(pdb_path, "r") as src, open(tmp.name, "w") as dst:
            for line in src:
                if line.startswith(("ATOM", "HETATM")) and len(line) >= 78:
                    fixed = line[:76] + line[76:78].upper() + line[78:]
                    dst.write(fixed)
                elif clear_bonds and line.startswith("CONECT"):
                    continue
                else:
                    dst.write(line)

        tmp2 = tempfile.NamedTemporaryFile(delete=False, suffix=".pdb")
        tmp_names.append(tmp2.name)
        mol = Chem.MolFromPDBFile(tmp.name, sanitize=False, removeHs=False)
        rdDetermineBonds.DetermineConnectivity(mol)
        Chem.MolToPDBFile(mol, tmp2.name)

        yield tmp2.name
    finally:
        for path in tmp_names:
            os.remove(path)


def _load_pdb(simulation_files: list[str],results_file: ResultsFile, simulation_directory: str) -> Universe:
    """
    Attempts to load simulation into MDAnalysis' universe using PDB topology + coords
    :param simulation_files: files representing the simulation
    :param results_file: to save successful load strategy
    :raises RuntimeError: if strategy fails or is not applicable
    :return: Universe
    """
    logger.info("Loading using PDB...")

    pdb_files: list[str] = filter_files_by_extension(simulation_files, ['pdb'])

    if len(pdb_files) != 1:
        raise RuntimeError(ERROR_STRATEGY_NOT_APPLICABLE)

    with fix_pdb(pdb_files[0], clear_bonds=True) as new_pdb_path:  # inference inside
        universe: Universe = Universe(new_pdb_path,
                                      in_memory=True,
                                      infer_system=True, guess_bonds=False)

    results_file.set_item(LOAD_STRATEGY_PATH, LoadStrategy.PDB.value)
    save_used_files(simulation_directory, [pdb_files[0]])
    return universe
