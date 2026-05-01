---
name: dvpod-monitoring
description: |
  Read-only queries against metrics and logs from a deployed Obol DVpod on Kubernetes. Use when
  investigating cluster health, charon errors, peer connectivity, validator duty performance, or
  beacon node behavior on a running DVpod. For deploying, configuring, or modifying a DVpod
  (including enabling Prometheus or Loki shipping), use the `dvpod` skill. For Obol's hosted
  Grafana with cross-cluster fleet view, use the `obol-monitoring` skill.
user-invocable: true
disable-model-invocation: false
allowed-tools: Read, Grep, Glob, Bash, Bash(kubectl get *), Bash(kubectl logs *), Bash(helm list *), Bash(helm get values *), Bash(curl -sG *)
argument-hint: "[query type] [release] — e.g. health my-dv-pod, errors, peers, duties, logs"
---

# DVpod Monitoring — Read-Only Queries

You investigate the health and behavior of a running DVpod by querying its metrics and logs. **You never modify state** — no `helm upgrade`, no `kubectl apply`, no secret writes. If the user wants to enable monitoring, change values, or deploy anything, hand off to the `dvpod` skill.

## Scope and hand-offs

- **This skill:** queries against a single deployed DVpod's metrics/logs.
- **`dvpod` skill:** deploy, configure (including enabling Prometheus and configuring Loki shipping), upgrade, troubleshoot, destroy.
- **`obol-monitoring` skill:** Obol's hosted Grafana, fleet-wide view across clusters.

For namespace, release, pod, and current-values discovery, read [`skills/dvpod/discovery.md`](../dvpod/discovery.md).

## Pre-flight: detect what is wired up

Before any query, decide which path applies for **metrics** and **logs** by reading the release's current values:

```bash
helm get values <release> -n <namespace> -o json
```

### Metrics path (in priority order)

1. **Bundled Prometheus** — `centralMonitoring.enabled=true`. There will be a `prometheus` Service on port 9090 in the namespace:
   ```bash
   kubectl get svc prometheus -n <namespace>
   ```
   Query path: port-forward `svc/prometheus 9090` and hit the standard Prometheus HTTP API.
2. **Cluster Prometheus via ServiceMonitor** — `serviceMonitor.enabled=true`. Auto-discover a Prometheus the operator manages:
   ```bash
   kubectl get prometheus -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{"\n"}{end}' 2>/dev/null
   kubectl get svc -A -l app.kubernetes.io/name=prometheus 2>/dev/null
   kubectl get svc -A -l app=kube-prometheus-stack-prometheus 2>/dev/null
   ```
   Port-forward whichever service is found. If multiple, ask the user which.
3. **Direct Charon `/metrics`** — always available, but single-instance and text-format only:
   ```bash
   kubectl port-forward -n <namespace> <pod> 3620:3620
   ```
   Use for spot checks; PromQL aggregation is not available against this endpoint.
4. **Nothing wired up** — tell the user, and suggest enabling `centralMonitoring` via the `dvpod` skill.

### Logs path

- **`kubectl logs`** is always available and is the default. Works even on a stock deployment with no monitoring enabled.
- **LogQL via Loki** is only useful if the user has set `charon.lokiAddresses` to a real Loki *and* can give you a queryable Loki HTTP endpoint. The chart configures *push* only — query routing is the user's responsibility.

## Gather arguments

Use `AskUserQuestion` to clarify, but skip if the request is already specific.

1. **Investigation focus** — health snapshot, charon errors, peer connectivity, duty performance, beacon node, custom PromQL/LogQL.
2. **Time range** — default last 15m; ask if investigating a specific incident.
3. **Release scope** — usually inferred from discovery; only ask if more than one DVpod release is present.

## Execution

### PromQL via bundled or cluster Prometheus

```bash
# Run port-forward in the background, then query.
kubectl port-forward -n <namespace> svc/prometheus 9090:9090 >/dev/null 2>&1 &
PF_PID=$!
trap "kill $PF_PID 2>/dev/null" EXIT

PROM=http://localhost:9090

# Instant query
curl -sG "$PROM/api/v1/query" --data-urlencode 'query=<PROMQL>'

# Range query (last 15m, 30s step)
curl -sG "$PROM/api/v1/query_range" \
  --data-urlencode 'query=<PROMQL>' \
  --data-urlencode "start=$(date -u -d '15 minutes ago' +%s)" \
  --data-urlencode "end=$(date -u +%s)" \
  --data-urlencode 'step=30s'
```

