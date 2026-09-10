# Harness Engines - Navigation

## Core Concept
Reusable Kubernetes-based harness engines for different simulation/database systems. Each engine follows consistent patterns with system-specific adaptations.

## Available Engines

| Engine | Purpose | Status |
|--------|---------|--------|
| **MDFind** | MDFind DB + S3 simulations | ✅ Documented |

## MDFind Engine

```
mdfind/
├── navigation.md         # This overview
├── architecture.md       # System design, components
├── kubernetes.md         # K8s manifests, deployment
└── s3-integration.md     # S3 download patterns
```

### Quick Start (MDFind)

1. Read `mdfind/architecture.md` - System overview
2. Read `mdfind/kubernetes.md` - Deploy to cluster
3. Read `mdfind/s3-integration.md` - S3 configuration

## Common Patterns

All harness engines share:
- FastAPI backend (port 8000)
- Celery workers (Redis broker)
- React UI with nginx proxy
- Kubernetes deployment
- Ingress with TLS

## Adding New Engine

1. Create directory: `harness-engines/{name}/`
2. Copy structure from MDFind
3. Adapt architecture for new system
4. Update K8s manifests
5. Document S3/storage integration

## Related Context

- `../context-system/standards/mvi.md` - File standards
- `../context-system/standards/structure.md` - Folder structure
