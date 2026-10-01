# FIX-FORWARD B1 — visual-pass findings (model: qwen3.8-27b)
READ: .tmp/tasks/ui-rework/CONTEXT.md, .tmp/tasks/ui-rework/errors/error-catalog.json (v2 - source of truth), PLAN WS3/WS4. Commit per numbered group ('ui: ...' / 'api: ...'), stage only own files, never push, never git add -A. Verification run for all UI checks: 01db1e2e-27d1-47d6-9864-023a008b0e79 (gromacs, seg_0..4, types protein/lipid/small_molecule/ion) + bce4a0fa (rich links) + a524e039 (degraded resolvers).

## G1 Run header (RunResultsPage) `ui: run header fallback + full uuid`
- Title: run_name if set, else literal "Annotation results". Below title: FULL run uuid in gray mono (no truncation), plus small copy-to-clipboard button w/ feedback.

## G2 TaskBar dominance `ui: taskbar prominence`
- Icon size up (to ~2rem area), step labels text-sm font-medium, active-severity ring; keep 5 groups + tooltips. Modest, clean, DS-consistent.

## G3 Mol* context view `ui: molstar context highlight + element colors`
CURRENT BUG: shows only selected segment (no context). REQUIRED:
- Always load the SYSTEM mmcif (/render system_mmcif) regardless of selection.
- Build one component PER segment from molecules segment_meta; type rule: protein->cartoon, others->ball_and_stick (as before).
- Colors: DS default/element coloring (molstar_use_default_coloring as legacy) for all — "colorful atoms".
- Opacity: selected segment 1.0; ALL others 0.02 (nearly invisible context, not 0.15). SYSTEM selected: everything 1.0.
- keepCamera: true on segment switches; keep single-plugin lifecycle + 25s watchdog -> static PNG -> gray "Structural data not available".

## G4 Database links (API additive + UI mirror) `api: swissprot+inchikey database_url` then `ui: link coverage`
- src_new/api/utils.py build_database_url (and any normalization helper used by identifiers/verification builders): SWISSPROT_ID -> https://www.uniprot.org/uniprotkb/<ID> ; INCHIKEY -> https://pubchem.ncbi.nlm.nih.gov/#query=<INCHIKEY> (URL-encoded). Extend unit tests (tests/src_new/api): both mappings + existing PDB/CHEMBL unaffected. Regenerate openapi from app.openapi() and diff vs contracts/openapi-live-baseline.json: additions-only (schema unchanged).
- ui/src/features/results/utils/links.ts: same two mappings client-side (mirror; fallback when server url missing) + tests.

## G5 Input & Files tab `ui: input+files correctness`
- Loading card: headline = green "Loaded successfully with {final_strategy}" when loading.success; attempts list = only attempts WITH non-empty error (render as muted "Tried {strategy}: {error}"); attempt with success:false AND error:null -> NEVER render (worker-side noise, verified on bce4a0fa + 01db1e2e).
- Input files: source = status.pipeline.input_files keys when present; ELSE derive from files list entries starting "input/" (exclude tmp*.json and nested dirs beyond input/). Render prominent "Uploaded input" zone at top with download icon per file (href /files/{runId}/{path}, download attr).
- All-files list: add per-row download icon button (currently missing).

## G6 Warnings v2 (bind catalog v2) `ui: warnings v2 - info demotion + resolver humanization`
- Sync ui error-catalog.ts to errors/error-catalog.json v2: signature_generator_failed => kind info, new title/what; identifier_resolver_failed => new copy w/ {resolver_human} + {reason_human}, 21-name resolver map, interpolation rules (parse '{resolver} ({generator}): {error}'; reason via raw_error_map substring match incl 'timed out' & 'file is not a database'; fallback 'did not finish').
- WarningsPanel: info-kind entries render neutral gray/blue, collapsed BELOW warnings (own "Information" section, NOT mixed with attention items). Resolver entries show resolver_human in title & what; add expandable "technical detail" (chevron) per entry with SANITIZED raw message (strip any /app/... filesystem paths). Never render internal paths.
- Add/adjust vitest coverage for interpolation + sanitization.

## GATE
npm run typecheck + npm test + npm run lint + npm run build (UI) AND repo venv pytest tests/src_new/api -q (only new+non-preexisting failures matter; the 2 known pre-existing failures in test_api.py are documented - don't chase them). Print Coder result format w/ per-group commit ids.
