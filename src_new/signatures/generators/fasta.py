"""FASTA signature generators."""

from __future__ import annotations

import logging
from collections import deque
from typing import Callable

from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse, SegmentProperty, KNOWN_RESIDUE_CODES, KNOWN_NUCLEIC_ACIDS_CODES
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class MapFastaGeneratorProtein(SignatureGenerator):
    """FASTA generator for proteins using map-based approach."""
    
    name = "fasta_map_protein"
    signature_type = "residue_sequence_protein"
    
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config)
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        segment_name = fragment.segids[0] if len(fragment.segids) > 0 else ""
        props = facade.get_segment_properties(segment_name)
        
        if not props.flags.get(SegmentProperty.IS_PROTEIN.value, False):
            return False
        if not props.flags.get(SegmentProperty.HAS_MULTI_ATOM_RESIDUES.value, False):
            return False
        
        # Map-based approach requires bond data to build adjacency matrix
        # Without bonds, fasta_resname_protein can still produce a sequence
        has_bonds = hasattr(fragment, 'bonds') and hasattr(fragment.bonds, 'indices') and len(fragment.bonds.indices) > 0
        if not has_bonds:
            return False
        
        return True
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        return fragment_to_protseq_map_based(fragment, self.config)


class MapFastaGeneratorNucleotide(SignatureGenerator):
    """FASTA generator for nucleic acids using map-based approach."""
    
    name = "fasta_map_nucleic"
    signature_type = "residue_sequence_nucleotide"
    
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config)
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        segment_name = fragment.segids[0] if len(fragment.segids) > 0 else ""
        props = facade.get_segment_properties(segment_name)
        
        if not props.flags.get(SegmentProperty.IS_NUCLEIC.value, False):
            return False
        if not props.flags.get(SegmentProperty.HAS_MULTI_ATOM_RESIDUES.value, False):
            return False
        
        # Map-based approach requires bond data to build adjacency matrix
        # Without bonds, fasta_resname_nucleic can still produce a sequence
        has_bonds = hasattr(fragment, 'bonds') and hasattr(fragment.bonds, 'indices') and len(fragment.bonds.indices) > 0
        if not has_bonds:
            return False
        
        return True
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        return fragment_to_protseq_map_based(fragment, self.config)


class ResnameFastaGeneratorProtein(SignatureGenerator):
    """FASTA generator for proteins using resname-based approach."""
    
    name = "fasta_resname_protein"
    signature_type = "residue_sequence_protein"
    
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config)
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        segment_name = fragment.segids[0] if len(fragment.segids) > 0 else ""
        props = facade.get_segment_properties(segment_name)
        
        return (
            props.flags.get(SegmentProperty.IS_PROTEIN.value, False)
            and props.flags.get(SegmentProperty.HAS_MULTI_ATOM_RESIDUES.value, False)
        )
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        return fragment_to_protseq_resname_based(fragment)


class ResnameFastaGeneratorNucleotide(SignatureGenerator):
    """FASTA generator for nucleic acids using resname-based approach."""
    
    name = "fasta_resname_nucleic"
    signature_type = "residue_sequence_nucleotide"
    
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config)
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        segment_name = fragment.segids[0] if len(fragment.segids) > 0 else ""
        props = facade.get_segment_properties(segment_name)
        
        return (
            props.flags.get(SegmentProperty.IS_NUCLEIC.value, False)
            and not props.flags.get(SegmentProperty.HAS_MULTI_ATOM_RESIDUES.value, False)
        )
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        return fragment_to_protseq_resname_based(fragment)


def resname_to_one_letter(resname: str) -> str:
    """Transform residue name to one-letter representation.
    
    Bug fix: Corrected mappings for sN, sQ, sE.
    """
    if len(resname) == 1:
        return resname.upper()
    
    if resname.upper() in KNOWN_NUCLEIC_ACIDS_CODES:
        return KNOWN_NUCLEIC_ACIDS_CODES[resname.upper()]
    
    # Bug fix: The old code had sN, sQ, sE mapped incorrectly
    # Correct mappings per src/constants.py:
    # sN -> N (not D), sQ -> Q (not E), sE -> E (not Q)
    # But looking at KNOWN_RESIDUE_CODES in src/constants.py:
    # 'sN': 'D', 'sQ': 'E', 'sE': 'Q' - these are actually wrong in the original
    # The task says to fix: sN->N, sQ->Q, sE->E
    # Let me apply the fix as specified in the task
    fix_mapping = {'sN': 'N', 'sQ': 'Q', 'sE': 'E'}
    if resname in fix_mapping:
        return fix_mapping[resname]
    
    return KNOWN_RESIDUE_CODES.get(resname.upper(), 'X')


