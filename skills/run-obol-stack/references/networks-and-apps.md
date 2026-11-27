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
- `--execution-client reth|geth|nethermind|besu|erigon`
- `--consensus-client lighthouse|prysm|teku|nimbus|lodestar|grandine|silver` (silver: alpha, obol v0.18.0 or later; suggest a testnet first. v0.19 runs Silver alpha.23, amd64 and arm64, including Apple Silicon; v0.18 was amd64-only)
- `--mode full|archive` *(default `full`)* — see "Full vs. archive" below.
- `--since <preset|block|duration>` *(reth-only; with `--mode archive`)* — bounds the archive at a historical point so you don't have to keep history all the way back to genesis. See "Partial archive with `--since`" below.
- `--execution-memory <size>` / `--consensus-memory <size>` *(e.g. `16Gi`)* — the client's memory **limit** (obol v0.18.0+; before that it was the request). Leave them unset: obol sizes each client per network, mode and client, and sync warns when a value is below the default limit. Only set one to give a client more room after it was OOM-killed, or to make a node fit on a small machine. Edit later as `executionMemory` / `consensusMemory` in the deployment's `values.yaml`, then `obol network sync`.

**Memory (obol v0.18.0+)**: every client gets a memory request and limit, and is told its limit (`GOMEMLIMIT`, JVM/Node heap sizes, Nethermind's memory hint, reth's cache). Hoodi beacon nodes get mainnet-sized limits, because Hoodi's validator set is as large as mainnet's. `network install` and `sync` warn when the cluster's memory requests won't fit, and `sync` says when it will restart clients to apply new limits (data is kept). After upgrading obol, sync every node, since its requests may drop. Not enough memory: stop a node (`obol network stop <network>/<id>`) before lowering limits.

**Client versions in obol v0.19.0** (pinned per release; `obol network sync` after upgrading obol moves a node to them):

| Execution | Version | Consensus | Version |
|---|---|---|---|
| reth (default) | v2.11.0 | lighthouse (default) | v8.3.3 |
| geth | v1.17.10 | prysm | v7.3.2 |
| nethermind | 2.3.0-rc | teku | 26.11.0 |
| besu | 26.11.3 | nimbus | v26.10.2 |
| erigon | v3.8.2 | lodestar | v1.51.0 |
| | | grandine | 2.0.6 |
| | | silver | v0.1.0-alpha.23 |

Nethermind is on a release candidate because 2.2.2 doesn't know Sepolia's Amsterdam fork (live since 2026-10-06).

**Hoodi Gloas/Amsterdam fork (planned for epoch 143616, 2026-12-15 19:12:24 UTC).** In v0.19.0 only **Besu 26.11.3** and **Silver alpha.23** schedule it. Every other client, including the default reth + lighthouse pair, needs a later Stack release with client versions that do. Tell anyone running a Hoodi node in the Stack to upgrade obol and run `obol network sync` before that date, or their node stops following Hoodi at the fork. Don't suggest hand-pinning client pre-releases for it.

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
| Execution JSON-RPC | `http://ethereum-execution.ethereum-<id>.svc.cluster.local:8545` | `obol network expose ethereum/<id> --execution` (v0.19+), or `obol kubectl port-forward -n ethereum-<id> svc/ethereum-execution 8545:8545` |
| Beacon API | `http://ethereum-beacon.ethereum-<id>.svc.cluster.local:5052` | `obol network expose ethereum/<id> --beacon` (v0.19+), or `obol kubectl port-forward -n ethereum-<id> svc/ethereum-beacon 5052:5052` |
| Unified eRPC (chain data, load-balanced) | `http://erpc.erpc.svc.cluster.local/rpc/<network>` | `http://obol.stack/rpc/<network>` |

The EL/CL ServiceMonitors carry `release: monitoring`, so the Stack's Prometheus (`monitoring-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090`) scrapes both clients. There are no per-node `obol.stack/ethereum-<id>/…` routes; use `network expose` or a port-forward to talk to one node directly. Each network namespace also has an `ethereum-<id>-metadata` ConfigMap listing its endpoints. `obol.stack` only resolves on the host (see the DNS gotcha in the main SKILL.md).

