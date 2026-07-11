# Agent commerce — sell + buy details

The depth reference for the sell-side and buy-side of the Stack. The main `SKILL.md` carries the framing and `obol sell demo` first-sale path; this file is the working manual for everything past that — picking a `sell` shape, polishing a sub-agent before listing it, picking a `buy` path, and understanding token / chain options.

Load this file when the user is past the demo and either:
- Wants to publish a real billable service (`obol sell inference`, `obol sell http`, `obol sell agent`).
- Wants to consume a paid service (`obol buy inference`, or hand off to the agent for an `obol sell agent` purchase / one-shot HTTP `pay`).
- Is asking about pricing tokens, ERC-8004 registration, or the ServiceOffer lifecycle.

## Sell-side

### Canonical first sale — `obol sell demo`

`obol sell demo` is the canonical first-time seller experience. It deploys a trivial HTTP service behind an x402 gate, registers it on the Cloudflare quick tunnel, waits for the offer to reach `Ready=True`, and prints copy-paste try-it instructions (curl + Python x402 SDK + agent prompt). Use this when the user is new — it's faster than explaining theory.

```bash
obol sell demo                     # default: hello @ 1 OBOL/req on Ethereum mainnet (gas-sponsored buy)
obol sell demo blocks              # 0.0001 USDC/req on base-sepolia (live chain data via eRPC)
obol sell demo quant               # 0.01 USDC/req on base-sepolia (agent-driven analysis report)

obol sell list                     # see deployed offers (alias: `obol sell status`)
obol sell stop <name> -n <ns>      # disable (keeps config)
obol sell delete <name> -n <ns>    # remove
```

`obol sell demo` skips ERC-8004 on-chain registration by default — the demo wallet would need ETH for gas, and back-to-back demos would trigger `setMetadata` reverts on already-registered agents. Run `obol sell register --chain <chain>` later if/when on-chain discovery matters. Pass `--register` to `obol sell demo` to opt in.

Framing for users: **`obol sell demo` is to the Obol Stack what "Hello World" is to a programming language.** Once they've watched a paid request settle end-to-end, the same machinery (`obol sell inference` / `obol sell http` / `obol sell agent`) wraps anything in their cluster.

### Picking a sell shape

Three real-world shapes, plus `demo`:

| Shape | Use when | Upstream is |
|-------|----------|-------------|
| `obol sell inference` | You want to monetise raw LLM completions from your cluster's LiteLLM. | An OpenAI-compatible model gateway. |
| `obol sell http` | You want to monetise any pod's HTTP endpoint (an index, an API, a dashboard). | An arbitrary Kubernetes Service. |
| `obol sell agent` | You want to monetise a *running agent's* replies — skills + memory + curated reference data, not just tokens. | An Agent CR's Hermes endpoint. |

Defaults for examples: **OBOL on Ethereum mainnet** (headline gasless UX) or **USDC on Base** (cheap real money). Reach for `base-sepolia` only for dev / smoke tests, and label it as such.

### `obol sell inference` — monetising LLM completions

```bash
obol sell inference my-model --model qwen3.5:35b --price 10 --per-mtok --token OBOL --chain ethereum
obol sell pricing --pay-to <addr> --chain ethereum --token OBOL
```

(`--pay-to` is the canonical recipient flag everywhere in `obol sell`; `--wallet` still works as a deprecated alias.)

Publishes the agent's LiteLLM inference behind x402. Buyers discover it via the tunnel's `/skill.md` or ERC-8004 registration.

### `obol sell http` — monetising an arbitrary HTTP upstream

