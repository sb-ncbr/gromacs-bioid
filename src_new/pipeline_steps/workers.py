"""Worker functions for parallel pipeline execution."""

from __future__ import annotations

import json
import logging
import types
from typing import Any

logger = logging.getLogger("base")

_CANONICAL_SIGNATURE_TYPES: dict[str, str] = {
    "smiles": "smiles",
    "smiles_not_sanitized": "smiles",
    "inchi_key": "inchikey",
    "morgan_fingerprint": "morgan_fingerprint",
    "selfies": "selfies",
    "molecular_formula": "formula",
    "fasta_map_protein": "residue_sequence_protein",
    "fasta_map_nucleic": "residue_sequence_nucleotide",
    "fasta_resname_protein": "residue_sequence_protein",
    "fasta_resname_nucleic": "residue_sequence_nucleotide",
    "pdb_protein": "pdb_protein",
    "pdb_not_sanitized_protein": "pdb_protein",
    "pdb_backbone_protein": "pdb_protein",
    "pdb_backbone_not_sanitized_protein": "pdb_protein",
    "pdb_nucleic": "pdb_nucleic",
    "pdb_not_sanitized_nucleic": "pdb_nucleic",
    "pdb_backbone_nucleic": "pdb_nucleic",
    "pdb_backbone_not_sanitized_nucleic": "pdb_nucleic",
    "ca_only_pdb": "ca_only_pdb",
    "tdi": "3di_sequence",
    "lipid_shorthand": "lipid_shorthand",
    "glycan_composition": "glycan_composition",
    "mmcif": "mmcif",
    "name_chain": "name",
    "name_molecule": "name",
    "name_segment": "name",
    "atom": "element",
    "fingerprint": "hash",
}


class MockResidueAtoms:
    """Mock atoms container for a single residue.
    
    Supports iteration over atoms, length, and attribute access for lists.
    """
    
    def __init__(self, atom_indices, snapshot):
        self._indices = atom_indices
        self._snapshot = snapshot
        
    def __iter__(self):
        for i in self._indices:
            yield types.SimpleNamespace(
                index=i,
                name=self._snapshot.names[i],
                element=self._snapshot.elements[i] if i < len(self._snapshot.elements) else "",
                position=self._snapshot.positions[i] if i < len(self._snapshot.positions) else [0.0, 0.0, 0.0],
                resid=self._snapshot.resids[i] if i < len(self._snapshot.resids) else 1,
                resname=self._snapshot.resnames[i] if i < len(self._snapshot.resnames) else "UNK",
                segid=self._snapshot.segids[i] if i < len(self._snapshot.segids) else "",
            )
    
    def __len__(self):
        return len(self._indices)
    
    @property
    def indices(self):
        return self._indices
    
    @property
    def names(self):
        return [self._snapshot.names[i] for i in self._indices]
    
    @property
    def elements(self):
        return [self._snapshot.elements[i] for i in self._indices]
    
    @property
    def positions(self):
        return [self._snapshot.positions[i] for i in self._indices] if len(self._indices) > 0 else []


class MockResidues:
    """Mock residues container that supports iteration.
    
    Provides per-residue properties matching MDAnalysis Residues interface.
    """
    
    def __init__(self, resnames, resids, residue_list):
        self._residue_list = residue_list
        # Build per-residue properties from residue_list
        self._resnames = [r.resname for r in residue_list]
        self._resids = [r.resid for r in residue_list]
        self._resnums = [getattr(r, 'resnum', i + 1) for i, r in enumerate(residue_list)]
    
    def __iter__(self):
        return iter(self._residue_list)
    
    def __len__(self):
        """Return number of residues."""
        return len(self._residue_list)
    
    @property
    def resnames(self):
        """Per-residue list of residue names."""
        return self._resnames
    
    @property
    def resids(self):
        """Per-residue list of residue IDs."""
        return self._resids
    
    @property
    def resnums(self):
        """Per-residue list of residue numbers (sequential if not available)."""
        return self._resnums