### Use the node from Docker containers (`obol network expose`, v0.19+)

For a charon, a test validator client or any other container on the same host that needs the Stack's node. It runs in the foreground until Ctrl-C, listens on `--bind` (default `127.0.0.1`), pipes each connection through a port-forward, checks the APIs every 15 s and reconnects when a pod restarts. It never exposes the engine API (8551). With neither `--beacon` nor `--execution` it forwards both.

```bash
# Docker Desktop (macOS/Windows): keep 127.0.0.1; containers use host.docker.internal
obol network expose ethereum/<id> --beacon
#   charon --beacon-node-endpoints=http://host.docker.internal:5052

# Linux: bind the docker0 bridge address and use it from the container
obol network expose ethereum/<id> --beacon --bind 172.17.0.1 --beacon-port 15052
#   charon --beacon-node-endpoints=http://172.17.0.1:15052
```

Other flags: `--execution`, `--beacon-port` (5052), `--execution-port` (8545). `--bind` takes an IP literal; loopback and private (RFC 1918, IPv6 ULA) addresses are accepted. The node APIs have no authentication: **never suggest `--allow-public`** (needed for `0.0.0.0` or a public address) unless the user has a firewall that keeps the port off the internet, and say why. It refuses stopped and non-Ethereum deployments. Keep it running (a terminal, tmux, or a user service) for as long as the container needs the node.

### Upgrades, your own image tags and the sync guard (v0.19+)

`obol network sync` renders each node from the templates built into the `obol` binary, so a new obol brings new client versions. Before it does:

- **Hand-set images**: if a client runs an image that matches neither the old pin, the new pin nor `overrides.yaml` (e.g. after `obol kubectl set image …`), sync warns that it will revert it and prints the `overrides.yaml` snippet that keeps it.
- **Durable overrides**: `~/.config/obol/networks/ethereum/<id>/overrides.yaml` (under `$OBOL_CONFIG_DIR`) is merged last into the node's chart values and survives upgrades, e.g.
  ```yaml
  silver:
    image:
      tag: v0.1.0-alpha.23
  ```
- **Silver older than alpha.18**: alpha.18 changed Silver's data format, and v0.18.0 pinned alpha.13, so **every Silver node from v0.18 needs a fresh checkpoint sync** when it moves to v0.19. Sync detects it, prints the steps with the exact data path and asks (default No); without a terminal it needs `--yes`. obol never deletes node data itself. The steps:
  ```bash
  obol network stop ethereum/<id>
  obol network sync ethereum/<id> --yes      # new image, still stopped
  sudo find ~/.local/share/obol/ethereum-<id>/consensus-silver-<network> -mindepth 1 -delete   # data owned by the container user
  obol network start ethereum/<id>           # Silver checkpoint-syncs from scratch (minutes on Hoodi)
  ```
  The data dir is `$OBOL_DATA_DIR` (default `~/.local/share/obol`); use the path sync prints. The execution client's data is kept. Have the user run the delete themselves after checking the path.
- **Pods that were never Ready.** A StatefulSet only rolls Ready pods, so a client crash-looping before the upgrade would keep its old spec. `obol network sync` handles it: after up to a minute it deletes such pods (only never-Ready ones; data is kept) so they come back on the new spec. Only if the change was applied some other way, delete the pod yourself: `obol kubectl -n ethereum-<id> delete pod ethereum-beacon-0` (or the execution pod).
- **Restart loops**: `obol doctor` warns when a node client keeps restarting (3+ restarts, the last within 24 h) and prints the `obol kubectl … logs --previous` command that shows why.

**Silver notes (v0.19):**

