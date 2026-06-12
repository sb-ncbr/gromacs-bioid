#!/usr/bin/env bash
# Usage: ./scripts/k8s/exec-into-pod.sh [pod-name]
#
# Default: exec into the worker pod. Otherwise specify pod name.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "${SCRIPT_DIR}/common.sh"

show_help() {
    cat <<HELP
Usage: $(basename "$0") [pod-name]

Exec into a bat3 pod with an interactive bash shell.

Arguments:
  pod-name    Name of the target pod (optional)
              If not specified, auto-detects the worker pod.

Options:
  -h, --help  Show this help message

Examples:
  $(basename "$0")              # Exec into worker pod (auto-detected)
  $(basename "$0") my-pod-123   # Exec into specific pod

Note: Falls back to /bin/sh if /bin/bash is not available in the container.
HELP
}

# Parse arguments
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    show_help
    exit 0
fi

POD_NAME="${1:-}"

# Resolve namespace
NAMESPACE="${NAMESPACE:-$(resolve_namespace)}"
if [[ -z "$NAMESPACE" ]]; then
    echo "Error: Could not detect namespace. Set NAMESPACE env var or ensure bat3-worker pods exist."
    exit 1
fi

# Auto-detect pod if not specified
if [[ -z "$POD_NAME" ]]; then
    # Try to find a worker pod first
    POD_NAME=$(${KUBECTL} -n "$NAMESPACE" get pods -l "app.kubernetes.io/instance=bat3,app.kubernetes.io/component=worker" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
    
    # Fallback to any pod with bat3 label
    if [[ -z "$POD_NAME" ]]; then
        POD_NAME=$(${KUBECTL} -n "$NAMESPACE" get pods -l "app=bat3-worker" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
    fi
    
    # Last resort: any running pod
    if [[ -z "$POD_NAME" ]]; then
        POD_NAME=$(${KUBECTL} -n "$NAMESPACE" get pods --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
    fi
    
    if [[ -z "$POD_NAME" ]]; then
        echo "Error: Could not auto-detect a pod in namespace '$NAMESPACE'."
        echo ""
        echo "Available pods:"
        ${KUBECTL} -n "$NAMESPACE" get pods --no-headers 2>/dev/null || echo "  (none)"
        echo ""
        echo "Specify a pod name explicitly:"
        echo "  $(basename "$0") <pod-name>"
        exit 1
    fi
    
    echo "Auto-detected pod: $POD_NAME"
fi

echo "=== Exec into Pod ==="
echo ""
echo "Pod: $POD_NAME"
echo "Namespace: $NAMESPACE"
echo ""

# Check if pod exists and is running
POD_STATUS=$(${KUBECTL} -n "$NAMESPACE" get pod "$POD_NAME" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
if [[ "$POD_STATUS" != "Running" ]]; then
    echo "Warning: Pod status is '$POD_STATUS' (not Running)."
    echo "Exec may fail if the container is not ready."
    echo ""
fi

# Try bash first, fall back to sh
echo "Connecting to $POD_NAME..."
echo "(Ctrl+] to disconnect, or type 'exit' to leave)"
echo ""

if ! ${KUBECTL} -n "$NAMESPACE" exec -it "$POD_NAME" -- /bin/bash 2>/dev/null; then
    echo ""
    echo "bash not available, trying sh..."
    ${KUBECTL} -n "$NAMESPACE" exec -it "$POD_NAME" -- /bin/sh
fi
