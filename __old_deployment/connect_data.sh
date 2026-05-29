#!/bin/bash
pod_id=$(kubectl get pods -n gromacs-bioid-ns -o json | jq -r '.items[] | select(.spec.volumes[]?.persistentVolumeClaim?.claimName == "gmx-bioid-gmx-bioid-annotation-data") | .metadata.name' | grep api)
kubectl exec -it "$pod_id" -n gromacs-bioid-ns -- /bin/sh
