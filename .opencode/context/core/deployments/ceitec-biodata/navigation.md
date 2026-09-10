# CEITEC BioData Deployment - Navigation

## Files

| File | Lines | Purpose |
|------|-------|---------|
| `navigation.md` | ~30 | This overview |
| `overview.md` | ~110 | Cluster access, ingress, secrets |
| `operations.md` | ~100 | Deployment procedures, troubleshooting |

## Quick Start

1. Read `overview.md` - Cluster setup, ingress pattern
2. Read `operations.md` - Deploy, monitor, troubleshoot

## Key Commands

```bash
# Deploy
kubectl set image deployment/app app=cerit.io/tomsko/app:v1.0 -n ceitec-biodata-ns

# Monitor
kubectl get pods -n ceitec-biodata-ns
kubectl logs -n ceitec-biodata-ns -l app=app --tail=50

# Troubleshoot
kubectl describe pod -n ceitec-biodata-ns {pod}
kubectl rollout undo deployment/app -n ceitec-biodata-ns
```

## Cluster Info

- **URL**: `rancher.cloud.e-infra.cz`
- **Namespace**: `ceitec-biodata-ns`
- **Domain**: `*.dyn.cloud.e-infra.cz`
- **Registry**: `cerit.io/tomsko/`

## Related Context

- `../harness-engines/mdfind/` - MDFind deployment
- `../context-system/standards/mvi.md` - MVI standards
