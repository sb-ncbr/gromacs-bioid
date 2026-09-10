# MDFind PostgreSQL Access & Credentials

## Core Concept
PostgreSQL connection patterns for MDFind: Kubernetes secrets, connection strings, SQLAlchemy setup.

## Key Points
- Credentials in Kubernetes secrets (never plain env vars)
- Connection via `DATABASE_URL` environment variable
- SQLAlchemy with connection pooling
- ClusterIP service for internal access

## Credential Storage

### Kubernetes Secret

```bash
kubectl create secret generic mdfind-db-secret -n ceitec-biodata-ns \
  --from-literal=username='mdfind_user' \
  --from-literal=password='SECURE_PASSWORD' \
  --from-literal=host='mdfind-postgres.ceitec-biodata-ns.svc.cluster.local' \
  --from-literal=port='5432' \
  --from-literal=database='mdfind'
```

### Deployment Reference

```yaml
env:
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: mdfind-db-secret
      key: connection-url
```

## Connection String

```python
# Format
postgresql://username:password@host:port/database

# Example
postgresql://mdfind_user:SECRET@mdfind-postgres:5432/mdfind

# With SSL (production)
postgresql://user:pass@host:5432/db?sslmode=require
```

## SQLAlchemy Setup

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv('DATABASE_URL')

engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,   # Auto-reconnect
    pool_recycle=3600     # Recycle hourly
)

SessionLocal = sessionmaker(bind=engine)

# FastAPI dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## Network Access

### Internal (Kubernetes)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mdfind-postgres
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
  type: ClusterIP  # Internal only
```

### Test Connection

```bash
# From API pod
API_POD=$(kubectl get pods -n ceitec-biodata-ns -l app=mdfind-api -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n ceitec-biodata-ns $API_POD -- python -c "
import psycopg2
conn = psycopg2.connect(host='mdfind-postgres', port=5432, user='mdfind_user', password='SECRET', database='mdfind')
print('Connected!')
"
```

### Local Development

```bash
# Port forward
kubectl port-forward -n ceitec-biodata-ns svc/mdfind-postgres 5432:5432

# Connect
psql postgresql://mdfind_user:SECRET@localhost:5432/mdfind
```

## Credential Rotation

```bash
# Update secret
kubectl create secret generic mdfind-db-secret -n ceitec-biodata-ns \
  --from-literal=password='NEW_PASSWORD' \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart pods
kubectl delete pods -n ceitec-biodata-ns -l app=mdfind-api
kubectl delete pods -n ceitec-biodata-ns -l app=mdfind-worker
```

## Security Best Practices

| Practice | How |
|----------|-----|
| Secrets in K8s | `kubectl create secret`, not env vars |
| Network isolation | ClusterIP only |
| Least privilege | Dedicated DB user |
| Rotate passwords | Every 90 days |
| SSL/TLS | `sslmode=require` |

## Troubleshooting

| Error | Solution |
|-------|----------|
| `Connection refused` | Verify service name, namespace |
| `Auth failed` | Check secret, rotate credentials |
| `Pool exhausted` | Increase `pool_size` |
| `Timeout` | Check NetworkPolicy |

## References
- `architecture.md` - System overview
- `kubernetes.md` - K8s manifests
- `../../deployments/ceitec-biodata/overview.md` - Cluster details
