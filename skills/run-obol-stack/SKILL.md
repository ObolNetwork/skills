---
name: run-obol-stack
description: Help a human install, boot, operate, and productise the Obol Stack — Obol's Kubernetes-based agent harness for running blockchain infrastructure locally, exposing services to the public internet, and charging for them via x402 micropayments. Use whenever a user mentions Obol Stack, Obol Agent, Hermes, OpenClaw, x402 payments, agent commerce, ERC-8004, selling inference / APIs from agents, running a local Ethereum or L2 node under `obol network`, deploying a Dockerfile via `obol-app`, or bringing up a Cloudflare tunnel for an agent service. You are helping from OUTSIDE the Stack — the agents inside it have their own skills and take over once the user is at the dashboard.
---

# Run the Obol Stack

The Obol Stack is a local-first agent harness: a k3d Kubernetes cluster, a default Obol Agent with an Ethereum wallet, a free rate-limited RPC (eRPC), the ability to sync real blockchain networks (Ethereum + L2s, Aztec), a Cloudflare tunnel for public exposure, and an x402 payment gateway so agents can charge for what they serve. The niche is **Ethereum-native agent commerce** — an agent syncs chains, builds an index or a service, and sells queries priced in OBOL (or USDC on Base while OBOL support rolls out) to other agents and humans discovering each other via ERC-8004 registries.

**This skill is for the Claude sitting at the user's terminal**, helping them install + operate + productise the Stack. Once the user lands in the Obol Agent's dashboard, control passes to the agent inside the Stack, which has its own skill set. Your job ends at "the agent is live and billable."