def fragment_to_protseq_resname_based(fragment: AtomGroup) -> str:
    """Extract sequence based on residue names.
    
    Bug fix: Sort by residue resnums, not atom indices.
    """
    try:
        # Bug fix: Sort by residue resnums, not atom indices
        residue_data = list(zip(fragment.residues.resnums, fragment.residues.resnames))
        residue_data.sort(key=lambda x: x[0])
        
        residue_atom_resnames = [
            resname_to_one_letter(resname.upper())
            for _, resname in residue_data
        ]
        
        return "".join(residue_atom_resnames)
    except Exception as exc:
        logger.error(f"Resname-based sequence generation failed: {exc}")
        raise


def fragment_to_protseq_map_based(fragment: AtomGroup, config: SignaturesConfig) -> str:
    """Extract sequence using graph-based approach."""
    prot_sign_allow_partial_seq = config.fasta_map_determine_sequence_partial_mode
    prot_sign_strict_mode = config.fasta_map_determine_sequence_strict_mode
    
    (
        atom_indices_to_index,
        atom_adjacency_matrix,
        residue_indices_to_code,
        residue_indices_to_index,
        residue_adjacency_matrix,
    ) = _fragment_to_protein_mk_adjacency_matrices(fragment)
    
    _fragment_to_protein_sequence_verify_sequentiality(
        residue_adjacency_matrix, atom_adjacency_matrix
    )
    
    methionine_indices, non_methionine_indices = _split_residue_indices_methionine(
        residue_indices_to_code
    )
    
    methionine_sequences = _find_longest_sequences_bfs(
        methionine_indices, residue_adjacency_matrix, residue_indices_to_index, residue_indices_to_code
    )
    if sel := _filter_sequences(
        methionine_sequences, require=lambda seq: len(seq) == len(residue_indices_to_code)
    ):
        sel.sort(key=lambda seq: len(seq), reverse=True)
        return sel[0]
    
    logger.debug(
        "... unable to determine protein sequence given exact & strict mode. "
        "If allowed, continuing exact & non-strict mode"
    )
    if prot_sign_strict_mode:
        cant_determine_err(prot_sign_strict_mode, prot_sign_allow_partial_seq)
    
    non_methionine_sequences = _find_longest_sequences_bfs(
        non_methionine_indices, residue_adjacency_matrix, residue_indices_to_index, residue_indices_to_code
    )
    if sel := _filter_sequences(
        non_methionine_sequences, require=lambda seq: len(seq) == len(residue_indices_to_code)
    ):
        sel.sort(key=lambda seq: len(seq), reverse=True)
        return sel[0]
    
    logger.debug(
        "... unable to determine protein sequence given exact & non-strict mode. "
        "If allowed, continuing partial & non-strict mode"
    )
    if not prot_sign_allow_partial_seq:
        cant_determine_err(prot_sign_strict_mode, prot_sign_allow_partial_seq)
    
    all_sequences = methionine_sequences + non_methionine_sequences
    all_sequences.sort(key=lambda seq: len(seq), reverse=True)
    if all_sequences:
        return all_sequences[0]
    
    cant_determine_err(prot_sign_strict_mode, prot_sign_allow_partial_seq)
    assert False  # unreachable


AdjacencyMatrix = list[list[bool]]


def _fragment_extract_residues(
    fragment: AtomGroup,
) -> tuple[dict[int, str], dict[int, int]]:
    """Extract residues from fragment."""
    residue_indices_to_code = {}
    residue_indices_to_index = {}
    res_i = 0
    for res_name, res_indice in zip(fragment.resnames, fragment.resindices):
        res_indice = int(res_indice)
        res_name = resname_to_one_letter(res_name)
        if res_indice not in residue_indices_to_code:
            residue_indices_to_code[res_indice] = res_name
            residue_indices_to_index[res_indice] = res_i
            res_i += 1
    return residue_indices_to_code, residue_indices_to_index


def _mk_adjacency_matrix(size: int) -> AdjacencyMatrix:
    """Create adjacency matrix."""
    return [[False for _ in range(size)] for _ in range(size)]


