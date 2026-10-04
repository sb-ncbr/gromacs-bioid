"""Canonical signature-type mapping.

Single source of truth for generator-name -> signature-type mapping (F-18).
Previously maintained as three byte-identical copies in
``identification/resolution_manager.py``, ``pipeline_steps/workers.py`` and
``verification/dedup.py`` — any generator addition had to land in three places.
Import from here only.
"""

from __future__ import annotations

CANONICAL_SIGNATURE_TYPES: dict[str, str] = {
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
