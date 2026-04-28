# DVpod Deployment Examples

## Example 1: Minimal Mainnet Deploy (Fresh Cluster)

The simplest deployment — auto-generates ENR, uses defaults for everything else.

```bash
helm repo add obol https://obolnetwork.github.io/helm-charts
helm repo update

helm upgrade --install my-dv-pod obol/dv-pod \
  --namespace dv-pod --create-namespace \
  --set charon.operatorAddress=0x1234567890abcdef1234567890abcdef12345678 \
  --set 'charon.beaconNodeEndpoints[0]=http://beacon-node:5052' \
  --timeout=10m
```

After deploy:
```bash
# Get your ENR to paste on the Launchpad
kubectl get secret charon-enr-private-key -n dv-pod \
  -o jsonpath='{.data.enr}' | base64 -d
```

## Example 2: Sepolia Testnet Deploy

```bash
helm upgrade --install test-dv obol/dv-pod \
  --namespace dv-pod-testnet --create-namespace \
  --set charon.operatorAddress=0xYOUR_ADDRESS \
  --set network=sepolia \
  --set 'charon.beaconNodeEndpoints[0]=http://sepolia-beacon:5052' \
  --set charon.logLevel=debug \
  --timeout=10m
```

## Example 3: Join Specific Cluster with Config Hash

When you have a cluster invitation from the Obol Launchpad:

```bash
helm upgrade --install my-dv-pod obol/dv-pod \
  --namespace dv-pod --create-namespace \
  --set charon.operatorAddress=0xYOUR_ADDRESS \
  --set 'charon.beaconNodeEndpoints[0]=http://beacon:5052' \
  --set charon.dkgSidecar.targetConfigHash=0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890 \
  --timeout=10m
```

## Example 4: Using Teku Validator Client

```bash
helm upgrade --install my-dv-pod obol/dv-pod \
  --namespace dv-pod --create-namespace \
  --set charon.operatorAddress=0xYOUR_ADDRESS \
  --set 'charon.beaconNodeEndpoints[0]=http://beacon:5052' \
  --set validatorClient.type=teku \
  --timeout=10m
```

## Example 5: Using Prysm Validator Client

Prysm requires accepting Terms of Service:

```bash
helm upgrade --install my-dv-pod obol/dv-pod \
  --namespace dv-pod --create-namespace \
  --set charon.operatorAddress=0xYOUR_ADDRESS \
  --set 'charon.beaconNodeEndpoints[0]=http://beacon:5052' \
  --set validatorClient.type=prysm \
  --set validatorClient.config.prysm.acceptTermsOfUse=true \
  --timeout=10m
```

## Example 6: Import Existing ENR

If you already have an ENR from a previous setup:

```bash
# Step 1: Create the secret
kubectl create namespace dv-pod --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic charon-enr-private-key -n dv-pod \
  --from-file=charon-enr-private-key=~/.charon/charon-enr-private-key \
  --from-literal=enr="enr:-IS4Q..."

# Step 2: Deploy referencing the secret
helm upgrade --install my-dv-pod obol/dv-pod \
  --namespace dv-pod \
  --set charon.operatorAddress=0xYOUR_ADDRESS \
  --set 'charon.beaconNodeEndpoints[0]=http://beacon:5052' \
  --set charon.enr.existingSecret.name=charon-enr-private-key \
  --timeout=10m
```

## Example 7: Group Cluster — Multiple Nodes with Different Operators

Deploy 4 nodes for a group cluster where each node has a distinct operator address.
Each operator will sign for their node on the Launchpad independently.

**IMPORTANT:** Each release MUST have:
- A unique operator address matching the Launchpad configuration
- `secrets.defaultEnrPrivateKey=""` so each gets its own ENR secret

```bash
# Node 0 — Operator A
helm upgrade --install my-dv-pod-0 obol/dv-pod \
  --namespace dv-pod --create-namespace \
  --set charon.operatorAddress=0xOPERATOR_A_ADDRESS \
  --set network=hoodi \
  --set 'charon.beaconNodeEndpoints[0]=http://beacon:5052' \
  --set secrets.defaultEnrPrivateKey="" \
  --timeout=10m

# Node 1 — Operator B
helm upgrade --install my-dv-pod-1 obol/dv-pod \
  --namespace dv-pod \
  --set charon.operatorAddress=0xOPERATOR_B_ADDRESS \
  --set network=hoodi \
  --set 'charon.beaconNodeEndpoints[0]=http://beacon:5052' \
  --set secrets.defaultEnrPrivateKey="" \
  --timeout=10m

# Node 2 — Operator C
helm upgrade --install my-dv-pod-2 obol/dv-pod \
  --namespace dv-pod \
  --set charon.operatorAddress=0xOPERATOR_C_ADDRESS \
  --set network=hoodi \
  --set 'charon.beaconNodeEndpoints[0]=http://beacon:5052' \
  --set secrets.defaultEnrPrivateKey="" \
  --timeout=10m

# Node 3 — Operator D
helm upgrade --install my-dv-pod-3 obol/dv-pod \
  --namespace dv-pod \
  --set charon.operatorAddress=0xOPERATOR_D_ADDRESS \
  --set network=hoodi \
  --set 'charon.beaconNodeEndpoints[0]=http://beacon:5052' \
  --set secrets.defaultEnrPrivateKey="" \
  --timeout=10m
```

After deploy, collect all ENRs and create the cluster on the Launchpad:
```bash
for i in 0 1 2 3; do
  echo "my-dv-pod-$i:"
  kubectl get secret "my-dv-pod-$i-enr-key" -n dv-pod \
    -o jsonpath='{.data.enr}' | base64 -d
  echo
done
```