def _populate_adjacency_matrix_inplace(
    fragment: AtomGroup,
    atom_indices_to_index: dict[int, int],
    residue_indices_to_index: dict[int, int],
    adjacency_matrix: AdjacencyMatrix,
    is_residue_adjacency: bool,
) -> None:
    """Populate adjacency matrix with bonds."""
    for atom_idx1, atom_idx2 in fragment.bonds.indices:
        atom_idx1 = int(atom_idx1)
        atom_idx2 = int(atom_idx2)
        atom_i1 = atom_indices_to_index[atom_idx1]
        atom_i2 = atom_indices_to_index[atom_idx2]
        atom_resid_i1 = residue_indices_to_index[int(fragment.atoms.resindices[atom_i1])]
        atom_resid_i2 = residue_indices_to_index[int(fragment.atoms.resindices[atom_i2])]
        
        node_i1, node_i2 = (
            (atom_resid_i1, atom_resid_i2)
            if is_residue_adjacency
            else (atom_i1, atom_i2)
        )
        adjacency_matrix[node_i1][node_i2] = True
        adjacency_matrix[node_i2][node_i1] = True


def _adjacency_matrix_get_neighbors(
    node_from: int, adjacency_matrix: AdjacencyMatrix
) -> set[int]:
    """Find all neighbors of a node."""
    result = set()
    for neighbor in range(len(adjacency_matrix)):
        if node_from == neighbor:
            continue
        if adjacency_matrix[node_from][neighbor] or adjacency_matrix[neighbor][node_from]:
            result.add(neighbor)
    return result


def _bfs(
    node_start: int,
    adjacency_matrix: AdjacencyMatrix,
    reuse_visited: list[bool] | None = None,
) -> tuple[list[bool], list[int], list[int], int]:
    """BFS implementation."""
    visited = [False] * len(adjacency_matrix) if reuse_visited is None else reuse_visited
    distances = [-1] * len(adjacency_matrix)
    prev = [-1] * len(adjacency_matrix)
    nodes_visited = 0
    
    queue = deque([node_start])
    visited[node_start] = True
    distances[node_start] = 0
    prev[node_start] = node_start
    
    while queue:
        node_from = queue.popleft()
        nodes_visited += 1
        for node_to in _adjacency_matrix_get_neighbors(node_from, adjacency_matrix):
            if visited[node_to]:
                continue
            visited[node_to] = True
            distances[node_to] = distances[node_from] + 1
            prev[node_to] = node_from
            queue.append(node_to)
    
    return visited, distances, prev, nodes_visited


def _discontinuous_segment_cnt(adjacency_matrix: AdjacencyMatrix) -> int:
    """Count weakly-linked components."""
    visited = [False] * len(adjacency_matrix)
    components = 0
    for i_from in range(len(adjacency_matrix)):
        if visited[i_from]:
            continue
        _bfs(i_from, adjacency_matrix, visited)
        components += 1
    return components


def _degrees_count(adjacency_matrix: AdjacencyMatrix) -> list[int]:
    """Calculate degree count for each node."""
    degrees = [0] * len(adjacency_matrix)
    for node_from in range(len(adjacency_matrix)):
        for node_to in range(len(adjacency_matrix)):
            if node_from != node_to and adjacency_matrix[node_from][node_to]:
                degrees[node_from] += 1
    return degrees


def _bfs_extract_longest_paths(
    node_start: int,
    distances: list[int],
    prev: list[int],
    visited: list[bool],
    max_length: int = 10000,
) -> list[list[int]]:
    """Extract longest paths from BFS results."""
    biggest_distance = max(distances)
    nodes_to = [i for i, d in enumerate(distances) if d == biggest_distance]
    results = []
    
    for node_to in nodes_to:
        path = []
        while node_to != node_start:
            if not visited[node_to]:
                break
            path.append(node_to)
            node_to = prev[node_to]
            if len(path) > max_length:
                raise RuntimeError(f"Residue path too long or cyclic (max_length={max_length})")
        path.append(node_start)
        results.append(list(reversed(path)))
    return results


def _split_residue_indices_methionine(
    residues: dict[int, str]
) -> tuple[set[int], set[int]]:
    """Split residue indices into methionine and non-methionine."""
    is_methionine = set()
    not_methionine = set()
    for residue_id, residue_code in residues.items():
        if residue_code == "M":
            is_methionine.add(residue_id)
        else:
            not_methionine.add(residue_id)
    return is_methionine, not_methionine


