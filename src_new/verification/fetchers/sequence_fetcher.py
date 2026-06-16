"""Sequence signature fetcher for proteins and nucleic acids."""

from __future__ import annotations

import logging
import requests

from ..base import SignatureFetcher

logger = logging.getLogger(__name__)


class SequenceSignatureFetcher(SignatureFetcher):
    """Fetches canonical sequences for proteins and nucleic acids."""
    
    SUPPORTED_TYPES = {"PDB_ID", "UNIPROT_ID", "ALPHAFOLD_ID", "NR_ID", "SWISSPROT_ID", "NT_ID", "CORE_NT_ID"}
    
    def supports(self, ident_type: str) -> bool:
        """Check if this fetcher supports the given identifier type."""
        return ident_type in self.SUPPORTED_TYPES
    
    def fetch(self, identifier: str, ident_type: str) -> str | None:
        """Fetch the canonical sequence for a protein/nucleic acid identifier.
        
        Args:
            identifier: The identifier (e.g., "1ABC" for PDB, "P04637" for UniProt).
            ident_type: The type of identifier ("PDB_ID", "UNIPROT_ID", "ALPHAFOLD_ID", 
                       "NR_ID", "SWISSPROT_ID", "NT_ID", or "CORE_NT_ID").
            
        Returns:
            The canonical sequence string (no newlines), or None if not found or on error.
        """
        try:
            if ident_type == "PDB_ID":
                return self._fetch_pdb(identifier)
            elif ident_type == "UNIPROT_ID":
                return self._fetch_uniprot(identifier)
            elif ident_type == "ALPHAFOLD_ID":
                return self._fetch_alphafold(identifier)
            elif ident_type == "NR_ID":
                return self._fetch_ncbi_protein(identifier)
            elif ident_type == "SWISSPROT_ID":
                return self._fetch_uniprot(identifier)
            elif ident_type in ("NT_ID", "CORE_NT_ID"):
                return self._fetch_ncbi_nucleotide(identifier)
            else:
                logger.warning(f"Unknown sequence ident_type: {ident_type}")
                return None
        except Exception as e:
            logger.warning(f"SequenceSignatureFetcher fetch failed for {identifier}: {e}")
            return None
    
    def _fetch_pdb_entities(self, pdb_id: str) -> list[str]:
        """Fetch all polymer entity sequences from PDB.
        
        Args:
            pdb_id: The PDB ID (e.g., "1ABC").
            
        Returns:
            List of canonical sequences for all polymer entities.
            Empty list if no polymer entities found or on error.
        """
        # Strip _entity suffix if present
        if '_' in pdb_id:
            pdb_id = pdb_id.split('_', maxsplit=1)[0]
        
        pdb_id_lower = pdb_id.lower()
        
        # First, fetch entry info to get polymer entity IDs
        entry_url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id_lower}"
        try:
            r = requests.get(entry_url, timeout=10)
            r.raise_for_status()
            entry_data = r.json()
            
            # Extract polymer entity IDs
            container_ids = entry_data.get("rcsb_entry_container_identifiers", {})
            polymer_entity_ids = container_ids.get("polymer_entity_ids", [])
            
            if not polymer_entity_ids:
                return []
            
            sequences = []
            for entity_id in polymer_entity_ids:
                entity_url = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id_lower}/{entity_id}"
                try:
                    r_entity = requests.get(entity_url, timeout=10)
                    r_entity.raise_for_status()
                    entity_data = r_entity.json()
                    
                    seq = entity_data.get("entity_poly", {}).get("pdbx_seq_one_letter_code_can")
                    if seq:
                        seq_clean = seq.replace("\n", "")
                        if seq_clean:  # Skip empty sequences
                            sequences.append(seq_clean)
                except Exception as e:
                    logger.warning(f"PDB {pdb_id} entity {entity_id} fetch failed: {e}")
                    continue
            
            return sequences
        except Exception as e:
            logger.warning(f"PDB {pdb_id} entry fetch failed: {e}")
            return []
    
    def _fetch_pdb(self, pdb_id: str) -> str | None:
        """Fetch sequence from PDB (first polymer entity).
        
        Uses _fetch_pdb_entities internally and returns the first sequence.
        """
        sequences = self._fetch_pdb_entities(pdb_id)
        if sequences:
            return sequences[0]
        
        # Fallback to old behavior if entity list is empty
        # Strip _entity suffix if present
        if '_' in pdb_id:
            pdb_id = pdb_id.split('_', maxsplit=1)[0]
        
        url = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id.lower()}/1"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            seq = data.get("entity_poly", {}).get("pdbx_seq_one_letter_code_can")
            if seq:
                return seq.replace("\n", "")
            return None
        except Exception as e:
            logger.warning(f"PDB {pdb_id} fetch sequence failed: {e}")
            return None
    
    def _fetch_uniprot(self, uniprot_id: str) -> str | None:
        """Fetch sequence from UniProt."""
        url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.fasta"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            lines = r.text.splitlines()
            # Skip header lines (starting with '>') and join sequence lines
            seq = ''.join(line.strip() for line in lines if not line.startswith('>'))
            return seq if seq else None
        except Exception as e:
            logger.warning(f"UniProt {uniprot_id} fetch FASTA failed: {e}")
            return None
    
    def _fetch_alphafold(self, alphafold_id: str) -> str | None:
        """Fetch sequence from AlphaFold (via UniProt)."""
        try:
            # Extract UniProt ID from AlphaFold ID (format: AF-UNIPROTID-F1-model_vX)
            parts = alphafold_id.split('-')
            if len(parts) < 3 or not alphafold_id.startswith("AF-"):
                logger.warning(f"AlphaFold ID '{alphafold_id}' does not match expected format AF-UNIPROT-F1-model_vX")
                return None
            uniprot_id = parts[1]
            return self._fetch_uniprot(uniprot_id)
        except Exception as e:
            logger.warning(f"AlphaFold {alphafold_id} fetch FASTA failed: {e}")
            return None
    
    def _fetch_ncbi_protein(self, accession: str) -> str | None:
        """Fetch protein sequence from NCBI (for NR_ID).
        
        Uses NCBI E-utilities EFetch endpoint.
        """
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=protein&id={accession}&rettype=fasta"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            lines = r.text.splitlines()
            # Skip header lines (starting with '>') and join sequence lines
            seq = ''.join(line.strip() for line in lines if not line.startswith('>'))
            return seq if seq else None
        except Exception as e:
            logger.warning(f"NCBI protein {accession} fetch FASTA failed: {e}")
            return None
    
    def _fetch_ncbi_nucleotide(self, accession: str) -> str | None:
        """Fetch nucleotide sequence from NCBI (for NT_ID, CORE_NT_ID).
        
        Uses NCBI E-utilities EFetch endpoint.
        """
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={accession}&rettype=fasta"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            lines = r.text.splitlines()
            # Skip header lines (starting with '>') and join sequence lines
            seq = ''.join(line.strip() for line in lines if not line.startswith('>'))
            return seq if seq else None
        except Exception as e:
            logger.warning(f"NCBI nucleotide {accession} fetch FASTA failed: {e}")
            return None