class MockAtomGroup:
    """Mock AtomGroup for signature generation in worker processes.
    
    Provides the same convenience attributes as MDAnalysis AtomGroup:
    - segids, resnames, resids, names, elements, masses, positions
    - n_residues, n_atoms
    - resindices (per-atom residue index mapping)
    - atoms, residues, bonds (containers)
    """
    
    def __init__(self, snapshot):
        import numpy as np
        
        self.snapshot = snapshot
        
        # Store arrays for convenience properties
        self._segids = snapshot.segids
        self._resnames = snapshot.resnames
        self._resids = snapshot.resids
        self._names = snapshot.names
        self._elements = snapshot.elements
        self._masses = np.array(snapshot.masses, dtype=np.float64)
        self._positions = np.array(snapshot.positions, dtype=np.float32)
        self._atom_indices = np.array(snapshot.atom_indices, dtype=np.int64)
        self._n_atoms = snapshot.atom_count
        self._n_residues = snapshot.residue_count
        
        # Build resindices: per-atom residue index
        # Maps each atom to its residue index (0-based, sequential per unique resid)
        resid_to_resindex = {}
        resindices = []
        ri = 0
        for resid in snapshot.resids:
            if resid not in resid_to_resindex:
                resid_to_resindex[resid] = ri
                ri += 1
            resindices.append(resid_to_resindex[resid])
        self._resindices = np.array(resindices, dtype=np.int64)
        
        # Build bonds - shape (n_bonds, 2), not transposed
        if snapshot.bonds:
            bond_array = np.array(snapshot.bonds, dtype=np.int64)  # shape (n_bonds, 2)
        else:
            bond_array = np.empty((0, 2), dtype=np.int64)  # correct empty shape
        self._bonds = types.SimpleNamespace(indices=bond_array)
        
        self._atoms = types.SimpleNamespace(
            indices=self._atom_indices,
            ids=self._atom_indices,  # fallback: ids = indices
            elements=self._elements,
            names=self._names,
            positions=self._positions,
            masses=self._masses,
            segids=self._segids,
            resids=self._resids,
            resnames=self._resnames,
            resindices=self._resindices,
            n_atoms=self._n_atoms,
            bonds=self._bonds,  # expose bonds on atoms too
        )
        
        # Build residue list
        resid_to_data = {}
        for i, (resid, resname) in enumerate(zip(snapshot.resids, snapshot.resnames)):
            if resid not in resid_to_data:
                resid_to_data[resid] = {'resname': resname, 'atom_indices': []}
            resid_to_data[resid]['atom_indices'].append(i)
        
        residue_list = []
        for resid, data in sorted(resid_to_data.items()):
            residue_list.append(types.SimpleNamespace(
                resid=resid,
                resname=data['resname'],
                atoms=MockResidueAtoms(data['atom_indices'], snapshot),
            ))
        
        self._residues = MockResidues(
            resnames=snapshot.resnames,
            resids=snapshot.resids,
            residue_list=residue_list
        )
    
    # Convenience properties matching MDAnalysis AtomGroup interface
    @property
    def segids(self):
        """Segment IDs for each atom."""
        return self._segids
    
    @property
    def resnames(self):
        """Residue names for each atom."""
        return self._resnames
    
    @property
    def resids(self):
        """Residue IDs for each atom."""
        return self._resids
    
    @property
    def names(self):
        """Atom names for each atom."""
        return self._names
    
    @property
    def elements(self):
        """Element symbols for each atom."""
        return self._elements
    
    @property
    def masses(self):
        """Atomic masses for each atom."""
        return self._masses
    
    @property
    def positions(self):
        """3D coordinates for each atom (numpy array)."""
        return self._positions
    
    @property
    def resindices(self):
        """Per-atom residue index (0-based, sequential)."""
        return self._resindices
    
    @property
    def n_atoms(self):
        """Number of atoms."""
        return self._n_atoms
    
    @property
    def n_residues(self):
        """Number of residues."""
        return self._n_residues
    
    @property
    def atoms(self):
        """Atoms container with same attributes as self."""
        return self._atoms
    
    @property
    def residues(self):
        """Residues container."""
        return self._residues
    
    @property
    def bonds(self):
        """Bonds container."""
        return self._bonds
    
    def write(self, path, format="mmCIF"):
        """Write mock atom data to file.
        
        Args:
            path: Output file path.
            format: Output format (only "mmCIF" supported).
        """
        if format.lower() != "mmcif":
            raise ValueError(f"Unsupported format: {format}. Only mmCIF is supported.")
        
        # Build mmCIF content
        lines = []
        lines.append("data_mock")
        lines.append("")
        lines.append("_atom_site.group_PDB atom")
        lines.append("")
        
        # Collect unique residue info
        resid_to_resname = {}
        for i, (resid, resname, segid) in enumerate(zip(self._resids, self._resnames, self._segids)):
            if resid not in resid_to_resname:
                resid_to_resname[resid] = (resname, segid)
        
        # Build atom_site loop
        lines.append("loop_")
        lines.append("_atom_site.id")
        lines.append("_atom_site.label_atom_id")
        lines.append("_atom_site.label_comp_id")
        lines.append("_atom_site.label_asym_id")
        lines.append("_atom_site.Cartn_x")
        lines.append("_atom_site.Cartn_y")
        lines.append("_atom_site.Cartn_z")
        lines.append("_atom_site.label_element_symbol")
        
        for i in range(self._n_atoms):
            atom_id = i + 1
            atom_name = self._names[i] if i < len(self._names) else f"ATOM{i}"
            resid = self._resids[i] if i < len(self._resids) else 1
            resname, segid = resid_to_resname.get(resid, ("UNK", "A"))
            pos = self._positions[i] if i < len(self._positions) else [0.0, 0.0, 0.0]
            element = self._elements[i] if i < len(self._elements) and self._elements[i] else "C"
            
            lines.append(f"{atom_id} {atom_name} {resname} {segid} {pos[0]:.3f} {pos[1]:.3f} {pos[2]:.3f} {element}")
        
        lines.append("")
        lines.append("#")
        
        with open(path, 'w') as f:
            f.write("\n".join(lines))


