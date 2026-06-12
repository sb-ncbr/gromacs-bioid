#!/usr/bin/env bash
# Usage: ./scripts/k8s/scale-worker.sh [up|down|0|1|N]
#
# Scale the bat3 worker deployment.
# Default: toggle between 0 and 1.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "${SCRIPT_DIR}/common.sh"

show_help() {
    cat <<HELP
Usage: $(basename "$0") [up|down|0|1|N]

Scale the bat3 worker deployment.

Arguments:
  up      Scale to 1 replica
  down    Scale to 0 replicas
  0       Scale to 0 replicas
  1       Scale to 1 replica
  N       Scale to N replicas (any positive integer)
  
  (no arg) Toggle: if currently 0 → 1, if >0 → 0

Options:
  -h, --help  Show this help message

Examples:
  $(basename "$0")          # Toggle on/off
  $(basename "$0") up       # Scale up
  $(basename "$0") down     # Scale down
  $(basename "$0") 3        # Scale to 3 replicas
HELP
}

# Parse arguments
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    show_help
    exit 0
fi

# Resolve namespace
NAMESPACE="${NAMESPACE:-$(resolve_namespace)}"
if [[ -z "$NAMESPACE" ]]; then
    echo "Error: Could not detect namespace. Set NAMESPACE env var or ensure bat3-worker pods exist."
    exit 1
fi

# Detect deployment
DEPLOYMENT="${DEPLOYMENT:-$(detect_worker_deployment)}"
if [[ -z "$DEPLOYMENT" ]]; then
    echo "Error: Could not detect worker deployment in namespace '$NAMESPACE'."
    echo "Set DEPLOYMENT env var explicitly."
    exit 1
fi

echo "Namespace: $NAMESPACE"
echo "Deployment: $DEPLOYMENT"
echo ""

# Get current replica count
CURRENT_REPLICAS=$(${KUBECTL} -n "$NAMESPACE" get deployment "$DEPLOYMENT" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
echo "Current replicas: $CURRENT_REPLICAS"

# Determine target replicas
TARGET_REPLICAS=""
ARG="${1:-}"

if [[ -z "$ARG" ]]; then
    # Toggle
    if [[ "$CURRENT_REPLICAS" -eq 0 ]]; then
        TARGET_REPLICAS=1
    else
        TARGET_REPLICAS=0
    fi
elif [[ "$ARG" == "up" ]]; then
    TARGET_REPLICAS=1
elif [[ "$ARG" == "down" ]]; then
    TARGET_REPLICAS=0
elif [[ "$ARG" =~ ^[0-9]+$ ]]; then
    TARGET_REPLICAS="$ARG"
else
    echo "Error: Invalid argument '$ARG'. Use 'up', 'down', or a number."
    echo "Run '$(basename "$0") --help' for usage."
    exit 1
fi

echo "Target replicas: $TARGET_REPLICAS"
echo ""

# Scale the deployment
echo "Scaling deployment..."
print_kubectl -n "$NAMESPACE" scale deployment/"$DEPLOYMENT" --replicas="$TARGET_REPLICAS"
${KUBECTL} -n "$NAMESPACE" scale deployment/"$DEPLOYMENT" --replicas="$TARGET_REPLICAS"

# Wait for pods to settle
echo ""
echo "Waiting for pods to settle..."

if [[ "$TARGET_REPLICAS" -eq 0 ]]; then
    # Wait for all pods to terminate
    TIMEOUT=60
    ELAPSED=0
    while [[ $ELAPSED -lt $TIMEOUT ]]; do
        POD_COUNT=$(${KUBECTL} -n "$NAMESPACE" get pods -l "app.kubernetes.io/instance=${DEPLOYMENT%-worker}" --field-selector=status.phase!=Terminated --no-headers 2>/dev/null | wc -l || echo "0")
        if [[ "$POD_COUNT" -eq 0 ]]; then
            echo "All pods terminated."
            break
        fi
        echo "  Waiting... ($POD_COUNT pods remaining)"
        sleep 2
        ELAPSED=$((ELAPSED + 2))
    done
    if [[ $ELAPSED -ge $TIMEOUT ]]; then
        echo "Warning: Timeout waiting for pods to terminate."
    fi
else
    # Wait for pods to be ready
    TIMEOUT=120
    ELAPSED=0
    while [[ $ELAPSED -lt $TIMEOUT ]]; do
        READY_PODS=$(${KUBECTL} -n "$NAMESPACE" get deployment "$DEPLOYMENT" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        if [[ "${READY_PODS:-0}" -ge "$TARGET_REPLICAS" ]]; then
            echo "Pods ready: $READY_PODS/$TARGET_REPLICAS"
            break
        fi
        echo "  Waiting... ($READY_PODS/$TARGET_REPLICAS ready)"
        sleep 2
        ELAPSED=$((ELAPSED + 2))
    done
    if [[ $ELAPSED -ge $TIMEOUT ]]; then
        echo "Warning: Timeout waiting for pods to be ready."
    fi
fi

echo ""
echo "Done."

# Print final status
${KUBECTL} -n "$NAMESPACE" get deployment "$DEPLOYMENT" -o wide
