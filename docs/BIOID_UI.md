# BioID Web UI — Architecture & Operations (as of ui-production-v1, 2026-10-01)

## Stack
`ui/` — Vite 6 · React 19 · TypeScript (strict) · Tailwind CSS v4 · `@e-infra/design-system@0.1.9` (pinned) with a custom BioID-green theme (unlayered `html[data-theme="custom"]` token override in `ui/src/index.css` — the DS default `:root` theme is unlayered and would otherwise win; see Landmines) · react-router v7 · TanStack Query · react-dropzone · Mol\* 4.18 (MVS viewer).

## Layout & flows
- `/` Frontpage: upload (dropzone + optional run name + Fast Mode + advanced config dialog), **IP-bound recent annotations** (`GET /api/v1/runs?mine=1`), per-run rerun/delete.
- `/runs/:runId` results; state is deep-linkable via `?segment` + `?tab` query params.
  Header: run_name or "Annotation results" + full gray uuid + copy button.
  Below: TaskBar (5 stage groups from `error-catalog.json`, click → warnings anchor), molecule selector (typed icons), Mol\* viewer (system context: selected segment opacity 1.0, others 0.02, element coloring; single plugin instance; 25 s watchdog → static PNG → gray "Structural data not available"), results panel (verification hits in **server stored order — never re-sorted client-side**; Name cell links to database, hover reveals raw identifier; panel height bound to left column via `xl:absolute xl:inset-0` in a stretched grid cell — selector+viewer drive row height, table scrolls inside; mobile falls back to 420px cap).
  Tabs: Overview · Input & Files (loading truthfulness rules, `input/` fallback, per-file downloads) · Signatures (human names, attempted/failed generators, blurred detail dialog) · Identifiers (clean table, provenance hovers, attempted/failed resolvers) · Verification (export JSON/TSV) · Warnings & Errors.

## Data & API doctrine
- API surface: FastAPI `src_new.api.main:app`. UI talks **only** to `/api/v1/*` + the static `/files/*` mount. Legacy root paths on the public host serve the SPA (React routes) by design.
- Additive-only rule: never change existing endpoints' semantics; versioned additions under `/api/v1`. Contract baselines live in `.tmp/tasks/ui-rework/contracts/` (diff = additions-only before any API deploy).
- Polling: adaptive via TanStack Query (`ui/src/features/results/hooks.ts`) — refetch only while pipeline non-terminal; per-stage enablement; no fixed-interval storms.
- Warning/error copy: `.tmp/tasks/ui-rework/errors/error-catalog.json` is the **planner-owned source of truth** (codes, severity, stage groups, resolver human names, interpolation + sanitization rules); UI mirrors it in `ui/src/features/results/error-catalog.ts`.
- Verification ranking is backend-owned (`verification/manager.py`, fidelity-first). UI renders stored order verbatim.

## Deployment (ceitec-biodata-ns)
- Images: `cerit.io/tomsko/bat3-frontend` (UI, from `Dockerfile.frontend`, nginx-unprivileged:8081) and `cerit.io/tomsko/bat3-api` (API, `Dockerfile.api`).
- Build ONLY from a clean git worktree (`git worktree add /tmp/opencode/deploy-wN <commit>`). Dirty-tree builds pulled in uncommitted work before; `.gitignore` collisions hid `ui/src/lib` before the fix (see Landmines).
- Deploy chain must use `set -o pipefail` and verify `docker image inspect` before `kubectl set image`. Rollouts: watch `kubectl rollout status`; on timeout roll back immediately.
- Rollback: images `bat3-frontend:legacy-pre-rework` (old UI), `bat3-api:ui1` (old API); git tags `ui-rework-w1..w8`, `ui-production-v1`; YAMLs in `.tmp/tasks/ui-rework/backups/`.
- Ingress: `/api /files /health /docs /openapi.json` → api service; `/` → web (SPA). Editing rules in `bat3-chart/templates/ingress.yaml`.

## Landmines (learned the hard way)
1. Python-era `.gitignore` pattern `lib/` also matched `ui/src/lib/` — files silently untracked while typecheck passed on disk. Negations appended in `.gitignore`; always verify `git ls-tree` after big scaffolds.
2. DS theming: `setup.css` declares its purple default at **unlayered** `:root`; `custom_setup.css` is `@layer`-wrapped and loses. Override unlayered with higher-specificity selectors.
3. Masked exit codes (`cmd | tail`) in deploy chains once rolled out a nonexistent image tag → brief outage. `pipefail` + image preflight now mandatory.
4. Legacy repo history tracked `ui/node_modules` + `dist`; index was purged (history bloat remains; filter-repo is way-later).

## Where things live
`.tmp/tasks/ui-rework/` — PLAN.md (workstreams, backlog), CONTEXT.md (coder bundle), errors/, contracts/, fixtures/ (live snapshots), backups/, deploys.md (append-only deploy + incident log), briefs/ (coder briefs), SESSION-RESUME.md.