def _generate_signatures_worker(item: tuple) -> dict[str, Any]:
    """Worker function for parallel signature generation.
    
    Args:
        item: Tuple of (snapshot_dict, config_dict) where snapshot_dict is
              a dict representation of SegmentSignatureSnapshot.
              
    Returns:
        Dict with segment_name, generated signatures, attempted generators, and errors.
        Never returns None - errors are collected in the 'errors' field.
    """
    try:
        from ..config.loader import RunConfig
        from ..signatures.registry import get_default_generators
        from ..signatures.snapshot import SegmentSignatureSnapshot
        
        snapshot_dict, config_dict = item
        deadline_epoch = config_dict.pop("_stage_deadline_epoch", None) if isinstance(config_dict, dict) else None
        snapshot = SegmentSignatureSnapshot(**snapshot_dict)
        config = RunConfig.from_dict(config_dict)
        if deadline_epoch is not None and __import__("time").time() > deadline_epoch:
            return {"segment_name": snapshot.segment_name, "generated": {}, "attempted": [],
                    "errors": [{"generator": "worker", "error": "stage_time_budget exceeded before start"}]}
        
        # Reconstruct mock AtomGroup from snapshot
        mock_fragment = MockAtomGroup(snapshot)
        
        # Reconstruct mock facade
        mock_facade = _build_mock_facade(snapshot)
        
        # Reconstruct mock instance
        mock_instance = _build_mock_instance(snapshot)
        
        # Get generators
        generators = get_default_generators(config.signatures)
        
        generated = {}
        attempted = []
        errors = []
        
        for generator in generators:
            if deadline_epoch is not None and __import__("time").time() > deadline_epoch:
                errors.append({"generator": generator.name, "error": "stage_time_budget exceeded mid-segment"})
                break
            try:
                if generator.is_applicable(mock_instance, mock_fragment, mock_facade):
                    attempted.append(generator.name)
                    sig = generator.generate(mock_instance, mock_fragment, mock_facade)
                    if sig is not None:
                        generated[generator.name] = sig
            except Exception as e:
                errors.append({"generator": generator.name, "error": str(e)})
                continue
        
        return {
            "segment_name": snapshot.segment_name,
            "generated": generated,
            "attempted": attempted,
            "errors": errors,
        }
    except Exception as e:
        return {"segment_name": "unknown", "generated": {}, "attempted": [], "errors": [{"generator": "worker", "error": str(e)}]}


def _build_mock_facade(snapshot: Any) -> types.SimpleNamespace:
    """Build a mock LoadedUniverse facade from snapshot.
    
    Args:
        snapshot: SegmentSignatureSnapshot.
        
    Returns:
        SimpleNamespace mimicking LoadedUniverse.
    """
    from ..loader.universe_facade import SegmentProperties
    
    props = SegmentProperties(
        atom_count_total=snapshot.atom_count,
        atom_count_fragment=snapshot.atom_count,
        residue_count=snapshot.residue_count,
        bond_count_total=len(snapshot.bonds),
        bond_count_fragment=len(snapshot.bonds),
        molecule_count=snapshot.copy_number,
        flags=snapshot.flags,
    )
    
    # Get the primary segid (first unique segid) for segment lookup
    primary_segid = snapshot.segids[0] if snapshot.segids else ""
    
    def get_segment_properties(segment_name: str) -> SegmentProperties:
        # Accept both the full segment_name and the primary segid
        if segment_name == snapshot.segment_name or segment_name == primary_segid:
            return props
        raise KeyError(f"Segment {segment_name} not found")
    
    return types.SimpleNamespace(
        get_segment_properties=get_segment_properties,
    )


