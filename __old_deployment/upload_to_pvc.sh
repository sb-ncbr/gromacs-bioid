#!/bin/bash
# Usage: ./upload_to_pvc.sh <local_folder> <pod_name> <namespace> [<remote_path_in_pod>] [<container_name>]
# Example: ./upload_to_pvc.sh ./data gmx-bioid-gmx-bioid-lts-databases-data pavlik-ns /databases
# ./upload_to_pvc.sh BAT2/databases gmx-bioid-gmx-bioid-worker-66bb775658-gpzbk gromacs-bioid-ns /app/databases
set -e

LOCAL_DIR="$1"
POD_NAME="$2"
NAMESPACE="$3"
REMOTE_PATH="${4:-/mnt/data}"
CONTAINER_NAME="${5:-}"

if [[ -z "$LOCAL_DIR" || -z "$POD_NAME" || -z "$NAMESPACE" ]]; then
  echo "Usage: $0 <local_folder> <pod_name> <namespace> [<remote_path_in_pod>] [<container_name>]"
  exit 1
fi

#if [[ ! -d "$LOCAL_DIR" ]]; then
#  echo "Error: local folder '$LOCAL_DIR' does not exist"
#  exit 1
#fi

echo "Uploading '$LOCAL_DIR' to pod '$POD_NAME:$REMOTE_PATH' in namespace '$NAMESPACE'..."

kubectl get pods -n pavlik-ns -o json | jq -r \
  '.items[] | select(.spec.volumes[]?.persistentVolumeClaim?.claimName == "gmx-bioid-gmx-bioid-lts-databases-data") | .metadata.name'

# Build kubectl cp command
if [[ -n "$CONTAINER_NAME" ]]; then
  kubectl cp "$LOCAL_DIR" "$NAMESPACE/$POD_NAME:$REMOTE_PATH" -c "$CONTAINER_NAME" -n "$NAMESPACE"
else
  kubectl cp "$LOCAL_DIR" "$NAMESPACE/$POD_NAME:$REMOTE_PATH" -n "$NAMESPACE"
fi

echo "✅ Upload completed successfully."
