#!/usr/bin/env bash
#
# fix-pvc.sh
#
# Helper to resize a PVC that doesn't support online expansion.
# The nfs-csi storage class requires PVC recreation for size changes.
#
# Usage:
#   ./scripts/k8s/fix-pvc.sh [--namespace <ns>]
#
# Options:
#   --namespace, -n  Kubernetes namespace (auto-detected if not provided)
#   --help, -h       Show this help message
#
# Environment variables:
#   NAMESPACE      - Kubernetes namespace (overrides auto-detection)
#   RELEASE_NAME   - Helm release name (default: bat3)
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "${SCRIPT_DIR}/common.sh"

HELM_RELEASE="${RELEASE_NAME:-bat3}"
PVC_NAME="${HELM_RELEASE}-bat3-databases-data"

show_help() {
    cat <<HELP
Usage: $(basename "$0") [--namespace <ns>]

Helper to resize a PVC that doesn't support online expansion.
The nfs-csi storage class requires PVC recreation for size changes.

Options:
  --namespace, -n  Kubernetes namespace (auto-detected if not provided)
  --help, -h       Show this help message

Environment variables:
  NAMESPACE      - Kubernetes namespace (overrides auto-detection)
  RELEASE_NAME   - Helm release name (default: bat3)

Examples:
  $(basename "$0")                     # Auto-detect namespace
  $(basename "$0") -n gromacs-bioid-ns # Specify namespace
HELP
}

# Parse CLI arguments
CLI_NAMESPACE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --namespace|-n)
            CLI_NAMESPACE="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Use CLI namespace, env var, or auto-detect
if [[ -n "$CLI_NAMESPACE" ]]; then
    NAMESPACE="$CLI_NAMESPACE"
elif [[ -z "${NAMESPACE:-}" ]]; then
    NAMESPACE=$(resolve_namespace)
fi

if [[ -z "$NAMESPACE" ]]; then
    NAMESPACE="default"
    echo "WARNING: Could not auto-detect namespace. Using 'default'."
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

# Check if the PVC exists
echo "Checking PVC status..."
if ${KUBECTL} -n "$NAMESPACE" get pvc "$PVC_NAME" &>/dev/null; then
    CURRENT_SIZE=$(${KUBECTL} -n "$NAMESPACE" get pvc "$PVC_NAME" -o jsonpath='{.status.capacity.storage}' 2>/dev/null || echo "unknown")
    STORAGE_CLASS=$(${KUBECTL} -n "$NAMESPACE" get pvc "$PVC_NAME" -o jsonpath='{.spec.storageClassName}' 2>/dev/null || echo "unknown")
    echo "PVC exists."
    echo "  Current size: $CURRENT_SIZE"
    echo "  Storage class: $STORAGE_CLASS"
else
    echo "WARNING: PVC '$PVC_NAME' not found in namespace '$NAMESPACE'."
    echo "Make sure you're using the correct namespace."
fi
echo ""

# Detect the worker deployment name
WORKER_DEPLOYMENT="${HELM_RELEASE}-worker"

echo "The nfs-csi storage class does not support online expansion."
echo "You have two options:"
echo ""
echo "=============================================="
echo "OPTION 1: Delete and recreate the PVC"
echo "=============================================="
echo "(Recommended if /app/databases is empty - no data loss)"
echo ""
echo "This will DELETE the current PVC and all data in /app/databases."
echo "Since the databases directory is typically empty on fresh installs, this is safe."
echo ""
echo "Commands to run:"
echo ""
echo "  WARNING: You MUST scale down the worker deployment first,"
echo "           otherwise the PVC will stay stuck in 'Terminating'."
echo "           Kubernetes cannot delete a PVC while it is mounted by a running pod."
echo ""
echo "  # Step 0: Scale down worker deployment (releases PVC mount)"
echo "  ${KUBECTL} -n $NAMESPACE scale deployment $WORKER_DEPLOYMENT --replicas=0"
echo ""
echo "  # Step 1: Delete the existing PVC"
echo "  ${KUBECTL} -n $NAMESPACE delete pvc $PVC_NAME"
echo ""
echo "  # Step 2: Upgrade Helm with new size (update values.yaml first)"
echo "  helm upgrade --install $HELM_RELEASE bat3-chart/ --namespace $NAMESPACE"
echo ""
echo "  # Step 3: Verify new PVC size"
echo "  ${KUBECTL} -n $NAMESPACE get pvc $PVC_NAME"
echo ""

echo "=============================================="
echo "OPTION 2: Create a second PVC and migrate"
echo "=============================================="
echo "(Use if you have data to preserve)"
echo ""
echo "Create a new larger PVC, copy data, then switch the deployment."
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

# Quick helper to do Option 1 automatically
echo "----------------------------------------------"
echo "Quick Action: Delete PVC and recreate?"
echo "----------------------------------------------"
echo ""
echo "Run these commands manually to proceed with Option 1:"
echo ""
echo "  ${KUBECTL} -n $NAMESPACE scale deployment $WORKER_DEPLOYMENT --replicas=0 && \\"
echo "  ${KUBECTL} -n $NAMESPACE delete pvc $PVC_NAME && \\"
echo "  helm upgrade --install $HELM_RELEASE bat3-chart/ --namespace $NAMESPACE"
echo ""
