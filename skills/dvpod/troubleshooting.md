# DVpod Troubleshooting Reference

## Diagnostic Checklist

Run these in order when troubleshooting a DVpod deployment (Obol Stack: prefix with `obol`):

```bash
# 0. Where is it? (charts >= 0.22)
kubectl get configmap <fullname>-dkg-status -n <ns> -o jsonpath='{.data.phase}{"\n"}{.data.message}{"\n"}'

# 1. Check pod status
kubectl get pods -n <ns> -l app.kubernetes.io/instance=<release> -o wide

# 2. Check events for errors
kubectl get events -n <ns> --sort-by='.lastTimestamp' --field-selector involvedObject.kind=Pod | tail -20

# 3. Check ENR job completion
kubectl get jobs -n <ns> -l app.kubernetes.io/instance=<release>
kubectl logs job/<fullname>-enr-job -n <ns>

# 4. Check DKG sidecar, then the DKG ceremony (dkg.runner: charon)
kubectl logs -n <ns> <pod> -c dkg-sidecar --tail=50
kubectl logs -n <ns> <pod> -c charon-dkg --tail=50

# 5. Check Charon (container named dv-pod)
kubectl logs -n <ns> <pod> -c dv-pod --tail=50

# 6. Check validator client
kubectl logs -n <ns> <pod> -c validator-client --tail=50

# 7. Check PVCs
kubectl get pvc -n <ns> -l app.kubernetes.io/instance=<release>

# 8. Check the ENR ConfigMap (public) — it names the Secret in .data.secretName
kubectl get configmap <fullname>-enr -n <ns> -o jsonpath='{.data.enr}{"\n"}{.data.secretName}{"\n"}'
```

## Common Issues

### Interpreting Results Quickly

- `WaitingForInvite` / `WaitingForSignatures` are normal until every operator has signed; persistent `WaitingForInvite` usually means an operator-address or ENR mismatch.
- `DefinitionReady` / `RunningDKG` that don't move: other operators' pods aren't online, or run a different charon minor.
- Phase not `Complete` / `LockPresent` (or, on charts < 0.22, no `/charon-data/cluster-lock.json`) means the DKG has not completed.
- Charon restart loops with beacon errors usually indicate bad/unreachable `charon.beaconNodeEndpoints`.
- Healthy pods but no DKG progress usually means external coordination (other operators) is incomplete.

### Pod stuck in Pending

**Symptoms:** Pod stays in `Pending` state.

**Causes & Fixes:**
- **Insufficient resources:** Check node capacity. Charon needs 1 CPU + 2Gi RAM minimum.
  ```bash
  kubectl describe pod <pod> -n <ns> | grep -A5 "Events"
  kubectl top nodes
  ```
- **PVC not binding:** StorageClass may not support `ReadWriteOnce` or no available PVs.
  ```bash
  kubectl get pvc -n <ns>
  kubectl get storageclass
  ```
- **Node selector/tolerations:** Check if nodeSelector or tolerations are misconfigured.

### ENR Job Failed

**Symptoms:** ENR job shows `Failed` or `BackoffLimitExceeded`.

**Causes & Fixes:**
- **RBAC issue:** The ENR job needs permission to create secrets.
  ```bash
  kubectl logs job/<release>-dv-pod-enr-job -n <ns>
  kubectl get role,rolebinding -n <ns> | grep enr
  ```
- **Image pull failure:** Check if the charon image is accessible.
- **"refusing to overwrite"**: the ENR Secret exists without the private-key field. The job never overwrites an identity; fix or (only if this identity is in no cluster) delete the Secret. Key names: `charon-enr-private-key` and `enr` (or `charon.enr.existingSecret.*DataKey`). Don't inspect the Secret yourself; ask the user to check which data keys it has.

### DKG Sidecar Polling Forever

**Symptoms:** DKG sidecar logs show repeated polling with no cluster found. Logs show cluster definitions
but say "No invite found" for all of them.

**Causes & Fixes:**
- **ENR mismatch:** the operator pasted an ENR on the Launchpad that isn't this pod's (e.g. one generated on a laptop). Compare the pod's `<fullname>-enr` ConfigMap with the ENR in the definition.
- **Operator address mismatch (most common):** Each release's `charon.operatorAddress` must exactly
  match the address assigned to that node's ENR on the Launchpad. For group clusters, each node
  typically has a different operator address. Verify with:
  ```bash
  helm get values <release> -n <ns> | grep operatorAddress
  ```
  Fix (DKG not done yet, so restarting is harmless): `helm upgrade <release> obol/dv-pod -n <ns> --version <current-chart-version> --reuse-values --set charon.operatorAddress=<correct-address>` (the upgrade restarts the pod).
- **Cluster not fully confirmed:** ALL operators must accept/sign on the Launchpad before the
  sidecar will detect the invite. Check the Launchpad cluster page to see which operators are pending.
- **Solo cluster:** Launchpad mode only finds group-cluster invites. For one person running every node, use the direct route (`mode: definition`).
- **Wrong targetConfigHash:** If set, verify it matches the cluster on Launchpad.
- **API connectivity:** Check if the pod can reach `api.obol.tech`.
  ```bash
  kubectl run -n <ns> api-check --rm -it --restart=Never --image=curlimages/curl -- curl -s https://api.obol.tech/v1/_health
  ```
- **Network policy blocking egress:** If `networkPolicy.enabled=true`, ensure Obol API egress is allowed.

### Multiple Releases Sharing the Same ENR (charts < 0.22)

