#!/bin/bash
# The paper's S7 pass (campaign_stats.py --full --sim) for one campaign arm,
# sharded across the repository-worker pods (idle after a rerun), using the
# scripts inside the deployed image (/app/scripts: the F-7 similarity
# engine). Successor of bioid_bughunt/scripts/g1_exports/{recompute_final,
# s7_verified}.sh, which ran on the retired bat3-ceitec-bat3-worker pods.
#
#   ARM=g2 [VERIFIED=1] [N=8] DATABASE_URL=postgresql://... s7_score.sh launch
#   ARM=g2 [VERIFIED=1] s7_score.sh status
#   ARM=g2 [VERIFIED=1] s7_score.sh merge OUT.json
#
# VERIFIED=1 = S7_VERIFIED_ONLY (verified hits only, BioID's order: the
# paper's headline table). REVALIDATE_ZEROS=1 recomputes cached 0.0
# similarities as they are read (GitHub #36) - back up
# /data/validation/sim_cache/pairs.jsonl first.
set -eu
NS=${NS:-ceitec-biodata-ns}
ARM=${ARM:?set ARM (e.g. g2)}
VERIFIED=${VERIFIED:-1}
TAG=$([ "$VERIFIED" = 1 ] && echo s7v || echo s7f)_$ARM
T=/data/validation/rerun-$ARM/s7
SELECTOR=${SELECTOR:-app=bat3-repo-worker}
CONTAINER=${CONTAINER:-repo-worker}
mapfile -t PODS < <(kubectl -n "$NS" get pods -l "$SELECTOR" --no-headers | awk '$3=="Running"{print $1}')
N=${N:-${#PODS[@]}}
[ "${#PODS[@]}" -gt 0 ] || { echo "no running pods for $SELECTOR"; exit 1; }
k() { kubectl -n "$NS" exec -c "$CONTAINER" "$1" -- sh -c "$2"; }
case ${1:-} in
launch)
  : "${DATABASE_URL:?set DATABASE_URL (the validation campaign database)}"
  k "${PODS[0]}" "mkdir -p $T"
  for s in $(seq 0 $((N - 1))); do
    P=${PODS[$((s % ${#PODS[@]}))]}
    k "$P" "cd /app/scripts && DATABASE_URL='$DATABASE_URL' S7_VERIFIED_ONLY=$VERIFIED \
      SIM_REVALIDATE_ZEROS=${REVALIDATE_ZEROS:-0} S7_SHARD=$s/$N S7_DUMP=$T/${TAG}_$s.jsonl \
      nohup python3 campaign_stats.py --full --sim --pattern results-$ARM.json --threads 4 \
      --sim-budget 100000000 --json-out $T/${TAG}_$s.json > $T/${TAG}_$s.log 2>&1 &"
    echo "shard $s/$N -> $P"
  done ;;
status)
  k "${PODS[0]}" "cd $T && for f in ${TAG}_*.log; do printf '%s ' \$f; grep -c 'JSON written' \$f || true; done" ;;
merge)
  OUT=${2:?merge OUT.json}
  tmp=$(mktemp -d)
  files=""
  for s in $(seq 0 $((N - 1))); do
    kubectl -n "$NS" cp -c "$CONTAINER" "${PODS[0]}:$T/${TAG}_$s.jsonl" "$tmp/${TAG}_$s.jsonl" >/dev/null
    files="$files $tmp/${TAG}_$s.jsonl"
  done
  python3 "$(dirname "$0")/s7_merge.py" "$OUT" $files | tail -40 ;;
*) echo "usage: ARM=<arm> $0 launch|status|merge OUT.json"; exit 2 ;;
esac
