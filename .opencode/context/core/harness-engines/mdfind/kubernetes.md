# MDFind Kubernetes Deployment Guide

## Core Concept
Complete Kubernetes manifests for MDFind harness engine deployment in CERIT-SC cluster.

## Key Points
- Namespace: `ceitec-biodata-ns` or dedicated `mdfind-ns`
- Image registry: `cerit.io/tomsko/`
- TLS: cert-manager with letsencrypt-prod
- Workers: 10+ replicas for parallel S3 downloads

## Secrets (Create First)

```bash
kubectl create secret generic mdfind-db-secret -n $NS \
  --from-literal=url='postgresql://user:pass@host:5432/mdfind'

kubectl create secret generic mdfind-s3-secret -n $NS \
  --from-literal=access-key='KEY' --from-literal=secret-key='SECRET'
```

## API Deployment (Key Parts)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mdfind-api
  namespace: ceitec-biodata-ns
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: api
        image: cerit.io/tomsko/mdfind-api:v1.0
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: mdfind-db-secret
              key: url
        - name: S3_BUCKET
          value: mdfind-simulations
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
```

## Worker Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mdfind-worker
  namespace: ceitec-biodata-ns
spec:
  replicas: 10
  template:
    spec:
      containers:
      - name: worker
        image: cerit.io/tomsko/mdfind-api:v1.0
        command: ["celery", "-A", "src.api.workers", "worker"]
        env:
        - name: REDIS_URL
          value: redis://mdfind-redis:6379/0
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
```

## Services

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mdfind-api
spec:
  selector:
    app: mdfind-api
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
---
apiVersion: v1
kind: Service
metadata:
  name: mdfind-ui
spec:
  selector:
    app: mdfind-ui
  ports:
  - port: 80
    targetPort: 80
  type: ClusterIP
```

## Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mdfind-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-buffer-size: 128k
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
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

## Deployment Commands

```bash
# Apply
kubectl apply -f k8s/

# Check status
kubectl get pods -n ceitec-biodata-ns -l app=mdfind-api

# Scale workers
kubectl scale deployment mdfind-worker --replicas=20 -n ceitec-biodata-ns

# Update image
kubectl set image deployment/mdfind-api api=cerit.io/tomsko/mdfind-api:v1.1 -n ceitec-biodata-ns
kubectl rollout status deployment/mdfind-api -n ceitec-biodata-ns

# Rollback
kubectl rollout undo deployment/mdfind-api -n ceitec-biodata-ns
```

## Monitoring

```bash
kubectl logs -n ceitec-biodata-ns -l app=mdfind-api --tail=50
kubectl logs -n ceitec-biodata-ns -l app=mdfind-worker --tail=50
kubectl get events -n ceitec-biodata-ns --sort-by='.lastTimestamp'
```

## References
- `architecture.md` - Overall architecture
- `../standards/mvi.md` - MVI standards