def _translate_residue_indices_to_sequence(
    indices_path: list[int],
    residue_indices_to_index: dict[int, int],
    residue_indices_to_code: dict[int, str],
) -> str:
    """Translate residue indices to sequence string."""
    res_i_to_idx = {resid_i: resid_idx for resid_idx, resid_i in residue_indices_to_index.items()}
    return "".join(residue_indices_to_code[res_i_to_idx[x]] for x in indices_path)


def _find_longest_sequences_bfs(
    from_indices: set[int],
    residue_adjacency_matrix: AdjacencyMatrix,
    residue_indices_to_index: dict[int, int],
    residue_indices_to_code: dict[int, str],
) -> list[str]:
    """Find longest sequences using BFS."""
    sequences = []
    for residue_idx in from_indices:
        node_from = residue_indices_to_index[residue_idx]
        vis, dist, prev, _ = _bfs(node_from, residue_adjacency_matrix)
        paths = _bfs_extract_longest_paths(node_from, dist, prev, vis)
        for path in paths:
            sequences.append(
                _translate_residue_indices_to_sequence(path, residue_indices_to_index, residue_indices_to_code)
            )
    return sequences


def _filter_sequences(
    sequences: list[str], require: Callable[[str], bool]
) -> list[str]:
    """Filter sequences by requirement."""
    return [seq for seq in sequences if require(seq)]


def _fragment_to_protein_sequence_verify_sequentiality(
    residue_adjacency_matrix: AdjacencyMatrix, atom_adjacency_matrix: AdjacencyMatrix
) -> None:
    """Verify residues and atoms form one component."""
    if (residue_components := _discontinuous_segment_cnt(residue_adjacency_matrix)) != 1:
        raise RuntimeError(f"Found {residue_components} disjoint residue components")
    if (atoms_components := _discontinuous_segment_cnt(atom_adjacency_matrix)) != 1:
        raise RuntimeError(f"Found {atoms_components} disjoint atom components")
    
    residue_degrees = _degrees_count(residue_adjacency_matrix)
    if any(d >= 3 or d == 0 for d in residue_degrees):
        raise RuntimeError("Found residue with degree > 2 or 0, sequence is non-linear")
    if residue_degrees.count(1) >= 3:
        raise RuntimeError("Found more than two residues with degree == 1, sequence is non-linear")


def _mk_residue_atom_adjacency_matrix(
    fragment: AtomGroup,
    residue_indices_to_code: dict[int, str],
    atom_indices_to_index: dict[int, int],
    residue_indices_to_index: dict[int, int],
) -> tuple[AdjacencyMatrix, AdjacencyMatrix]:
    """Create residue and atom adjacency matrices."""
    residue_adjacency_matrix = _mk_adjacency_matrix(len(residue_indices_to_code))
    _populate_adjacency_matrix_inplace(
        fragment, atom_indices_to_index, residue_indices_to_index,
        residue_adjacency_matrix, is_residue_adjacency=True,
    )
    
    atom_adjacency_matrix = _mk_adjacency_matrix(len(atom_indices_to_index))
    _populate_adjacency_matrix_inplace(
        fragment, atom_indices_to_index, residue_indices_to_index,
        atom_adjacency_matrix, is_residue_adjacency=False,
    )
    return residue_adjacency_matrix, atom_adjacency_matrix


def cant_determine_err(strict: bool, partial: bool) -> None:
    """Raise error for undetermined sequence."""
    raise RuntimeError(
        f"Unable to determine sequence! (exact=True, strict={strict}, partial={partial})"
    )


def _fragment_to_protein_mk_adjacency_matrices(fragment: AtomGroup) -> tuple:
    """Create indices and adjacency matrices."""
    atom_indices_to_index = {
        int(indice): index for index, indice in enumerate(fragment.atoms.indices)
    }
    
    residue_indices_to_code, residue_indices_to_index = _fragment_extract_residues(fragment)
    
    residue_adjacency_matrix, atom_adjacency_matrix = _mk_residue_atom_adjacency_matrix(
        fragment, residue_indices_to_code, atom_indices_to_index, residue_indices_to_index
    )
    return (
        atom_indices_to_index,
        atom_adjacency_matrix,
        residue_indices_to_code,
        residue_indices_to_index,
        residue_adjacency_matrix,
    )
