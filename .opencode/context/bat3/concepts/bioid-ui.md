# BioID Web UI (post-rework)

## Core Concept
Production web frontend for BAT3 identification runs. Full rewrite (2026-10-01, git tag `ui-production-v1`): Vite 6 + React 19 + TS strict + Tailwind v4 + `@e-infra/design-system@0.1.9` (pinned) + custom BioID-green theme. Lives in `ui/`.

## Key Points
- Prod architecture/ops/rollback: `docs/BIOID_UI.md` (read this FIRST for any UI work).
- API doctrine: additive-only on `src_new/api`; UI consumes only `/api/v1/*` + static `/files/*`; openapi additions-only diff gate per API wave (baselines in `.tmp/tasks/ui-rework/contracts/`).
- Verification hit ordering is backend-owned (fidelity-first, `verification/manager.py`); UI renders stored order verbatim — NEVER resort client-side.
- Warning/error copy driven by `.tmp/tasks/ui-rework/errors/error-catalog.json` (16 codes, 5 stage groups, 21 resolver human names, sanitization rules) → mirrored in `ui/src/features/results/error-catalog.ts`.
- Polling: adaptive TanStack Query only; terminal states stop refetch; per-stage enablement.
- Deep-linkable state: `/runs/:id?segment=X&tab=Y` (+ `#warn-<group>` anchors from TaskBar).
- Mol*: single plugin instance, system-context rendering (selected 1.0 / others 0.02, element coloring), 25s watchdog → static PNG → gray "Structural data not available".
- Reference validation runs (4): a524e039 (pdb, degraded resolvers), bce4a0fa (gromacs rich), 787bb198 (POPC lipid), 4964c437 (failed).

## Gotchas / Landmines
- `.gitignore` python `lib/` pattern silently ignored `ui/src/lib` — negations appended; verify `git ls-tree` after scaffolds.
- DS `custom_setup.css` (`@layer`) cannot beat `setup.css` unlayered `:root` purple — override unlayered (`html[data-theme="custom"]`).
- Deploys: worktree builds only, `pipefail` chains, `docker image inspect` preflight, rollout-timeout ⇒ rollback.
- Agent ops: long CLI sessions die after ~15–60 min; per-deliverable commits + disk salvage recover losslessly; qwen3.8-27b reliable, qwen3.8-flash-next stalled on long briefs.
- Height-constraining siblings in grids: flex h-full alone is circular — use absolute-inset-0 decoupling (P2-5). ResultsPanel uses it on xl.
- Compact table pattern (w10): Name cell = database link, identifier revealed on hover tooltip (fewer columns, same information).

## Reference
- `.tmp/tasks/ui-rework/` — PLAN.md, CONTEXT.md, briefs/, deploys.md, SESSION-RESUME.md
- `ui-legacy-pre-rework` git tag — old UI snapshot
