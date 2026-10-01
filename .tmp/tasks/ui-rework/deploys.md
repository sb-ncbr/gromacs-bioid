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
