# Networks, apps, and public exposure

Reference for the three lower-traffic but bulky parts of the skill: syncing a blockchain node under `obol network`, deploying an arbitrary Dockerfile via the `obol-app` chart, and exposing routes publicly via `obol tunnel`.

Load this file when the user is doing infra work that isn't the agent commerce loop — bringing up an Ethereum / Aztec node, packaging their own service, or wiring up Cloudflare.

## Sync a blockchain network

Two-stage model: **install** (save config) then **sync** (deploy).

```bash
obol network list                                     # what's available
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

Resulting endpoints (replace `{id}` with the deployment ID they chose):

- Execution RPC: `http://obol.stack/ethereum-{id}/execution`
- Beacon API: `http://obol.stack/ethereum-{id}/beacon`
- Unified eRPC (load-balances across installed execution deployments): `http://obol.stack/rpc`

From inside pods use the cluster-internal DNS instead — `obol.stack` only resolves on the host (see the DNS gotcha in the main SKILL.md).

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

The connector token is a least-privilege, single-tunnel credential — **not** an account-wide API key. Steer users here once they're ready to sell. (Advanced: `obol tunnel setup --management local` / `obol tunnel login` uses a browser login on the host instead, which needs `cloudflared` installed.)

The tunnel publishes **only** the public-safe routes:

- `/services/<name>/*` — x402-gated user services
- `/.well-known/agent-registration.json` — ERC-8004 agent registration
- `/skill.md` — human/agent-readable catalogue of what this Stack is selling

### Critical invariant — never relax route restrictions

The frontend (`/`) and eRPC (`/rpc`) routes are **hostname-restricted to `obol.stack`** in the Traefik Gateway HTTPRoutes. They are meant to be local-only. **Never** remove the hostname restrictions to expose them publicly — the frontend has cluster-admin-like UI capabilities and eRPC is unauthenticated. Exposing either is a critical security flaw. If a user asks to "expose my local RPC through the tunnel", push them toward wrapping it in an `obol-app` service with their own auth layer on a `/services/<name>/*` route instead.

### Tunnel idle timeout (relevance to agent commerce)

The Cloudflare quick tunnel has a ~100s idle timeout on HTTP requests that send no response bytes. For paid agent endpoints, **prefer `stream: true`** on chat completions — the SSE chunks keep the wire warm. Non-streaming responses to slow agents will be dropped by the tunnel before the buffered body arrives. Full discussion in `agent-commerce.md` under "Streaming is the preferred mode".
