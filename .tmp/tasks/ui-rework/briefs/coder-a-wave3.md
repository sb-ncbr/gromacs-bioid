# CODER A — WAVE 3: Frontpage (upload flow + IP-bound recents)  [model: qwen3.8-27b]
PRECONDITION: ui scaffold exists (it does). /api/v1 live: POST /runs, GET /runs?mine=1, POST /runs/{id}/rerun, DELETE /runs/{id}, GET /runs/config/default (aliased). READ: CONTEXT.md, PLAN WS2. Design: DS only.
## Deliverables (ui/src/, commits per group)
1. `pages/Frontpage.tsx` full (commit `ui: frontpage upload flow`):
   - Hero: 2-sentence biologist intro (no marketing fluff) + supported inputs bulleted compactly (.tpr/.top+.itp/.gro/.pdb, zip/tar bundles; copy from CONTEXT tone rules).
   - Dropzone (react-dropzone; accept map from legacy: tpr gro top itp pdb json yaml yml zip tar tar.gz ini) + file table (name truncated, ext badge, remove X).
   - Run name text field; Fast Mode switch (sets executor.{signatures,identifiers,verification}_parallel=true in posted config); "Advanced configuration" DS Dialog with generic section/field editor port (booleans→Switch, numbers→validated input like legacy rules, strings→Input; source = GET /runs/config/default aliased; on error use fallback object EXACTLY as legacy MINIMAL_DEFAULT_CONFIG — extract from git tag ui-legacy-pre-rework:ui/src/Pages/Frontpage.tsx).
   - Submit: POST /runs multipart (files + run_name + config_json when customized/fast) → navigate to /runs/{id}.
   - use mutation (TanStack) with pending/disabled states + DS Alert on error.
2. Recents section on same page (commit `ui: ip-bound recents`):
   - GET /api/v1/runs?mine=1, table/list cards: run_name (fallback input_kind, fallback short id), status Badge (pending gray/running blue/success green/failed red/warning amber), created date, actions: View (link), Rerun (POST rerun, DS AlertDialog confirm "Re-queue this annotation with the same files and settings?"), Delete (DS AlertDialog confirm, DELETE, invalidate list).
   - Empty state: "No annotations from this browser yet."
   - Queued runs: small "in queue" chip via /runs/{id}/queue ONLY when status pending (avoid N calls: fetch lazily per pending run).
   - NO re-run-all anywhere.
3. Wire Layout: page grid two columns on xl (form 7 / recents 5), stacked on mobile; Skeletons while loading.
## Gate
typecheck ✓ lint ✓ test ✓ build ✓ (planner deploys + live-submits a real pdb run before user visual pass)
