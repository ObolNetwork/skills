# DVpod Discovery

Shared helper for finding the namespace, helm release, pod, and current values of a deployed DVpod. Used by both the `dvpod` skill (deploy/manage) and the `dvpod-monitoring` skill (read-only queries). In the Obol Stack, prefix every command with `obol` (`obol helm …`, `obol kubectl …`).

## Find the namespace

Try in order:

1. User-specified namespace.
2. Existing DVpod releases across all namespaces:
   ```bash
   helm list -A -o json | jq -r '.[] | select(.chart | startswith("dv-pod-")) | "\(.namespace)\t\(.name)\t\(.chart)"'
   ```
3. Default `dv-pod`.

If multiple namespaces have DVpod releases, ask the user which to target.

## Find the release

```bash
helm list -n <namespace> -o json | jq -r '.[] | select(.chart | startswith("dv-pod-")) | .name'
```

Multiple releases can share a namespace. Each has its own ENR, pod, PVCs, and (if enabled) ServiceMonitor — never assume there is only one.

`<fullname>` (used in resource names) is the release name if it contains `dv-pod`, else `<release>-dv-pod`.

## Find the pod

```bash
kubectl get pods -n <namespace> \
  -l app.kubernetes.io/instance=<release> \
  -o jsonpath='{.items[0].metadata.name}'
```

## Containers in the pod

| Container | Purpose |
|---|---|
| `dv-pod` | Charon middleware (named after the chart) — metrics, `/readyz` on `:3620` |
| `validator-client` | Lighthouse / Teku / Prysm / Nimbus / Lodestar |
| `dkg-sidecar` (init) | Finds and validates the cluster definition, waits for signatures, writes the status ConfigMap |
| `charon-dkg` (init) | Runs `charon dkg` with the chart's charon image (`dkg.runner: charon`) |
| `dkg-report` (init) | Records the DKG result in the status ConfigMap |
| `prepare-validator-data`, `import-keystores` / `prysm-wallet-import` / `nimbus-import` (init) | Load key shares into the VC |

Public ConfigMaps (charts ≥ 0.22, readable without Secret access): `<fullname>-enr` (`enr`, `secretName`) and `<fullname>-dkg-status` (`phase`, `message`, `signatures`, `configHash`, `lockHash`, …).

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
| `mode` | auto / launchpad / definition / lock / lockHash |
| `validatorClient.type` | Which VC implementation is running |
