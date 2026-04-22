---
name: test-a-dv-cluster
description: Run `charon alpha test` suites against an Obol Distributed Validator node or cluster to diagnose infra, peers, beacon node, validator client, and MEV relay setup. Use whenever a user wants to verify a DV node is healthy, bring-up is correct before activation, or a freshly rejoined cluster is ready. Prefer `docker exec` / `kubectl exec` into a running Charon and always pass `--publish` so results correlate to the live ENR.
---

# Test a Distributed Validator Cluster

`charon alpha test` runs diagnostic suites covering the full DV stack. This skill routes users to the right suite, the right execution mode, and the right flags.

## When to use this skill

- User finished setting up a DV node (via CDVN, LCDVN, `dv-pod`, or the Obol Stack) and wants to verify it works **before activation**.
- User asks generically "is my cluster healthy?" and the answer is a one-shot test, not live monitoring (for live monitoring, use `obol-monitoring`).
- User is troubleshooting attestation failures, slow consensus, or peer connectivity and needs a baseline capability check.
- User mentions `charon alpha test` by name, or the suites: `infra`, `peers`, `beacon`, `validator`, `mev`.

## Test suites

`charon alpha test <suite>` — six subcommands:

| Suite | What it checks | Prerequisites | When to run |
|-------|----------------|---------------|-------------|
| `infra` | Local machine — CPU, memory, disk I/O, network, clock | **None.** Works on any host. | **Start here for solo diagnostics.** The only suite that's useful before a cluster is fully assembled. |
| `peers` | P2P connectivity to cluster peers + relays; RTT; ENR validity | Completed DKG (`.charon/cluster-lock.json` in place); other operators' Charons reachable | Once the whole cluster is up post-DKG |
| `beacon` | Beacon node endpoint(s) — latency, sync status, API support | Running beacon node (URL passed via `--endpoints` or read from env) | Whenever BN is stood up or changed |
| `validator` | Validator client API reachability | Running VC pointed at Charon's validator API (port 3600) | After VC is configured |
| `mev` | MEV relay reachability + API behavior | MEV relays configured (not `MEV=mev-none`) | After MEV config |
| `all` | Runs all five above | Prereqs of every suite above | Final pre-activation verification. Use sparingly — one slow BN or MEV relay will drag the whole run. |

## Default execution pattern

**Preferred: `docker exec` / `kubectl exec` into a running Charon + `--publish`.**

Why this matters: `--publish` signs the test report with the Charon ENR private key and posts it to the Obol API. When run *inside* the container, the signing key is the real ENR key at `.charon/charon-enr-private-key`, so the published result correlates to the actual production ENR. If `--publish` is used outside that container (or without the key file), Charon silently generates a temporary key and publishes under a throwaway ENR — the result isn't tied back to the user's node, which defeats most of the point.

```bash
# CDVN / LCDVN — Docker Compose stack
docker compose exec charon charon alpha test <suite> --publish

# Obol Stack / helm-charts dv-pod — Kubernetes
kubectl exec -n <ns> <charon-pod> -c charon -- charon alpha test <suite> --publish
```

**Always pass `--publish`** unless the user explicitly objects. Cost is negligible, and it buys: (1) correlation to the user's real ENR, (2) fleet-level visibility into DV health for the Obol team, (3) a signed receipt the user can reference when asking for support.

**Fallback: host-run via `docker run` or a native `charon` binary.** Accept the temp-key tradeoff; `--publish` still works, just anonymously.

```bash
# No running container — one-shot via docker image
docker run --rm obolnetwork/charon:latest alpha test infra --publish
```

## Key flags (apply to every suite)

| Flag | Default | Guidance |
|------|---------|----------|
| `--publish` | `false` | **Default on** in every invocation this skill recommends. |
| `--publish-address` | `https://api.obol.tech/v1` | Leave alone unless user explicitly targets a staging/test endpoint. |
| `--publish-private-key-file` | `.charon/charon-enr-private-key` | Inside a running Charon container this path already resolves correctly; don't override. |
| `--output-json <path>` | (stdout only) | Pass when archiving results or combining with `--quiet`. |
| `--quiet` | `false` | Requires `--output-json`. Use in CI / scripts. |
| `--timeout <dur>` | `1h` | Shorten for quick sanity checks (e.g. `--timeout 5m`). |
| `--test-cases a,b,c` | (all cases in suite) | Filter to specific named tests. `charon alpha test <suite> --help` lists available case names. |

## Solo user / pre-activation path

If the user is bringing up their node first and cluster-mates haven't completed their side yet — which is the norm in the DKG-to-activation window — cluster-wide suites (`peers`, `beacon`-against-shared-BN, `validator`, `all`) will fail *by design* because the prerequisites aren't in place. Don't let the user chase false negatives.

Route them to `infra` first:

```bash
docker compose exec charon charon alpha test infra --publish
```

`infra` is the single most useful suite for a solo user who just wants to know whether their machine is a healthy host for a Charon. It's independent of the rest of the cluster and is where most first-time setup issues (slow disk, clock skew, too little RAM, bad NAT/firewall) get caught.

Only progress to `peers` once the cluster is fully DKG'd *and* all operators have reported their nodes are up. Progress through `beacon` and `validator` after the respective components are configured. Leave `all` for the final pre-activation check.

## Interpreting results

Per-test verdicts: `Good` / `Avg` / `Poor` (measurement tests), `OK` / `Fail` (boolean tests), `Skip` (prereqs not met). Category score: `A` / `B` / `C`. A `C` means at least one `Poor` or one unacceptable `Fail` — always surface to the user.

Each `Poor` or `Fail` result carries a `Suggestion` string written by the Charon team. **Surface suggestions verbatim** — they're the most actionable part of the output.

Common `Poor` patterns to anticipate:

- **`infra`** — high disk write latency, clock skew vs NTP, low RAM, low file-descriptor limit. Surface the exact measurement so the user can compare.
- **`peers`** — elevated RTT to a specific peer or relay. The hostname is in the measurement. If the same peer is slow from multiple tests, it's that operator's side; if all peers are slow, it's the user's network / relay path.
- **`beacon`** — slow `attestation_data` latency. Teku BNs have ~170ms median and that's normal. Lighthouse / Prysm / Nimbus / Lodestar / Grandine should be <10ms — anything slower is worth checking.
- **`validator`** — VC endpoint unreachable. Near-universal root cause: user pointed the VC at the beacon node URL instead of Charon's validator API on port 3600.
- **`mev`** — relay API slow or returning errors. Can be a relay-side issue; test against a second relay before blaming local config.

## Adjacent skills / docs

- Live runtime diagnostics on a cluster that's already activated → `obol-monitoring` (Grafana-based, not `charon alpha test`-based).
- Deploying OVM / reward splits → `deploy-obol-ovm` (in `obol-splits/.claude/skills/`).
- Canonical CLI reference: https://docs.obol.org/docs/charon/charon-cli-reference
- Errors & failure mode catalogue: https://docs.obol.org/docs/faq/errors
- Activation flow: https://docs.obol.org/docs/next/start/activate
