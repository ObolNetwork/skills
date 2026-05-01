#!/usr/bin/env bash
# DVpod health snapshot via bundled Prometheus + kubectl logs.
# Usage: health.sh [release] [namespace]
#   - With no args: auto-detects if there is exactly one dv-pod release.
#   - With release only: looks up its namespace via helm.

set -euo pipefail

RELEASE="${1:-}"
NAMESPACE="${2:-}"

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERROR: '$1' not found in PATH" >&2; exit 1; }
}
require helm; require kubectl; require curl; require jq

releases_json() { helm list -A --filter '.*dv-pod.*' -o json 2>/dev/null; }

if [[ -z "$RELEASE" && -z "$NAMESPACE" ]]; then
  rels=$(releases_json | jq -r '.[] | "\(.namespace)/\(.name)"')
  count=$(printf '%s\n' "$rels" | grep -c . || true)
  if [[ "$count" -eq 0 ]]; then
    echo "ERROR: no dv-pod helm releases found in any namespace" >&2; exit 1
  fi
  if [[ "$count" -gt 1 ]]; then
    echo "ERROR: multiple dv-pod releases found; pass <release> [namespace]:" >&2
    printf '  %s\n' $rels >&2
    exit 1
  fi
  line="$rels"
  NAMESPACE="${line%%/*}"
  RELEASE="${line##*/}"
elif [[ -n "$RELEASE" && -z "$NAMESPACE" ]]; then
  NAMESPACE=$(releases_json | jq -r ".[] | select(.name==\"$RELEASE\") | .namespace" | head -1)
  [[ -n "$NAMESPACE" ]] || { echo "ERROR: release '$RELEASE' not found in any namespace" >&2; exit 1; }
fi

echo "## DVpod: $RELEASE  (namespace: $NAMESPACE)"
echo

values=$(helm get values "$RELEASE" -n "$NAMESPACE" -o json)
central=$(echo "$values" | jq -r '.centralMonitoring.enabled // false')
nickname=$(echo "$values" | jq -r '.charon.nickname // ""')
bns=$(echo "$values" | jq -r '.charon.beaconNodeEndpoints[]?' | paste -sd, -)
fbns=$(echo "$values" | jq -r '.charon.fallbackBeaconNodeEndpoints[]?' | paste -sd, -)

echo "### Pre-flight"
echo "- nickname: ${nickname:-<unset>}"
echo "- beaconNodeEndpoints: ${bns:-<none>}"
[[ -n "$fbns" ]] && echo "- fallbackBeaconNodeEndpoints: $fbns"
echo "- centralMonitoring.enabled: $central"

if [[ "$central" != "true" ]]; then
  echo
  echo "ERROR: centralMonitoring is not enabled. This script targets the bundled Prometheus path." >&2
  echo "       Enable it via the dvpod skill, or query charon :3620 directly for spot checks." >&2
  exit 2
fi

LPORT=$(( RANDOM % 10000 + 30000 ))
PFLOG=$(mktemp)
kubectl port-forward -n "$NAMESPACE" svc/prometheus "${LPORT}:9090" >"$PFLOG" 2>&1 &
PF_PID=$!
trap 'kill "$PF_PID" 2>/dev/null || true; rm -f "$PFLOG"' EXIT

for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl -sG "http://localhost:${LPORT}/-/ready" >/dev/null 2>&1 && break
  sleep 0.5
done
if ! curl -sG "http://localhost:${LPORT}/-/ready" >/dev/null 2>&1; then
  echo "ERROR: prometheus port-forward did not become ready" >&2
  cat "$PFLOG" >&2
  exit 3
fi

PROM="http://localhost:${LPORT}"
q() { curl -sG "$PROM/api/v1/query" --data-urlencode "query=$1"; }

readyz=$(q 'app_monitoring_readyz' | jq -r '.data.result[0].value[1] // "no-data"')
active=$(q 'core_scheduler_validators_active' | jq -r '.data.result[0].value[1] // "no-data"')

