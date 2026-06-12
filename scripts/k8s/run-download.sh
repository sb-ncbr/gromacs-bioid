#!/usr/bin/env bash
# Usage: ./scripts/k8s/run-download.sh [--databases db1,db2,...] [--follow]
#
# Run the BLAST database download as a standalone pod.
# Advantages over Job:
#   - Logs accessible until pod is deleted
#   - No backoff limit (pod restarts on its own if it fails)
#   - Easy to exec into for troubleshooting

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "${SCRIPT_DIR}/common.sh"

POD_NAME="bat3-blast-db-download"
IMAGE="${DOWNLOAD_IMAGE:-cerit.io/tomsko/bat3-worker:latest}"
PVC_NAME="bat3-bat3-databases-data"
DATABASES=""
FOLLOW=false
WORKER_DEPLOYMENT=""

show_help() {
    cat <<HELP
Usage: $(basename "$0") [--databases db1,db2,...] [--follow] [--image IMAGE]

Run the BLAST database download as a standalone pod (not a Job).

Advantages over using a Job:
  - Logs remain accessible until pod is explicitly deleted
  - No backoff limit - pod can restart on failure
  - Easy to exec into for troubleshooting

Options:
  --databases LIST  Comma-separated list of databases to download
                    (default: all configured databases)
  --follow, -f      Wait for pod to start and stream logs
  --image IMAGE     Container image to use (default: $IMAGE)
  --keep            Don't scale worker back up automatically
  -h, --help        Show this help message

After completion:
  To delete the pod:    kubectl -n <namespace> delete pod $POD_NAME
  To view logs:         $(basename "$0") --follow
  To exec into pod:     kubectl -n <namespace> exec -it $POD_NAME -- bash

Examples:
  $(basename "$0")                      # Download all databases
  $(basename "$0") --databases nt,nr    # Download specific databases
  $(basename "$0") -f                   # Run and follow logs
HELP
}

# Parse arguments
KEEP_WORKER=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --databases)
            DATABASES="$2"
            shift 2
            ;;
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        --image)
            IMAGE="$2"
            shift 2
            ;;
        --keep)
            KEEP_WORKER=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown argument '$1'"
            show_help
            exit 1
            ;;
    esac
done

# Resolve namespace
NAMESPACE="${NAMESPACE:-$(resolve_namespace)}"
if [[ -z "$NAMESPACE" ]]; then
    echo "Error: Could not detect namespace. Set NAMESPACE env var or ensure bat3-worker pods exist."
    exit 1
fi

echo "=== BLAST Database Download Pod ==="
echo ""
echo "Namespace: $NAMESPACE"
echo "Pod name: $POD_NAME"
echo "Image: $IMAGE"
echo "PVC: $PVC_NAME"
if [[ -n "$DATABASES" ]]; then
    echo "Databases: $DATABASES"
else
    echo "Databases: all (default)"
fi
echo ""

# Check if pod already exists
if ${KUBECTL} -n "$NAMESPACE" get pod "$POD_NAME" &>/dev/null; then
    echo "Warning: Pod '$POD_NAME' already exists in namespace '$NAMESPACE'."
    echo ""
    echo "Current pod status:"
    ${KUBECTL} -n "$NAMESPACE" get pod "$POD_NAME" -o wide
    echo ""
    echo "Options:"
    echo "  1. Delete existing pod and create new one:"
    echo "     ${KUBECTL} -n $NAMESPACE delete pod $POD_NAME"
    echo "  2. View logs from existing pod:"
    echo "     ${KUBECTL} -n $NAMESPACE logs $POD_NAME"
    echo "  3. Exec into existing pod:"
    echo "     ${KUBECTL} -n $NAMESPACE exec -it $POD_NAME -- bash"
    echo ""
    echo "Aborting. Delete the existing pod first or use one of the commands above."
    exit 1
fi

