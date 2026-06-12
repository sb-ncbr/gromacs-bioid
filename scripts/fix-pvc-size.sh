#!/usr/bin/env bash
#
# fix-pvc-size.sh
#
# Helper to resize a PVC that doesn't support online expansion.
# The nfs-csi storage class requires PVC recreation for size changes.
#
# Usage:
#   ./fix-pvc-size.sh [--namespace <ns>]
#
# Options:
#   --namespace, -n  Kubernetes namespace (auto-detected from Helm if not provided)
#   --help, -h       Show this help message
#
# Environment variables:
#   NAMESPACE      - Kubernetes namespace (overrides auto-detection)
#   RELEASE_NAME   - Helm release name (default: bat3)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELM_RELEASE="${RELEASE_NAME:-bat3}"
PVC_NAME="${HELM_RELEASE}-bat3-databases-data"

# Parse CLI arguments
NAMESPACE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --namespace|-n)
            NAMESPACE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--namespace <ns>]"
            echo ""
            echo "Helper to resize a PVC that doesn't support online expansion."
            echo ""
            echo "Options:"
            echo "  --namespace, -n  Kubernetes namespace (auto-detected from Helm if not provided)"
            echo "  --help, -h       Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  NAMESPACE      - Kubernetes namespace (overrides auto-detection)"
            echo "  RELEASE_NAME   - Helm release name (default: bat3)"
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1"
            echo "Usage: $0 [--namespace <ns>]"
            echo "Run with --help for more information."
            exit 1
            ;;
    esac
done

# Function to detect namespace from Helm release
detect_namespace() {
    local ns
    # Try to get the bat3 release from any namespace using JSON output
    ns=$(helm list --all-namespaces -o json 2>/dev/null | python3 -c "
import sys, json
try:
    releases = json.load(sys.stdin)
    for r in releases:
        if r.get('name') == '${HELM_RELEASE}':
            print(r.get('namespace', ''))
            break
except (json.JSONDecodeError, Exception):
    pass
" 2>/dev/null)
    
    if [[ -n "$ns" ]]; then
        echo "$ns"
        return 0
    fi
    
    # Fallback: try kubectl to find pods with release labels
    ns=$(kubectl get pods --all-namespaces -l "app.kubernetes.io/instance=${HELM_RELEASE}" -o jsonpath='{.items[0].metadata.namespace}' 2>/dev/null || true)
    if [[ -n "$ns" ]]; then
        echo "$ns"
        return 0
    fi
    
    return 1
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
echo "PVC Resize Helper"
echo "=============================================="
echo "PVC Name: $PVC_NAME"
echo "Namespace: $NAMESPACE"
echo ""

# Check if helm is available
if ! command -v helm &>/dev/null; then
    echo "WARNING: helm command not found."
    echo "Namespace auto-detection may not work correctly."
    echo ""
fi

# Check if the PVC exists
echo "Checking PVC status..."
if kubectl -n "$NAMESPACE" get pvc "$PVC_NAME" &>/dev/null; then
    CURRENT_SIZE=$(kubectl -n "$NAMESPACE" get pvc "$PVC_NAME" -o jsonpath='{.status.capacity.storage}' 2>/dev/null || echo "unknown")
    echo "PVC exists. Current size: $CURRENT_SIZE"
else
    echo "WARNING: PVC '$PVC_NAME' not found in namespace '$NAMESPACE'."
    echo "Make sure you're using the correct namespace."
fi
echo ""

echo "The current PVC was created at 50Gi. Your storage class (nfs-csi)"

# Detect the worker deployment name
WORKER_DEPLOYMENT="${HELM_RELEASE}-worker"
echo "does not support online expansion. You have two options:"
echo ""
echo "=============================================="
echo "OPTION 1: Delete and recreate the PVC"
echo "=============================================="
echo "(Recommended if /app/databases is empty - no data loss)"
echo ""
echo "This will DELETE the current PVC and all data in /app/databases."
echo "Since the databases directory is currently empty, this is safe."
echo ""
echo "Commands to run:"
echo ""
echo "  WARNING: You MUST scale down the worker deployment first,"
echo "           otherwise the PVC will stay stuck in 'Terminating'."
echo "           Kubernetes cannot delete a PVC while it is mounted by a running pod."
echo ""
echo "  # Step 0: Scale down worker deployment (releases PVC mount)"
echo "  kubectl -n $NAMESPACE scale deployment $WORKER_DEPLOYMENT --replicas=0"
echo ""
echo "  # Step 1: Delete the existing PVC"
echo "  kubectl -n $NAMESPACE delete pvc $PVC_NAME"
echo ""
echo "  # Step 2: Upgrade Helm with new size (update values.yaml first)"
echo "  helm upgrade --install $HELM_RELEASE bat3-chart/ --namespace $NAMESPACE"
echo ""
echo "  # Step 3: Verify new PVC size"
echo "  kubectl -n $NAMESPACE get pvc $PVC_NAME"
echo ""

echo "=============================================="
echo "OPTION 2: Create a second PVC and migrate"
echo "=============================================="
echo "(Use if you have data to preserve)"
echo ""
echo "Create a new 2Ti PVC, copy data, then switch the deployment."
echo "Not needed if /app/databases is empty."
echo ""
echo "Steps:"
echo ""
echo "  # 1. Update values.yaml with new PVC size"
echo "  # 2. Create the new PVC manually or via Helm upgrade"
echo "  # 3. Copy data from old PVC to new PVC (requires a pod with both mounted)"
echo "  # 4. Delete old PVC and update deployment to use new PVC"
echo ""
echo "This approach is more complex and usually unnecessary for fresh installations."
echo ""

echo "=============================================="
echo "Before proceeding:"
echo "=============================================="
echo "- Verify the databases directory is empty (if using Option 1)"
echo "- Ensure your values.yaml has the desired PVC size configured"
echo "- Have a backup strategy if there's any important data"
echo ""
