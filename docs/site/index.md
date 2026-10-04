# BAT3 / BioID Validation Pipeline

BAT3 identifies the molecular contents of molecular-dynamics (MD) simulations —
proteins, nucleic acids, small molecules, ions, lipids, glycans — and **validates**
those identifications against ground-truth annotations (MDDBR) at campaign scale.

In one sentence per stage:

1. **Load** simulation inputs (topology + trajectory), repair and normalize them.
2. **Segment** the system into per-molecule fragments (with strand-aware splitting
   for mixed/multi-component assemblies).
3. **Generate signatures** per fragment: sequences (FASTA), structures (PDB/mmCIF),
   SMILES/InChI/fingerprints, formulas, names, element counts.
4. **Resolve identifiers** by querying local and remote databases with those
   signatures (BLAST, RCSB, PubChem/ChEMBL/ChEBI/IDSM, AlphaFind, Foldseek, CCD).
5. **Verify** candidates by re-fetching canonical data and scoring agreement,
   producing a ranked, deduplicated hit table per fragment.
6. **Report** standardized `results.json` per entry plus campaign-wide statistics.

## Current trust level (campaign v12, 2026-10-04)

14,624 simulation entries processed. Headline similarity-validation metrics
(hit@10, verified):

| Ground truth family | verified hit@10 |
|---|---|
| InChIKey (chemicals, frozen window 5,768 attempted) | **92.9% exact** (window held v11→v12) |
| PDB annotations | 99.5% pct / 11,130 of 11,181 abs |
| UniProt annotations | 98.2% |
| Any-molecule @10 | 99.5% |
| Nucleic acids (post-N1 wave) | 1.89% → **19.75%** (413/2,091 hit; 412 verified) |

Chemical residual: 410 candidate rows under continuous coverability watch;
zero drift v11→v12.

## Quickstart

- **Run one validation** → [Running validations](running-a-validation.md)
- **Understand the stack** → [Architecture](architecture.md)
- **Interpret a results.json** → [Identification & verification](identifiers.md)
- **Trust the numbers** → [Methodology & statistics](methodology.md)
- **Operate the fleet** → [Operations](operations.md)

!!! note "Status of this site"
    Built 2026-10-04 from a full read-only code audit (findings F-01…F-28 in
    `docs/CHEMISTRY_FIX_TODO.md`). Where behavior and intent differ, this site
    documents **behavior as verified live**, with pointers to the finding.
