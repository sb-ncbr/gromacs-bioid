# CODER A — WAVE 1: Scaffold, shell, API client, tooling  [model: qwen3.8-27b]

READ FIRST: /home/tomsko/work/bat3/.tmp/tasks/ui-rework/CONTEXT.md and PLAN.md. Legacy reference (patterns to salvage, not copy verbatim): git show ui-legacy-pre-rework:ui/src/... especially MDComponents/MDViewer.tsx MVS usage.

## Goal
Replace `ui/` with a fresh production-grade app scaffold that builds, deploys via existing Dockerfile.frontend path, and renders DS shell on both routes with stub pages. NO feature components yet (Coder B builds those against fixtures after you land).

## Deliverables
1. ui/ fresh: Vite 6 + React 19 + TS strict; Tailwind v4 wired per DS README (`@import "tailwindcss"; @import "@e-infra/design-system/setup.css"; @source "../node_modules/@e-infra/design-system/dist"`), `@e-infra/design-system@0.1.9` EXACT pin; custom 3-color theme, primary #2E7D32 (custom_setup.css mechanism); lucide-react; react-router-dom v7; @tanstack/react-query; react-dropzone; molstar@^4.18 (keep vite manualChunks vendor-molstar + optimizeDeps like legacy vite.config).
2. `src/lib/api/client.ts`: typed fetch wrapper (base `/api/v1`, legacy `/` fallback const), error normalization; `src/lib/api/types.ts` generated via `openapi-typescript` from contracts/openapi-live-baseline.json (script `gen:api` reading ./.tmp/tasks/ui-rework/contracts/openapi-live-baseline.json first arg, URL override allowed); TS must compile with zero `any` in client.
3. Router + deep-link helpers: `/`, `/runs/:runId` with `segment`/`tab` query helpers in `src/lib/nav.ts`. Stub pages: Frontpage (shell + "under construction" DS Card), RunResults (shell + run id display).
4. Shell: Header (BioID title w/ green accent, mail link only — no GitHub/Manual/Docs links (no docs exist yet; way-later TODO)), Footer preserving ELIXIR legal copy from legacy Footer.tsx verbatim (asset: reuse legacy elixirlogo.png path — copy asset from git tag), Layout w/ responsive container.
5. Tooling: eslint + prettier configs, vitest configured (jsdom), npm scripts dev/build/test/lint/typecheck. TS strict passes.
6. Dockerfile.frontend: keep 2-stage node:22 build → nginx-unprivileged :8081; update only if paths change. deploy/nginx-frontend.conf: keep legacy proxy locations AND ADD `/api` location proxying to `bat3-ceitec-bat3-api:8000` (prep for WS7; SPA fallback must exclude /api).
7. `ui/README.md`: 20 lines max — stack, scripts, how to regen API types.

## Out of scope
Pages/tabs/panels/components beyond stubs, API python changes, ingress changes, deploy to cluster.

## Validation (must all pass; report outputs)
- cd ui && npm ci && npm run typecheck && npm run lint && npm run build → clean
- npm run dev: DS Button/Card render, both routes load, theme primary is #2E7D32 (screenshot or describe)
- docker build -f Dockerfile.frontend -t cerit.io/tomsko/bat3-frontend:next . (build only)
- grep -r "@mui\|emotion" ui/src → empty
STOP and report on any failure; do not work around with any-types or skipped checks.
