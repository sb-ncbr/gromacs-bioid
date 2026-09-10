# MDFind Harness Engine - Navigation

## Files

| File | Lines | Purpose |
|------|-------|---------|
| `navigation.md` | ~35 | This overview |
| `architecture.md` | ~120 | System design, components, patterns |
| `kubernetes.md` | ~160 | K8s manifests, deployment |
| `s3-integration.md` | ~100 | S3 download patterns |
| `postgres.md` | ~150 | Database access, credentials |

## Quick Start

1. Read `architecture.md` - System overview
2. Read `kubernetes.md` - Deploy to cluster
3. Read `postgres.md` - Database configuration
4. Read `s3-integration.md` - S3 downloads

## Key Commands

```bash
# Deploy
kubectl apply -f k8s/

# Check status
kubectl get pods -n ceitec-biodata-ns -l app=mdfind

# Database connection test
kubectl port-forward -n ceitec-biodata-ns svc/mdfind-postgres 5432:5432
psql postgresql://user:pass@localhost:5432/mdfind

# Logs
kubectl logs -n ceitec-biodata-ns -l app=mdfind-api --tail=50
```

## Related Context

- `../standards/mvi.md` - File size standards
- `../../deployments/ceitec-biodata/overview.md` - Cluster details
