# MDFind Harness Engine Architecture

## Core Concept
Kubernetes-based harness engine for accessing MDFind database, indexing simulations, and downloading from S3. Built on BAT3 validation system patterns with MDFind-specific adaptations.

## Key Components

| Component | Purpose | Tech Stack |
|-----------|---------|------------|
| **API** (`mdfind-api`) | Database queries, S3 indexing | FastAPI, PostgreSQL, port 8000 |
| **Worker** (`mdfind-worker`) | Async indexing/downloads | Celery, Redis, 10+ replicas |
| **UI** (`mdfind-ui`) | Frontend + nginx proxy | React, nginx |
| **Ingress** | TLS termination, routing | nginx-ingress, cert-manager |

## Architecture Flow

```
Internet → Ingress → UI(nginx:80) → API(FastAPI:8000) → {PostgreSQL, Redis, S3}
                                    ↓
                              Worker(Celery)
```

## nginx Proxy Config (UI)

```nginx
location /api/ {
    rewrite ^/api/(.*) /$1 break;
    proxy_pass http://mdfind-api:8000;
}
location /simulations/ {
    proxy_pass http://mdfind-api:8000/simulations/;
}
location / {
    try_files $uri $uri/ /index.html;
}
```

## Ingress Pattern

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mdfind-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-buffer-size: 128k
spec:
  ingressClassName: nginx
  tls:
  - hosts: [mdfind.dyn.cloud.e-infra.cz]
    secretName: mdfind-tls
  rules:
  - host: mdfind.dyn.cloud.e-infra.cz
    http:
      paths:
      - backend:
          service:
            name: mdfind-ui
            port: {number: 80}
        path: /
        pathType: Prefix
```

## Critical Environment Variables

```bash
DATABASE_URL=postgresql://user:pass@mdfind-postgres:5432/mdfind
REDIS_URL=redis://mdfind-redis:6379/0
S3_BUCKET=mdfind-simulations
S3_ENDPOINT=https://s3.cerit-sc.cz
S3_ACCESS_KEY_ID=from-secret
S3_SECRET_ACCESS_KEY=from-secret
WORKER_CONCURRENCY=10
```

## Deployment Workflow

```bash
docker build -f Dockerfile.api -t cerit.io/tomsko/mdfind-api:v1.0 .
docker push cerit.io/tomsko/mdfind-api:v1.0
kubectl set image deployment/mdfind-api api=cerit.io/tomsko/mdfind-api:v1.0 -n {namespace}
kubectl rollout status deployment/mdfind-api -n {namespace}
curl https://mdfind.dyn.cloud.e-infra.cz/simulations/status
```

## Debugging Commands

```bash
kubectl logs -n {ns} -l app=mdfind-api --tail=50
kubectl exec -n {ns} {ui-pod} -- curl http://mdfind-api:8000/simulations
kubectl get pods -n {ns} -l app=mdfind-api
kubectl delete pod -n {ns} -l app=mdfind-api
```

## Common Pitfalls & Solutions

| Problem | Cause | Solution |
|---------|-------|----------|
| `AttributeError` on model | Missing attribute | Check SQLAlchemy model first |
| 500 error on endpoint | Code bug | Fix → rebuild → deploy → restart |
| HTML instead of JSON | nginx SPA fallback | Add `location /path/` proxy |
| S3 timeout | Large files | Add `proxy-buffer-size: 128k` |
| Workers idle | Redis unreachable | Verify `REDIS_URL` |

## File Structure

```
mdfind-harness/
├── api/main.py          # FastAPI app
├── api/models.py        # SQLAlchemy models
├── api/workers.py       # Celery tasks
├── web/src/Pages/       # React components
├── web/nginx.conf       # Proxy config
├── Dockerfile.api
├── Dockerfile.worker
├── Dockerfile.ui
└── k8s/                 # Kubernetes manifests
```

## References
- `../standards/mvi.md` - File size standards
- `/home/tomsko/work/bat3/src_new/api/main.py` - API patterns
