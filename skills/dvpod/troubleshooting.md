# DVpod Troubleshooting Reference

## Diagnostic Checklist

Run these in order when troubleshooting a DVpod deployment:

```bash
# 1. Check pod status
kubectl get pods -n <ns> -l app.kubernetes.io/instance=<release> -o wide

# 2. Check events for errors
kubectl get events -n <ns> --sort-by='.lastTimestamp' --field-selector involvedObject.kind=Pod | tail -20

# 3. Check ENR job completion
kubectl get jobs -n <ns> -l app.kubernetes.io/instance=<release>
kubectl logs job/<release>-dv-pod-enr-job -n <ns>

# 4. Check DKG sidecar
kubectl logs -n <ns> <pod> -c dkg-sidecar --tail=50

# 5. Check Charon
kubectl logs -n <ns> <pod> -c charon --tail=50

# 6. Check validator client
kubectl logs -n <ns> <pod> -c validator-client --tail=50

# 7. Check PVCs
kubectl get pvc -n <ns> -l app.kubernetes.io/instance=<release>

# 8. Check secrets exist
kubectl get secrets -n <ns> | grep -E "enr|charon"
```

## Common Issues

## Interpreting Results Quickly

- DKG sidecar polling is normal right after deploy; persistent polling usually means Launchpad/operator mismatch or pending signatures.
- Missing `/charon-data/cluster-lock.json` means DKG has not completed yet.
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
- **Secret already exists with wrong keys:** The secret must have keys `charon-enr-private-key` and `enr`.
  ```bash
  kubectl get secret charon-enr-private-key -n <ns> -o json | jq '.data | keys'
  ```

### DKG Sidecar Polling Forever

**Symptoms:** DKG sidecar logs show repeated polling with no cluster found. Logs show cluster definitions
but say "No invite found" for all of them.

**Causes & Fixes:**
- **Operator address mismatch (most common):** Each release's `charon.operatorAddress` must exactly
  match the address assigned to that node's ENR on the Launchpad. For group clusters, each node
  typically has a different operator address. Verify with:
  ```bash
  helm get values <release> -n <ns> | grep operatorAddress
  ```
  Fix: `helm upgrade <release> obol/dv-pod -n <ns> --reuse-values --set charon.operatorAddress=<correct-address>`
  then restart the pod: `kubectl delete pod <pod> -n <ns>`
- **Cluster not fully confirmed:** ALL operators must accept/sign on the Launchpad before the
  sidecar will detect the invite. Check the Launchpad cluster page to see which operators are pending.
- **Solo cluster (not supported):** The DKG sidecar auto-discovery only works with group clusters.
  Solo cluster flows on the Launchpad use a different mechanism.
- **Wrong targetConfigHash:** If set, verify it matches the cluster on Launchpad.
- **API connectivity:** Check if the pod can reach `api.obol.tech`.
  ```bash
  kubectl exec -n <ns> <pod> -c dkg-sidecar -- wget -qO- https://api.obol.tech/health 2>&1 || echo "Cannot reach API"
  ```
- **Network policy blocking egress:** If `networkPolicy.enabled=true`, ensure Obol API egress is allowed.

### Multiple Releases Sharing the Same ENR

**Symptoms:** Multiple DVpod releases in the same namespace all report the same public ENR. DKG sidecar polls forever because the cluster definition expects distinct peer identities.

**Cause:** By default, the ENR job writes to a shared secret named `charon-enr-private-key`. When multiple releases exist in the same namespace, each ENR job overwrites the previous one, so all pods end up with the last-generated key.

**Fix:** Set `secrets.defaultEnrPrivateKey=""` on every release so each gets its own secret (`<release>-enr-key`):
```bash
helm upgrade <release> obol/dv-pod -n <ns> \
  --reuse-values \
  --set secrets.defaultEnrPrivateKey=""
```
After upgrading, verify each release has a unique ENR:
```bash
for release in my-dv-pod-0 my-dv-pod-1 my-dv-pod-2 my-dv-pod-3; do
  enr=$(kubectl get secret -n <ns> ${release}-enr-key -o jsonpath='{.data.enr}' | base64 -d)
  echo "${release}: ${enr}"
done
```

### ENR Mismatch Error

**Symptoms:** DKG sidecar logs show "ENR MISMATCH".

**Causes & Fixes:**
- The ENR in the secret doesn't match what's registered in the cluster definition.
- **Option 1:** Update the cluster definition on Launchpad with the current ENR.
- **Option 2:** Delete the secret and redeploy with the correct ENR:
  ```bash
  # Get current ENR
  kubectl get secret charon-enr-private-key -n <ns> -o jsonpath='{.data.enr}' | base64 -d
  ```

### CrashLoopBackOff on Charon Container

**Symptoms:** Charon container keeps restarting.

**Causes & Fixes:**
- **No beacon node configured:**
  ```bash
  helm get values <release> -n <ns> | grep beacon
  ```
  Fix: Set `charon.beaconNodeEndpoints[0]`.
- **Beacon node unreachable:** Check network connectivity from the pod.
  ```bash
  kubectl exec -n <ns> <pod> -c charon -- wget -qO- <beacon-url>/eth/v1/node/health 2>&1
  ```
- **Invalid cluster-lock.json:** Check Charon logs for specific error messages.
- **Port conflicts:** Ensure ports 3600, 3610, 3620 are not conflicting.

### Local k3d/macOS Mount Error in dkg-sidecar

**Symptoms:** Init container fails with an error similar to:
`error mounting ... /charon-data/charon-enr-private-key ... mountpoint ... is outside of rootfs`.

**Cause:** Environment-specific mount behavior when a secret subPath is mounted under a PVC path.

**Testing workaround:** disable charon-data persistence for the test run:
```bash
helm upgrade <release> obol/dv-pod -n <ns> \
  --reuse-values \
  --set persistence.enabled=false
```

**Note:** This workaround is for test/dev only; data is not persisted across restarts.
This chart-level mount-path issue is expected to be fixed soon.

### Validator Client Not Starting

**Symptoms:** validator-client container in CrashLoopBackOff or Error.

**Causes & Fixes:**
- **No keystores yet:** Validator client needs DKG to complete first. Check if `cluster-lock.json` exists.
  ```bash
  kubectl exec -n <ns> <pod> -c charon -- ls /charon-data/cluster-lock.json
  ```
- **Wrong validator client type:** Check compatibility with the network.
- **Prysm ToS not accepted:**
  ```bash
  helm get values <release> -n <ns> | grep acceptTerms
  ```
  Fix: Set `validatorClient.config.prysm.acceptTermsOfUse=true`.
- **Keystore import failure:** Check init container logs:
  ```bash
  kubectl logs -n <ns> <pod> -c import-keystores
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

If DKG fails or gets stuck:

1. Check all operators' nodes are online and running
2. Check all operators have signed on the Launchpad
3. Check DKG sidecar logs for specific errors
4. If needed, restart the DKG sidecar:
   ```bash
   kubectl delete pod <pod> -n <ns>
   ```
   The StatefulSet will recreate it and DKG sidecar will retry.

## Monitoring Endpoints

```bash
# Charon metrics
kubectl port-forward -n <ns> <pod> 3620:3620
# Visit: http://localhost:3620/metrics

# Validator client metrics (if enabled)
kubectl port-forward -n <ns> <pod> 5064:5064
# Visit: http://localhost:5064/metrics
```
