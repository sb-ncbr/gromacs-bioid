#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="gromacs-bioid-ns"

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <web|worker|api>"
    exit 1
fi

TARGET=$1
DEPLOY="gmx-bioid-gmx-bioid-$TARGET"

echo "🔍 Finding pod for deployment: $DEPLOY in namespace $NAMESPACE..."
POD=$(kubectl get pods -n "$NAMESPACE" -o json \
    | jq -r --arg deploy "$DEPLOY" '.items[] | select(.metadata.name | contains($deploy)) | .metadata.name' \
    | head -n 1)

if [[ -z "$POD" ]]; then
    echo "❌ No running pod found for $DEPLOY"
    exit 1
fi

echo "📜 Connecting to logs of pod: $POD"
kubectl logs -n "$NAMESPACE" -f "$POD"
