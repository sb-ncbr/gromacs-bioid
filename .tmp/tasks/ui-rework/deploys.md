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