```bash
obol sell http my-service \
  --pay-to <addr> \
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

### `obol sell agent` — monetising a specialised sub-agent

The shortest path from "an agent exists" to "buyers can pay it for replies". `obol sell agent <name>` wraps an `Agent` CR (created via `obol agent new <name> --skills ... --model ... --create-wallet`, or inline by `obol sell agent` itself when the user opts in) as an OpenAI-compatible paid endpoint:

```bash
obol sell agent quant --price 10   --token OBOL --chain ethereum            # headline UX: gasless OBOL on mainnet
obol sell agent quant --price 0.01 --token USDC --chain base                # USDC on Base — cheap, real money, mainnet
obol sell agent quant --price 0.01 --token USDC --chain base-sepolia        # use only for dev / smoke tests
```

What happens under the hood: a `ServiceOffer` of `type=agent` references the Agent CR; the serviceoffer-controller resolves it to the agent's Hermes endpoint (port 8642) and publishes `/services/<name>/*`. Buyers POST to `/v1/chat/completions` with an `X-PAYMENT` header — same wire format as `obol sell inference`, but the upstream is a *running agent* (skills + memory + wallet), not a raw LLM. The 402 response includes the agent's model, skill list, and runtime in its `extra` block so buyers can pick the right offer before paying.

#### Polishing the agent before (and while) it sells — earn the margin

A sub-agent is only worth selling if its replies are clearly better than a buyer's own raw LLM call would be. That is the **margin justification**, and it's where the Claude using this skill earns its keep: once the user has run `obol agent new <name> --skills ... --model ... --create-wallet`, the agent's identity, skills, and reference materials live as ordinary files on the host and can be iterated on directly.

**Host paths** (resolve `OBOL_DATA_DIR` from the user's environment if set; otherwise it's `~/.local/share/obol/`):

```
${OBOL_DATA_DIR:-~/.local/share/obol}/agent-<name>/hermes-data/.hermes/
├── SOUL.md                  ← agent identity, objective, persona, tone, refusal policy
├── obol-skills/             ← operator-curated skills; each is a directory with SKILL.md + optional scripts/references
│   ├── <skill>/SKILL.md
│   └── <skill>/references/  ← drop curated docs, schemas, addresses, runbooks here
└── .no-bundled-skills       ← marker present by design — keep the agent narrow, not a generalist
```

Things the outside-Claude should help the user iterate on **before announcing the agent on a marketplace**:

1. **SOUL.md** — sharpen the objective beyond the one-liner from `--objective`. Spell out: the niche, the inputs the agent expects, the outputs it returns (schema if structured), tone, what it explicitly will *not* do, and any "house style" the user wants enforced. A sloppy SOUL.md is the #1 reason a paid agent feels like a worse-than-GPT wrapper.
2. **Skills curation** — `obol agent update <name> --skills +foo,-bar` for additions/removals through the CLI, or directly edit the `obol-skills/` directory. Keep it narrow: an agent selling on-chain analysis doesn't need `gif-search`. The `.no-bundled-skills` marker is already in place to stop Hermes' ~80 stock skills from leaking back in.
3. **Reference data** — drop high-signal artefacts the agent can cite into `obol-skills/<skill>/references/`: chain-specific contract addresses, ABI fragments, protocol docs trimmed to the section the agent actually needs, recent metrics snapshots, internal taxonomy. The agent reads these the same way it reads its SKILL.md.
4. **Try it as a buyer would** — run `curl -N ... /v1/chat/completions ... '"stream": true'` against your own tunnel and read the replies critically. If you wouldn't pay for them, neither will anyone else.

After edits, the agent picks up SOUL.md and skill changes on pod restart; force one with:

```bash
obol kubectl rollout restart deployment/hermes -n agent-<name>
```

`obol agent update` automates the spec-level fields (model, objective, skill list). For deeper iteration on reference materials inside skill directories, direct file edits + a rollout are the workflow.

**Margin framing for the user**: a buyer pays you because your agent embodies operator knowledge (curated skills + reference data + sharpened SOUL) that they don't have. Without that, you're competing on raw LLM price and you'll lose to whoever's selling inference cheapest. The iteration loop above is what turns a generic Hermes shell into something worth its price.

#### The business loop (run every agent idea through it)

```
NICHE → SCOUT → PACK ALPHA → BUILD → EVALUATE → PRICE → SELL → MEASURE → ITERATE or KILL
```

- **Niche**: one agent, one job. "Crypto assistant" is not a niche; "liquidation-risk monitor for Aave positions on Base" is.
- **Scout**: probe comparable services' 402s for live pricing before building. A crowded niche at high prices means demand exists; an empty niche is a graveyard until proven otherwise.
- **Evaluate — the gate**: before listing, write the 10 hardest questions a paying buyer in the niche would ask. Ask the sub-agent all 10, then answer them with a raw model (no niche skills) as baseline. List only if the sub-agent clearly wins ≥ 7 of 10. Keep the question set as a file and re-run after every change — it is the agent's regression test, and skipping it is the #1 way to ship an agent nobody buys twice.
- **Price the answer, not the tokens**: fact lookups backed by your data 0.001–0.01 USDC; analysis turns 0.01–0.10; workflows that save the buyer real money 0.10–5.00. Anchor against scouted competitors; 2× their price is fine if the eval gap shows, 10× cheaper than everyone signals junk.
- **Measure**: revenue is the payTo wallet's on-chain balance — give each offer its own payTo for per-agent attribution and snapshot weekly.
- **Iterate or kill**: steady sales → refresh alpha on a cadence, then test a price raise. No sales in ~30 days → `obol sell delete` the offer, keep the agent, reuse its parts in the next attempt. Killing fast is what lets the user test many niches; a dozen half-alive offers is worse than one great one — curation IS the storefront.

The agent inside the Stack ships with a matching `sub-agent-business` skill, so once the user is in `obol hermes chat` their agent can run this loop itself (scouting via its `discovery`/`buy-x402` skills, building children via `agent-factory`). Host-side, you own the honest quality judgment plus the pieces the in-cluster agent can't reach: tunnel, domain, `sell info` branding, and `sell register` signing.

#### Streaming is the preferred mode

The agent endpoint speaks the OpenAI Chat Completions protocol, including `stream: true` → Server-Sent Events. Both modes work, but **prefer streaming whenever the consumer supports it** for two real reasons:

1. **The Cloudflare quick tunnel has a ~100s idle timeout.** A non-streaming request to a slow agent (think: skill-driven analysis, multi-tool chains) sends zero bytes to the buyer until the agent is done. The tunnel sees an idle connection and drops it before the buffered response arrives. Streaming sends SSE chunks as the agent generates them, which keeps the wire warm indefinitely.
2. **Better UX**: tokens appear as they're produced instead of after a long wall-clock wait.

When suggesting a curl / SDK invocation, pass `"stream": true` by default:

```bash
curl -N -X POST https://<tunnel>.trycloudflare.com/services/quant/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-PAYMENT: <buyer-supplied>" \
  -d '{"model":"hermes-agent","stream":true,"messages":[{"role":"user","content":"explain..."}]}'
```

For non-streaming clients (legacy SDKs, simple webhooks), responses < 90s upstream are safe; longer than that, switch to `stream: true` or expect tunnel drops. There's no server-side keep-alive for buffered responses by design.

### ServiceOffer lifecycle (what happens under the hood)

When the user runs any `obol sell ...` verb, the serviceoffer-controller reconciles a `ServiceOffer` CR through stages:

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

### Storefront branding — `obol sell info`

The tunnel hostname serves a public storefront landing page plus a machine-readable catalogue at `/api/services.json` (and `/skill.md`). Branding is operator-set and applies to every buyer-facing surface — storefront, 402 paywall pages, wallet sign-in, `/api` docs, per-offer landing pages:

```bash
obol sell info                       # buyer's-eye view: branding + every on-sale service
obol sell info <name>                # focus one service + how-to-buy (add --verbose for health)
obol sell info set \
  --display-name "One Dollar Audit" \
  --tagline "A serious security audit. One dollar." \
  --logo-file ./logo.png \
  --theme obol \
  --description 'Ships as a **signed report** — findings ranked by severity.'
obol sell info reset                 # back to defaults (or reset individual fields via flags)
```

The full knob set (all optional, all patch-only):

- `--theme light|dark|obol` — built-in presets (`light` default); `--accent '#hex'` recolors any of them.
- `--logo-file` / `--favicon-file` / `--og-image-file` — inline local images as data: URIs (no hosting, no CORS pain); the OG image drives link previews.
- `--description '<markdown>'` — longer seller copy; safe markdown subset (bold, lists, links, small headings) rendered on the storefront and paywall pages.
- `--css-file custom.css` — capped custom stylesheet injected after the theme; target the stable `data-obol="…"` attributes (e.g. `[data-obol="price"]`). This is the styling API — write CSS against these hooks, not against class names.
- `--hostname <host> …` — per-origin override for an offer bound to its own hostname (each product gets its own identity; unset fields inherit the storefront's). `--contact-email` stays storefront-wide.

`sell info` shows what buyers see (only operationally-ready offers); operator health and conditions (including draining/not-ready offers) live under `obol sell status`. Run `sell info` with the user after any change — it's the fastest "would I buy from this storefront?" check. For a visual check, open the tunnel URL in a browser, and curl a paid route with `Accept: text/html` to see the branded 402 checkout page.

### Surviving restarts — `obol sell resume`

Sell offers are persisted and replayed: `obol stack up` re-publishes every offer automatically after a reboot, and `obol sell resume` does the same on demand. On Linux, `obol sell resume --install-boot-unit` installs a systemd user unit so offers come back without anyone at the keyboard. (`obol sell mcp` is the exception — foreground-only, no offer, not resumed.)

### `obol sell mcp` — paid MCP tools

`obol sell mcp [name]` runs a foreground x402-paid MCP server that forwards buyer JSON args to a backend HTTP service, injecting the **seller's own API key** so the buyer never sees it. Payment rides MCP `_meta`. Use it to resell metered access to an upstream API as an MCP tool; remember it's foreground-only and not persisted.

### ERC-8004 agent registration

Registration is **enabled by default** on `obol sell inference|http|agent` — each offer gets a RegistrationRequest, and the controller publishes `/.well-known/agent-registration.json` on the tunnel. Shape it with `--register-name`, `--description`, `--register-skills` (OASF tags), `--register-domains`, `--register-metadata`; opt out with `--no-register`. The **on-chain** identity mint is a separate operator action:

```bash
obol sell register --chain <mainnet|base|base-sepolia> [--name <s>]
```

The controller watches the chain selected by the offer's payment network for the matching registration tx — it never submits transactions itself. **Don't recommend a specific marketplace URL to the user** — the agent-registry / marketplace ecosystem is evolving rapidly; let the user pick the registry they want and just make sure their agent is registered so they can be found.

## Buy-side

### Buying inference vs. buying agents — they answer different needs

Get this distinction right before recommending either path. They look similar (both go through x402, both pre-sign auths, both end at `/v1/chat/completions`) but solve different problems:

- **Buying inference is renting a brain.** You do this when your own Obol Agent can't run its model locally — Ollama isn't installed, the user doesn't have an Anthropic / OpenAI API key, the local hardware can't fit the model they want, or they specifically want a hosted model they don't otherwise have access to. The purchase is undifferentiated LLM completions; what you get back is tokens, nothing more. Sellers compete on price / latency / model quality.
- **Buying an agent is renting specialised work.** You do this when you want a *task done on your behalf* — drafting on-chain trades, monitoring a validator set, summarising a Discord, writing and publishing a Farcaster post, etc. The seller is another agent (skills + memory + wallet), not a raw model. You pay per turn for an action, not per token for completion. This is also where the marketplace dynamic lives: anyone running the Stack can publish a specialised agent via `obol sell agent` and earn from buyers who don't want to build it themselves.

Mental model: **inference is the substrate, agents are the product.** A user with no local model who wants their agent to *exist* buys inference; a user whose agent works fine but lacks a particular skill buys an agent. Some users will buy both — paid inference powering their own agent, while their agent reaches out to other agents for specialised tasks.

### Buy paths from the host CLI

**Inference (pre-paid model budget) — `obol buy inference`:**

```bash
obol buy inference https://seller.example/          # interactive: walks the catalogue, previews cost, confirms
obol buy inference https://seller.example/ --agent research   # pay from agent `research`'s wallet AND switch only it to the paid model
obol buy inference https://seller.example/ --set-default      # promote the paid model globally + sync every agent
```

The seller URL is positional (omit it to use the default storefront). The command walks the seller's `/api/services.json` catalogue, auto-resolves the model and payment token from the offer, and on a TTY prompts through: auto-top-up Y/N → request count with a cost preview → final confirm. It then pre-signs authorisations via the buying agent's remote signer, creates a `PurchaseRequest`, and publishes `paid/<remote-model>` through LiteLLM (the in-pod `x402-buyer` sidecar spends one auth per call — bounded spend by construction). Useful flags: `--model` (only needed when the seller lists several), `--count`/`--budget` (non-interactive sizing), `--auto-refill` with `--refill-threshold`/`--refill-count` (agent-managed top-ups), `--cost-cap` (refuse refills if the seller hikes the per-request price above this ceiling), `--expected-agent-id` (opt-in ERC-8004 identity check — default skips verification). After it returns, the user can call the model from any OpenAI-compatible client pointed at the cluster's LiteLLM — and **call it with `stream: true`** for the same tunnel-idle-timeout reasons as the sell side.

**Agent services and ad-hoc HTTP — agent-driven via `obol hermes chat` → `buy-x402`:** there is no `obol buy agent` host-side wrapper today. Buying from another agent (or paying a one-shot HTTP service) is best done from inside the agent's chat — it knows how to probe the 402, pick the right token, sign, send the actual request, and interpret the reply. The skill lives at `${OBOL_SKILLS_DIR:-/data/.hermes/obol-skills}/buy-x402/scripts/buy.py` (`buy.py pay <url>` for one-shots; `buy.py buy <name> ...` for inference-shaped budgets).

Don't have the outside Claude `kubectl exec` into the pod and drive `buy.py` directly unless the user explicitly wants a dry-run for debugging.
