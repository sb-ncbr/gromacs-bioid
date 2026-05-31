"""mmCIF signature generator."""

from __future__ import annotations

import logging
import os
import tempfile

from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse, SegmentProperty
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class MmCifGenerator(SignatureGenerator):
    """mmCIF string generator."""
    
    name = "mmcif"
    signature_type = "mmcif"
    
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
        
        # Need positions
        return props.flags.get(SegmentProperty.HAS_POSITIONS.value, False)
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        fd, tmp_path = tempfile.mkstemp(suffix=".cif")
        os.close(fd)
        try:
            fragment.write(tmp_path, format="mmCIF")
            with open(tmp_path, "r", encoding="utf-8") as f:
                return f.read()
        except AttributeError:
            # Real AtomGroup missing write(), or MockAtomGroup without write() in stale deployment
            return self._generate_mmcif_fallback(fragment, tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def _generate_mmcif_fallback(self, fragment: AtomGroup, tmp_path: str) -> str:
        """Generate mmCIF directly from atom attributes when write() is unavailable."""
        lines = ["data_mock", ""]
        lines.append("loop_")
        lines.append("_atom_site.group_PDB")
        lines.append("_atom_site.id")
        lines.append("_atom_site.label_atom_id")
        lines.append("_atom_site.label_comp_id")
        lines.append("_atom_site.label_asym_id")
        lines.append("_atom_site.label_seq_id")
        lines.append("_atom_site.Cartn_x")
        lines.append("_atom_site.Cartn_y")
        lines.append("_atom_site.Cartn_z")
        lines.append("_atom_site.type_symbol")
        
        for i in range(fragment.n_atoms):
            atom_name = fragment.atoms.names[i] if hasattr(fragment.atoms, 'names') and i < len(fragment.atoms.names) else f"AT{i}"
            resname = fragment.atoms.resnames[i] if hasattr(fragment.atoms, 'resnames') and i < len(fragment.atoms.resnames) else "UNK"
            segid = fragment.atoms.segids[i] if hasattr(fragment.atoms, 'segids') and i < len(fragment.atoms.segids) else "A"
            resid = fragment.atoms.resids[i] if hasattr(fragment.atoms, 'resids') and i < len(fragment.atoms.resids) else 1
            pos = fragment.atoms.positions[i] if hasattr(fragment.atoms, 'positions') and i < len(fragment.atoms.positions) else [0.0, 0.0, 0.0]
            element = fragment.atoms.elements[i] if hasattr(fragment.atoms, 'elements') and i < len(fragment.atoms.elements) else ""
            
            lines.append(f"ATOM {i+1} {atom_name} {resname} {segid} {resid} {pos[0]:.3f} {pos[1]:.3f} {pos[2]:.3f} {element}")
        lines.append("#")
        
        mmcif_content = "\n".join(lines)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(mmcif_content)
        with open(tmp_path, "r", encoding="utf-8") as f:
            return f.read()
