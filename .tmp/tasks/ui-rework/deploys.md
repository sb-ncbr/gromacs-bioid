# Deploy Log — UI Rework

## 2026-10-01 W1 skeleton smoke deploy ✅
- Image: cerit.io/tomsko/bat3-frontend:next (digest sha256:822cac967b7d) → deployment bat3-ceitec-bat3-web
- Backups: registry bat3-frontend:legacy-pre-rework (d60c7d983e1f), backups/bat3-web-deploy-pre-rework.yaml, backups/ingress-pre-rework.yaml
- Rollback: kubectl set image deployment/bat3-ceitec-bat3-web web=cerit.io/tomsko/bat3-frontend:legacy-pre-rework -n ceitec-biodata-ns (or rollout undo)
- Smoke results:
  - / → new SPA (data-theme=custom, fresh hashed assets) ✅
  - asset JS 200 ✅ · /health → API ✅
  - /api/v1 → 404 from FastAPI = nginx /api proxy chain works, awaits API deploy ✅ (expected)
  - deep-link /runs/<id> → still JSON (KNOWN, WS7 ingress fix pending) ✅ tracked

## 2026-10-01 A-wave2 API deploy ✅ (gate: PASSED, independently verified)
- Gate: pytest 62 passed + 2 pre-existing failures (VERIFIED pre-existing at f8d78423a worktree - NOT caused by A2 or F16; logged to PLAN known-issues). OpenAPI diff: 0 removed paths/methods, +23 additive (`/api/v1/*` aliases + `/runs/{id}/queue` + `/runs/{id}/rerun`).
- Image: cerit.io/tomsko/bat3-api:ui-rework-a2 (sha256:f9c73f44fc73) → deployment bat3-ceitec-bat3-api. Backup: backups/bat3-api-deploy-pre-a2.yaml; rollback image tag: ui1.
- Live smoke: /api/v1/health 200 ✅ · /api/v1/runs list ✅ · legacy /runs 200 ✅ · ?mine=1 200 ✅ · rerun fake-id → clean 404 ✅ · queue finished-run → done ✅ · **links: 1,600 RCSB URLs on bce4a0fa, broken_suffix=0** ✅
- Fixtures identifiers/verification for bce4a0fa refreshed to post-fix truth.
- Live now: /api/v1 alias, creator_ip on new runs, ?mine=1, /runs/{id}/rerun, /runs/{id}/queue, canonical database_url.

## 2026-10-01 W2 frontpage deploy ✅
- Image: cerit.io/tomsko/bat3-frontend:w2 (sha256:d1aa8440f1f1) ← built from CLEAN WORKTREE at ac00189eb (worktree builds are mandatory since .gitignore-collision incident)
- Live: frontpage upload flow (dropzone, config dialog, fast mode, run name) + IP-bound recents (mine=1) + rerun/delete dialogs. Results page: still stub (B-wave pending).
- E2E smoke run: POST /api/v1/runs 1CRN.pdb → run 89fe2c7b-8c2c-426a-9f02-a235b74232e7, success <10s, type_counts {protein:1}; ?mine=1 returned exactly 1 (IP binding works); queue state transitions queued→running observed.
- KNOWN remaining: deep-link /runs/<id> direct-entry → JSON (WS7 ingress fix, next infra wave).

## 2026-10-01 W3 theme + B-wave1 components deploy ✅
- 746a782e1 green theme: setup.css :root is UNLAYERED purple → DS custom_setup (layered) can never win. Fix: unlayered html[data-theme=custom] full token override (brand, ramps 50-950, heading, focus, charts) - beats :root by specificity, cascade-proof.
- 6708cc453 lint gate fixes (B-wave1 now lint/typecheck/test/build all green, 86 tests).
- Image bat3-frontend:w3 (sha256:e9d91f5b26e1) from clean worktree 6708cc453. Live css verified: #2e7d32 present, data-theme=custom in bundle.
- Includes B-wave1 components (TaskBar, MoleculeSelector, ResultsPanel, SignatureDialog, utils) - not page-wired yet; B-wave2 (integration, adaptive polling) running now.

## 2026-10-01 W4 full results UI deploy ✅ (B-wave2 gated: 86 tests, lint/typecheck/build green)
- Session resilience note: network reset killed b-wave2 at D3; resumed detached from D3->D5 clean (insurance architecture held).
- Commits: d957b4767 hooks (adaptive polling), b85339cba page assembly, 8162fc26d warnings panel+catalog copy, 8978e166e tabs, 9277b37c8 molstar single-plugin + 25s watchdog -> static PNG fallback -> gray "Structural data not available".
- Image bat3-frontend:w4 (sha256:e42cb9f7e986) from clean worktree 9277b37c8. Bundle smoke: results UI strings present.
- Remaining: WS7 ingress deep-link fix; then 4-run visual suite with user.

## 2026-10-01 WS7 deep-link fix + w5 deploy ✅ BUG KILLED
- Cause chain: ingress /runs->api AND nginx-frontend /runs->api. Fix both: ingress now /api,/files,/health,/docs,/openapi.json -> api, / -> web; nginx-frontend reduced to SPA fallback + /api + /files proxies.
- Applied: ingress-ws7-fixed.yaml (backup of old: backups/ingress-pre-rework.yaml). Chart template updated for posterity (bat3-chart/templates/ingress.yaml).
- Image bat3-frontend:w5 (sha256:89405826231d).
- Matrix: /runs/<id> 200 text/html (was JSON) | /api/v1/* JSON | /health JSON | /openapi.json JSON | / HTML. API surface at host root is GONE by design (SPA routes); clients use /api/v1.
- Rollback: re-apply backups/ingress-pre-rework.yaml + set web image bat3-frontend:legacy-pre-rework (nginx conf inside image matches old behavior).
