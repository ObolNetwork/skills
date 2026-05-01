# DVpod Values Reference

Quick reference for the most important `dv-pod` Helm chart values. For the complete schema, see the [values.yaml](https://github.com/ObolNetwork/helm-charts/blob/main/charts/dv-pod/values.yaml) in the helm-charts repo.

## Essential Values

| Value | Description | Default | Required |
|-------|-------------|---------|----------|
| `charon.operatorAddress` | Ethereum address for auto-DKG | — | Yes |
| `network` | Network: mainnet, sepolia, hoodi | `mainnet` | No |
| `charon.beaconNodeEndpoints[0]` | Primary beacon node URL | — | Recommended |

## Network / Chain ID Mapping

| Network | Chain ID | Notes |
|---------|----------|-------|
| mainnet | 1 | Production Ethereum |
| sepolia | 11155111 | Primary testnet |
| hoodi | 560048 | Newer testnet |

## Charon Configuration

| Value | Description | Default |
|-------|-------------|---------|
| `charon.nickname` | Node identifier (max 32 chars) | — |
| `charon.beaconNodeEndpoints` | List of beacon node URLs | `[]` |
| `charon.fallbackBeaconNodeEndpoints` | Fallback beacon node URLs | `[]` |
| `charon.builderApi` | Enable MEV/builder API | `true` |
| `charon.featureSet` | Feature set: alpha, beta, stable | `stable` |
| `charon.logLevel` | Log level: debug, info, warn, error | `info` |
| `charon.logFormat` | Log format: console, logfmt, json | `json` |
| `charon.p2pRelays` | libp2p relay URLs | — |
| `charon.p2pExternalHostname` | External P2P hostname | — |
| `charon.directConnectionEnabled` | Pod-to-pod direct P2P | `true` |
| `charon.noVerify` | Disable verification | `false` |

## DKG Sidecar

| Value | Description | Default |
|-------|-------------|---------|
| `charon.dkgSidecar.enabled` | Enable DKG sidecar | `true` |
| `charon.dkgSidecar.targetConfigHash` | Target specific cluster (0x + 64 hex) | — |
| `charon.dkgSidecar.apiEndpoint` | Obol API endpoint | `https://api.obol.tech` |
| `charon.dkgSidecar.image.repository` | DKG sidecar image | `obolnetwork/charon-dkg-sidecar` |
| `charon.dkgSidecar.image.tag` | DKG sidecar version | `main` |

## ENR Management

| Value | Description | Default |
|-------|-------------|---------|
| `charon.enr.generate.enabled` | Auto-generate ENR | `true` |
| `charon.enr.existingSecret.name` | Use pre-existing ENR secret | — |
| `charon.enr.existingSecret.privateKeyDataKey` | Secret key for private key | `charon-enr-private-key` |
| `charon.enr.existingSecret.publicKeyDataKey` | Secret key for public ENR | `enr` |
| `charon.enr.privateKey` | Direct ENR private key (hex) | — |
| `secrets.defaultEnrPrivateKey` | Default ENR secret name | `charon-enr-private-key` |

## Validator Client

| Value | Description | Default |
|-------|-------------|---------|
| `validatorClient.enabled` | Enable validator client | `true` |
| `validatorClient.type` | Type: lighthouse, teku, prysm, nimbus, lodestar | `lighthouse` |
| `validatorClient.image.repository` | Custom image (auto-selected if empty) | — |
| `validatorClient.image.tag` | Custom image tag | — |
| `validatorClient.config.graffiti` | Block graffiti string | — |
| `validatorClient.config.extraArgs` | Additional CLI arguments | `[]` |
| `validatorClient.config.prysm.acceptTermsOfUse` | Accept Prysm ToS | `false` |
| `validatorClient.resources.requests.cpu` | CPU request | `500m` |
| `validatorClient.resources.requests.memory` | Memory request | `1Gi` |

## Persistence

| Value | Description | Default |
|-------|-------------|---------|
| `persistence.enabled` | Enable persistent storage | `true` |
| `persistence.size` | Charon data volume size | `1Gi` |
| `persistence.validatorDataSize` | Validator data volume size | `500Mi` |
| `persistence.accessModes` | PVC access modes | `[ReadWriteOnce]` |

## Monitoring

| Value | Description | Default |
|-------|-------------|---------|
| `centralMonitoring.enabled` | Enable central monitoring | `false` |
| `centralMonitoring.promEndpoint` | Prometheus remote write URL | `https://vm.monitoring.gcp.obol.tech/write` |
| `centralMonitoring.token` | Monitoring auth token | — |
| `serviceMonitor.enabled` | Enable Prometheus ServiceMonitor | `false` |

## Resources

| Component | CPU Request | CPU Limit | Mem Request | Mem Limit |
|-----------|-----------|-----------|-------------|-----------|
| Charon | 1000m | 2000m | 2Gi | 4Gi |
| Validator Client | 500m | 1000m | 1Gi | 2Gi |
| DKG Sidecar | 50m | 200m | 128Mi | 256Mi |

## Security & RBAC

| Value | Description | Default |
|-------|-------------|---------|
| `rbac.enabled` | Enable RBAC resources | `true` |
| `serviceAccount.enabled` | Create service account | `true` |
| `networkPolicy.enabled` | Enable network policy | `false` |
| `podDisruptionBudget.enabled` | Enable PDB | `true` |

## Image

| Value | Description | Default |
|-------|-------------|---------|
| `image.repository` | Charon image | `obolnetwork/charon` |
| `image.tag` | Charon version | `v1.9.2` |
| `image.pullPolicy` | Pull policy | `IfNotPresent` |
