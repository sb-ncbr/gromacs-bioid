#!/usr/bin/bash
set -euo pipefail

NAMESPACE="gromacs-bioid-ns"
DEPLOYMENTS=(
  "gmx-bioid-gmx-bioid-worker"
)

echo "🚀 Restarting deployments in namespace: $NAMESPACE"
for DEPLOY in "${DEPLOYMENTS[@]}"; do
    echo "🔄 Deleting pods for deployment: $DEPLOY"
    kubectl delete pod -n "$NAMESPACE" \
        -l "app=$DEPLOY" \
        --ignore-not-found
done

echo "✅ Done! Kubernetes will now pull fresh images and recreate pods."