**Symptoms:** several releases in one namespace report the same public ENR; the DKG never forms.

**Cause:** charts < 0.22 defaulted every release to one shared `charon-enr-private-key` Secret. Charts ≥ 0.22 give each release its own `<fullname>-enr-key`.

**Fix:** keep the shared Secret with the release whose ENR is in the cluster definition/lock; give every other release its own identity (`charon.enr.existingSecret.name`, or upgrade to 0.22, which adopts the legacy Secret for at most one release). Before any DKG has completed this is safe; after, it's a recovery — stop and plan with the user. Compare ENRs via each release's `<fullname>-enr` ConfigMap.

### ENR Mismatch Error

**Symptoms:** DKG sidecar logs show "ENR MISMATCH", the phase stays `WaitingForInvite`, or `charon-dkg` reports the key "differs from the ENR private key in Secret".

**Causes & Fixes:**
- The definition lists a different ENR than this pod's (`kubectl get cm <fullname>-enr -n <ns> -o jsonpath='{.data.enr}'`). Before signatures are complete, have the operator update their ENR on the Launchpad (or the creator recreate the definition) with the pod's ENR.
- Never delete or regenerate an ENR Secret whose identity is already in a cluster lock — that node can no longer join its cluster. Find which identity the definition/lock lists before changing anything.

### CrashLoopBackOff on Charon Container

**Symptoms:** Charon container keeps restarting.

**Causes & Fixes:**
- **No beacon node configured:**
  ```bash
  helm get values <release> -n <ns> | grep beacon
  ```
  Fix: Set `charon.beaconNodeEndpoints[0]`.
- **Beacon node unreachable or syncing:** Check from inside the cluster (Obol Stack: `obol network status ethereum/<id>`).
  ```bash
  kubectl run -n <ns> bn-check --rm -it --restart=Never --image=curlimages/curl -- curl -s <beacon-url>/eth/v1/node/syncing
  ```
- **Invalid cluster-lock.json:** Check Charon logs for specific error messages.
- **Port conflicts:** Ensure ports 3600, 3610, 3620 are not conflicting.

### Local k3d/macOS Mount Error (charts < 0.21)

`error mounting ... /charon-data/charon-enr-private-key ... outside of rootfs`: fixed in 0.21 (the key is mounted at `/data/charon-enr-private-key`). Upgrade the chart; don't disable persistence on anything holding keys.

### Validator Client Not Starting

**Symptoms:** validator-client container in CrashLoopBackOff or Error.

**Causes & Fixes:**
- **No keystores yet:** Validator client needs DKG to complete first. Check if `cluster-lock.json` exists.
  ```bash
  kubectl get cm <fullname>-dkg-status -n <ns> -o jsonpath='{.data.phase}'   # Complete or LockPresent
  ```
- **Wrong validator client type:** Check compatibility with the network.
- **Keystore import failure:** Check init container logs:
  ```bash
  kubectl logs -n <ns> <pod> -c import-keystores    # prysm-wallet-import / nimbus-import for those VCs
  ```

### Storage Issues

**Symptoms:** Pod restart loses data, or PVC shows as `Pending`.

**Causes & Fixes:**
- **persistence.enabled=false:** Data stored in emptyDir is lost on restart.
  ```bash
  helm get values <release> -n <ns> | grep persistence
  ```
- **StorageClass missing:** Ensure a default StorageClass exists.
  ```bash
  kubectl get storageclass
  ```

### Network Connectivity Between Peers

**Symptoms:** Charon logs show peer connection failures.

**Causes & Fixes:**
- **P2P relays not configured:** For clusters spanning networks, relays may be needed.
  ```bash
  helm get values <release> -n <ns> | grep p2p
  ```
- **Firewall/NetworkPolicy:** Ensure port 3610 (P2P TCP) is accessible.
- **External IP not set:** If running behind NAT:
  ```bash
  --set charon.p2pExternalHostname=<hostname>
  # or
  --set charon.p2pExternalIp=<ip>
  ```

## Recovery from Failed DKG

If the DKG fails or gets stuck:

1. Phase and message in `<fullname>-dkg-status`; logs of `dkg-sidecar` and `charon-dkg`.
2. All operators' nodes online at the same time, all signatures in (Launchpad route).
3. Same charon minor version on every operator (charon's DKG rejects other minors).
4. `charon-dkg` retries by itself; a pod restart (`kubectl delete pod`) is only for a stuck pod **before** the DKG completed.
5. "data dir contains `validator_keys/` but no lock": an earlier DKG left partial output. The chart never deletes key material — back up `/charon-data`, ask the other operators whether their DKG completed (is the lock on the Obol API?), and clean up only by hand with the user.

## Monitoring Endpoints

```bash
# Charon metrics (always exposed)
kubectl port-forward -n <ns> <pod> 3620:3620
# Visit: http://localhost:3620/metrics

# Validator client metrics (if enabled)
kubectl port-forward -n <ns> <pod> 5064:5064
# Visit: http://localhost:5064/metrics

# Bundled Prometheus UI (only when centralMonitoring.enabled=true)
kubectl port-forward -n <ns> svc/<fullname>-prometheus 9090:9090
# Visit: http://localhost:9090
```

If `centralMonitoring.enabled=true` was set, a `<fullname>-prometheus` Deployment runs in the
namespace and scrapes Charon at `:3620`, then remote-writes to `centralMonitoring.promEndpoint`:

```bash
kubectl get deploy,svc -n <ns> | grep prometheus
kubectl logs -n <ns> deploy/<fullname>-prometheus
```
