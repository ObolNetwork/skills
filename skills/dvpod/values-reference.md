# DVpod Values Reference

The values that matter most for `dv-pod` chart **0.22.x** (charon `v1.11.0`). The chart's [values.yaml](https://github.com/ObolNetwork/helm-charts/blob/main/charts/dv-pod/values.yaml) and README are the source of truth; read them for anything not listed. The schema is strict: unknown keys fail `helm install`.

## Essentials

| Value | Description | Default |
|-------|-------------|---------|
| `network` | `mainnet`, `sepolia`, `hoodi` (chain ID derived). **Always set explicitly** | `mainnet` |
| `mode` | How the node joins its cluster — see below | `auto` |
| `charon.operatorAddress` | Operator wallet that signs on the Launchpad. Required for `mode: launchpad` (and `auto` without lock/definition) | `""` |
| `charon.beaconNodeEndpoints` | Synced beacon API(s); all are called for every request. Empty = the Obol Stack's node for `network` (`http://ethereum-beacon.ethereum-<network>.svc.cluster.local:5052`); **set it** outside the Stack or when the Stack deployment has another id. | `[]` |
| `charon.fallbackBeaconNodeEndpoints` | Used when the primaries fail | `[]` |
| `charon.publicnodeFallback` | With no fallbacks set, fall back to publicnode.com's beacon API for `network` | `true` |
| `image.tag` | Charon version (also runs the DKG with `dkg.runner: charon`) | `v1.11.0` |

## Modes

| `mode` | Use when | Required |
|---|---|---|
| `auto` | Existing installs; infers: `configMaps.clusterLock` → lock, `charon.lockHash` → lockHash, any `dkg.definition.*` → definition, else launchpad | as inferred |
| `launchpad` | Launchpad invite; sidecar polls the Obol API by operator address | `charon.operatorAddress` |
| `definition` | Direct route: a `charon create dkg` definition | exactly one of `dkg.definition.configHash` / `.url` / `.configMap` |
| `lock` | Import an existing cluster, no DKG | `configMaps.clusterLock` (+ `validatorClient.keystores.secretName`) |
| `lockHash` | Same, lock > 1 MB fetched from the Obol API | `charon.lockHash` (+ `validatorClient.keystores.secretName`) |

## DKG

| Value | Description | Default |
|-------|-------------|---------|
| `dkg.definition.configHash` | Published definition (`charon create dkg --publish`), `0x` + 64 hex | `""` |
| `dkg.definition.url` | HTTPS URL serving `cluster-definition.json` | `""` |
| `dkg.definition.configMap` / `.configMapKey` | ConfigMap in the release namespace holding the definition | `""` / `cluster-definition.json` |
| `dkg.runner` | `charon`: `charon dkg` runs in the `charon-dkg` init container with `image` (same version as the node). `sidecar`: legacy, uses the sidecar's bundled charon | `charon` |
| `dkg.publish` | Publish the lock to the Obol API after the DKG | `true` |
| `dkg.timeout` / `dkg.retryDelaySeconds` / `dkg.extraArgs` | Per-attempt timeout, retry delay, extra `charon dkg` args | `""` / `10` / `[]` |
| `dkg.status.enabled` | Sidecar writes progress to ConfigMap `<fullname>-dkg-status` | `true` |
| `charon.dkgSidecar.targetConfigHash` | `launchpad` mode only: join just this definition | `""` |
| `charon.dkgSidecar.apiEndpoint` | Obol API | `https://api.obol.tech` |
| `charon.dkgSidecar.image.tag` | Sidecar image (`obolnetwork/charon-dkg-sidecar`); 1.1.0 is needed for `dkg.runner: charon`, `definition` mode and status | `1.1.0` |
| `configMaps.clusterLock` | Existing `cluster-lock.json` ConfigMap (`mode: lock`) | `""` |
| `charon.lockHash` | Lock hash for `mode: lockHash` | `""` |

## Public status (no Secret access needed)

| Object | Contents |
|---|---|
| ConfigMap `<fullname>-enr`, key `enr` | This node's public ENR (written by the ENR job) |
| ConfigMap `<fullname>-dkg-status` | `phase`, `message`, `updatedAt`, `enr`, `operatorAddress`, `definitionSource`, `configHash`, `clusterName`, `signatures` (e.g. `3/4`), `lockHash`, `numValidators`, `sidecarVersion` |
| `statusReaders` | `[{namespace, serviceAccount}]` granted get/watch on just those two ConfigMaps (no list). Obol Stack Hermes: `{namespace: hermes-obol-agent, serviceAccount: hermes}` |

Phases: `Initializing`, `WaitingForInvite`, `WaitingForSignatures`, `DefinitionReady`, `RunningDKG` (sidecar runner only), `Complete`, `LockPresent`, `Failed`.

`<fullname>` is the release name if it contains `dv-pod`, else `<release>-dv-pod`. Name releases `dv-pod-<something>` to keep names predictable.

## ENR identity

