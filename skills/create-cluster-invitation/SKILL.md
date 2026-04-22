---
name: create-cluster-invitation
description: Create a Distributed Validator (DV) cluster invitation — a cluster-definition that other operators accept, then run a DKG ceremony against to produce a cluster-lock and validator key shares. Use whenever a user wants to set up a new DV cluster (solo-with-friends, squad, institutional, Lido Simple DVT), wants to invite operators to a cluster they're creating, mentions "cluster definition", "DKG", "config_hash", "cluster-lock", "operator ENR", or "invite operators". Prefer the `charon` CLI (via Docker image) path over the SDK; reach for the SDK only when programmatic integration is needed (staking pool apps, institutional workflows, web frontends). **Always encourage the user to verify the cluster's shape before any 32 ETH deposit.**
---

# Create a Distributed Validator cluster invitation

A DV cluster starts with one operator (the **creator**) producing a `cluster-definition.json` — the invitation. The other operators accept it, then all `n` operators run `charon dkg` together to produce key shares + a `cluster-lock.json`. After verification, each operator brings up their Charon node and the cluster is ready for 32 ETH deposits.

This skill walks the creator through that invitation and coordinates the ceremony. It is **not** for running the node after DKG — for that, see CDVN / LCDVN / dv-pod.

## When to use this skill

- User wants to create a new DV cluster and invite operators.
- User mentions `cluster-definition.json`, `config_hash`, `cluster-lock.json`, DKG ceremony, operator ENR.
- User is setting up a solo-with-friends DV, a squad of operators, a Lido Simple DVT cluster, or a custom/institutional cluster.
- User wants to know whether to use the Launchpad UI or the CLI.
- User asks about pointing a DV's withdrawal credentials at a smart contract (OVM / splits).

Don't use this skill for:
- **Running** a DV node after DKG → CDVN (Docker Compose) / LCDVN (Lido) / `helm-charts/charts/dv-pod` (K8s).
- **Testing** a cluster → `test-a-dv-cluster` (`charon alpha test` suites).
- **Deploying the withdrawal-address smart contract** → `deploy-obol-ovm` (OVM) for new clusters, `deploy-obol-splits-legacy` for legacy OWR+0xSplits.
- **Runtime monitoring** → `obol-monitoring` (hosted Grafana).

## Two paths — pick before you start

### Path A — `charon` CLI (Docker image) [PREFERRED]

Straightforward, reproducible, no npm project needed. The user runs one Docker invocation; the other operators either accept via Launchpad (address-mode) or via CLI (ENR-mode). Works on any machine with Docker.

### Path B — Obol SDK (`@obolnetwork/obol-sdk`, npm)

For programmatic integration: staking-pool apps, institutional dashboards, scripted onboarding flows, or anywhere the cluster definition needs to be created as part of a larger TypeScript/Node workflow. See the `ObolNetwork/obol-sdk` CLAUDE.md and `ObolNetwork/obol-sdk-examples` for detail. This skill covers Path A in depth and Path B at a pointer level.

**Default to Path A** unless the user has an explicit integration reason for Path B.

---

## Path A — `charon create dkg` via Docker

### Mental model

```
  [Creator: charon create dkg ...]  →  cluster-definition.json  (the invitation)
                                       └── published to Obol API (via --publish)
                                           with a config_hash other operators use to find it
                                       │
  [Operators accept the definition]   (one of two modes — see below)
                                       │
  [All operators run: charon dkg]    →  cluster-lock.json + validator_keys/ + charon-enr-private-key
                                       └── published to Obol API (via --publish on the dkg command)
                                       │
  [Verify the cluster: charon alpha test, bring-up smoke test]
                                       │
  [Only then: deposit 32 ETH per validator to the cluster's deposit data]
```

Two outputs matter most:
- **`cluster-definition.json`** — the invitation. Contains creator, operators, validators, withdrawal + fee-recipient addresses, threshold, fork version, config hash. Publishable and shareable by config hash.
- **`cluster-lock.json`** — the ceremony's cryptographic proof + deposit data. One per cluster, identical across all operators' machines. Also publishable and crucial to back up.

