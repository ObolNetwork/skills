# Query Cookbook

Curated PromQL and LogQL examples for a deployed DVpod. PromQL examples assume you have port-forwarded a Prometheus that scrapes Charon (either the bundled `prometheus` service or your cluster Prometheus via ServiceMonitor).

`cluster_name` is set on Charon metrics from cluster-lock metadata once DKG has completed (usually matches the cluster's nickname). `cluster_peer` distinguishes nodes within a cluster. Substitute real values before running, or drop the filter if you only have one DVpod scraped.

## PromQL — Cluster health

```promql
# Is this node ready? 1 = ready, anything else = degraded.
app_monitoring_readyz{cluster_name="$CLUSTER_NAME"}

# Active validators on the local node
core_scheduler_validators_active{cluster_name="$CLUSTER_NAME"}

# Total validators in the cluster (from cluster-lock)
cluster_validators{cluster_name="$CLUSTER_NAME"}

# Operators and consensus threshold
cluster_operators{cluster_name="$CLUSTER_NAME"}
cluster_threshold{cluster_name="$CLUSTER_NAME"}
```

## PromQL — Peer connectivity

```promql
# Per-peer ping success (0 = peer unreachable)
sum by (cluster_peer, peer) (p2p_ping_success{cluster_name="$CLUSTER_NAME"})

# p90 ping latency by peer over 5m
histogram_quantile(
  0.90,
  sum by (le, peer) (
    rate(p2p_ping_latency_secs_bucket{cluster_name="$CLUSTER_NAME"}[5m])
  )
)

# Connection type breakdown (direct vs relayed)
max by (peer, type) (p2p_peer_connection_types{cluster_name="$CLUSTER_NAME"})
```

## PromQL — Duty performance

```promql
# Successful duties per type, last 5m
sum by (duty) (
  increase(core_tracker_success_duties_total{cluster_name="$CLUSTER_NAME"}[5m])
)

# Failed duties per type, last 5m (should be near zero)
sum by (duty, reason) (
  increase(core_tracker_failed_duties_total{cluster_name="$CLUSTER_NAME"}[5m])
)
```

## PromQL — Beacon node health

```promql
# BN call latency p95 by endpoint
histogram_quantile(
  0.95,
  sum by (le, endpoint) (
    rate(app_beacon_node_latency_secs_bucket{cluster_name="$CLUSTER_NAME"}[5m])
  )
)

# BN errors per endpoint
sum by (endpoint) (
  rate(app_beacon_node_errors_total{cluster_name="$CLUSTER_NAME"}[5m])
)

# Detected BN client per peer (useful for diversity audit)
max by (cluster_peer, beacon_id) (
  app_beacon_node_version{cluster_name="$CLUSTER_NAME"}
)
```

## PromQL — Health checks / alerts

```promql
# Currently failing health checks, with severity and description
max by (name, severity, description) (
  app_health_checks_failed_total{cluster_name="$CLUSTER_NAME"} > 0
)
```

## kubectl logs — first-line log search

`kubectl logs` is always available, regardless of monitoring config. Prefer it for ad-hoc debugging.

```bash
# Recent charon errors / warnings
kubectl logs -n <ns> <pod> -c charon --since=15m | grep -iE 'error|warn'

# Filter charon by component (logs are JSON when logFormat=json, the default)
kubectl logs -n <ns> <pod> -c charon --since=15m | jq -c 'select(.component=="p2p" and .level=="error")'

# Lines around a specific slot
kubectl logs -n <ns> <pod> -c charon --since=1h | grep 'slot=12345678'

# Validator client missed duties
kubectl logs -n <ns> <pod> -c validator-client --since=15m | grep -i 'missed\|fail'

# Tail across all replicas of a release
kubectl logs -n <ns> -l app.kubernetes.io/instance=<release> -c charon --tail=100 --prefix
```

## LogQL — for users with Charon shipping to Loki

These only work if `charon.lokiAddresses` is set and the user provides a queryable Loki endpoint. Label set depends on the user's Loki ingest config; the examples below assume Charon's default labels (`service`, `level`).

```logql
# All charon errors in the window
{service="charon"} |= "error"

# Errors excluding noisy known-benign topics
{service="charon"} |= "error" != "context canceled"

# Filter by component (charon logs as JSON by default)
{service="charon"} | json | component="p2p" | level="error"

# Logs around a specific slot
{service="charon"} |= "slot=12345678"

# Rate of errors per minute
sum(rate({service="charon"} |= "error" [1m]))
```

## Tips

- All Charon metrics carry `cluster_peer` — add `by (cluster_peer)` to fan out per-operator.
- If a metric returns nothing, first check that the Prometheus you queried actually scrapes Charon. With the bundled Prom this is automatic; with a cluster Prom it depends on the ServiceMonitor selector matching.
- `kubectl logs --since=...` is your friend for incident timelines — the value of having Loki configured is multi-pod / multi-node aggregation, not single-pod debugging.
- For per-component or per-level filtering, leave `charon.logFormat=json` (the default) — it makes `jq` and LogQL filtering far easier than `logfmt`.