- Its beacon API answers only requests whose `Host` is an IP, `localhost`, or a name the Stack configures: the deployment's `ethereum-beacon` service names (bare, `.ethereum-<id>`, `.svc`, `.svc.cluster.local`) and `host.docker.internal`. Anything else gets `403 host not allowed`. Add names via `silver.config` in `overrides.yaml`; that key replaces the Stack's whole block, so repeat its lines (`beacon_api_allowed_hosts = [...]`, `metrics.enabled = true`, `metrics.bind = "0.0.0.0:5054"`). Never use `*`.
- Metrics are on port 5054 (not the API port), scraped by their own ServiceMonitor.
- If Silver misbehaves, run a second node with the default consensus client next to it (own namespace and data), then point consumers (e.g. a dv-pod's `charon.beaconNodeEndpoints`) at it:
  ```bash
  obol network install ethereum --network hoodi --consensus-client lighthouse --id hoodi-lighthouse
  obol network sync ethereum/hoodi-lighthouse
  ```
  On Hoodi, remember that Lighthouse in v0.19 doesn't schedule the Gloas fork (see above).

### Is the node synced?

A DV (or anything validating) needs a node that is **synced**, which means all of:

- **EL**: `eth_syncing` returns `false`, and `net_peerCount` > 0.
- **CL**: `/eth/v1/node/syncing` has `is_syncing: false`, `is_optimistic: false`, `el_offline: false`, and `sync_distance` ≤ 2 slots; `/eth/v1/node/peer_count` `connected` > 0.

Check it, in order of preference:

1. `obol network status ethereum/<id>` (or no argument for every node): pods, EL (`eth_syncing`, head, peers, version), CL (syncing, peers, version) and a verdict — `synced`, `syncing` (with progress), `waiting`, `degraded`, `el_offline`, `unreachable`, `not_deployed`. Gate on `synced` with no peer warnings; `obol -o json network status ethereum/<id>` → `.nodes[].verdict` for scripting. (CLIs before v0.16 show only eRPC health here; fall back to step 2.) From v0.19 a node stopped with `obol network stop` shows since when, and roughly how many slots behind it will be when started (`stopped_for` in JSON); older stops show `time unknown`.
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

### MEV

The Stack runs no MEV-boost sidecar: until Gloas the beacon node builds blocks locally, and from Gloas (ePBS) builder bids arrive in-protocol over p2p, so relays and mev-boost no longer apply. A dv-pod on this node keeps `charon.builderApi: false`, and its DV cluster must agree to run without MEV.

## Deploy a Helm chart or your own service (`obol app`)

`obol app` installs any Helm chart as a managed deployment: a directory `~/.config/obol/applications/<name>/<id>/` (`helmfile.yaml`, `values.yaml`, and from v0.19 `obol-app.yaml` with the release name and last synced revision), deployed with `obol app sync` and replayed on `obol stack up`. Install only writes config; **`sync` deploys**.

```bash
obol app install bitnami/redis --set auth.enabled=false     # repo/chart[@version]
obol app install bitnami/postgresql@15.0.0 --name mydb --id prod
obol app install oci://registry-1.docker.io/bitnamicharts/redis --name cache --id prod
obol app sync mydb/prod                                       # deploy (or re-deploy after editing values.yaml)
obol app list
obol app delete mydb/prod                                     # see "Delete" below
```

What v0.19 changed (check `obol version`; older CLIs behave differently, see the last bullet):

- **Chart references.** `repo/chart` looks the repo up in your local helm repos first (`obol helm repo list`), then the built-in alias **`obol`** (`https://obolnetwork.github.io/helm-charts`, e.g. `obol/dv-pod`, `obol/obol-app`), then ArtifactHub (which lists Obol's repo as `charon`). Direct `https://…/chart-x.y.z.tgz` and `oci://` work too.
- **Names.** Namespace `<name>-<id>`; new installs also default the **release** to `<name>-<id>` (`--release <name>` to choose). Pre-v0.19 apps keep their old release name.
- **values.yaml holds only the user's overrides** (`--values`, `--set`, plus a header pointing at `obol helm show values …`). Chart defaults are read on every sync, so a chart upgrade brings its new defaults. Charts that ship `values-examples/obol-stack.yaml` (dv-pod does) start from that file, comments included. Comments and key order survive, and number-like strings (`0x…` addresses, hashes) stay quoted so helm doesn't read them as floats. Edit the file, then `obol app sync` (or `obol app sync <app>/<id> --set k=v`, which is persisted into values.yaml).
- **Drift guard.** Sync refuses when the live release was changed with `obol helm upgrade`/`rollback` since obol's last sync, naming the differing keys (never values): fold them into values.yaml, or `--force` to revert them. **Don't mix `obol helm upgrade` with an `obol app`-managed release.**
- **Namespaces and existing releases.** `--namespace` and `--release` override the `<name>-<id>` defaults; namespaces the Stack owns (`kube-*`, `default`, `traefik`, `x402`, `llm`, `erpc`, `monitoring`, `obol-frontend`, `reloader`, `hermes-*`, `ethereum-*`, `aztec-*`) are refused. Install refuses when a helm release of the same name already exists there and obol app doesn't manage it; `--adopt` takes it over, seeding values.yaml from its current values (`helm get values`) and using its current revision as the sync baseline. Adopt at the chart version the release runs now (`obol helm list -n <ns>`), then upgrade separately.
- **Chart upgrades**: `obol app upgrade <app>/<id> --version <v>` checks the repo has that version, sets `version:` in the app's `helmfile.yaml`, and syncs with the drift check; if the sync is refused for drift, helmfile.yaml goes back to the old version (`--force` overrides the check). values.yaml is untouched, so read the new chart's notes and example for new settings. A pre-v0.19 values.yaml that is a full copy of the old defaults gets a warning (it would keep old image tags pinned): slim it first with `obol app install <chart>@<new> --name <n> --id <id> --force --values <overrides.yaml>`. (Doing it by hand: edit `version:` in helmfile.yaml, then `obol app sync`.) Charts installed from a versioned `.tgz` URL can't be upgraded this way.
- **Delete keeps data.** Before deleting, obol checks the namespace for PVCs and Secrets that look like key material (dv-pod key shares and ENR keys, keystores). If any exist, or it can't tell, it removes **only the helm release**; namespace, PVCs, Secrets and config stay, and `obol app sync` redeploys onto them. A namespace that also holds other helm releases (e.g. an adopted one in a namespace made by hand) is never deleted as a whole, and `--delete-data` then refuses and names the PVCs to delete. `--delete-data` deletes everything (type the app name on a terminal; `--delete-data --yes` without one). `--keep-data` always removes only the release. `--force` only skips the yes/no prompt and never deletes data. Before v0.19, `obol app delete` removed the whole namespace, PVCs included: on an older CLI never use it on anything holding keys.
- **Secrets without echoing values**: `obol app secret set <app>/<id> <secret> --from-file key=<path>` (or `--from-env-file <file>`) reads the files itself and applies the Secret through kubectl stdin; values never appear in arguments or output. It creates the namespace if needed, so it can run before the first sync. `obol app secret list <app>/<id>` shows names, types and key names only. Have the user write the file; don't read it.
- **Sell hints.** After a sync obol suggests `obol sell http …` for the app's Services, but never for validator/signer charts (dv-pod, charon, charon-relay, remote-signer) or Services on validator, signer or node ports (3600, 3610–3640, 5051/5052/5054, 5062, 7500, 8545/8546/8551, 9000/9001, 30303). Never suggest selling those yourself either.

Full guide: `ObolNetwork/obol-stack/docs/guides/apps.md`. A dv-pod in the Stack follows this flow too: see the `dvpod` skill's `obol-stack.md`.

**Ship your own Dockerfile** with the generic `obol-app` chart (a pod + Service + HTTPRoute wrapper, not DV-specific):

1. Build and push the image to a registry the cluster can reach (Docker Hub, GHCR, a local registry).
2. Write a values file for `obol-app`: at least `image.repository`, `image.tag`, the ports to expose, env and resources. The chart enforces `values.schema.json`; read `ObolNetwork/helm-charts/charts/obol-app/values.yaml` for the full knob set first.
3. `obol app install obol/obol-app --name <svc> --id <id> --values my-values.yaml` (`-f` is `--force`, not a values file), then `obol app sync <svc>/<id>`.

It runs as a Kubernetes Service in the cluster. To make it public and/or billable, use the tunnel section below and the sell-side material in `agent-commerce.md`.

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
