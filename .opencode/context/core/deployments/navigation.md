# Deployments - Navigation

## Core Concept
Kubernetes deployment targets for harness engines and applications.

## Available Deployments

| Deployment | Purpose | Status |
|------------|---------|--------|
| **ceitec-biodata** | CEITEC-SC production cluster | ✅ Documented |

## CEITEC BioData

```
ceitec-biodata/
├── navigation.md      # Overview
├── overview.md        # Cluster access, ingress, secrets
└── operations.md      # Procedures, monitoring, troubleshooting
```

### Quick Start

1. Read `ceitec-biodata/overview.md` - Cluster setup
2. Read `ceitec-biodata/operations.md` - Deploy & operate

## Cluster Details

- **Provider**: CEITEC-SC
- **Management**: Rancher
- **Namespace**: `ceitec-biodata-ns`
- **Ingress**: `*.dyn.cloud.e-infra.cz`
- **TLS**: letsencrypt-prod via cert-manager

## Common Patterns

All deployments use:
- Docker images from `cerit.io/tomsko/`
- Kubernetes deployments with 2+ replicas
- ClusterIP services
- nginx-ingress with TLS
- Resource quotas per namespace

## Adding New Deployment

1. Create directory: `deployments/{name}/`
2. Document cluster access
3. Define ingress pattern
4. Create deployment procedures
5. Add troubleshooting guide

## Related Context

- `../harness-engines/` - Application patterns
- `../context-system/standards/structure.md` - Folder structure