def _build_mock_instance(snapshot: Any) -> Any:
    """Build a mock MoleculeInstance from snapshot.
    
    Args:
        snapshot: SegmentSignatureSnapshot.
        
    Returns:
        SimpleNamespace mimicking MoleculeInstance.
    """
    from ..molecules.instances import MoleculeType
    
    mol_type = MoleculeType(snapshot.molecule_type)
    
    return types.SimpleNamespace(
        instance_id=snapshot.instance_id,
        atom_indices=snapshot.atom_indices,
        residue_indices=list(range(snapshot.residue_count)),
        segment_ids=[snapshot.segment_name],
        chain_ids=snapshot.chain_ids,
        resids=snapshot.resids,
        resnames=snapshot.resnames,
        molecule_type=mol_type,
        copy_number=snapshot.copy_number,
        atom_count=snapshot.atom_count,
        element_composition=snapshot.element_composition,
    )


def _identify_molecules_worker(item: tuple) -> dict[str, Any]:
    """Worker function for parallel identification.
    
    Args:
        item: Tuple of (fragment_name, signatures_dict, config_dict, signature_type_map).
              signatures_dict maps generator_name -> signature string.
              
    Returns:
        Flat dict mapping result paths to values, plus attempted lists and errors.
        Never returns None - errors are collected in the 'errors' field.
    """
    try:
        from ..config.loader import RunConfig
        from ..identification.registry import get_default_resolvers, IdentifierRegistry
        from ..identification.cache_manager import ResolverCache
        from ..identification.resolution_manager import IdentifierResolutionManager
        
        fragment_name, signatures_dict, config_dict, sig_type_map = item
        deadline_epoch = config_dict.pop("_stage_deadline_epoch", None) if isinstance(config_dict, dict) else None
        config = RunConfig.from_dict(config_dict)
        if deadline_epoch is not None and __import__("time").time() > deadline_epoch:
            return {"fragment_name": fragment_name, "results": {},
                    "errors": [{"resolver": "worker", "generator": "", "error": "stage_time_budget exceeded before start"}]}

        # Create local instances
        resolvers = get_default_resolvers(config)
        registry = IdentifierRegistry(resolvers)
        cache = ResolverCache(config)
        manager = IdentifierResolutionManager(registry, config, signature_type_map=sig_type_map)
        
        results = {}
        errors = []
        
        for generator_name, signature in signatures_dict.items():
            if not signature:
                continue
            if deadline_epoch is not None and __import__("time").time() > deadline_epoch:
                errors.append({"resolver": "worker", "generator": generator_name, "error": "stage_time_budget exceeded mid-fragment"})
                break

            # Call resolve directly with local cache
            attempted_path = f"identifiers/{fragment_name}/{generator_name}/attempted"
            
            try:
                # We need to call resolve for each signature
                # But the manager.resolve method expects ResultsManager
                # So let's use a minimal approach - call the internal logic
                
                from ..identification.base import IdentifierResolver
                
                # Determine signature type
                signature_type = sig_type_map.get(generator_name) if sig_type_map else None
                if signature_type is None:
                    signature_type = _CANONICAL_SIGNATURE_TYPES.get(generator_name)
                if signature_type is None:
                    logger.warning(f"Unknown signature generator '{generator_name}', cannot determine signature type. Skipping.")
                    continue
                
                logger.debug(f"[Identify] {fragment_name}/{generator_name}: signature_type='{signature_type}', signature_len={len(signature)}")
                
                attempted_resolvers = []
                
                # Phase 1: Identity resolution
                identity_resolvers = registry.get_applicable_resolvers(signature_type, as_similarity=False)
                
                for resolver in identity_resolvers:
                    if not resolver.is_applicable(signature, signature_type, as_similarity=False):
                        continue
                    
                    attempted_resolvers.append(resolver.name)
                    
                    try:
                        result = resolver.resolve(
                            signature=signature,
                            as_similarity=False,
                            working_directory="",
                            cache=cache
                        )
                        
                        if result:
                            resolver_data = {
                                "signature": signature,
                                "hit_type": "identity",
                                "hits": result,
                                "ident_type": resolver.identifier_type,
                                "signature_type": signature_type
                            }
                            metadata = resolver.get_last_resolution_metadata()
                            if metadata is not None:
                                resolver_data["hits_metadata"] = metadata
                            results[f"identifiers/{fragment_name}/{generator_name}/{resolver.name}"] = resolver_data
                    except Exception as e:
                        errors.append({"resolver": resolver.name, "generator": generator_name, "error": str(e)})
                        continue
                
                # Phase 2: Similarity resolution
                similarity_resolvers = registry.get_applicable_resolvers(signature_type, as_similarity=True)
                
                for resolver in similarity_resolvers:
                    if not resolver.is_applicable(signature, signature_type, as_similarity=True):
                        continue
                    
                    attempted_resolvers.append(resolver.name)
                    
                    try:
                        result = resolver.resolve(
                            signature=signature,
                            as_similarity=True,
                            working_directory="",
                            cache=cache
                        )
                        
                        if result:
                            resolver_data = {
                                "signature": signature,
                                "hit_type": "similarity",
                                "hits": result,
                                "ident_type": resolver.identifier_type,
                                "signature_type": signature_type
                            }
                            metadata = resolver.get_last_resolution_metadata()
                            if metadata is not None:
                                resolver_data["hits_metadata"] = metadata
                            results[f"identifiers/{fragment_name}/{generator_name}/{resolver.name}"] = resolver_data
                    except Exception as e:
                        errors.append({"resolver": resolver.name, "generator": generator_name, "error": str(e)})
                        continue
                
                # Record attempted
                if attempted_resolvers:
                    results[attempted_path] = attempted_resolvers
                    
            except Exception as e:
                errors.append({"generator": generator_name, "error": str(e)})
                continue
        
        return {"fragment_name": fragment_name, "results": results, "errors": errors}
        
    except Exception as e:
        return {"fragment_name": "unknown", "results": {}, "errors": [{"error": str(e)}]}


