# CODER B — WAVE 1: Results-domain presentational components (fixture-driven)  [model: qwen3.8-flash-next]

PRECONDITION: coder-a-wave1 merged (scaffold + generated API types exist in ui/). If not merged yet: STOP and report back.
READ FIRST: .tmp/tasks/ui-rework/CONTEXT.md (display mappings + copy rules are spec), PLAN.md WS3/WS4, errors/error-catalog.json (stage groups + user copy source). Design = @e-infra/design-system ONLY (no MUI). All components PURE (props in, events out) — no fetch; data hooks land in wave B2.

## Deliverables (ui/src/features/results/, commits per group)
1. `utils/` + vitest tests (commit `ui: results utils`):
   - `signature-names.ts` — human names + groups + extension map per CONTEXT (unknown key → Title Case fallback)
   - `links.ts` — database link builder incl. PDB `_CHAIN` strip (mirror of API fix; defensive client-side), CHEMBL prefix; unit tests from CONTEXT table
   - `verification.ts` — merge/sort: verified first → final_confidence desc → similarity desc; bestConfidence(hits); truncate helper (name >60ch → ellipsis w/ full for tooltip)
   - `export.ts` — verification hits → TSV + JSON download blob builders
2. `TaskBar.tsx` (commit `ui: taskbar`) — 5 stage groups from catalog; per-group state = worst severity of member tasks (ok=blue? NO: completed=green, running=blue pulse, warning=orange, failed=red, pending=gray); per-task tooltips (name, duration from started/finished); onClick(group) → emits group id (parent handles tab jump + anchor). Unknown task ids → append ungrouped rail, never crash.
3. `MoleculeSelector.tsx` — props: segments, segmentMeta, selected, onSelect; icon per molecule type per CONTEXT map (unknown → Shapes); option label `{segment} · {type}` + atom count, SYSTEM first w/ "Whole system".
4. `ResultsPanel.tsx` (commit `ui: results panel`) — title `Segment: {id}`; type icon chip; atoms/residues chips; best-confidence bar; verification table: ✓/✗ (+ⓘ rejection_reason tooltip; i uses DS Tooltip) · name (truncated, tooltip full; empty → identifier) · identifier (link from links.ts, external icon, target _blank) · type (muted small) · similarity % · confidence (mini bar + %); sort from utils; empty states: no hits + no failed resolvers = "No confident identifications."; no hits + failed resolvers = "Identification could not be completed — some search services were unavailable." (+link to identifiers tab via prop).
5. `SignatureDialog.tsx` — DS Dialog (blurred backdrop by design system), props: generator, signature, segment; header human name + group badge; 1-line explainer (from copy map in CONTEXT human names table); mono preview scrollable + copy button; download w/ extension map.
6. Demo harness: `src/dev/FixturesPlayground.tsx` route `/dev/results-demo` rendering all components from local copies of 2 fixture payloads (a524e039 status+molecules+verification_A; 4964c437 status) — visual check without backend. Route only in dev build.

## Gate
npm run typecheck ✓ · npm run test ✓ · npm run build ✓ · demo route shows: a524e039 panel (4 segments, degraded-resolver empty-state path for A) + failed-run TaskBar (red export group). Report any ambiguity in spec to planner, do not improvise copy.
