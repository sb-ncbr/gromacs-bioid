# bat3-chart is retired (2026-11-17)

Helm last deployed BioID on 2026-09-10 (release `bat3-ceitec`, revision 6).
Since then production has been changed with `kubectl set image` / `set env` /
`patch`: new images, the UI worker pool, secrets, probes, the shared cache.
The chart describes none of it, so a `helm upgrade` would roll production
back two months.

The chart now refuses to render (`templates/retired.yaml`), so an upgrade
fails before touching anything. The helm release record is left in the
cluster as it is; do not `helm uninstall` it: that would delete the
deployments it still owns (API, fleet workers, web, ingress).

How BioID is deployed now:

- `deploy/live/*.yaml`: the production manifests (exported from the cluster
  with `deploy/export-live.sh`, environment secrets as references).
- `deploy/release.sh`: rolls new backend / web / docs / MCP images, with the
  safety checks (busy queues, active runs, snapshots, secret wiring).
- `deploy/bioid-ingress-extras.yaml`, `deploy/bioid-cache-redis.yaml`,
  `deploy/mcp-server.yaml`: additional objects.
