# DVpod Deployment Examples

All examples pin chart `0.22.0` and set `network` explicitly — check `helm search repo obol/dv-pod --versions` for a newer version (and its release notes) before using them. Replace every `0xYOUR_…`, `<beacon-url>` and hash. In the Obol Stack prefix `helm`/`kubectl` with `obol` and start from [obol-stack.md](obol-stack.md).

```bash
helm repo add obol https://obolnetwork.github.io/helm-charts
helm repo update
```

## Example 1: Launchpad route (hoodi)

```bash
helm upgrade --install dv-pod-hoodi obol/dv-pod --version 0.22.0 \
  --namespace dv-pod --create-namespace \
  --set mode=launchpad \
  --set network=hoodi \
  --set charon.operatorAddress=0xYOUR_OPERATOR_ADDRESS \
  --set 'charon.beaconNodeEndpoints[0]=<beacon-url>' \
  --timeout=10m

# ENR to paste on https://hoodi.launchpad.obol.org (sign with 0xYOUR_OPERATOR_ADDRESS)
kubectl get configmap dv-pod-hoodi-enr -n dv-pod -o jsonpath='{.data.enr}'
```

Join one specific invite: add `--set charon.dkgSidecar.targetConfigHash=0x<64 hex>`.

## Example 2: Direct route (definition from `charon create dkg`)

After Example 1 (or any install) produced the pod's ENR and the creator published a definition containing it:

```bash
helm upgrade dv-pod-hoodi obol/dv-pod --version 0.22.0 -n dv-pod --reuse-values \
  --set mode=definition \
  --set dkg.definition.configHash=0xCONFIG_HASH \
  --timeout=10m
```

From an unpublished file instead:

```bash
kubectl create configmap cluster-definition -n dv-pod --from-file=cluster-definition.json
helm upgrade dv-pod-hoodi obol/dv-pod --version 0.22.0 -n dv-pod --reuse-values \
  --set mode=definition --set dkg.definition.configMap=cluster-definition --timeout=10m
```

See the chart's `values-examples/definition.yaml`.

## Example 3: Mainnet with fallbacks and a minority VC

```bash
helm upgrade --install dv-pod-mainnet obol/dv-pod --version 0.22.0 \
  --namespace dv-pod --create-namespace \
  --set mode=launchpad \
  --set network=mainnet \
  --set charon.operatorAddress=0xYOUR_OPERATOR_ADDRESS \
  --set charon.nickname=my-operator \
  --set 'charon.beaconNodeEndpoints[0]=http://primary-beacon:5052' \
  --set 'charon.fallbackBeaconNodeEndpoints[0]=http://fallback-beacon:5052' \
  --set validatorClient.type=teku \
  --timeout=10m
```

With no `fallbackBeaconNodeEndpoints`, `charon.publicnodeFallback=true` (default) uses publicnode.com for the network; set it to `false` to run with no fallback. Prysm needs nothing extra (`validatorClient.type=prysm`; using it accepts Prysm's terms).

## Example 4: Several operators' nodes in one namespace (testing)

Each release gets its own `<fullname>-enr-key` identity on charts ≥ 0.22. Each needs a distinct operator address that will sign for that node on the Launchpad.

```bash
for i in 0 1 2 3; do
  helm upgrade --install dv-pod-$i obol/dv-pod --version 0.22.0 \
    --namespace dv-pod --create-namespace \
    --set mode=launchpad \
    --set network=hoodi \
    --set charon.operatorAddress=0xOPERATOR_${i}_ADDRESS \
    --set 'charon.beaconNodeEndpoints[0]=<beacon-url>' \
    --timeout=10m
done
for i in 0 1 2 3; do
  echo "dv-pod-$i: $(kubectl get configmap dv-pod-$i-enr -n dv-pod -o jsonpath='{.data.enr}')"
done
```

On charts < 0.22, add `--set secrets.defaultEnrPrivateKey=""` to every release and read ENRs from each `<release>-enr-key` Secret's public `enr` field. If one person controls all four nodes, use the direct route (Example 2) — the Launchpad solo flow isn't supported.

## Example 5: Import an existing ENR key

The user creates the Secret themselves (it contains the private key):

```bash
kubectl create namespace dv-pod --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic my-enr -n dv-pod \
  --from-file=charon-enr-private-key=<path-to>/charon-enr-private-key

helm upgrade --install dv-pod-hoodi obol/dv-pod --version 0.22.0 \
  --namespace dv-pod \
  --set mode=launchpad \
  --set network=hoodi \
  --set charon.operatorAddress=0xYOUR_OPERATOR_ADDRESS \
  --set 'charon.beaconNodeEndpoints[0]=<beacon-url>' \
  --set charon.enr.existingSecret.name=my-enr \
  --timeout=10m
```

The ENR job adds the public `enr` field if it's missing and never overwrites the key.

## Example 6: Monitoring

```bash
# Prometheus Operator in the cluster (Obol Stack: labels.release=monitoring)
  --set serviceMonitor.enabled=true --set serviceMonitor.labels.release=monitoring

# Bundled Prometheus (<fullname>-prometheus:9090) remote-writing to Obol's backend, or your own
  --set centralMonitoring.enabled=true --set centralMonitoring.token=<token>
  --set centralMonitoring.promEndpoint=https://prom.example.com/api/v1/write

# Push charon logs to Loki
  --set charon.lokiAddresses=http://loki.monitoring.svc:3100/loki/api/v1/push --set charon.lokiService=dv-pod-hoodi
```

Have the user pass tokens themselves rather than pasting them into chat.

## Example 7: Production-leaning settings

```bash
helm upgrade --install dv-pod-mainnet obol/dv-pod --version 0.22.0 \
  --namespace dv-prod --create-namespace \
  --set mode=launchpad \
  --set network=mainnet \
  --set charon.operatorAddress=0xYOUR_OPERATOR_ADDRESS \
  --set charon.nickname=prod-operator-1 \
  --set 'charon.beaconNodeEndpoints[0]=http://primary-beacon:5052' \
  --set 'charon.fallbackBeaconNodeEndpoints[0]=http://fallback-beacon:5052' \
  --set charon.builderApi=true \
  --set persistence.size=5Gi \
  --set serviceMonitor.enabled=true \
  --set networkPolicy.enabled=true \
  --timeout=10m
```

`charon.builderApi=true` only if the beacon nodes have a builder (MEV-boost) and the whole cluster runs MEV. With `networkPolicy.enabled`, set `networkPolicy.monitoring` selectors so Prometheus can still scrape 3620.

## Quick status

```bash
kubectl get pods,pvc,jobs -n dv-pod -l app.kubernetes.io/instance=dv-pod-hoodi
kubectl get configmap dv-pod-hoodi-dkg-status -n dv-pod -o jsonpath='{.data.phase} {.data.signatures}{"\n"}{.data.message}{"\n"}'
kubectl logs -n dv-pod dv-pod-hoodi-0 -c dkg-sidecar --tail=20
kubectl logs -n dv-pod dv-pod-hoodi-0 -c charon-dkg --tail=20
```
