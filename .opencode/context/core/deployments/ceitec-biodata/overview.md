# CEITEC BioData Kubernetes Deployment

## Core Concept
Production Kubernetes cluster at CEITEC-SC for BAT3 validation and MDFind harness engines.

## Key Points
- Cluster: `rancher.cloud.e-infra.cz`
- Namespace: `ceitec-biodata-ns`
- Ingress: `*.dyn.cloud.e-infra.cz`
- TLS: cert-manager + letsencrypt-prod
- Registry: `cerit.io/tomsko/`

## Cluster Access

```bash
kubectl config use-context {cluster-name}
kubectl get nodes
kubectl create namespace ceitec-biodata-ns
```

## Ingress Pattern

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: validation-ui-v2
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-buffer-size: 128k
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
spec:
  ingressClassName: nginx
  tls:
  - hosts: [bat3-validation.dyn.cloud.e-infra.cz]
    secretName: bat3-validation-tls
  rules:
  - host: bat3-validation.dyn.cloud.e-infra.cz
    http:
      paths:
      - backend:
          service: {name: validation-ui, port: {number: 80}}
        path: /
        pathType: Prefix
```

## Secrets

```bash
kubectl create secret generic validation-db-secret -n ceitec-biodata-ns \
  --from-literal=url='postgresql://user:pass@host:5432/db'

kubectl create secret generic validation-s3-secret -n ceitec-biodata-ns \
  --from-literal=access-key='KEY' --from-literal=secret-key='SECRET'
```

## Common Services

| Service | Image | Replicas | Port |
|---------|-------|----------|------|
| validation-api | bat3-validation-api:vX.Y | 2 | 8000 |
| validation-worker | bat3-validation-api:vX.Y | 10-30 | - |
| validation-ui | bat3-validation-ui:vZ | 2 | 80 |
| mdfind-api | mdfind-api:v1.0 | 2 | 8000 |
| mdfind-worker | mdfind-api:v1.0 | 10+ | - |

## Deployment Workflow

```bash
docker build -f Dockerfile.api -t cerit.io/tomsko/app:v1.0 .
docker push cerit.io/tomsko/app:v1.0
kubectl set image deployment/app app=cerit.io/tomsko/app:v1.0 -n ceitec-biodata-ns
kubectl rollout status deployment/app -n ceitec-biodata-ns
```

## Monitoring

```bash
kubectl get pods -n ceitec-biodata-ns
kubectl logs -n ceitec-biodata-ns -l app=validation-api --tail=50
kubectl logs -n ceitec-biodata-ns -l app=validation-worker --tail=50
kubectl get events -n ceitec-biodata-ns --sort-by='.lastTimestamp'
kubectl top pods -n ceitec-biodata-ns
```

## Scaling

```bash
kubectl scale deployment validation-worker --replicas=30 -n ceitec-biodata-ns
kubectl scale deployment validation-api --replicas=4 -n ceitec-biodata-ns
```

## Rollback

```bash
kubectl rollout undo deployment/validation-api -n ceitec-biodata-ns
kubectl rollout history deployment/validation-api -n ceitec-biodata-ns
```

## Troubleshooting

| Issue | Command | Solution |
|-------|---------|----------|
| Pod pending | `kubectl describe pod` | Check resources, capacity |
| ImagePullBackOff | `kubectl describe pod` | Verify image, credentials |
| CrashLoopBackOff | `kubectl logs` | Check app errors |
| Ingress broken | `kubectl get ingress` | Check TLS, annotations |

## References
- `../harness-engines/mdfind/architecture.md` - System patterns
- `../context-system/standards/mvi.md` - MVI standards
