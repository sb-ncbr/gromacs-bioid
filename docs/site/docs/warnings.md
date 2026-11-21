# Warnings and errors

Every warning and error a run can record, by its `code`. The API gives each
one a `docs_url` pointing at its section here, and the results page links to
it. A **warning** means the run finished but something is worth knowing; an
**error** means the run stopped.

Each entry says what happened, whether the results are still usable, and what
to do.

## Not shown as warnings

Some searches do not apply to some molecules: the RCSB structure search for
a pure nucleic acid, which RCSB does not offer (`na_mode_unsupported`; runs
before 2026-11-21 also recorded it for every protein), a polymer structure
search on a small molecule (`no_polymer_payload`), a chemical search for a
SMILES with an impossible valence, such as a carbon with 17 bonds from bonds
guessed on a crowded system (`invalid_valence`), a structure search whose every
chain is above RCSB's size limit (`query_too_large`). These are skips, not failures. Runs record
them in `results.json` under `data.identification._meta.not_applicable.<segment>`
(resolver, generator, reason); they are not counted as warnings. Runs from
before 2026-11-17 stored them as `identifier_resolver_failed` warnings; the API
leaves those out of warning lists and counts.

## Warnings

### identifier_resolver_failed

**What happened:** one database search for a molecule stopped or got no
answer (timeout, HTTP error, service unavailable). The message names the
search and the reason; `details` names the segment.

**Results:** usable. Matches from the other databases are complete; matches
only that database would have found may be missing.

