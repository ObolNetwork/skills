# DVpod Discovery

Shared helper for finding the namespace, helm release, pod, and current values of a deployed DVpod. Used by both the `dvpod` skill (deploy/manage) and the `dvpod-monitoring` skill (read-only queries).

## Find the namespace

Try in order:

1. User-specified namespace.
2. Existing DVpod releases across all namespaces:
   ```bash
   helm list -A --filter ".*dv-pod.*" -o json | jq -r '.[] | "\(.namespace)\t\(.name)"'
   ```
3. Default `dv-pod`.

If multiple namespaces have DVpod releases, ask the user which to target.

## Find the release

```bash
helm list -n <namespace> --filter ".*dv-pod.*" -o json | jq -r '.[].name'
```

Multiple releases can share a namespace. Each has its own ENR, pod, PVCs, and (if enabled) ServiceMonitor — never assume there is only one.

## Find the pod

```bash
kubectl get pods -n <namespace> \
  -l app.kubernetes.io/instance=<release> \
  -o jsonpath='{.items[0].metadata.name}'
```

## Containers in the pod

| Container | Purpose |
|---|---|
| `charon` | Charon middleware — main process, exposes metrics on `:3620` |
| `validator-client` | Lighthouse / Teku / Prysm / Nimbus / Lodestar |
| `dkg-sidecar` | DKG orchestration; only active during cluster setup |
| `import-keystores` | Init container; runs once after DKG to load keys into VC |

## Resolve current values

```bash
helm get values <release> -n <namespace> -o json
```

Keys to inspect when reasoning about monitoring/logging:

| Key | Meaning |
|---|---|
| `centralMonitoring.enabled` | Bundled Prometheus pod is deployed in this namespace |
| `centralMonitoring.promEndpoint` | Where the bundled Prom remote-writes |
| `serviceMonitor.enabled` | A ServiceMonitor CRD exists for an external Prometheus Operator |
| `charon.lokiAddresses` | Charon ships logfmt logs to this Loki endpoint (push only) |
| `charon.nickname` | Appears as `cluster_name` label on Charon metrics |
| `charon.logLevel` / `logFormat` | Verbosity and structure of stderr logs |
| `network` | mainnet / sepolia / hoodi |
| `validatorClient.type` | Which VC implementation is running |
