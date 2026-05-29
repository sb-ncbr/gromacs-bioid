"""3Di signature generator using mini3di."""

from __future__ import annotations

import logging

import numpy as np
from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse, SegmentProperty
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class ThreeDiGenerator(SignatureGenerator):
    """3Di sequence generator using mini3di."""
    
    name = "tdi"
    signature_type = "3di_sequence"
    
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
        
        # Need IS_PROTEIN flag
        if not props.flags.get(SegmentProperty.IS_PROTEIN.value, False):
            return False
        
        # Need positions
        if not props.flags.get(SegmentProperty.HAS_POSITIONS.value, False):
            return False
        
        # Need at least 2 residues
        if len(fragment.residues) < 2:
            return False
        
        return True
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        try:
            import mini3di
        except ImportError:
            logger.warning("mini3di not available, skipping 3Di generation")
            return ""
        
        # Extract coordinates for N, CA, C, CB per residue
        n_coords = []
        ca_coords = []
        c_coords = []
        cb_coords = []
        
        nan_array = np.full(3, np.nan)
        
        for residue in fragment.residues:
            res_atoms = residue.atoms
            
            # Find N, CA, C, CB atoms
            n_pos = nan_array
            ca_pos = nan_array
            c_pos = nan_array
            cb_pos = nan_array
            
            for atom in res_atoms:
                name = atom.name.strip()
                if name == 'N':
                    n_pos = atom.position.copy()
                elif name == 'CA':
                    ca_pos = atom.position.copy()
                elif name == 'C':
                    c_pos = atom.position.copy()
                elif name == 'CB':
                    cb_pos = atom.position.copy()
            
            # For Glycine, CB is missing - use nan
            if residue.resname.upper() == 'GLY' and np.all(cb_pos == nan_array):
                cb_pos = nan_array
            
            n_coords.append(n_pos)
            ca_coords.append(ca_pos)
            c_coords.append(c_pos)
            cb_coords.append(cb_pos)
        
        # Convert to numpy arrays
        n_coords = np.array(n_coords, dtype=np.float32)
        ca_coords = np.array(ca_coords, dtype=np.float32)
        c_coords = np.array(c_coords, dtype=np.float32)
        cb_coords = np.array(cb_coords, dtype=np.float32)
        
        # Encode using mini3di
        encoder = mini3di.Encoder()
        try:
            result = encoder.encode_atoms(n_coords, ca_coords, c_coords, cb_coords)
            return result.lower()
        except Exception as exc:
            logger.warning(f"mini3di encoding failed: {exc}")
            return ""
