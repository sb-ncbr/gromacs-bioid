# BioID UI (rework)

Vite 6 + React 19 + TS strict · Tailwind v4 · `@e-infra/design-system` (pinned `0.1.9`, custom theme `data-theme="custom"`, primary `#2E7D32`) · react-router v7 · TanStack Query.

## Scripts
- `npm run dev` — local dev on :8081 (proxies /api, /runs, /files, /health → :8000)
- `npm run build` / `npm run typecheck` / `npm run lint` / `npm test`
- `npm run gen:api` — regenerate `src/lib/api/types.ts` from the OpenAPI baseline JSON (first arg may be a path or URL)

## Conventions
- Deep-linkable run state: `/runs/:id?segment=X&tab=Y` via `src/lib/nav.ts`
- Typed API access only via `src/lib/api/client.ts` (`/api/v1` base; legacy static `/files/*`)
- No MUI/emotion. Design-system components + Tailwind tokens only.
