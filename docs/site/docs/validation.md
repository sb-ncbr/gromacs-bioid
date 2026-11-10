# Validation & internals

This part of the documentation is for developers and operators: how the
pipeline works, how it is configured and deployed, and how it was validated
against curated annotations. For using BioID, see
[Using BioID](index.md).

## The pipeline

BioID (codebase name BAT3, package `src_new/`) runs one pipeline per
submitted simulation, stage by stage:

1. **Load**: find the topology and coordinate files, load them with
   MDAnalysis (GROMACS, AMBER, CHARMM/NAMD, LAMMPS, PDB/mmCIF), repair missing
   elements, masses and bonds, and make molecules whole across periodic
   boundaries.
2. **Segment**: split the system into molecules; identical copies (chains,
   ligands, lipids, ions, water) are grouped and processed once.
3. **Signatures**: describe each molecule in the forms databases accept:
   sequences, structures (PDB, mmCIF, Cα model, 3Di), SMILES/SELFIES,
   InChIKey, formulas, skeleton fingerprints, lipid shorthand, glycan
   composition, names, elements.
4. **Identify**: search the [databases](databases.md) with those signatures:
   a first pass over the main databases, then a second pass over the
   supplementary and deferred ones.
5. **Verify**: re-fetch each candidate's database record, compare it with
   the molecule (sequence alignment, skeleton fingerprint, structural
   TM-score, element) and compute a 0–100 confidence; the result is a
   ranked table of verified hits per molecule.
6. **Export and render**: a whole-system mmCIF with per-molecule selectors,
   PNG renders for the web application, and `results.json`, the single
   record of the run.

Each expensive stage has a wall-clock budget; a stage that runs out records a
`stage_time_budget` warning and the run continues with what it has.

## Validation

BioID was validated on the MDDBR/MDposit repository: every deposit was run
through the pipeline and the identifications were compared with the
deposits' curated annotations (PDB and UniProt accessions, InChIKeys, ions).
How the comparison is scored is described in
[Methodology & statistics](methodology.md).

### Current figures: campaign g1 (2026-11-07)

15,094 of 15,133 MDposit deposits processed end to end (99.7 %). Share of
curated annotations matched by a **verified** BioID hit at rank 1 / within
the top 5 / within the top 10 (verified-only rescore, S7 script):

| Annotation type | n | @1 | @5 | @10 |
|---|---|---|---|---|
| PDB | 12,448 | 98.3 % | 99.6 % | 99.6 % |
| UniProt | 14,695 | 94.3 % | 97.7 % | 98.4 % |
| Small molecule (InChIKey) | 6,735 | 94.9 % | 95.3 % | 95.3 % |
| Ion | 2,849 | 98.9 % | 98.9 % | 98.9 % |
| Deposit (any annotation) | — | 99.6 % | 99.9 % | 99.9 % |

Molecule funnel: 25,876 molecules → 25,092 with a database candidate
(97.0 %) → 24,824 verified (95.9 %). Per class: proteins 100 % verified,
small molecules 96.6 %, lipids 83.6 %, nucleic acids 39.7 %, ions and water
100 %.

These are the numbers of the manuscript in preparation; their source
artifacts are listed in the project's publication notes. The campaign ran the
code of commits `9004f72d0` … `497395c0c` with its own campaign
configuration; it predates the supplementary databases, the deferred
resolvers and the run presets (2026-11-09/10), which these figures do not
cover.

!!! note "History"
    Earlier campaigns used other scoring windows and are not directly
    comparable: v12 (2026-10-04, 14,624 entries; verified hit@10 InChIKey
    92.9 %, PDB 99.5 %, UniProt 98.2 %, nucleic acids 19.75 %) and v14
    (2026-10-09). The audit findings F-01…F-28 that this site's first version
    (2026-10-04) was built from are pinned in `docs/CHEMISTRY_FIX_TODO.md`;
    those still relevant are cited by number on the pages that follow.

## Where to go next

- **Databases searched** → [Databases](databases.md)
- **Run a campaign, read a results.json** → [Running validations](running-a-validation.md)
- **Components and data flow** → [Architecture](architecture.md)
- **HTTP surfaces** → [API](api.md)
- **How a molecule becomes a verified hit** → [Identification & verification](identifiers.md)
- **Settings** → [Configuration](configuration.md)
- **How the numbers are produced** → [Methodology & statistics](methodology.md)
- **Deploying and running the service** → [Operations](operations.md)
- **Working on the code** → [Developers](developers.md)