### Decide the invitation mode

`charon create dkg` supports two mutually-exclusive flags that determine how operators accept:

| Mode | Flag | What operators do to accept |
|------|------|-----------------------------|
| **Address-mode** | `--operator-addresses 0xA,0xB,...` | Operators visit the DV Launchpad, connect the wallet matching their address, sign acceptance in the UI. Use this when the user doesn't know the operators' ENRs upfront — the Launchpad flow walks each operator through generating an ENR and signing T&Cs. |
| **ENR-mode** | `--operator-enrs enr:-Iu4Q...,enr:-Iu4Q...` | Operators pre-share their Charon ENRs with the creator (out of band). The entire ceremony happens via CLI — no Launchpad required. Use this when operators are technical and can run `docker run obolnetwork/charon:latest create enr` on their own first. |

**How to pick:**
- Friends / squad / mixed-technical group → address-mode usually lands smoother, Launchpad's UI handles the acceptance UX.
- Institutional / pro-operator / Lido SDVT / CI-driven → ENR-mode is cleaner and scriptable.
- Unsure → address-mode is the safer default.

If the user is going address-mode, you also need `--publish` — the cluster-definition has to land in Obol API for the Launchpad to discover it by config_hash.

### Gather inputs before running anything

Before you craft the Docker invocation, get these from the user:

1. **Network.** `mainnet`, `sepolia`, `hoodi`. Nudge them off deprecated networks — no `goerli`, `holesky`, `gnosis`, `chiado`.
2. **Cluster name.** Cosmetic. Helpful for operators to identify the invitation.
3. **Number of operators (`n`).** **Minimum 4** for a real DV. More operators → better fault tolerance but higher coordination overhead. Common sizes: 4, 5, 7.
4. **Threshold (`t`).** Defaults to `ceil(2n/3)`. For `n=4` → `t=3`. Warn the user away from custom thresholds — the default is the sweet spot for fault tolerance + security.
5. **Number of validators.** How many DVs the cluster manages. Each validator needs a 32 ETH deposit. Default: 1.
6. **Fee recipient address.** Where MEV + tx-fee tips go. One for all validators, or one per validator.
7. **Withdrawal address.** Where principal + consensus rewards exit to when the validator exits. **Critical decision point — see next section.**
8. **Operator identities.** Either a list of Ethereum addresses (address-mode) or a list of Charon ENRs (ENR-mode). These are equal-length lists — `n` entries.
9. **(Optional) Compounding.** `--compounding` enables 0x02 withdrawal credentials (EIP-7251) — lets a validator accumulate rewards above 32 ETH rather than sweeping them. Recommend **on** for most new clusters, unless the user has a specific reason (e.g. they want auto-sweep to a splits contract).
10. **(Optional) Partial deposits.** `--deposit-amounts 8,8,8,8` — useful for splitting a 32 ETH deposit across multiple tx (institutional compliance / multi-sig workflows).

### The withdrawal-address decision

The withdrawal address is where the validator's exit value ends up. Choices:

- **Plain EOA** — simple, the user's own wallet. Fine for solo-with-friends.
- **Gnosis Safe / multisig** — for shared custody of the principal.
- **Obol Validator Manager (OVM) smart contract** — **recommended for new clusters** that want rewards splitting, role-gated operations, or EIP-7002/7251 withdrawal/consolidation flows on-chain. Deploy the OVM **first** via the `deploy-obol-ovm` skill, grab its address, then pass that address as `--withdrawal-addresses 0x<ovm>` here.
- **Legacy OWR + 0xSplits** — only for users who already have that infra and know why they want it. Use `deploy-obol-splits-legacy` if they need it.

**Cross-reference:** If the user wants the cluster to sit behind an OVM, pause here and route them to `deploy-obol-ovm` first. The cluster-definition burns the withdrawal address into the deposit data; getting it wrong means a re-DKG. Deploy the OVM, verify its ownership + roles, then return to this skill with the OVM address in hand.

