#!/usr/bin/env bash
#
# download-databases.sh
#
# Launch the BLAST database download job on Kubernetes.
# This script applies the standalone Job manifest and optionally streams logs.
#
# Usage:
#   ./download-databases.sh [--namespace <ns>] [--follow-logs] [--no-scale-worker]
#
# Options:
#   --namespace, -n  Kubernetes namespace (auto-detected from pods if not provided)
#   --follow-logs, -f  Follow job logs after creation
#   --no-scale-worker  Skip automatic worker scale-down (use if worker is already stopped)
#   --help, -h       Show this help message
#
# Environment variables:
#   NAMESPACE  - Kubernetes namespace (overrides auto-detection)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
K8S_JOB_MANIFEST="$PROJECT_ROOT/k8s/blast-db-download-job.yaml"
JOB_NAME="bat3-blast-db-download"

# Parse CLI arguments
NAMESPACE=""
FOLLOW_LOGS=""
SCALE_WORKER="yes"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --namespace|-n)
            NAMESPACE="$2"
            shift 2
            ;;
        --follow-logs|-f)
            FOLLOW_LOGS="yes"
            shift
            ;;
        --no-scale-worker)
            SCALE_WORKER="no"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--namespace <ns>] [--follow-logs] [--no-scale-worker]"
            echo ""
            echo "Launch the BLAST database download job on Kubernetes."
            echo ""
            echo "Options:"
            echo "  --namespace, -n  Kubernetes namespace (auto-detected from pods if not provided)"
            echo "  --follow-logs, -f  Follow job logs after creation"
            echo "  --no-scale-worker  Skip automatic worker scale-down (use if worker is already stopped)"
            echo "  --help, -h       Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  NAMESPACE  - Kubernetes namespace (overrides auto-detection)"
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1"
            echo "Usage: $0 [--namespace <ns>] [--follow-logs] [--no-scale-worker]"
            echo "Run with --help for more information."
            exit 1
            ;;
    esac
done

# Function to detect namespace from running pods
detect_namespace() {
    kubectl get pods --all-namespaces -l app=bat3-worker -o jsonpath='{range .items[*]}{.metadata.namespace}{"\n"}{end}' 2>/dev/null | head -1
}

# Function to detect worker deployment
detect_worker_deployment() {
    local release_names
    release_names=$(kubectl -n "$NAMESPACE" get deployments -o json 2>/dev/null | python3 -c "
import sys, json
deps = json.load(sys.stdin)['items']
for d in deps:
    name = d['metadata']['name']
    if name.endswith('-worker') or 'worker' in name:
        print(name)
        break
" 2>/dev/null)
    echo "$release_names"
}

# Scale worker deployment
scale_worker() {
    local replicas="$1"
    if [[ -n "$WORKER_DEPLOYMENT" ]]; then
        echo "Scaling worker deployment '$WORKER_DEPLOYMENT' to $replicas replicas..."
        kubectl -n "$NAMESPACE" scale deployment "$WORKER_DEPLOYMENT" --replicas="$replicas"
        if [[ "$replicas" == "0" ]]; then
            echo "Waiting for worker pods to terminate..."
            kubectl -n "$NAMESPACE" wait --for=delete pod -l app="$WORKER_DEPLOYMENT" --timeout=120s 2>/dev/null || true
        fi
    fi
}

# Auto-detect namespace if not provided via CLI or env
if [[ -z "${NAMESPACE:-}" ]]; then
    DETECTED_NS=$(detect_namespace)
    if [[ -n "$DETECTED_NS" ]]; then
        NAMESPACE="$DETECTED_NS"
        echo "Auto-detected namespace: $NAMESPACE"
    else
        NAMESPACE="default"
        echo "WARNING: Could not auto-detect namespace. Using 'default'."
        echo "Set NAMESPACE env var or pass --namespace <ns> to override."
    fi
else
    echo "Using namespace: $NAMESPACE"
fi

echo ""
echo "=============================================="
echo "BLAST Database Download Job Launcher"
echo "=============================================="
echo "Namespace: $NAMESPACE"
echo "Job manifest: $K8S_JOB_MANIFEST"
echo ""

# Check if job manifest exists
if [[ ! -f "$K8S_JOB_MANIFEST" ]]; then
    echo "ERROR: Job manifest not found: $K8S_JOB_MANIFEST"
    exit 1
fi

# Check if we need to scale down worker to free quota
WORKER_DEPLOYMENT=""
if [[ "$SCALE_WORKER" == "yes" ]]; then
    WORKER_DEPLOYMENT=$(detect_worker_deployment)
    if [[ -n "$WORKER_DEPLOYMENT" ]]; then
        echo ""
        echo "NOTE: Worker deployment '$WORKER_DEPLOYMENT' detected."
        echo "The database download job needs resources that may exceed namespace quota."
        echo "Scaling worker to 0 replicas temporarily. It will be restarted after download."
        echo ""
        scale_worker 0
    fi
fi

# Apply the job manifest
echo "Applying BLAST database download job..."
kubectl -n "$NAMESPACE" apply -f "$K8S_JOB_MANIFEST"

echo ""
echo "Job created successfully!"
echo ""
echo "Check status with:"
echo "  kubectl -n $NAMESPACE get jobs"
echo "  kubectl -n $NAMESPACE describe job $JOB_NAME"
echo ""
echo "View logs with:"
echo "  kubectl -n $NAMESPACE logs -f job/$JOB_NAME"
echo ""

# Print scale-up reminder if worker was scaled down
if [[ -n "$WORKER_DEPLOYMENT" ]]; then
    echo ""
    echo "=============================================="
    echo "IMPORTANT: After the download job finishes,"
    echo "remember to scale the worker back up:"
    echo ""
    echo "  kubectl -n $NAMESPACE scale deployment $WORKER_DEPLOYMENT --replicas=1"
    echo "=============================================="
    echo ""
fi

# Optionally follow logs
if [[ "$FOLLOW_LOGS" == "yes" ]]; then
    echo "Waiting for job pod to be ready..."
    kubectl -n "$NAMESPACE" wait --for=condition=ready pod -l job-name="$JOB_NAME" --timeout=120s 2>/dev/null || true
    echo "Following job logs (Ctrl+C to stop)..."
    kubectl -n "$NAMESPACE" logs -f job/"$JOB_NAME"
fi
