# CEITEC BioData Operational Procedures

## Core Concept
Standard operating procedures for deploying and maintaining applications in CEITEC BioData namespace.

## Key Points
- Pre-flight checks before deployment
- Rollout verification steps
- Monitoring commands
- Incident response
- Backup/recovery

## Pre-Flight Checklist

```bash
kubectl get nodes
kubectl get namespace ceitec-biodata-ns
kubectl get secrets -n ceitec-biodata-ns
kubectl describe quota -n ceitec-biodata-ns
```

## Deployment Procedure

```bash
# Build & Push
export VERSION=3.81
docker build -f Dockerfile.api -t cerit.io/tomsko/app:v${VERSION} .
docker push cerit.io/tomsko/app:v${VERSION}

# Deploy
kubectl set image deployment/app app=cerit.io/tomsko/app:v${VERSION} -n ceitec-biodata-ns

# Verify
kubectl rollout status deployment/app -n ceitec-biodata-ns
kubectl get pods -n ceitec-biodata-ns -l app=app
curl https://bat3-validation.dyn.cloud.e-infra.cz/health
```

## Daily Monitoring

```bash
kubectl get pods -n ceitec-biodata-ns
kubectl top pods -n ceitec-biodata-ns
kubectl get events -n ceitec-biodata-ns --field-selector type=Warning
kubectl get ingress -n ceitec-biodata-ns
```

## Incident Response

### CrashLoopBackOff
```bash
kubectl describe pod -n ceitec-biodata-ns {pod}
kubectl logs -n ceitec-biodata-ns {pod} --previous
kubectl rollout undo deployment/app -n ceitec-biodata-ns
```

### High Memory
```bash
kubectl top pods -n ceitec-biodata-ns --sort-by=memory
kubectl delete pod -n ceitec-biodata-ns {pod}
kubectl scale deployment app --replicas=0 -n ceitec-biodata-ns  # restart
```

### Ingress 502/503
```bash
kubectl describe ingress validation-ui-v2 -n ceitec-biodata-ns
kubectl get endpoints validation-ui -n ceitec-biodata-ns
kubectl get secret bat3-validation-tls -n ceitec-biodata-ns
```

## Backup

```bash
# Database
kubectl exec -n ceitec-biodata-ns {db-pod} -- pg_dump -U user dbname > backup.sql

# K8s configs
kubectl get deployments -n ceitec-biodata-ns -o yaml > deployments.yaml
kubectl apply -f deployments.yaml  # restore
```

## Maintenance

```bash
# Scale down
kubectl scale deployment app --replicas=0 -n ceitec-biodata-ns

# Scale up
kubectl scale deployment app --replicas=2 -n ceitec-biodata-ns

# Force restart
kubectl delete pods -n ceitec-biodata-ns -l app=app
```

## References
- `overview.md` - Cluster overview
- `../harness-engines/mdfind/kubernetes.md` - K8s manifests