def _verify_results_worker(item: tuple) -> dict[str, Any]:
    """Worker function for parallel verification.
    
    Args:
        item: Tuple of (segment, segment_identifiers_data, config_dict, segment_signatures_data).
              segment_identifiers_data is the data under identifiers/{segment}/.
              segment_signatures_data is the data under signatures/{segment}/ (or None).
              
    Returns:
        Dict with segment name, verified_hits list, and errors.
        Never returns None - errors are collected in the 'errors' field.
    """
    try:
        from ..config.loader import RunConfig
        from ..verification.manager import VerificationManager
        from ..results.results_manager import ResultsManager
        import tempfile
        import os

        segment, segment_identifiers_data, config_dict, segment_signatures_data = item
        deadline_epoch = config_dict.pop("_stage_deadline_epoch", None) if isinstance(config_dict, dict) else None
        config = RunConfig.from_dict(config_dict)

        # Create a temporary ResultsManager for this worker
        # This is needed because VerificationManager expects ResultsManager
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            temp_path = f.name
            # Initialize with valid JSON structure
            json.dump({"pipeline_name": "verification_worker", "data": {}}, f)
        
        errors = []
        try:
            # Create minimal results manager with just this segment's identifiers
            temp_manager = ResultsManager(temp_path, pipeline_name="verification_worker")
            
            # Set up the identifiers data for this segment
            if segment_identifiers_data:
                for key, value in segment_identifiers_data.items():
                    temp_manager.set_data(f"identifiers/{segment}/{key}", value)
            
            # Set up the signatures data for this segment (needed for chemical verification gates)
            if segment_signatures_data:
                temp_manager.set_data(f'signatures/{segment}', segment_signatures_data)
            
            # Create VerificationManager and run verification
            manager = VerificationManager(config)
            manager.verify_all(temp_manager, deadline_epoch=deadline_epoch)
            
            # Extract verified hits
            verified_hits = temp_manager.get_data(f"verification/{segment}/verified_hits", [])
            
            return {
                "segment": segment,
                "verified_hits": verified_hits,
                "errors": errors,
            }
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            # Also clean up WAL/SHM files if they exist
            for suffix in ['-wal', '-shm']:
                wal_path = temp_path + suffix
                if os.path.exists(wal_path):
                    os.unlink(wal_path)
                    
    except Exception as e:
        return {"segment": "unknown", "verified_hits": [], "errors": [{"error": str(e)}]}