echo
echo "### Health"
echo "- app_monitoring_readyz: $readyz   (1 = ready, anything else = degraded)"
echo "- core_scheduler_validators_active: $active"

echo
echo "### readyz histogram, last 30m"
curl -sG "$PROM/api/v1/query_range" \
  --data-urlencode 'query=app_monitoring_readyz' \
  --data-urlencode "start=$(date -u -d '30 minutes ago' +%s)" \
  --data-urlencode "end=$(date -u +%s)" \
  --data-urlencode 'step=60s' \
  | jq -r '[.data.result[0].values[]?[1]] | group_by(.) | map("  code=\(.[0]) count=\(length)") | .[]'

echo
self=$(q 'app_monitoring_readyz' | jq -r '.data.result[0].metric.cluster_peer // "unknown"')
echo "### Peers (this node: $self${nickname:+ / nickname=$nickname})"

peers_all=$(q 'p2p_peer_connection_types' | jq -r '.data.result[].metric.peer' | sort -u)
ping_kv=$(q 'p2p_ping_success' | jq -r '.data.result[] | "\(.metric.peer) \(.value[1])"')
conn_kv=$(q 'p2p_peer_connection_types' | jq -r '.data.result[] | "\(.metric.peer) \(.metric.type) \(.value[1])"')

remote_seen=0
while read -r p; do
  [[ -z "$p" || "$p" == "$self" ]] && continue
  remote_seen=$((remote_seen + 1))
  ping=$(awk -v p="$p" '$1==p{print $2; exit}' <<<"$ping_kv")
  direct=$(awk -v p="$p" '$1==p && $2=="direct"{print $3; exit}' <<<"$conn_kv")
  relay=$(awk -v p="$p" '$1==p && $2=="relay"{print $3; exit}' <<<"$conn_kv")
  ping_int=${ping%%.*};     ping_int=${ping_int:-0}
  direct_int=${direct%%.*}; direct_int=${direct_int:-0}
  relay_int=${relay%%.*};   relay_int=${relay_int:-0}

  if [[ "$ping_int" -gt 0 ]]; then
    if   [[ "$direct_int" -gt 0 ]]; then status="ok (direct)"
    elif [[ "$relay_int"  -gt 0 ]]; then status="ok (relayed)"
    else                                  status="ok (pinging, no active connection)"
    fi
  else
    status="UNREACHABLE (last ping failed)"
  fi
  printf "  %-20s ping=%s direct=%s relay=%s  %s\n" "$p" "$ping_int" "$direct_int" "$relay_int" "$status"
done <<< "$peers_all"

if [[ "$remote_seen" -eq 0 ]]; then
  echo "  (no remote peers detected — this node may be alone in the cluster, or metrics not yet populated)"
fi

echo
echo "### Beacon nodes seen by charon"
q 'app_beacon_node_version' | jq -r '.data.result[]? | "  - \(.metric.version)"'
echo "  peers reported by one BN: $(q 'app_beacon_node_peers' | jq -r '.data.result[0].value[1] // "no-data"')"

echo
echo "### Recent charon errors/warns (last 15m, deduped)"
pod=$(kubectl get pods -n "$NAMESPACE" -l "app.kubernetes.io/instance=$RELEASE" -o jsonpath='{.items[0].metadata.name}')
container=$(kubectl get pod "$pod" -n "$NAMESPACE" -o jsonpath='{range .spec.containers[*]}{.name}{"\n"}{end}' \
  | { grep -E '^(charon|dv-pod)$' || true; } | head -1)
container="${container:-charon}"
errs=$(kubectl logs -n "$NAMESPACE" "$pod" -c "$container" --since=15m 2>/dev/null \
  | { grep -E '"level":"(error|warn)"' || true; } \
  | jq -r '"\(.level | ascii_upcase) [\(.topic // "?")] \(.msg)"' 2>/dev/null \
  | sort | uniq -c | sort -rn | head -10) || true
if [[ -z "$errs" ]]; then
  echo "  (none)"
else
  printf '%s\n' "$errs" | sed 's/^/  /'
fi
