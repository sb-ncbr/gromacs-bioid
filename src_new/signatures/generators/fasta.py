"""FASTA signature generators."""

from __future__ import annotations

import logging
from collections import deque
from typing import Callable

from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse, SegmentProperty, KNOWN_RESIDUE_CODES, KNOWN_NUCLEIC_ACIDS_CODES
from ...molecules.nucleic_acid import normalize_nucleic_resname
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
        # anchor=None: 'M' cannot occur in the nucleic alphabet, so the
        # methionine-anchor branch is dead weight here (wave-7 B3).
        return fragment_to_protseq_map_based(fragment, self.config, anchor=None)


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
    """FASTA generator for nucleic acids using resname-based approach.

    Fallback role (wave-7 B2): fires whenever the map-based generator
    cannot - coarse-grained (single-atom-residue) NA as before, and now
    also atomistic NA fragments WITHOUT bonds, which previously produced
    no sequence signature at all. Never double-fires: the map-based
    generator requires bonds, this one stays silent when bonds exist and
    residues are multi-atom (the exact map-based applicability condition).
    """

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

        if not props.flags.get(SegmentProperty.IS_NUCLEIC.value, False):
            return False

        multi_atom = props.flags.get(SegmentProperty.HAS_MULTI_ATOM_RESIDUES.value, False)
        has_bonds = (
            hasattr(fragment, 'bonds')
            and hasattr(fragment.bonds, 'indices')
            and len(fragment.bonds.indices) > 0
        )
        # Applicable exactly when the map-based generator is not.
        return not multi_atom or not has_bonds
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        return fragment_to_protseq_resname_based(fragment)


def resname_to_one_letter(resname: str) -> str:
    """Transform residue name to one-letter representation.

    Wave-7: the nucleic normalizer runs first (D- prefix, [3|5] terminal
    codes), then the legacy tables. Bug fix retained: sN/sQ/sE mappings.
    """
    if len(resname) == 1:
        return resname.upper()

    base = normalize_nucleic_resname(resname)
    if base is not None:
        return base

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


def fragment_to_protseq_map_based(
    fragment: AtomGroup, config: SignaturesConfig, anchor: str | None = "M"
) -> str:
    """Extract sequence using graph-based approach.

    Args:
        anchor: one-letter code of the preferred path-start residue.
            "M" (methionine) is the biologically meaningful anchor for
            proteins. Pass None for nucleic acids: 'M' can never occur in
            the NA alphabet, so the anchor branch is dead weight there;
            disabling it makes the nucleic path explicit and skips the
            empty-anchor scan. Control flow for proteins is unchanged.
    """
    prot_sign_allow_partial_seq = config.fasta_map_determine_sequence_partial_mode
    prot_sign_strict_mode = config.fasta_map_determine_sequence_strict_mode

    (
        atom_indices_to_index,
        atom_adjacency_matrix,
        residue_indices_to_code,
        residue_indices_to_index,
        residue_adjacency_matrix,
    ) = _fragment_to_protein_mk_adjacency_matrices(fragment)

    try:
        _fragment_to_protein_sequence_verify_sequentiality(
            residue_adjacency_matrix, atom_adjacency_matrix
        )
    except RuntimeError as exc:
        # F-N1b: merged duplexes / multi-chain assemblies / branched graphs
        # previously produced NO fasta at all (silent identification hole).
        # Fall back to largest-component selection; strict path below stays
        # byte-identical whenever the graph verifies.
        return _fragment_to_seq_best_component(
            residue_indices_to_code,
            residue_indices_to_index,
            residue_adjacency_matrix,
            anchor=anchor,
            reason=str(exc),
        )

    anchor_indices, non_anchor_indices = _split_residue_indices_methionine(
        residue_indices_to_code, anchor=anchor
    )

    methionine_sequences = _find_longest_sequences_bfs(
        anchor_indices, residue_adjacency_matrix, residue_indices_to_index, residue_indices_to_code
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
        non_anchor_indices, residue_adjacency_matrix, residue_indices_to_index, residue_indices_to_code
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


def _residue_components(adjacency_matrix: AdjacencyMatrix) -> list[list[int]]:
    """Connected components of the residue graph as row-index lists (F-N1b).

    Deterministic: components sorted by (-size, min row index).
    """
    visited = [False] * len(adjacency_matrix)
    comps: list[list[int]] = []
    for i_from in range(len(adjacency_matrix)):
        if visited[i_from]:
            continue
        # fresh BFS (no reuse_visited): returned mask == this component only
        vis, _, _, _ = _bfs(i_from, adjacency_matrix)
        comp = [idx for idx, seen in enumerate(vis) if seen]
        for idx in comp:
            visited[idx] = True
        comps.append(comp)
    comps.sort(key=lambda c: (-len(c), c[0]))
    return comps


def _is_linear_chain(adjacency_matrix: AdjacencyMatrix) -> bool:
    """True iff graph is a single linear chain (degrees all in {1,2}, ≤2 endpoints)."""
    degrees = _degrees_count(adjacency_matrix)
    if any(d >= 3 or d == 0 for d in degrees):
        return False
    return degrees.count(1) <= 2


def _submatrix(adjacency_matrix: AdjacencyMatrix, rows: list[int]) -> AdjacencyMatrix:
    return [[adjacency_matrix[i][j] for j in rows] for i in rows]


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
    residues: dict[int, str], anchor: str | None = "M"
) -> tuple[set[int], set[int]]:
    """Split residue indices into anchor and non-anchor residue.

    Defaults to methionine (protein path start). With ``anchor=None``
    (nucleic acids) the anchor set is always empty, so only the generic
    longest-path branch runs - matching the effective NA control flow.
    """
    is_methionine = set()
    not_methionine = set()
    for residue_id, residue_code in residues.items():
        if anchor is not None and residue_code == anchor:
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