### The Docker command (address-mode)

```bash
docker run --rm -v "$(pwd):/opt/charon" obolnetwork/charon:latest \
  create dkg \
  --name "My Cluster" \
  --network hoodi \
  --num-validators 1 \
  --fee-recipient-addresses 0xYourFeeRecipient \
  --withdrawal-addresses 0xYourWithdrawalOrOVM \
  --operator-addresses 0xOp1,0xOp2,0xOp3,0xOp4 \
  --compounding \
  --publish
```

Result: `.charon/cluster-definition.json` in the working dir, and (because of `--publish`) the definition is posted to Obol API. The creator gets back a `config_hash` to share with operators. Operators visit [launchpad.obol.org](https://launchpad.obol.org), paste the hash (or follow a shareable link), connect their wallet matching the address the creator listed, and sign acceptance.

`--publish` requires the creator's wallet to sign Obol's T&C on-chain — the command will walk them through this. Have an Ethereum signer ready.

### The Docker command (ENR-mode)

First, **each operator** generates their ENR on their own machine:

```bash
docker run --rm -v "$(pwd):/opt/charon" obolnetwork/charon:latest \
  create enr
```

This outputs a `.charon/charon-enr-private-key` (must stay secret, never share) and prints the ENR to stdout (must share). The operators send their ENRs to the creator out of band.

Then the creator runs:

```bash
docker run --rm -v "$(pwd):/opt/charon" obolnetwork/charon:latest \
  create dkg \
  --name "My Cluster" \
  --network hoodi \
  --num-validators 1 \
  --fee-recipient-addresses 0xYourFeeRecipient \
  --withdrawal-addresses 0xYourWithdrawalOrOVM \
  --operator-enrs enr:-Iu4Q...,enr:-Iu4Q...,enr:-Iu4Q...,enr:-Iu4Q... \
  --compounding \
  --publish
```

`--publish` is still recommended in ENR-mode — it makes the definition discoverable by config hash so operators can cross-check they have the same file. Operators don't need to visit the Launchpad for acceptance in this mode, but publishing gives them a way to verify the canonical definition and its hash.

### Always publish

Push the user to include `--publish` on **both** `create dkg` and the later `dkg` command. Two reasons:

1. **Discoverability** — operators fetch the canonical definition / lock from Obol API by config hash rather than relying on out-of-band file sharing that can get mangled.
2. **Cross-verification** — each operator can compare their local file's hash against the published one. Disagreement surfaces a corrupted / malicious copy before keys are generated or a deposit lands.

If the user pushes back on publishing, dig into why. Privacy is rarely the right answer — the cluster definition is already a public artifact in practice (the deposit data is on-chain). The only real reason to skip publishing is a pure local-testing exercise.

### Share the config hash with operators

Once `create dkg --publish` succeeds, the creator shares:

- The **`config_hash`** (printed by the command + retrievable from `cluster-definition.json`).
- The **Launchpad URL** (if address-mode) so operators can accept.
- Instructions for operators to either:
  - (address-mode) visit the Launchpad, accept, then when all operators accept they all run `charon dkg` simultaneously, or
  - (ENR-mode) pull the definition via the API and run `charon dkg` simultaneously.

### Run the DKG ceremony

Once all operators have accepted (address-mode) or received the definition (ENR-mode), **every operator** runs the DKG at the same time:

```bash
docker run --rm --net=host -v "$(pwd)/.charon:/opt/charon/.charon" \
  obolnetwork/charon:latest \
  dkg --publish
```

`--net=host` is required for the DKG's P2P exchange (operators connect to each other). The ceremony typically takes under a minute. Each operator's machine produces:

- `.charon/cluster-lock.json` — the cryptographically-signed proof of a successful ceremony. Identical across all operators.
- `.charon/validator_keys/keystore-*.json` + `.txt` — the operator's key shares. **Secret, per-operator, not identical.**
- `.charon/charon-enr-private-key` — the Charon ENR private key. **Secret, per-operator.**
- `.charon/deposit-data.json` — the aggregated deposit data for activating each validator.

`--publish` on the `dkg` command publishes the cluster-lock to Obol API so operators can cross-verify their lock matches the canonical one.

---

## Verify the cluster before any deposit

**This is the most important section. Do not let the user send 32 ETH to a validator whose shape you (the agent) helped configure without human verification.** A misconfigured DV — wrong withdrawal address, wrong fee recipient, wrong operator set, wrong threshold — is not undoable once deposited. Exit-and-redeposit costs the full activation queue + exit queue wait, which can be weeks.

Walk the user through these checks, and **state explicitly that you (the agent) could have made a mistake in any of the inputs above — the human must double-check**:

1. **Inspect the cluster-lock and definition**:
   ```bash
   cat .charon/cluster-definition.json | jq .
   cat .charon/cluster-lock.json | jq '. | {name, operators, validators, threshold, fork_version}'
   ```
   Confirm: operator set is exactly who the user expected (compare addresses / ENRs), threshold matches, withdrawal/fee addresses match, network (`fork_version`) is correct.

2. **If the withdrawal address is an OVM or splits contract**: verify the contract is deployed, owner/beneficiary/reward-recipient roles are correct, and principal-stake parameters match the intended cluster size. Use the `deploy-obol-ovm` skill's `query-ovm.sh` and `query-roles.sh` to read on-chain state.

3. **Spin up the cluster before depositing**. All operators bring up a Charon node (CDVN / LCDVN / dv-pod), pointing at their beacon node. Even without validator funds yet, Charon + VCs should reach `app_monitoring_readyz=1` and consensus must succeed in dry-runs.

4. **Run `charon alpha test` suites** via the `test-a-dv-cluster` skill. At minimum: `infra`, `peers`, `beacon`. Use `--publish` to correlate results to the live ENR. A cluster that can't pass `peers` + `beacon` should not receive a deposit.

5. **Read back the deposit-data one more time**:
   ```bash
   cat .charon/deposit-data.json | jq '.[] | {pubkey, withdrawal_credentials, amount}'
   ```
   `withdrawal_credentials` is the raw bytes — decode it to confirm it matches the withdrawal address. The high byte is the credential version (`0x01` = EOA/contract, `0x02` = compounding).

6. **Only then activate**. See [docs.obol.org: Activate](https://docs.obol.org/docs/next/start/activate).

Say this to the user, verbatim or close to it, whenever they're about to deposit:

> **Before you send 32 ETH: I (the agent) could have put a wrong address in the command we ran. Please confirm the operator set, the withdrawal address, the fee recipient, and the network in `cluster-definition.json` / `cluster-lock.json` match what you expect. If the withdrawal address is a smart contract, verify its on-chain state and ownership. Mistakes here are very hard to undo.**

---

## Path B — SDK (brief)

Reach for `@obolnetwork/obol-sdk` when the cluster creation is part of a larger programmatic flow (frontend, staking pool, institutional dashboard, etc.). The core surface:

```typescript
import { Client } from '@obolnetwork/obol-sdk';

const client = new Client({ chainId: 560048 /* hoodi */ }, signer);
await client.acceptObolLatestTermsAndConditions();     // required once per creator wallet

const configHash = await client.createClusterDefinition({
  name: 'my-cluster',
  operators: [{ address: '0x...' }, /* ... */],
  validators: [{ fee_recipient_address: '0x...', withdrawal_address: '0x...' }],
});

// Operators (their own flow):
await client.acceptClusterDefinition({ address: '0x...' }, configHash);

const lock = await client.getClusterLock(configHash);  // after DKG
```

Full surface is in `ObolNetwork/obol-sdk/CLAUDE.md`. Canonical working examples: [`ObolNetwork/obol-sdk-examples`](https://github.com/ObolNetwork/obol-sdk-examples) — adapt the TS-Example rather than writing from scratch.

SDK handles only the **invitation + lock fetch**. The actual DKG ceremony still runs via the `charon` binary (`charon dkg`) on each operator's machine — the SDK doesn't orchestrate the P2P ceremony itself.

**Pricing alert on the SDK path:** T&C signing is required once per creator wallet, handled by `acceptObolLatestTermsAndConditions()`. Without it, `createClusterDefinition` fails silently — a common first-time footgun.

---

## Integrating with OVM / splits contracts

If the cluster wants a smart contract at the withdrawal address:

1. **Deploy the OVM first** via the `deploy-obol-ovm` skill. OVM is the current-gen choice; legacy OWR + 0xSplits is only for users with existing infra (see `deploy-obol-splits-legacy`).
2. **Grant roles** on the OVM — at minimum a WITHDRAWAL_ROLE to whichever operator will trigger exits, DEPOSIT_ROLE to whoever is running the deposits. `deploy-obol-ovm` has scripts for this.
3. **Use the OVM address as `--withdrawal-addresses`** in `charon create dkg`.
4. **Verify the OVM's state matches expectations** before the deposit (see Verify step 2 above).

---

## Footguns and invariants

- **Each operator's `.charon/validator_keys/` and `.charon/charon-enr-private-key` are SECRET.** Never ask the user to share them or paste them into a chat / log. They're the operator's signing authority for their share.
- **`cluster-lock.json` is CRITICAL to back up.** Losing it is painful but recoverable (all operators have identical copies). Losing it *and* your key shares is catastrophic.
- **Don't run DKG asynchronously.** All `n` operators must be online and running `charon dkg` at roughly the same time. The ceremony is a synchronous P2P exchange.
- **Version-match Charon across operators.** `charon create dkg` and each operator's `charon dkg` + the eventual runtime should be the same Charon major/minor version. Mixing versions has caused incidents in the past.
- **Partial deposits sum to 32 ETH exactly** (or higher multiples per validator). Off-by-one ETH = failed deposit.
- **`--network` is required.** If the user forgets it, `create dkg` fails with "network not specified". The alternative is `--testnet-fork-version` for custom testnets — not needed for mainnet / sepolia / hoodi.
- **Address-mode requires `--publish`.** Operators can't accept from the Launchpad if the definition isn't published.
- **`charon create cluster` ≠ `charon create dkg`.** `create cluster` is the **solo / local testing** shortcut that generates all `n` sets of key shares on one machine — useful for local end-to-end testing but **never for a real multi-operator cluster**. Real clusters always use `create dkg` followed by a real multi-machine DKG ceremony.
- **Obol T&C signing is on-chain** when using `--publish`. The creator needs a small amount of ETH on the target network for the signing gas.

---

## Related skills and docs

- **After DKG, testing**: `test-a-dv-cluster` (`charon alpha test` suites, with `--publish` for ENR correlation).
- **Running the cluster after DKG**: `ObolNetwork/charon-distributed-validator-node` (Docker Compose), `ObolNetwork/lido-charon-distributed-validator-node` (Lido SDVT), `ObolNetwork/helm-charts/charts/dv-pod` (K8s).
- **Smart-contract withdrawal target**: `deploy-obol-ovm` (current), `deploy-obol-splits-legacy` (legacy, on-request).
- **Runtime monitoring**: `obol-monitoring`.
- **SDK deep dive**: `ObolNetwork/obol-sdk/CLAUDE.md`; examples at `ObolNetwork/obol-sdk-examples`.
- **Canonical docs**:
  - Key concepts: https://docs.obol.org/docs/int/key-concepts
  - DKG ceremony: https://docs.obol.org/docs/start/dkg
  - Charon CLI reference: https://docs.obol.org/docs/charon/charon-cli-reference
  - Activation: https://docs.obol.org/docs/next/start/activate
  - Launchpad (hosted acceptance UI): https://launchpad.obol.org
- **Canonical agent index**: https://obol.org/llms.txt