### Direct Charon `/metrics` (no Prometheus)

```bash
kubectl port-forward -n <namespace> <pod> 3620:3620 >/dev/null 2>&1 &
PF_PID=$!
trap "kill $PF_PID 2>/dev/null" EXIT

# Pull the whole metrics dump and grep for what you need
curl -s localhost:3620/metrics | grep -E '^(app_monitoring_readyz|core_scheduler_validators_active|p2p_ping_success)'
```

### Logs via `kubectl logs`

```bash
# Recent charon log lines
kubectl logs -n <namespace> <pod> -c charon --tail=200

# Errors in last 15 minutes
kubectl logs -n <namespace> <pod> -c charon --since=15m | grep -iE 'error|warn'

# Validator client logs
kubectl logs -n <namespace> <pod> -c validator-client --since=15m

# Across replicas in a release (if the StatefulSet has more than one pod)
kubectl logs -n <namespace> -l app.kubernetes.io/instance=<release> -c charon --tail=100 --prefix
```

### Logs via LogQL (only if Loki is reachable)

```bash
LOKI=<user-provided-loki-base>
curl -sG "$LOKI/loki/api/v1/query_range" \
  --data-urlencode 'query={service_name="charon"} |= "error"' \
  --data-urlencode "start=$(date -u -d '15 minutes ago' +%s)000000000" \
  --data-urlencode "end=$(date -u +%s)000000000" \
  --data-urlencode 'limit=200'
```

For a query cookbook, see [queries.md](queries.md).

## Output handling

- Parse JSON; surface labels and values; flag anomalies.
- For range queries, summarise min/max/avg over the window and call out spikes.
- For logs, group by container or `cluster_peer` if present; show error/warn lines verbatim with timestamps; suppress repetitive noise.
- Always echo the **exact query that was run** so the user can re-run it themselves.
- If a query returns `"status":"error"`, surface the `error`/`errorType` and stop — do not invent results.

## Common diagnoses

When showing results, watch for and explicitly call out:

- **`app_monitoring_readyz != 1`** — node is not ready (BN unreachable, CL not synced, peer threshold not met).
- **High `p2p_ping_latency_secs` p90** — peer network is slow; check `p2p_peer_connection_types` for relayed vs direct.
- **`p2p_ping_success == 0`** for a peer — that operator is unreachable.
- **`core_scheduler_validators_active < cluster_validators`** — some validators not active yet (DKG just completed and deposit unconfirmed, or validator exited).
- **Error spikes in charon logs** — group by `topic` / `component` to identify the failing subsystem.
- **DKG sidecar polling forever** — see `skills/dvpod/troubleshooting.md` for the operator-address mismatch case.

## Capabilities and limits

- Read-only against a deployed DVpod's local metrics/logs.
- Cannot enable monitoring, change values, or modify the cluster — those belong to the `dvpod` skill.
- Direct Charon `/metrics` works without Prometheus but supports only point-in-time scalar lookups.
- LogQL requires the user to provide a queryable Loki URL — the chart only configures push.

## Parsing $ARGUMENTS

Parse the first word of `$ARGUMENTS` as the query type:

- `/dvpod-monitoring health [release]` — readyz, peers, active validators
- `/dvpod-monitoring errors [release]` — recent charon errors
- `/dvpod-monitoring peers [release]` — peer connectivity / ping latency
- `/dvpod-monitoring duties [release]` — duty success/failure breakdown
- `/dvpod-monitoring beacon [release]` — beacon node latency / errors
- `/dvpod-monitoring query <PROMQL>` — raw PromQL passthrough
- `/dvpod-monitoring logs [release] [pattern]` — search logs (kubectl or Loki depending on what is available)
- `/dvpod-monitoring` (no args) — auto-detect a release, run pre-flight, and offer the menu