def _fragment_to_seq_best_component(
    residue_indices_to_code: dict[int, str],
    residue_indices_to_index: dict[int, int],
    residue_adjacency_matrix: AdjacencyMatrix,
    anchor: str | None,
    reason: str,
) -> str:
    """F-N1b: extract the longest sequence from a merged/branched assembly.

    The strict sequentiality check already failed (``reason``). Instead of
    giving up on the whole segment (merged duplexes, multi-chain proteins),
    decompose the residue graph into connected components, select the LARGEST
    (ties: lowest minimum row index — deterministic), and extract its longest
    linear sequence. Documented trade-off: non-longest strands of asymmetric
    assemblies are not represented (W4 design lock 2026-10-03; complementary
    duplex strands share blast subject sets). Deterministic tie-breaks:
    (-length, sequence string) everywhere in this fallback.

    Raises RuntimeError when nothing extractable remains.
    """
    comps = _residue_components(residue_adjacency_matrix)
    keep_rows = comps[0]
    row_to_resid = {row: resid for resid, row in residue_indices_to_index.items()}
    kept_resids = sorted(row_to_resid[r] for r in keep_rows)

    sub_adj = _submatrix(residue_adjacency_matrix, keep_rows)
    sub_code = {resid: residue_indices_to_code[resid] for resid in kept_resids}
    sub_index = {resid: i for i, resid in enumerate(kept_resids)}

    # Note: if the strict check failed ONLY on the atom-component count while
    # the residue graph is a clean linear chain, plain extraction below returns
    # the full chain — strictly more useful than giving up.
    seqs = _find_longest_sequences_bfs(
        set(kept_resids), sub_adj, sub_index, sub_code
    )
    seqs = [s for s in seqs if s]
    if not seqs:
        raise RuntimeError(
            f"no linear sequence extractable from {len(comps)}-component assembly ({reason})"
        )
    full = len(sub_code)
    exact = [s for s in seqs if len(s) == full]
    pool = exact if exact else seqs
    pool.sort(key=lambda s: (-len(s), s))
    chosen = pool[0]
    logger.info(
        f"fasta strand-select: {len(comps)} components, kept largest "
        f"({len(keep_rows)}/{len(residue_indices_to_code)} residues, "
        f"len={len(chosen)}) after: {reason}"
    )
    return chosen


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