**Adjacent audiences this skill is NOT for:**
- Agents running *inside* the Stack — they ship with 20+ embedded skills (see [Handoff to the agent inside](#handoff-to-the-agent-inside)).
- Developers hacking on the Stack's Go code — route them to `obol-stack/.claude/skills/obol-stack-dev/SKILL.md` (invoke with `/obol-stack-dev`) and the repo's `CLAUDE.md`.

## When to use this skill

Match on any of:

- User wants to install / bring up / stop / purge Obol Stack (`obol stack ...`).
- User wants to deploy their own Dockerfile on the Stack and expose it (`obol app install`, `obol-app` helm chart).
- User wants to sync a local Ethereum / L2 / Aztec node and use it (`obol network install`, `obol network sync`).
- User wants to expose an agent service on the internet with a tunnel (`obol tunnel`).
- User wants to **charge** for an agent service — inference, HTTP API, RPC, indexed data (`obol sell ...`, ERC-8004 registration, x402).
- User mentions "OpenClaw", "Obol Agent", "8004", "agent registration", "agent commerce", "payment-gated endpoint", "local inference + tunnel".
- User is running the `obol sell demo` flow (lands in 0.9+) and wants help paying for / interpreting the demo skill.

Don't use this skill for:
- Running a Distributed Validator node → see CDVN / LCDVN / helm-charts CLAUDE.mds and the `test-a-dv-cluster` skill.
- Obol's hosted Grafana cluster monitoring → see the `obol-monitoring` skill.
- Live diagnostics against the *DV* fleet → also `obol-monitoring`.
- Contributor work on the Stack's Go code → see `obol-stack-dev` in the repo.

## Product mental model (keep it short for the user)

Four concepts the user needs, nothing more:

1. **Cluster** — a local k3d Kubernetes cluster, brought up by `obol stack up`. All services run as pods.
2. **Obol Agent** — the AI agent running inside the cluster. Gets its own Ethereum wallet (backed by a remote-signer), a bearer token for its gateway, and a pre-installed skill set. As of Stack 0.9, the default agent runtime is **Hermes** ([github.com/NousResearch/hermes](https://github.com/NousResearch/hermes)). OpenClaw is supported as an alternate runtime via `obol agent new --runtime openclaw`. Prefer "Obol Agent" generically when explaining, and name the runtime only when a specific CLI verb requires it (`obol hermes ...`, `obol openclaw ...`).
3. **x402** — HTTP 402 micropayments gateway. Any pod behind `/services/<name>/*` gets payment-gated via Traefik ForwardAuth. Stack 0.9+ supports both **$OBOL on Ethereum mainnet** and **USDC on Base / Base-Sepolia / Ethereum / Polygon / Avalanche / Arbitrum**. Critical $OBOL property: when buyers pay in OBOL on mainnet, the Obol-operated facilitator (`x402.gcp.obol.tech`) batches an EIP-2612 permit with the on-chain transfer at settlement — **buyers never spend ETH on gas** and skip the one-time `approve(Permit2, max)` step. Sellers receive OBOL directly.
4. **Tunnel** — Cloudflare quick tunnel that publishes `/services/<name>/*`, the `/skill.md` service catalogue, and `/.well-known/agent-registration.json` for ERC-8004 discovery. The frontend and eRPC routes are hostname-restricted to `obol.stack` and **must never** be exposed to the tunnel.

## Prerequisites (always check these first)

Before any install/bring-up advice, confirm:

- **Docker** running. `docker ps` to verify.
  - Linux → Docker Engine; macOS / Windows → Docker Desktop.
- **Ollama** installed + running with at least one pulled model, **if** the user wants local inference. `ollama serve` in background + `ollama pull qwen3.5:35b` (or a smaller model for low-RAM boxes). Tool-call-capable models matter for agent use.
  - If the user plans to use Anthropic or OpenAI directly via LiteLLM, Ollama is optional — they'll run `obol model setup --provider anthropic|openai` after bring-up.
- **Foundry** (optional) — for on-chain payment testing. `foundryup` to install.
- **Disk / memory**:
  - Cluster + agent alone: ~10GB disk, ~4GB RAM.
  - Plus an Ethereum mainnet full node: **~1TB disk** (execution) + ~200GB (consensus) + 16GB+ RAM recommended.
  - For a testnet (sepolia, hoodi): ~200GB disk is plenty.
- **Ports free**: `8080` (Traefik). `~/.config/obol/` writable.

Don't skip these — most "stack up fails" reports trace back to Docker not running, not enough disk, or Ollama missing.

## Installation

One-liner:

```bash
bash <(curl -s https://stack.obol.org)
```

What it does: installs the `obol` CLI plus `kubectl`, `helm`, `k3d`, `helmfile`, `k9s` into `~/.local/bin/`, configures PATH, offers to start the cluster. On success:

```bash
obol version
```

should report a version. Subsequent updates:

```bash
obol update      # update CLI + pinned tools
obol upgrade     # upgrade in-cluster components
```

**For contributors working from source** (not the typical user path), they'll use `OBOL_DEVELOPMENT=true ./obolup.sh` from inside a repo checkout — don't recommend this to end users.

## First boot (the happy path)

```bash
obol stack init                           # allocates a petname stack ID, writes ~/.config/obol/
obol stack up                             # creates the k3d cluster, deploys infra, creates the default Hermes agent + wallet
obol hermes chat                          # opens an interactive chat TUI against the default agent
```

`stack up` is slow on first run — 2-5 min — and does a lot:
- Creates the k3d cluster
- Deploys Traefik + Cloudflared + LiteLLM + eRPC + Monitoring + x402 verifier + ServiceOffer controller + frontend
- Creates the default Hermes agent (namespace `hermes-obol-agent`) with an Ethereum signing wallet and an embedded skill set
- Auto-configures LiteLLM with any host Ollama models it finds

Crucially, **the default agent is created by `stack up` itself**. `obol agent new` is for creating **additional** agents beside the default, each with its own wallet and skill set. Don't tell users to run `obol agent new` immediately after `stack up` unless they want a second agent.

**Talking to the default agent:**
- `obol hermes chat` — interactive chat TUI in the terminal (the most direct path to "is the agent alive and does it route to my LLM?")
- `obol hermes setup` — interactive flow to wire up messaging integrations (Telegram, Discord, Slack, etc.) so the agent can ping the user out-of-band when long-running work finishes
- `obol hermes skills list` — live skill catalogue
- `obol hermes <anything>` is a passthrough to the in-cluster Hermes binary; `obol hermes --help` is the source of truth.

After bring-up, sanity-check pods:

```bash
obol kubectl get pods -A
```

Expect `Running` / `Completed` for every pod. Any `CrashLoopBackOff` / `Pending` / `ImagePullBackOff` → go to [Debugging](#debugging).

## The `obol` CLI surface

The top-level verbs. Use `obol <verb> --help` for full details rather than memorising subcommand flags — they evolve.

| Verb | What | When to reach for it |
|------|------|---------------------|
| `stack` | `init`, `up`, `down`, `purge` | Cluster lifecycle. `down` preserves config + data; `purge --force` wipes everything. |
| `agent` | `init`, `new`, `setup`, `sync`, `auth`, `list`, `delete`, `wallet` | Manage agent instances. `init` (re)creates the stack-managed default; `new --runtime hermes\|openclaw` spawns an additional instance. |
| `hermes` | passthrough to the native Hermes CLI inside the default agent pod | `chat`, `skills`, `config`, `setup` (messaging integrations), `dashboard`, etc. Default runtime as of Stack 0.9. |
| `openclaw` | `onboard`, `setup`, `sync`, `list`, `delete`, `dashboard`, `cli`, `token`, `skills` | OpenClaw-specific runtime ops (alternate runtime). |
| `network` | `list`, `install`, `add`, `remove`, `status`, `sync`, `delete` | Deploy a blockchain network (ethereum / aztec). Two-stage: `install` writes config, `sync` deploys. |
| `app` | `install`, `sync`, `list`, `delete` | Deploy any Helm chart from Artifact Hub or your own Dockerfile via the `obol-app` chart. |
| `sell` | `demo`, `inference`, `http`, `list`, `status`, `stop`, `delete`, `pricing`, `register` | Create payment-gated endpoints. **`demo` is the canonical first-sale experience (0.9+)** — start there with new users. |
| `model` | `setup`, `status` | Switch LiteLLM between Ollama / Anthropic / OpenAI / custom OpenAI-compatible endpoints. Patches the in-cluster ConfigMap + restarts LiteLLM + syncs agents. |
| `tunnel` | `status`, `login`, `provision`, `restart`, `logs` | Cloudflare tunnel for public exposure. |
| `kubectl` / `helm` / `helmfile` / `k9s` | passthrough | Run the underlying tool with `KUBECONFIG` auto-set to the cluster. Prefer these over running the raw tools. |
| `update` / `upgrade` | — | CLI + cluster components respectively. |
| `version` | — | Report version. First thing to check when debugging drift. |

Always read `obol <verb> --help` fresh in a session — the help is the source of truth; this table rots.

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

**Client diversity nudge**: same as CDVN — if the user is running mainnet, push them off the default EL/CL to something non-majority. Rationale is network-level (correlated client failures hurt Ethereum) not just Stack-level.

Resulting endpoints (replace `{id}` with the deployment ID they chose):
- Execution RPC: `http://obol.stack/ethereum-{id}/execution`
- Beacon API: `http://obol.stack/ethereum-{id}/beacon`
- Unified eRPC (load-balances across installed execution deployments): `http://obol.stack/rpc`

From inside pods use the cluster-internal DNS instead (see [DNS gotcha](#dns-gotcha) below).

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

Exposed inside the cluster as a Kubernetes Service. To make it public and/or billable, go through [Cloudflare tunnel](#public-exposure-via-cloudflare-tunnel) + [x402 sell-side](#agent-commerce-sell-side).

## Public exposure via Cloudflare tunnel

```bash
obol tunnel login                  # authenticate against Cloudflare
obol tunnel provision              # creates the tunnel
obol tunnel status                 # prints public URL
obol tunnel logs                   # tail cloudflared logs
obol tunnel restart                # on change
```

The tunnel publishes **only** the public-safe routes:
- `/services/<name>/*` — x402-gated user services
- `/.well-known/agent-registration.json` — ERC-8004 agent registration
- `/skill.md` — human/agent-readable catalogue of what this Stack is selling

### Critical invariant — never relax route restrictions

The frontend (`/`) and eRPC (`/rpc`) routes are **hostname-restricted to `obol.stack`** in the Traefik Gateway HTTPRoutes. They are meant to be local-only. **Never** remove the hostname restrictions to expose them publicly — the frontend has cluster-admin-like UI capabilities and eRPC is unauthenticated. Exposing either is a critical security flaw. If a user asks to "expose my local RPC through the tunnel", push them toward wrapping it in an `obol-app` service with their own auth layer on a `/services/<name>/*` route instead.

## Agent commerce (sell-side)

The sell-side is where the Stack differentiates — turning a pod into a billable service in one command.

### Canonical first sale — `obol sell demo`

Starting in Stack 0.9, `obol sell demo` is the canonical first-time seller experience. It deploys a trivial HTTP service behind an x402 gate, registers it on the Cloudflare quick tunnel, waits for the offer to reach `Ready=True`, and prints copy-paste try-it instructions (curl + Python x402 SDK + agent prompt). Use this when the user is new — it's faster than explaining theory.

```bash
obol sell demo                     # default: hello @ 1 OBOL/req on Ethereum mainnet (gas-sponsored buy)
obol sell demo blocks              # 0.0001 USDC/req on base-sepolia (live chain data via eRPC)
obol sell demo quant               # 0.01 USDC/req on base-sepolia (agent-driven analysis report)

obol sell list                     # see deployed offers (alias: `obol sell status`)
obol sell stop <name> -n <ns>      # disable (keeps config)
obol sell delete <name> -n <ns>    # remove
```

`obol sell demo` skips ERC-8004 on-chain registration by default — the demo wallet would need ETH for gas, and back-to-back demos would trigger `setMetadata` reverts on already-registered agents. Run `obol sell register --chain <chain>` later if/when on-chain discovery matters. Pass `--register` to `obol sell demo` to opt in.

The framing for users: **`obol sell demo` is to the Obol Stack what "Hello World" is to a programming language.** Once they've watched a paid request settle end-to-end, the same machinery (`obol sell inference` / `obol sell http`) wraps anything in their cluster.

### Selling inference from the agent's LLM gateway

```bash
obol sell inference my-model --model qwen3.5:35b --price 0.01 --per-mtok
obol sell pricing --wallet --chain base-sepolia
```

This publishes the agent's LiteLLM inference behind x402. Buyers discover it via the tunnel's `/skill.md` or ERC-8004 registration.

### Selling an arbitrary HTTP upstream

```bash
obol sell http my-service \
  --wallet <addr> \
  --chain base \
  --price 0.001 --per-request \
  --upstream http://my-service.my-ns.svc.cluster.local \
  --port 8080 \
  --namespace my-ns \
  --health-path /healthz
```

Any pod in the cluster that exposes a Service can be wrapped. Common pattern:
1. Deploy the upstream via `obol app install` + `obol app sync`.
2. Wrap it with `obol sell http`.
3. Announce via `obol sell register --name my-service --private-key-file <file>` (publishes to ERC-8004).

### ServiceOffer lifecycle (what happens under the hood)

When the user runs `obol sell http`, the serviceoffer-controller reconciles a `ServiceOffer` CR through stages:

1. `ModelReady` — the upstream's model (if inference) is resolvable.
2. `UpstreamHealthy` — upstream passes the health check.
3. `PaymentGateReady` — x402 Traefik Middleware is attached.
4. `RoutePublished` — HTTPRoute is live at `/services/<name>/*`.
5. `Registered` — RegistrationRequest reconciled; optional ERC-8004 side effects.
6. `Ready` — buyers can now pay and consume.

Surface this progression to the user when troubleshooting a stuck offer:

```bash
obol kubectl get serviceoffer -A                   # check status
obol kubectl describe serviceoffer <name> -n x402  # see which stage is stuck
```

### Pricing — $OBOL on mainnet vs USDC

Token / chain support in Stack 0.9+:

| Token | Chain(s) | Settlement | Notes |
|-------|----------|------------|-------|
| **$OBOL** | `ethereum` (mainnet) | Permit2 + EIP-2612 with facilitator gas sponsorship | Buyers sign a permit off-chain; the Obol facilitator (`x402.gcp.obol.tech`) batches `permit()` with `transferFrom` at settlement. **Buyers spend zero gas**, never need ETH, skip the one-time approve. |
| **USDC** | `base`, `base-sepolia`, `ethereum`, `polygon`, `polygon-amoy`, `avalanche`, `avalanche-fuji`, `arbitrum-one`, `arbitrum-sepolia` | EIP-3009 `transferWithAuthorization` | Standard x402 USDC flow. Facilitator pays the on-chain settlement gas. |

**The OBOL-on-mainnet flow is the headline UX**: buyer signs an off-chain message, seller receives OBOL, neither party touches gas tokens. Lead with this when explaining "why pay in OBOL" — it's the most concretely better-than-card experience the Stack offers.

When quoting prices, always name the unit explicitly (`0.01 OBOL / MTok`, `0.001 USDC / request`). Don't write `$0.01` — the payment rail matters.

**Testing locally without real chain ops**: x402-verifier runs with `verifyOnly: true` for ForwardAuth; `foundryup` lets the user fake-sign EIP-3009 auths for local smoke tests.

### ERC-8004 agent registration

Publish the agent's wallet + service catalogue to an ERC-8004 registry:

```bash
obol sell register --name <service> --private-key-file <path>
```

This signs a RegistrationRequest on-chain. The registered agent then appears in any ERC-8004-compatible discovery tool. **Don't recommend a specific marketplace URL to the user** — the agent-registry / marketplace ecosystem is evolving rapidly; let the user pick the registry they want and just make sure their agent is registered so they can be found.

## Agent commerce (buy-side — handoff)

The buy-side lives **inside** the agent pod. The current skill name is `buy-x402` (formerly `buy-inference` / `buy`); the embedded scripts live under `${OBOL_SKILLS_DIR:-/data/.hermes/obol-skills}/buy-x402/scripts/buy.py` for Hermes (or `/data/.openclaw/skills/buy-x402/scripts/buy.py` for OpenClaw). Outside Claude's role:

1. Walk the user to `obol hermes chat` (or `obol openclaw dashboard <id>` for OpenClaw runtimes) and have them ask the agent to probe / pay an x402 endpoint.
2. Hand off — the Obol Agent inside the Stack knows how to use `buy-x402` to probe a remote 402 endpoint, pre-sign ERC-3009 / Permit2 authorisations, and route through the `x402-buyer` sidecar to spend them.

That's it. Don't have the outside Claude kubectl-exec into the pod and drive `buy.py` manually unless the user explicitly wants a dry-run for debugging.

## The Obol Agent

**Default runtime as of Stack 0.9: Hermes.** OpenClaw is supported as an alternate runtime via `obol agent new --runtime openclaw`. The Stack is agent-runtime-agnostic by design; talk in terms of "the Obol Agent" generically and only name the runtime when a CLI verb requires it.

Per-agent:
- Unique Ethereum signing wallet, backed by a remote-signer Service in the same namespace. Back it up: `obol agent wallet backup -o ~/obol-wallet-backup.json --passphrase "..."`. **Back the export up externally** — losing it loses the agent's on-chain identity.
- An API server bearer token: `obol agent auth [<instance>]` (regenerate with `--regenerate`).
- An embedded skill set (covers cluster diag, Ethereum reads, local-wallet sending, DV monitoring, DeFi concepts, L2 routing, building-block patterns, security, indexing, orchestration, x402 buy/sell, and more — exact list grows).

**Always have the user list skills fresh** rather than recite from memory:

```bash
# Hermes (default)
obol hermes skills list                 # live catalogue
obol hermes skills add <package>
obol hermes skills remove <name>

# OpenClaw (alternate)
obol openclaw skills list <instance>
obol openclaw skills add <package>
obol openclaw skills remove <name>
```

Skill packages come from the [`ObolNetwork/skills`](https://github.com/ObolNetwork/skills) repo (global skills, also published as a Claude Code plugin — see "Adjacent Claude integration" below), the embedded skills shipped in the `obol` binary itself, and from each runtime's broader skill ecosystem. The agent is meant to grow — telling a user "your agent can do X" without checking the live catalogue will misroute them.

### Adjacent Claude integration

Stack 0.9 also ships a public Claude Code plugin at [`ObolNetwork/skills`](https://github.com/ObolNetwork/skills). If the user is on Claude Code, recommend installing it so future sessions get this very skill (`run-obol-stack`) plus the others (DV testing, fleet monitoring, etc.) without having to copy-paste files:

```
/plugin marketplace add ObolNetwork/skills
/plugin install obol@obol
```

Reload plugins if needed (`/reload-plugins`). The plugin includes this skill, so once installed, future Claude sessions will pick it up on relevant prompts automatically.

## Debugging

Lead with these, in order:

```bash
obol kubectl get pods -A                   # overall cluster health
obol kubectl logs -n <ns> <pod>            # logs for a specific pod
obol kubectl describe pod -n <ns> <pod>    # events / scheduling issues
obol k9s                                   # interactive TUI — fastest for poking around
obol tunnel status                         # is the tunnel live?
obol tunnel logs                           # cloudflared tail
obol version                               # CLI version for bug reports
```

Common failure modes:

- **`stack up` hangs at image pulls**: Docker is running but out of disk, or Docker Desktop's pull limit is rate-limited. `docker system prune -af` if safe.
- **Pods `CrashLoopBackOff` after bring-up**: almost always means a bind-mount or secret didn't materialise. `obol kubectl describe` the failing pod — look at events.
- **Can't reach `http://obol.stack/`**: local DNS isn't resolving. Check `/etc/hosts` or your OS DNS resolver — the installer wires `obol.stack` to `127.0.0.1`. On macOS, sometimes needs a restart of `mDNSResponder`.
- **LiteLLM returns empty responses**: host Ollama isn't reachable from the cluster. Test with `obol kubectl run -n llm ollama-test --rm -it --image=curlimages/curl -- curl -s http://ollama.llm.svc.cluster.local:11434/api/tags`.
- **ServiceOffer stuck**: go through the stage list in [ServiceOffer lifecycle](#serviceoffer-lifecycle-what-happens-under-the-hood) — each stage has a distinct root cause.

### DNS gotcha

- `obol.stack` resolves **only on the host** (macOS DNS resolver / `/etc/hosts` entry).
- **From inside any pod**, `obol.stack:8080` will not resolve. Use the cluster-internal DNS:
  - `http://traefik.traefik.svc.cluster.local/services/<name>/...` for user-service routes.
  - `http://ollama.llm.svc.cluster.local:11434` for in-cluster Ollama reach.
  - `http://<svc>.<ns>.svc.cluster.local` is the generic pattern.

This bites every new user the first time they try to `kubectl exec` into a pod and curl `obol.stack`.

## Invariants and footguns

- **Never expose the frontend (`/`) or eRPC (`/rpc`) routes to the public tunnel** — they are hostname-restricted to `obol.stack` for a reason. Exposing them is a critical security flaw.
- **Wallet backups at `~/.config/obol/obol-wallet-backup-*.json`** (or `$OBOL_CONFIG_DIR/...`) must be protected and externally backed up. Losing them means losing agent identity.
- **Obol Stack is alpha software.** Before a user reports a bug, have them run `obol version`, `obol update`, and `obol upgrade` — version-drift between CLI + in-cluster charts is the single most common cause of weirdness.
- **`OBOL_DEVELOPMENT=true` is for contributors working on the Stack source** — don't set it for end users. It points at `.workspace/` dirs and uses `go run` instead of compiled binaries.
- **`obol stack purge --force` is destructive** — wipes the cluster, config, and data (including wallet backups if the user hasn't copied them out first). Double-check wallet backups are outside `~/.config/obol/` before recommending purge.
- **Don't mix `OBOL_CONFIG_DIR`s across shells** — if the user has multiple Stack checkouts (development worktrees), each has its own cluster state. `KUBECONFIG` is set from `$OBOL_CONFIG_DIR/kubeconfig.yaml`. Running `obol kubectl` from the wrong directory can point at the wrong cluster.

## Handoff to the agent inside

Once the user has `obol hermes chat` open (or the agent's dashboard, depending on runtime) and the agent is responsive, your role as outside-Claude is essentially done. The Obol Agent has its own embedded skills covering:

- Ethereum read-only queries (`cast`-style — blocks, balances, ERC-20, ENS)
- Ethereum signing via the per-agent remote-signer
- Kubernetes cluster diagnostics from inside the cluster
- DV cluster monitoring / audit
- DeFi building blocks (OpenZeppelin patterns, DEX + oracle integration)
- L2 routing (Base, Arbitrum, Optimism, zkSync)
- Indexing (The Graph, Dune, custom)
- Gas / security / MEV / reentrancy patterns

**Have the user run `obol hermes skills list` (or `obol openclaw skills list <instance>` for OpenClaw) to see the live catalogue** instead of reciting it. The list evolves and running it fresh keeps the user on current reality.

Things to hand over to the inside agent rather than driving yourself:
- Running `buy-x402` to pay a remote seller.
- Using the agent's wallet to sign any meaningful tx.
- Querying indexes the agent built.
- Any `cast` call against a chain the agent has synced.

Things to keep doing from outside:
- Operating the Stack itself (`stack up/down`, `app install`, `sell ...`, `tunnel`).
- Upgrading, debugging infra pods, version-drift resolution.
- Setting up a second agent instance.
- Explaining the Stack's mental model to a user before they're in the agent's chat.

## Related products + key docs

- Stack repo + authoritative docs: [`ObolNetwork/obol-stack`](https://github.com/ObolNetwork/obol-stack), [docs.obol.org → Obol Stack](https://docs.obol.org/obol-stack/).
- Stack getting-started (human-facing walkthrough): `ObolNetwork/obol-stack/docs/getting-started.md`.
- Monetize inference guide: `ObolNetwork/obol-stack/docs/guides/monetize-inference.md`.
- The `obol-app` chart: `ObolNetwork/helm-charts/charts/obol-app/` — read `values.yaml` for the full knob surface.
- Obol Claude Code plugin (this skill + others): [`ObolNetwork/skills`](https://github.com/ObolNetwork/skills) — install with `/plugin marketplace add ObolNetwork/skills && /plugin install obol@obol`.
- Hermes (default agent runtime): [`NousResearch/hermes`](https://github.com/NousResearch/hermes).
- OpenClaw (alternate agent runtime): [openclaw.ai](https://openclaw.ai).
- x402 protocol: [x402.org](https://www.x402.org/).
- ERC-8004 reference: [eips.ethereum.org/EIPS/eip-8004](https://eips.ethereum.org/EIPS/eip-8004).
- $OBOL token: [docs.obol.org → OBOL token](https://docs.obol.org/community-and-governance/obol-token/).
- Cloudflared quick tunnels: [Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/).
- Stack-internal dev skill (contributors only): `ObolNetwork/obol-stack/.claude/skills/obol-stack-dev/SKILL.md`.
- DV operator paths (out of scope for this skill): `charon-distributed-validator-node`, `lido-charon-distributed-validator-node`, `helm-charts/charts/dv-pod`, plus the global `test-a-dv-cluster` and `obol-monitoring` skills.
- Canonical agent index: [obol.org/llms.txt](https://obol.org/llms.txt) (once live).
