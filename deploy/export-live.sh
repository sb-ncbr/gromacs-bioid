#!/bin/bash
# Export BioID's production objects to deploy/live/*.yaml, the source of
# truth since the helm chart was retired (2026-11-17). Run after any change
# made outside deploy/release.sh, review `git diff deploy/live`, commit.
#
# Cluster bookkeeping (status, uids, revisions, managed fields) is dropped.
# Refuses to write when a manifest carries a literal secret (an env value
# named *PASSWORD*, *SECRET*, *TOKEN*, *_KEY or DATABASE_URL, or a URL with
# a password in it): move it into the bioid-api-secrets Secret and reference
# it with secretKeyRef first. Not exported: Secrets themselves, the
# validation-* deployments and the dm1 dark-matter worker (separate projects).
set -euo pipefail
NS=ceitec-biodata-ns
OUT=$(cd "$(dirname "$0")" && pwd)/live
OBJECTS=(
  deploy/bat3-ceitec-bat3-api deploy/bat3-ceitec-bat3-worker deploy/bat3-ui-worker deploy/bat3-repo-worker
  deploy/bat3-ceitec-bat3-web deploy/bat3-redis deploy/bioid-cache-redis
  deploy/bioid-mcp deploy/validation-docs
  svc/bat3-ceitec-bat3-api svc/bat3-ceitec-bat3-web svc/bat3-redis svc/bioid-cache-redis
  svc/bioid-mcp svc/validation-docs
  ingress/bat3-ceitec-bat3-ingress
)
mkdir -p "$OUT"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
for o in "${OBJECTS[@]}"; do
  kubectl -n $NS get "$o" -o json > "$tmp/$(tr / - <<<"$o").json"
done
python3 - "$tmp" "$OUT" <<'EOF'
import json, re, sys
from pathlib import Path
import yaml

src, out = Path(sys.argv[1]), Path(sys.argv[2])
SECRET_NAME = re.compile(r"(PASSWORD|SECRET|TOKEN|_KEY$|^DATABASE_URL$)", re.I)
URL_PASSWORD = re.compile(r"://[^/@\s:]+:[^/@\s]+@")
DROP_META = ("uid", "resourceVersion", "creationTimestamp", "generation", "managedFields", "selfLink")
DROP_ANN = ("deployment.kubernetes.io/revision", "kubectl.kubernetes.io/last-applied-configuration",
            "kubectl.kubernetes.io/restartedAt")
problems = []

def clean(obj):
    obj.pop("status", None)
    meta = obj.get("metadata", {})
    for k in DROP_META:
        meta.pop(k, None)
    for k in DROP_ANN:
        (meta.get("annotations") or {}).pop(k, None)
    tmpl = ((obj.get("spec") or {}).get("template") or {}).get("metadata") or {}
    for k in DROP_ANN:
        (tmpl.get("annotations") or {}).pop(k, None)
    if obj.get("kind") == "Service":
        for k in ("clusterIP", "clusterIPs"):
            obj["spec"].pop(k, None)
    return obj

def check(name, obj):
    spec = ((obj.get("spec") or {}).get("template") or {}).get("spec") or {}
    for c in spec.get("containers", []) + spec.get("initContainers", []):
        for e in c.get("env") or []:
            v = e.get("value")
            if v is None:
                continue
            if SECRET_NAME.search(e["name"]) or URL_PASSWORD.search(str(v)):
                problems.append(f"{name}: container {c['name']} env {e['name']} is a literal value")

for f in sorted(src.glob("*.json")):
    obj = clean(json.loads(f.read_text()))
    check(f.stem, obj)
    obj["__file"] = f.stem
    f.write_text(json.dumps(obj))
if problems:
    print("REFUSED, literal secrets (nothing written):", *problems, sep="\n  ")
    sys.exit(1)
for f in sorted(src.glob("*.json")):
    obj = json.loads(f.read_text()); name = obj.pop("__file")
    (out / f"{name}.yaml").write_text(
        "# Exported from ceitec-biodata-ns by deploy/export-live.sh; do not edit by hand\n"
        "# without applying the same change to the cluster.\n" + yaml.safe_dump(obj, sort_keys=False))
    print("wrote", out / f"{name}.yaml")
EOF
