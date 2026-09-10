# Guide: Safe Helm Upgrade Against `kubectl-set` Drift

## Core Concept
Release `bat3-ceitec` (namespace `ceitec-biodata-ns`) has live drift from post-install `kubectl set image/env/scale`. Blind `helm upgrade` either fails with server-side-apply conflicts or silently reverts production state. This procedure makes upgrades deterministic.

## Procedure

```bash
# 1) Discover LIVE truth (not values!)
kubectl get deployment bat3-ceitec-bat3-worker -n ceitec-biodata-ns \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}{.spec.replicas}{"\n"}'
kubectl get deployment <d> -o jsonpath='{range .spec.template.spec.containers[0].env[*]}{.name}={.value} {end}'

# 2) Backup current release values + manifests
helm get values bat3-ceitec -n ceitec-biodata-ns -a > values-backup.yaml
kubectl get deployment <d> -n ceitec-biodata-ns -o yaml > <d>-backup.yaml

# 3) Freeze values to live truth in values-upgrade.yaml
#    - image tags = CURRENT pod images (e.g. worker v2.13)
#    - replicas = CURRENT live count (e.g. 20, not chart default 10)
#    - intentionallly change ONLY what you are fixing

# 4) Dry-check render
helm template bat3-ceitec ./bat3-chart -f values-upgrade.yaml -n ceitec-biodata-ns | grep -E 'claimName|image:'

# 5) Upgrade (adopt drifted fields; identical where frozen)
helm upgrade bat3-ceitec ./bat3-chart -n ceitec-biodata-ns -f values-upgrade.yaml --force-conflicts

# 6) Verify
kubectl rollout status deployment/<d> -n ceitec-biodata-ns --timeout=300s
```

## Why --force-conflicts
SSA refuses to change fields owned by manager `kubectl-set` (e.g. `.image`, celery envs). With rendered values IDENTICAL to live for frozen fields, `--force-conflicts` only reassigns ownership — no behavior change. Conflicts have occurred twice; both resolved this way.

## Non-helm deployments
`validation-api` / `validation-worker` are plain deployments: `kubectl set image` + `kubectl patch` (add volumes/command). No release to preserve — but keep `deploy/validation-worker-deployment.yaml` updated.

## Reference
- `../lookup/ceitec-deployment.md` — current live pins
- Chart: `bat3-chart/` (existingClaim bug fixed in 0.1.1)
