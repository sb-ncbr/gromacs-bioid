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


#: GitHub #17: _atom_site columns of the fallback writer, in row order.
#: The original ten columns keep their positions (identification/resolvers/
#: mmcif.py reads the residue name as the 4th token).
_ATOM_SITE_COLUMNS = (
    "group_PDB", "id", "label_atom_id", "label_comp_id", "label_asym_id",
    "label_seq_id", "Cartn_x", "Cartn_y", "Cartn_z", "type_symbol",
    "label_alt_id", "pdbx_PDB_ins_code", "occupancy", "B_iso_or_equiv",
    "auth_seq_id", "auth_comp_id", "auth_asym_id", "auth_atom_id",
    "pdbx_PDB_model_num",
)


def _cif_value(value) -> str:
    """One whitespace-free CIF token; '?' for an empty value (an empty field
    used to shift every later column of the row)."""
    text = "".join(str(value).split())
    return text or "?"


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
        except Exception:
            # Real AtomGroup missing write(), or MockAtomGroup without write() in stale deployment
            # Also catches ValueError/RuntimeError when MDAnalysis writer is not found
            return self._generate_mmcif_fallback(fragment, tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def _generate_mmcif_fallback(self, fragment: AtomGroup, tmp_path: str) -> str:
        """Generate mmCIF directly from atom attributes when write() is unavailable."""
        lines = ["data_mock", ""]
        lines.append("loop_")
        # GitHub #17: the full PDBx column set. Without label_alt_id and
        # pdbx_PDB_model_num gemmi read the loop as 0 models / 0 atoms, so
        # every mmcif-routed hit failed TM-score verification.
        lines.extend(f"_atom_site.{c}" for c in _ATOM_SITE_COLUMNS)
        
        # B-07 (red-team 4.3): fragment.atoms.<attr> materializes an N-length
        # array per access; hoisting once turns the writer loop from O(N^2)
        # into O(N).
        _names = fragment.atoms.names if hasattr(fragment.atoms, 'names') else None
        _resnames = fragment.atoms.resnames if hasattr(fragment.atoms, 'resnames') else None
        _segids = fragment.atoms.segids if hasattr(fragment.atoms, 'segids') else None
        _resids = fragment.atoms.resids if hasattr(fragment.atoms, 'resids') else None
        _positions = fragment.atoms.positions if hasattr(fragment.atoms, 'positions') else None
        _elements = fragment.atoms.elements if hasattr(fragment.atoms, 'elements') else None
        for i in range(fragment.n_atoms):
            atom_name = _names[i] if _names is not None and i < len(_names) else f"AT{i}"
            resname = _resnames[i] if _resnames is not None and i < len(_resnames) else "UNK"
            segid = _segids[i] if _segids is not None and i < len(_segids) else "A"
            resid = _resids[i] if _resids is not None and i < len(_resids) else 1
            pos = _positions[i] if _positions is not None and i < len(_positions) else [0.0, 0.0, 0.0]
            element = _elements[i] if _elements is not None and i < len(_elements) else ""
            
            name, comp, asym = _cif_value(atom_name), _cif_value(resname), _cif_value(segid)
            seq = _cif_value(resid)
            lines.append(
                f"ATOM {i+1} {name} {comp} {asym} {seq} "
                f"{pos[0]:.3f} {pos[1]:.3f} {pos[2]:.3f} {_cif_value(element)} "
                f". ? 1.00 0.00 {seq} {comp} {asym} {name} 1")
        lines.append("#")
        
        mmcif_content = "\n".join(lines)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(mmcif_content)
        with open(tmp_path, "r", encoding="utf-8") as f:
            return f.read()
