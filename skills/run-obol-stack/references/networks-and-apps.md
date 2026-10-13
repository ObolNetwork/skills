# Networks, apps, and public exposure

Reference for the three lower-traffic but bulky parts of the skill: syncing a blockchain node under `obol network`, deploying an arbitrary Dockerfile via the `obol-app` chart, and exposing routes publicly via `obol tunnel`.

Load this file when the user is doing infra work that isn't the agent commerce loop — bringing up an Ethereum / Aztec node, packaging their own service, or wiring up Cloudflare.

## Sync a blockchain network

Two-stage model: **install** (save config) then **sync** (deploy).

```bash
obol network list                                     # installed nodes (type/id, network, EL/CL, mode, MEV) + installable types
obol network install ethereum --network=hoodi --id demo   # config only
obol network sync ethereum/demo                       # deploys to the cluster
```

Networks available (verify with `obol network list` to avoid rot): **ethereum** (mainnet, sepolia, hoodi — don't use goerli / holesky / gnosis / chiado), **aztec**.

Ethereum install knobs:

- `--network mainnet|sepolia|hoodi`
- `--execution-client reth|geth|nethermind|besu|erigon|ethereumjs`
- `--consensus-client lighthouse|prysm|teku|nimbus|lodestar|grandine`
- `--mode full|archive` *(default `full`)* — see "Full vs. archive" below.
- `--since <preset|block|duration>` *(reth-only; with `--mode archive`)* — bounds the archive at a historical point so you don't have to keep history all the way back to genesis. See "Partial archive with `--since`" below.

**Client diversity nudge**: same as CDVN — if the user is running mainnet, push them off the default EL/CL to something non-majority. Rationale is network-level (correlated client failures hurt Ethereum) not just Stack-level.

### Full vs. archive — which does the user want?

```bash
obol network install ethereum --mode full      # default: pruned full node, ~500 GB mainnet / ~100 GB testnet
obol network install ethereum --mode archive   # archive node, varies (see below)
```

**Push the user to `--mode archive` whenever they intend to read deeper history than the recent tip.** Concrete signals to listen for: they say "index events", "search past logs", "historical `eth_call`", "replay a transaction", "build a block explorer", "trace contract state at block N", "back-fill a Dune-style dataset", or any analytics over a fixed historical window. A pruned full node will return errors for these — `state at block N is pruned` and similar — so it's better to size the disk correctly up front than to redeploy after the user hits the wall.

Use `--mode full` (the default) when the user only needs near-tip data: wallet UIs, validator infra, current-block dApps, oracle reads. That covers the majority of users; don't reach for archive when they don't need it, the disk cost is real.

**On a TTY**, omitting `--mode` triggers an interactive picker that shows both options with size estimates; on a non-TTY (scripted / CI) the default is `full` so unattended installs are deterministic.

A disk preflight runs before the install — it warns and prompts if the data dir doesn't have enough free space for the chosen mode. In non-interactive mode it auto-continues, so scripted installs don't deadlock; surface this to the user if a CI install lands in `Pending` for a disk-bound pod.

### Partial archive with `--since` — don't pay for history you won't read

Archive mode defaults to "all history from genesis", which is **~4 TB+ on mainnet** — most users don't actually need that. `--since` lets the user keep archive replay capability only back to a chosen point in time, and disk usage drops dramatically the closer that point is to the tip.

```bash
obol network install ethereum --mode archive --since prague        # since the Prague hardfork (~0.4 TB on mainnet)
obol network install ethereum --mode archive --since 365d          # last 365 days (~0.6 TB on mainnet)
obol network install ethereum --mode archive --since 22500000      # since block 22,500,000
obol network install ethereum --mode archive --since genesis       # explicit: all history (~4 TB+ mainnet)
```

Accepted `--since` values:

- **Hardfork name** (mainnet only): `merge` (~1.5 TB) · `shanghai` (~1.2 TB) · `cancun` (~0.8 TB) · `prague` (~0.4 TB) · `osaka` (~0.2 TB). The CLI rejects hardfork names on testnets (the mainnet block numbers don't apply there).
- **Duration**: `365d`, `1y`, `6mo` — resolved against the post-merge 12-second slot rate into a prune-distance from tip.
- **Block number**: e.g. `22500000` — keeps archive state from that block forward.
- **`genesis` / `all`** — explicit "no bound; keep everything".

On a TTY with `--mode archive` set but `--since` omitted, an interactive "Archive scope" picker offers the hardfork presets (defaulted to *the merge*), `last 365 days`, `all history`, and a custom-block-number entry. Non-TTY defaults to `genesis` so unattended installs are deterministic — pair `--mode archive` with an explicit `--since` in any script that doesn't want to provision 4 TB.

**Caveats:**

- `--mode` and `--since` are **wired only for reth** today. With geth / besu / erigon / nethermind they emit a warning and fall back to the chart's default archive behavior; reach for `--execution-client reth` when the user wants the partial-archive behavior.
- A bigger window than the user needs is wasted disk; a smaller window than the user needs is a re-sync. Default the conversation to "what's the oldest block your indexer / analysis needs to read?" and choose the next-older preset.

Resulting endpoints (replace `<id>` with the deployment ID from `obol network list`; `-o json` has `deployments[]`). The first install of a network gets the network name as its id (`ethereum-mainnet`, `ethereum-hoodi`), and a second one a petname; the dv-pod chart defaults its beacon node to `ethereum-<network>`.

| What | In-cluster (pods, dv-pod, Hermes) | From the host |
|---|---|---|
| Execution JSON-RPC | `http://ethereum-execution.ethereum-<id>.svc.cluster.local:8545` | `obol kubectl port-forward -n ethereum-<id> svc/ethereum-execution 8545:8545` |
| Beacon API | `http://ethereum-beacon.ethereum-<id>.svc.cluster.local:5052` | `obol kubectl port-forward -n ethereum-<id> svc/ethereum-beacon 5052:5052` |
| Unified eRPC (chain data, load-balanced) | `http://erpc.erpc.svc.cluster.local/rpc/<network>` | `http://obol.stack/rpc/<network>` |

The EL/CL ServiceMonitors carry `release: monitoring`, so the Stack's Prometheus (`monitoring-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090`) scrapes both clients. There are no per-node `obol.stack/ethereum-<id>/…` routes; port-forward to talk to one node directly. Each network namespace also has an `ethereum-<id>-metadata` ConfigMap listing its endpoints. `obol.stack` only resolves on the host (see the DNS gotcha in the main SKILL.md).

### Is the node synced?

A DV (or anything validating) needs a node that is **synced**, which means all of:

- **EL**: `eth_syncing` returns `false`, and `net_peerCount` > 0.
- **CL**: `/eth/v1/node/syncing` has `is_syncing: false`, `is_optimistic: false`, `el_offline: false`, and `sync_distance` ≤ 2 slots; `/eth/v1/node/peer_count` `connected` > 0.

Check it, in order of preference:

1. `obol network status ethereum/<id>` (or no argument for every node): pods, EL (`eth_syncing`, head, peers, version), CL (syncing, peers, version), mev-boost health and a verdict — `synced`, `syncing` (with progress), `waiting`, `degraded`, `el_offline`, `unreachable`, `not_deployed`. Gate on `synced` with no peer warnings; `obol -o json network status ethereum/<id>` → `.nodes[].verdict` for scripting. (CLIs before v0.16 show only eRPC health here; fall back to step 2.)
2. Probe the APIs yourself through port-forwards (`obol kubectl -n ethereum-<id> port-forward svc/ethereum-beacon 5052:5052 &`, same for `svc/ethereum-execution 8545:8545`), then:
   ```bash
   curl -s localhost:5052/eth/v1/node/syncing | jq .data
   curl -s localhost:5052/eth/v1/node/peer_count | jq .data.connected
   curl -s -X POST localhost:8545 -H 'content-type: application/json' \
     -d '{"jsonrpc":"2.0","id":1,"method":"eth_syncing","params":[]}' | jq .result
   ```
3. Pods: `obol kubectl get pods -n ethereum-<id>` — both clients `Running` with few restarts.

While syncing, report progress (CL `head_slot` + `sync_distance`, EL `currentBlock`/`highestBlock`) and an honest ETA rather than polling silently. An EL with `eth_syncing=false` at block 0 is waiting for the CL, not synced.

### Sizing for a validating node

Use `--mode full`. Mainnet: ≥2 TB fast SSD free (EL ~1 TB and growing, CL ~200 GB), 16–32 GB RAM, 4+ cores. Hoodi/sepolia: ~300 GB. The node's PVC sizes (mainnet 500Gi EL / 200Gi CL; testnets 100Gi / 50Gi) are not enforced by local-path storage — the host disk is what fills up.

### MEV (opt-in)

`obol network install ethereum --mev [--mev-relays 'https://0x<pubkey>@<host>,…']` runs mev-boost (`mev-boost:18550`) in the node's namespace and wires the CL's builder flag to it, with a vetted relay list per network by default (relay choice has censorship/trust trade-offs). Re-installing without `--mev` and syncing removes it. `obol network list` shows whether a node has MEV; the `ethereum-<id>-metadata` ConfigMap (`metadata.json` → `.mev.enabled`, `.builderEndpoint`, `.relays`) records it too. **A dv-pod on this node sets `charon.builderApi: true` if and only if MEV is enabled here** — with no builder path, proposals fall back to local blocks with warnings. A whole DV cluster must agree on MEV on/off — ask the cluster's operators before choosing.

## Deploy your own service (the `obol-app` chart)

The Stack's general-purpose "run any Dockerfile as a managed app" mechanism is the `obol-app` Helm chart shipped in `ObolNetwork/helm-charts`. It's a generic pod+service+HTTPRoute wrapper — it's NOT DV-specific and shouldn't be confused with `dv-pod`.

Two common patterns:

**(a) Install an off-the-shelf Artifact Hub chart:**

```bash
obol app install bitnami/redis
obol app install bitnami/postgresql@15.0.0          # pin a version
obol app sync postgresql                            # deploy
obol app list                                       # see what's installed
obol app delete postgresql/eager-fox --force        # remove (petnames used for deployment IDs)
```

**(b) Ship your own Dockerfile:**

1. Build + push the image to a registry the cluster can reach (Docker Hub / GHCR / a local registry).
2. Write a `values.yaml` for `obol-app` — minimally `image.repository`, `image.tag`, ports to expose, env, resources. Schema is enforced via `values.schema.json` in the chart.
3. Install via `obol app install obol/obol-app -f values.yaml` (or via `helmfile` for helmfile-managed persistence — see Stack's CLAUDE.md for the helmfile path).
4. `obol app sync` to deploy.

The chart's values surface is in `ObolNetwork/helm-charts/charts/obol-app/values.yaml`; read that file to see the full knob set before authoring a values file. Reference docs: `https://artifacthub.io/packages/helm/obol/obol-app`.

Exposed inside the cluster as a Kubernetes Service. To make it public and/or billable, go through the Cloudflare tunnel section below + the sell-side material in `agent-commerce.md`.

## Public exposure via Cloudflare tunnel

`obol stack up` brings up a **temporary** quick tunnel automatically — its `https://<id>.trycloudflare.com` URL rotates on every restart, which is fine for local testing but breaks any bookmarked/registered URL. For a **permanent** URL, run `obol tunnel setup` with a Cloudflare **connector token**:

```bash
# In the Cloudflare dashboard: Networks → Tunnels → Create a tunnel, then add a
# Public Hostname routing your hostname → http://traefik.traefik.svc.cluster.local:80
obol tunnel setup --hostname stack.example.com <connector-token>   # paste the token (or the whole `cloudflared tunnel run --token …` line)
obol tunnel status                 # prints public URL + connector health
obol tunnel logs                   # tail cloudflared logs
obol tunnel restart                # on change
```

The connector token is a least-privilege, single-tunnel credential — **not** an account-wide API key. Steer users here once they're ready to sell. (The browser-login path, `obol tunnel setup --management local` / `obol tunnel login`, is deprecated and removed in v0.16 — don't recommend it.)

The tunnel publishes **only** the public-safe routes:

- `/services/<name>/*` — x402-gated user services
- `/.well-known/agent-registration.json` — ERC-8004 agent registration
- `/skill.md` — human/agent-readable catalogue of what this Stack is selling

### Critical invariant — never relax route restrictions

The frontend (`/`) and eRPC (`/rpc`) routes are **hostname-restricted to `obol.stack`** in the Traefik Gateway HTTPRoutes. They are meant to be local-only. **Never** remove the hostname restrictions to expose them publicly — the frontend has cluster-admin-like UI capabilities and eRPC is unauthenticated. Exposing either is a critical security flaw. If a user asks to "expose my local RPC through the tunnel", push them toward wrapping it in an `obol-app` service with their own auth layer on a `/services/<name>/*` route instead.

### Tunnel idle timeout (relevance to agent commerce)

The Cloudflare quick tunnel has a ~100s idle timeout on HTTP requests that send no response bytes. For paid agent endpoints, **prefer `stream: true`** on chat completions — the SSE chunks keep the wire warm. Non-streaming responses to slow agents will be dropped by the tunnel before the buffered body arrives. Full discussion in `agent-commerce.md` under "Streaming is the preferred mode".