**What to do:** usually temporary. Rerun later if you need that database's
matches. A query the service rejected as malformed (IDSM `QueryBadFormed`,
PubChem `PUGREST.BadRequest`, ChEMBL "Problem standardizing the query
molecule") would be rejected again: it does not make the run incomplete and
is not retried automatically.

### stage_time_budget

**What happened:** a stage (fingerprints, database search or verification) hit
its time limit before finishing every molecule.

**Results:** partial. Molecules handled before the limit are complete; the
rest may have fewer matches or none.

**What to do:** rerun later, when the service is less busy, or contact us if
it keeps happening.

### structure_search_unavailable

**What happened:** structure searches against RCSB PDB could not run for this
run (the uploaded structure could not be made available to RCSB, or RCSB did
not answer).

**Results:** usable. Sequence and chemistry matches are complete; matches by
3D shape from RCSB are missing.

**What to do:** rerun later if you need structure matches.

### identification_groups_unresolved

**What happened:** some groups of identical molecules got no database
candidates at all.

**Results:** usable for the other molecules. The molecules in these groups are
shown as not identified.

**What to do:** see what BioID knows about them on the results page (formula,
SMILES, rejected candidates). Rerun with the *Thorough* preset, or tell us
what they are.

### verification_failed

**What happened:** the candidate structures for a molecule could not be
compared with it.

**Results:** usable with care. Those matches have lower confidence than usual.

**What to do:** treat these matches with caution; rerun if it matters.

### annotation_fetch_failed

**What happened:** BioID could not fetch some candidates' database records
(ChEBI, ChEMBL, UniProt or PubChem) while checking them, because the
service did not answer in time or reported an error. The message names the
service and how many records were missing.

**Results:** usable. The matches are the same, but their confidence was
computed without the record-quality part, so it can differ slightly from a
run where the records were available.

**What to do:** usually temporary. Rerun later; records fetched once are
kept, so a rerun is quick.

### signature_generator_failed

**What happened:** one chemical description (fingerprint) of a molecule could
not be computed.

**Results:** usable. Other descriptions were used for searching; exact-structure
matches are unaffected.

**What to do:** nothing.

### chemistry_skipped_size

**What happened:** a molecule was above the atom limit for chemistry
descriptions (SMILES, InChI), so they were not computed. This is normal for
proteins and large assemblies.

**Results:** usable. Sequence and structure searches still ran.

**What to do:** nothing.

### pbc_jumps_detected

**What happened:** some molecules cross the periodic box edge and were not
made whole, so they may be split into pieces.

**Results:** split molecules may be identified wrongly.

**What to do:** fix before uploading: `gmx trjconv -pbc mol`, cpptraj
`autoimage`, or VMD `pbc unwrap`.

### pbc_unwrap_applied

**What happened:** molecules crossed the box edge; BioID joined them before
identification. Your files were not changed.

**Results:** usable.

**What to do:** nothing.

### pbc_unwrap_failed

**What happened:** BioID could not make molecules whole across the box. "No
box information" means the input has no periodic box, so nothing can be split
across one; that case is not shown as a note.

**Results:** split molecules may be identified wrongly.

**What to do:** fix periodic images before uploading (`gmx trjconv -pbc mol -ur
compact`), then upload again.

### pbc_unwrap_incomplete

**What happened:** after joining molecules across the box, some bonded atoms
are still far apart.

**Results:** the affected molecules may be identified wrongly.

**What to do:** fix periodic images before uploading (see above).

### insufficient_bonds

**What happened:** few chemical bonds were found, even after BioID guessed
bonds from the coordinates (it does this whenever the input has too few,
usually a PDB file without CONECT records), so molecules may be split or merged.

**Results:** molecule boundaries may be wrong.

**What to do:** upload a topology (.tpr, .prmtop, .psf) with the coordinates.

### coords_rescaled_nm_to_angstrom

**What happened:** coordinates were in nanometres and were converted to
ångströms. Informational.

**Results:** usable.

**What to do:** nothing.

### coords_rescaled_unexpected

**What happened:** coordinates were rescaled although their units were not
clearly nanometres.

**Results:** check that the molecules look right in the 3D view.

**What to do:** if they do not, check the units and upload again.

### geometry_scale_anomalous

**What happened:** atoms are closer together or further apart than expected.

**Results:** molecule boundaries and chemistry may be wrong.

**What to do:** check the coordinate units and upload again.

### system_export_failed

**What happened:** the whole-system structure file for download and the 3D
view could not be created.

**Results:** identification results are unaffected; the 3D view may be missing.

**What to do:** nothing; rerun if you need the file.

### segment_export_failed

**What happened:** the structure file of one molecule could not be created.

**Results:** identification results are unaffected.

**What to do:** nothing.

### render

Codes `render_no_facade`, `render_pymol_unavailable`, `render_no_mmcifs`,
`render_failed`, `render_budget_exhausted`.

**What happened:** a preview image could not be created.

**Results:** usable. Only the thumbnail is affected; the 3D view is fine.

**What to do:** nothing.

## Errors (the run stopped)

### missing_input

**What happened:** no complete simulation was found in the upload.

**What to do:** upload a topology and coordinates together, e.g. .tpr + .gro,
.prmtop + .inpcrd, .psf + .pdb.

### load_failed

**What happened:** the files could not be read. `details.attempts` lists what
was tried.

**What to do:** check that atom counts match and that all .itp files are
included, or upload a .pdb of the first frame.

### worker_lost

**What happened:** the processing server stopped unexpectedly. This was a
problem on our side, not with your files.

**What to do:** rerun. If it happens twice, contact us with the run id.

### timeout

**What happened:** the run exceeded its total time limit.

**What to do:** rerun later; for very large systems, try the *Quick look*
preset.

### pipeline_child_crashed

**What happened:** the process running your analysis stopped without a
message, most often because the system needed more memory than available.

**What to do:** rerun once; if it happens again, contact us with the run id.

### internal

Codes `missing_universe`, `missing_facade`, `unhandled_exception`,
`pipeline_execution_failed`, and pre/postcondition codes (`file_missing`,
`file_empty_or_missing`, `artifact_missing`, `result_is_none`).

**What happened:** something went wrong on our side; it was not caused by your
files.

**What to do:** rerun. If it happens again, contact us with the run id.