| Value | Description | Default |
|-------|-------------|---------|
| `charon.enr.existingSecret.name` | Use this Secret (keys below); never overwritten | `""` |
| `charon.enr.existingSecret.privateKeyDataKey` / `.publicKeyDataKey` | Key names in that Secret | `charon-enr-private-key` / `enr` |
| `charon.enr.privateKey` | Provide the key hex directly (stored in the Helm release — prefer `existingSecret`) | `""` |
| `charon.enr.generate.enabled` | Generate a key if none exists | `true` |
| `secrets.defaultEnrPrivateKey` | Legacy shared Secret name, adopted only if it exists and no other StatefulSet uses it; `""` never adopts | `charon-enr-private-key` |

Secret precedence: `existingSecret.name` → the Secret the release already mounts (an identity is never replaced on upgrade) → the legacy `charon-enr-private-key` if unclaimed → a new per-release `<fullname>-enr-key`. Two releases in one namespace therefore never share an identity (charts < 0.22 did, unless `secrets.defaultEnrPrivateKey=""`).

## Charon

| Value | Description | Default |
|-------|-------------|---------|
| `charon.nickname` | Name in monitoring and peers' logs (≤ 32 chars) | `""` |
| `charon.builderApi` | MEV/builder proposals. Needs a builder (MEV-boost) on the beacon node; the Obol Stack has none, so `false` there | `true` |
| `charon.featureSet` / `featureSetEnable` / `featureSetDisable` | Feature gates | `stable` / `""` / `""` |
| `charon.logLevel` / `logFormat` | Logging | `info` / `json` |
| `charon.lokiAddresses` / `lokiService` | Push logfmt logs to Loki | `""` |
| `charon.monitoringAddress` | Metrics, `/readyz`, `/livez` | `0.0.0.0:3620` |
| `charon.p2pRelays` / `p2pExternalHostname` / `p2pExternalIp` / `p2pTcpAddress` / `p2pUdpAddress` | libp2p (`p2pUdpAddress` = QUIC, alpha; needs `featureSetEnable: quic`) | relays default / `""` / `""` / `0.0.0.0:3610` / `""` |
| `charon.directConnectionEnabled` | Advertise the pod name for pod-to-pod peers | `true` |
| `charon.executionClientRpcEndpoint` | Only for smart-contract-wallet operator signatures | `""` |
| `p2pService.enabled` / `.type` | Expose libp2p outside the cluster (LoadBalancer / NodePort) | `false` / `LoadBalancer` |

## Validator client

| Value | Description | Default |
|-------|-------------|---------|
| `validatorClient.enabled` | Run a VC in the pod (`false` → point an external VC at the `validator-api` Service) | `true` |
| `validatorClient.type` | `lighthouse`, `teku`, `prysm`, `nimbus`, `lodestar` | `lighthouse` |
| `validatorClient.image.repository` / `.tag` | Override the per-type image | auto |
| `validatorClient.config.graffiti` / `.extraArgs` / `.prysm.extraArgs` | VC options (using Prysm accepts its terms; there is no accept flag) | `""` / `[]` / `[]` |
| `validatorClient.keystores.secretName` | Existing key-share Secret (`keystore-*.json` + `.txt`), for `lock` / `lockHash` | `""` |

## Persistence

| Value | Description | Default |
|-------|-------------|---------|
| `persistence.enabled` | PVC for `/charon-data` (lock, key shares). Never disable outside tests | `true` |
| `persistence.size` / `validatorDataSize` | charon-data / validator-data (slashing protection, always persistent) | `1Gi` / `500Mi` |
| `persistence.retentionPolicy` | PVCs are retained when the StatefulSet is deleted or scaled down | `Retain` / `Retain` |

## Monitoring

| Value | Description | Default |
|-------|-------------|---------|
| `serviceMonitor.enabled` / `.labels` / `.interval` | ServiceMonitor for a Prometheus Operator. Obol Stack: `labels: {release: monitoring}` | `false` / `{}` / `1m` |
| `centralMonitoring.enabled` / `.promEndpoint` / `.token` | Bundled Prometheus pod (`prometheus:9090` in the namespace) remote-writing to Obol (token stored in a Secret) | `false` / `https://vm.monitoring.gcp.obol.tech/write` / `""` |
| `readinessProbe.enabled` | Pod Ready = charon `/readyz` OK (no liveness probe by default, on purpose) | `true` |

## Security

| Value | Description | Default |
|-------|-------------|---------|
| `rbac.enabled` / `serviceAccount.enabled` | Needed for the status ConfigMap | `true` / `true` |
| `networkPolicy.enabled` | Restrict traffic; keep Prometheus (and Hermes via `networkPolicy.monitoring.extraFrom`) able to reach 3620 | `false` |
| `podDisruptionBudget.enabled` | PDB | `true` |

## Resources (defaults)

| Component | CPU req / limit | Memory req / limit |
|---|---|---|
| charon (`resources`) | 1000m / 2000m | 2Gi / 4Gi |
| validator client | 500m / 1000m | 1Gi / 2Gi |
| dkg-sidecar | 50m / 200m | 128Mi / 256Mi |
| charon-dkg (`dkg.resources`) | 100m / 1000m | 256Mi / 1Gi |

## Network → chain ID

`mainnet` 1, `sepolia` 11155111, `hoodi` 560048.