Each operator must accept the cluster invite on the Launchpad for DKG to begin.

## Example 8: Multiple Beacon Nodes with Fallbacks

```bash
helm upgrade --install my-dv-pod obol/dv-pod \
  --namespace dv-pod --create-namespace \
  --set charon.operatorAddress=0xYOUR_ADDRESS \
  --set 'charon.beaconNodeEndpoints[0]=http://primary-beacon:5052' \
  --set 'charon.beaconNodeEndpoints[1]=http://secondary-beacon:5052' \
  --set 'charon.fallbackBeaconNodeEndpoints[0]=http://fallback-beacon:5052' \
  --timeout=10m
```

## Example 9: Custom Resource Limits

For resource-constrained environments:

```bash
helm upgrade --install my-dv-pod obol/dv-pod \
  --namespace dv-pod --create-namespace \
  --set charon.operatorAddress=0xYOUR_ADDRESS \
  --set 'charon.beaconNodeEndpoints[0]=http://beacon:5052' \
  --set resources.requests.cpu=500m \
  --set resources.requests.memory=1Gi \
  --set resources.limits.cpu=1000m \
  --set resources.limits.memory=2Gi \
  --timeout=10m
```

## Example 10: Enable Central Monitoring

```bash
helm upgrade --install my-dv-pod obol/dv-pod \
  --namespace dv-pod --create-namespace \
  --set charon.operatorAddress=0xYOUR_ADDRESS \
  --set 'charon.beaconNodeEndpoints[0]=http://beacon:5052' \
  --set centralMonitoring.enabled=true \
  --set centralMonitoring.token=YOUR_MONITORING_TOKEN \
  --timeout=10m
```

## Example 11: Enable Prometheus ServiceMonitor

For clusters running Prometheus Operator:

```bash
helm upgrade --install my-dv-pod obol/dv-pod \
  --namespace dv-pod --create-namespace \
  --set charon.operatorAddress=0xYOUR_ADDRESS \
  --set 'charon.beaconNodeEndpoints[0]=http://beacon:5052' \
  --set serviceMonitor.enabled=true \
  --set serviceMonitor.interval=30s \
  --timeout=10m
```

## Example 12: Full Production Deploy

A comprehensive production deployment with all recommended settings:

```bash
helm upgrade --install prod-dv obol/dv-pod \
  --namespace dv-prod --create-namespace \
  --set charon.operatorAddress=0xYOUR_ADDRESS \
  --set charon.nickname="prod-operator-1" \
  --set 'charon.beaconNodeEndpoints[0]=http://primary-beacon:5052' \
  --set 'charon.beaconNodeEndpoints[1]=http://secondary-beacon:5052' \
  --set 'charon.fallbackBeaconNodeEndpoints[0]=http://fallback-beacon:5052' \
  --set charon.builderApi=true \
  --set charon.featureSet=stable \
  --set charon.logLevel=info \
  --set validatorClient.type=lighthouse \
  --set persistence.size=5Gi \
  --set centralMonitoring.enabled=true \
  --set centralMonitoring.token=YOUR_TOKEN \
  --set serviceMonitor.enabled=true \
  --set podDisruptionBudget.enabled=true \
  --set networkPolicy.enabled=true \
  --timeout=10m
```

## Example 13: Obol Stack Full Node + DVpod End-to-End

Use Obol Stack to deploy the full Ethereum node the DVpod needs, then deploy `dv-pod` against
the Obol Stack beacon endpoint.

```bash
# Step 1: Bring up Obol Stack
obol stack init
obol stack up

# Step 2: Deploy Ethereum full node stack (execution + consensus)
obol network install ethereum --network=hoodi --id dv
obol network sync ethereum/dv
obol kubectl get pods -n ethereum-dv

# Step 3: Verify beacon API is reachable
curl -s http://obol.stack/ethereum-dv/beacon/eth/v1/node/health

# Step 4: Deploy DVpod using Obol Stack beacon endpoint
helm repo add obol https://obolnetwork.github.io/helm-charts
helm repo update
helm upgrade --install my-dv-pod obol/dv-pod \
  --namespace dv-pod --create-namespace \
  --set charon.operatorAddress=0xYOUR_ADDRESS \
  --set network=hoodi \
  --set 'charon.beaconNodeEndpoints[0]=http://obol.stack/ethereum-dv/beacon' \
  --set secrets.defaultEnrPrivateKey="" \
  --timeout=10m

# Step 5: Get ENR and monitor startup
kubectl get secret my-dv-pod-enr-key -n dv-pod -o jsonpath='{.data.enr}' | base64 -d
kubectl get pods -n dv-pod -l app.kubernetes.io/instance=my-dv-pod
kubectl logs -n dv-pod -l app.kubernetes.io/instance=my-dv-pod -c dkg-sidecar --tail=50
```

If `obol.stack` DNS is unavailable from where DVpod runs, use a reachable internal service endpoint
for the consensus client beacon API in `charon.beaconNodeEndpoints`.

## Quick Status Check Commands

```bash
# All-in-one status
kubectl get pods,pvc,jobs,secrets -n dv-pod -l app.kubernetes.io/instance=my-dv-pod

# Get ENR
kubectl get secret charon-enr-private-key -n dv-pod -o jsonpath='{.data.enr}' | base64 -d

# DKG progress
kubectl logs -n dv-pod -l app.kubernetes.io/instance=my-dv-pod -c dkg-sidecar --tail=20

# Check if DKG completed
kubectl exec -n dv-pod my-dv-pod-dv-pod-0 -c charon -- ls /charon-data/cluster-lock.json 2>/dev/null && echo "DKG COMPLETE" || echo "DKG NOT YET COMPLETE"
```