# Scale worker to 0 to avoid PVC conflicts
if [[ "$KEEP_WORKER" != "true" ]]; then
    WORKER_DEPLOYMENT=$(detect_worker_deployment)
    if [[ -n "$WORKER_DEPLOYMENT" ]]; then
        echo "Scaling down worker deployment ($WORKER_DEPLOYMENT) to avoid PVC conflicts..."
        CURRENT_REPLICAS=$(${KUBECTL} -n "$NAMESPACE" get deployment "$WORKER_DEPLOYMENT" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
        echo "  Current replicas: $CURRENT_REPLICAS"
        ${KUBECTL} -n "$NAMESPACE" scale deployment "$WORKER_DEPLOYMENT" --replicas=0
        
        # Wait for worker pods to terminate
        echo "  Waiting for worker pods to terminate..."
        TIMEOUT=60
        ELAPSED=0
        while [[ $ELAPSED -lt $TIMEOUT ]]; do
            POD_COUNT=$(${KUBECTL} -n "$NAMESPACE" get pods -l "app.kubernetes.io/instance=${WORKER_DEPLOYMENT%-worker}" --field-selector=status.phase!=Terminated,status.phase!=Succeeded --no-headers 2>/dev/null | wc -l || echo "0")
            if [[ "$POD_COUNT" -eq 0 ]]; then
                echo "  Worker pods terminated."
                break
            fi
            sleep 2
            ELAPSED=$((ELAPSED + 2))
        done
    else
        echo "Note: Could not detect worker deployment. Skipping scale-down."
    fi
fi

echo ""
echo "Creating download pod..."

# Build command arguments
CMD_ARGS='["python", "/app/scripts/populate_blast_databases.py", "--target-dir", "/app/databases"]'
if [[ -n "$DATABASES" ]]; then
    CMD_ARGS='["python", "/app/scripts/populate_blast_databases.py", "--target-dir", "/app/databases", "--databases", "'"$DATABASES"'"]'
fi

# Create pod manifest
cat <<PODMANIFEST | ${KUBECTL} -n "$NAMESPACE" apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: ${POD_NAME}
  labels:
    app: bat3-db-download
spec:
  restartPolicy: OnFailure
  containers:
    - name: download
      image: ${IMAGE}
      imagePullPolicy: Always
      command:
        - python
        - /app/scripts/populate_blast_databases.py
        - --target-dir
        - /app/databases
$(if [[ -n "$DATABASES" ]]; then echo "        - --databases"; echo "        - \"${DATABASES}\""; fi)
      volumeMounts:
        - name: databases-data
          mountPath: /app/databases
      resources:
        requests:
          memory: "512Mi"
          cpu: "250m"
        limits:
          memory: "4Gi"
          cpu: "2"
  volumes:
    - name: databases-data
      persistentVolumeClaim:
        claimName: ${PVC_NAME}
PODMANIFEST

echo ""
echo "Pod created successfully."
echo ""

if [[ "$FOLLOW" == "true" ]]; then
    echo "Waiting for pod to start..."
    
    # Wait for pod to be running
    TIMEOUT=120
    ELAPSED=0
    while [[ $ELAPSED -lt $TIMEOUT ]]; do
        PHASE=$(${KUBECTL} -n "$NAMESPACE" get pod "$POD_NAME" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
        if [[ "$PHASE" == "Running" || "$PHASE" == "Succeeded" || "$PHASE" == "Failed" ]]; then
            echo "Pod status: $PHASE"
            break
        fi
        echo "  Waiting... (current: $PHASE)"
        sleep 2
        ELAPSED=$((ELAPSED + 2))
    done
    
    if [[ $ELAPSED -ge $TIMEOUT ]]; then
        echo "Warning: Timeout waiting for pod to start."
    fi
    
    echo ""
    echo "=== Logs (Ctrl+C to stop following) ==="
    echo ""
    ${KUBECTL} -n "$NAMESPACE" logs "$POD_NAME" -f
else
    echo "Pod is starting. Use these commands:"
    echo ""
    echo "  Follow logs:         $(basename "$0") --follow"
    echo "  View status:         ${KUBECTL} -n $NAMESPACE get pod $POD_NAME -o wide"
    echo "  View logs:           ${KUBECTL} -n $NAMESPACE logs $POD_NAME"
    echo "  Exec into pod:       ${KUBECTL} -n $NAMESPACE exec -it $POD_NAME -- bash"
    echo ""
    echo "When finished:"
    echo "  Delete pod:          ${KUBECTL} -n $NAMESPACE delete pod $POD_NAME"
    if [[ -n "$WORKER_DEPLOYMENT" && "$KEEP_WORKER" != "true" ]]; then
        echo "  Scale worker up:     ${KUBECTL} -n $NAMESPACE scale deployment $WORKER_DEPLOYMENT --replicas=1"
    fi
fi

echo ""
echo "Done."
