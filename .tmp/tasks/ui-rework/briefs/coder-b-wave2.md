# CODER B — WAVE 2: Run-results integration (data hooks, assembly, Mol*)  [model: qwen3.8-flash-next; Mol* parts: care]
PRECONDITION: B-wave1 merged (features/results components + utils exist, tests green). READ: CONTEXT.md, PLAN WS3/WS4 gate notes, errors/error-catalog.json.

## Deliverables (ui/src/, commits per group)
1. `features/results/hooks.ts` (commit `ui: results data hooks`) — TanStack Query hooks w/ ADAPTIVE polling (kills 3s×5 storm):
   - useRunStatus(runId): refetchInterval 2500 while pipeline.status in (pending, running, queued), false at terminal (success/failed); staleTime 2000.
   - useRunMolecules/Loading: refetch only while status not terminal; useRunSignatures/Identifiers/Verification: enabled only when their stage exists in status.tasks (fetch-once when stage appears, then while running; don't poll after terminal).
   - useRunQueue(runId): enabled only while pipeline pending.
   - Types from lib/api/types (generated components schemas), no `any`.
2. Assemble `pages/RunResultsPage.tsx` (commit `ui: results page assembly`):
   - Title: run_name from list/summary (fallback: first 8 of runId); TaskBar on top; click group → tab=warnings + anchor `#warn-<group>`.
   - Layout grid: Mol* viewer LEFT (span 7/12), MoleculeSelector ABOVE viewer, ResultsPanel RIGHT (span 5/12) per PLAN wireframe.
   - Queued state: banner with queue position from useRunQueue.
   - Keep URL segment/tab state synced (lib/nav helpers) — selector + tabs update query params (replace, not push).
   - Tabs wired: Overview (run meta + task durations from status), Input&Files, Signatures, Identifiers, Verification, Warnings. Tab contents below as Deliverable 4; where B-wave1 components exist use them; placeholder DS Skeleton otherwise — but Warnings must be real (Deliverable 3).
3. `features/results/WarningsPanel.tsx` + copy binding (commit `ui: warnings panel`):
   - Group statusData.warnings + critical_errors by stage via catalog stages; render DS Alert list per group with user_title (bold), user_what, user_action when present; interpolate {details} from warning.details (bond_count etc.); id anchors `warn-<group>`; raw code in muted caption; severity: critical→red Alert, warning→amber, info→blue/neutral. Unknown codes: friendly fallback title (Title Case of code) + message + "details on hover".
4. Tab panels (commit `ui: results tabs`): Overview (meta + task duration list only), Input&Files (loading strategy card + attempts ✓/✗; INPUT files highlighted section (pipeline.input_files keys merged w/ files list); key outputs row: results.json (DS Button, downloads via /files JSON), logs normal/debug (icon links to /api/v1/runs/{id}/logs?type=), config.ini if exists; full file list in DS Accordion/Collapsible), Signatures (segment select; grouped buttons w/ human names from utils; attempted-missing generators dashed disabled w/ failure ⓘ from attempted_generators; SignatureDialog on click), Identifiers (segment select; hits table hiding all-null metric columns per resolver type; ⓘ hover card w/ provenance; attempted/failed resolvers chips block w/ failure reason tooltips), Verification (full hits table: verified ✓/✗ col, name (truncated+tooltip), identifier link, type, similarity, confidence; stored order verbatim; rejection_reason ⓘ; TSV+JSON export buttons from utils/export.ts).
5. Mol* integration `features/results/MolstarViewer.tsx` (commit `ui: molstar viewer`) — port legacy MVS logic INTO single-plugin lifecycle: create plugin once (ref), loadMVS with replaceExisting+keepCamera per segment change; per-segment component build from molecules payload types (protein→cartoon else ball_and_stick, unselected opacity .15 — reuse MoleculeSummary segment_meta types, NO per-segment verification prefetch); load watchdog: Promise.race 25s → fallback <img src=/files/{id}/render/system.png> w/ caption "Static rendering (interactive view unavailable)"; if /render lacks system_mmcif AND png 404s → gray box text "Structural data not available". Dispose plugin on unmount.
6. Frontpage interim link: stub Frontpage add "View demo results" links to fixture run ids only if trivial; else skip (frontpage wave is separate).

## Gate
typecheck ✓ test ✓ build ✓ (planner deploys + runs 4-run visual matrix; fix-forward any planner findings)
