#!/usr/bin/env bash
# Usage: ./scripts/k8s/copy-script-to-pod.sh <pod-name>
#
# Copies the local populate_blast_databases.py into the pod.
# Useful for testing script changes without rebuilding the image.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "${SCRIPT_DIR}/common.sh"

# Local script to copy
LOCAL_SCRIPT="${SCRIPT_DIR}/../populate_blast_databases.py"
REMOTE_PATH="/app/scripts/populate_blast_databases.py"

show_help() {
    cat <<HELP
Usage: $(basename "$0") <pod-name>

Copy the local populate_blast_databases.py script into a running pod.
Useful for testing script changes without rebuilding the container image.

Arguments:
  pod-name    Name of the target pod (required)

Options:
  -h, --help  Show this help message

Examples:
  $(basename "$0") bat3-worker-abc123     # Copy to specific pod
  $(basename "$0") bat3-blast-db-download # Copy to download pod

Note: The script is copied to: $REMOTE_PATH
HELP
}

# Parse arguments
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    show_help
    exit 0
fi

POD_NAME="${1:-}"

if [[ -z "$POD_NAME" ]]; then
    echo "Error: Pod name is required."
    echo ""
    show_help
    exit 1
fi

# Check if local script exists
if [[ ! -f "$LOCAL_SCRIPT" ]]; then
    echo "Error: Local script not found: $LOCAL_SCRIPT"
    exit 1
fi

# Resolve namespace
NAMESPACE="${NAMESPACE:-$(resolve_namespace)}"
if [[ -z "$NAMESPACE" ]]; then
    echo "Error: Could not detect namespace. Set NAMESPACE env var or ensure bat3-worker pods exist."
    exit 1
fi

echo "=== Copy Script to Pod ==="
echo ""
echo "Source: $LOCAL_SCRIPT"
echo "Target: $POD_NAME:$REMOTE_PATH"
echo "Namespace: $NAMESPACE"
echo ""

# Check if pod exists
if ! ${KUBECTL} -n "$NAMESPACE" get pod "$POD_NAME" &>/dev/null; then
    echo "Error: Pod '$POD_NAME' not found in namespace '$NAMESPACE'."
    echo ""
    echo "Available pods:"
    ${KUBECTL} -n "$NAMESPACE" get pods --no-headers 2>/dev/null || echo "  (none)"
    exit 1
fi

# Check pod status
POD_STATUS=$(${KUBECTL} -n "$NAMESPACE" get pod "$POD_NAME" -o jsonpath='{.status.phase}' 2>/dev/null)
if [[ "$POD_STATUS" != "Running" ]]; then
    echo "Warning: Pod status is '$POD_STATUS' (not Running)."
    echo "Copy may fail if the container is not ready."
    echo ""
fi

echo "Copying script..."
print_kubectl -n "$NAMESPACE" cp "$LOCAL_SCRIPT" "$POD_NAME:$REMOTE_PATH"

${KUBECTL} -n "$NAMESPACE" cp "$LOCAL_SCRIPT" "$POD_NAME:$REMOTE_PATH"

if [[ $? -eq 0 ]]; then
    echo ""
    echo "Script copied successfully!"
    echo ""
    echo "To verify:"
    echo "  ${KUBECTL} -n $NAMESPACE exec -it $POD_NAME -- head -5 $REMOTE_PATH"
    echo ""
    echo "To run the updated script:"
    echo "  ${KUBECTL} -n $NAMESPACE exec -it $POD_NAME -- python $REMOTE_PATH --target-dir /app/databases"
else
    echo ""
    echo "Error: Failed to copy script."
    echo "Make sure the pod is running and the container is ready."
    exit 1
fi
