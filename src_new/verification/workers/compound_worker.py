"""Compound verification worker for small molecules using SMILES/Tanimoto similarity."""

from __future__ import annotations

import logging

from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem, MACCSkeys

from ..base import VerificationWorker
from ..models import VerificationScore

logger = logging.getLogger(__name__)


class CompoundVerificationWorker(VerificationWorker):
    """Verifies compound identifications using SMILES fingerprint similarity."""
    
    SUPPORTED_IDENT_TYPES = {"PUBCHEM_CID", "CHEMBL_ID", "CHEBI_ID"}
    SUPPORTED_SIGNATURE_TYPES = {"smiles", "selfies"}
    
    def is_applicable(self, signature_type: str, ident_type: str) -> bool:
        """Check if this worker can verify the given signature and identifier types."""
        return (
            signature_type.lower() in self.SUPPORTED_SIGNATURE_TYPES and
            ident_type in self.SUPPORTED_IDENT_TYPES
        )
    
    def verify(
        self,
        signature: str,
        identifier: str,
        ident_type: str,
        canonical_signature: str | None = None,
        signature_type: str | None = None,
    ) -> VerificationScore | None:
        """Verify a compound hit by comparing SMILES using multi-fingerprint similarity.
        
        Args:
            signature: The SMILES extracted from simulation.
            identifier: The compound identifier (not used directly, canonical_signature is used).
            ident_type: The type of identifier.
            canonical_signature: The canonical SMILES from database. Required.
            
        Returns:
            VerificationScore if verification was performed, None if not applicable.
        """
        # Cannot verify without canonical SMILES
        if canonical_signature is None:
            return None
        
        # Convert to RDKit molecules
        try:
            mol_sim = Chem.MolFromSmiles(signature)
            mol_canon = Chem.MolFromSmiles(canonical_signature)
            
            if mol_sim is None or mol_canon is None:
                logger.warning(f"RDKit failed to parse SMILES: sim={signature!r}, canon={canonical_signature!r}")
                return None
        except Exception as e:
            logger.warning(f"RDKit molecule parsing failed: {e}")
            return None
        
        # Compute multi-fingerprint similarity
        try:
            score = self._compute_similarity(mol_sim, mol_canon)
            if score is None:
                # All fingerprint comparisons failed
                return VerificationScore(
                    kind="similarity",
                    metric_name="multi_fingerprint_tanimoto",
                    raw_score=0.0,
                    normalized_score=0.0,
                )
            return score
        except Exception as e:
            logger.warning(f"Compound verification failed: {e}")
            return None
    
    def _compute_similarity(self, mol1: Chem.Mol, mol2: Chem.Mol) -> VerificationScore | None:
        """Compute multi-fingerprint Tanimoto/Dice similarity.
        
        Uses the same fingerprints as the original compound_worker.py:
        - rdkit (Tanimoto)
        - atompair (Dice)
        - topotorsion (Dice)
        - circular/Morgan radius=2 (Dice)
        - maccs (Tanimoto)
        
        Returns average of all successful scores × 100.0.
        """
        fingerprints = ['rdkit', 'atompair', 'topotorsion', 'circular', 'maccs']
        scores = []
        
        for fp_type in fingerprints:
            try:
                if fp_type == 'rdkit':
                    gen = AllChem.GetRDKitFPGenerator()
                    f1, f2 = gen.GetFingerprint(mol1), gen.GetFingerprint(mol2)
                    scores.append(DataStructs.TanimotoSimilarity(f1, f2))
                elif fp_type == 'atompair':
                    gen = AllChem.GetAtomPairGenerator()
                    f1, f2 = gen.GetSparseCountFingerprint(mol1), gen.GetSparseCountFingerprint(mol2)
                    scores.append(DataStructs.DiceSimilarity(f1, f2))
                elif fp_type == 'topotorsion':
                    gen = AllChem.GetTopologicalTorsionGenerator()
                    f1, f2 = gen.GetSparseCountFingerprint(mol1), gen.GetSparseCountFingerprint(mol2)
                    scores.append(DataStructs.DiceSimilarity(f1, f2))
                elif fp_type == 'circular':
                    gen = AllChem.GetMorganGenerator(radius=2)
                    f1, f2 = gen.GetSparseCountFingerprint(mol1), gen.GetSparseCountFingerprint(mol2)
                    scores.append(DataStructs.DiceSimilarity(f1, f2))
                elif fp_type == 'maccs':
                    f1, f2 = MACCSkeys.GenMACCSKeys(mol1), MACCSkeys.GenMACCSKeys(mol2)
                    scores.append(DataStructs.TanimotoSimilarity(f1, f2))
            except Exception:
                # Individual fingerprint failure is okay, skip it
                pass
        
        if not scores:
            return None
        
        avg_score = sum(scores) / len(scores)
        # Scale to 0-100, cap at 100
        normalized = min(avg_score * 100.0, 100.0)
        
        return VerificationScore(
            kind="similarity",
            metric_name="multi_fingerprint_tanimoto",
            raw_score=avg_score,
            normalized_score=normalized,
        )
