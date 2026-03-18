```skill
---
name: obol-monitoring
description: Monitor and diagnose Obol DVT cluster performance using their hosted Grafana (Prometheus metrics + Loki logs)
user-invokable: true
---

# Obol Cluster Monitoring

Diagnose health issues, duty failures, and performance issues and opportunities across Obol Distributed Validator Technology (DVT) clusters using Grafana datasources (Prometheus for metrics, Loki for logs).

## Product Context

### What is Charon?

Charon is distributed validator middleware for Ethereum proof-of-stake. A cluster of 4-7 independent nodes each run Charon to coordinate threshold BLS signing for shared validators. If a threshold `t` of `n` nodes agree on duty data and sign it, the duty succeeds. Typical configurations: 3-of-4 (fault tolerance 1) or 5-of-7 (fault tolerance 2).

### Deployment Topology

Each node in a cluster runs:
- **Execution Client (EL)** — Nethermind, Geth, Besu, Erigon (ports 8545/8551)
- **Beacon Node (CL)** — Lighthouse, Teku, Prysm, Nimbus, Lodestar, Grandine (port 5052, metrics 5054)
- **Charon** — DV middleware (P2P port 3610, monitoring/metrics 3620, validator API 3600)
- **Validator Client (VC)** — Lighthouse, Teku, Prysm, Nimbus, Lodestar (connects to Charon's 3600, NOT directly to BN)
- **MEV-boost** (optional) — MEV relay selection (port 18550)

Deployed via docker-compose from [CDVN](https://github.com/ObolNetwork/charon-distributed-validator-node) or [LCDVN](https://github.com/ObolNetwork/lido-charon-distributed-validator-node) repos.

### Duty Workflow Pipeline

Every validator duty flows through these stages. A failure at any stage produces a specific reason code:

```
Scheduler → Fetcher → Consensus (QBFT) → DutyDB → ValidatorAPI → ParSigDB → ParSigEx → SigAgg → AggSigDB → Broadcast
```

- **Scheduler**: Triggers duties at the correct time based on beacon chain state
- **Fetcher**: Gets unsigned duty data from the beacon node API
- **Consensus**: QBFT (Istanbul BFT) ensures all nodes agree on the same data to sign
- **DutyDB**: Stores agreed-upon data, acts as slashing protection
- **ValidatorAPI**: Serves data to the VC, receives partial signatures back
- **ParSigDB/ParSigEx**: Stores and exchanges partial threshold BLS signatures between peers
- **SigAgg**: Aggregates partial signatures when threshold is reached
- **Broadcast**: Submits the final aggregated signature to the beacon node

### Duty Types & Economic Impact

| Duty Type | Timing | Economic Impact | Notes |
|-----------|--------|-----------------|-------|
| `proposer` | Slot start (T+0) | **High** — missed block reward | Rare but high-value |
| `attester` | T + slot_duration/3 (~T+4s) | **Medium** — missed attestation reward + inactivity penalty | Most common duty |
| `sync_message` / `sync_contribution` | Various | **Low** — small sync committee rewards | Only for validators in sync committee |
| `aggregator` / `prepare_aggregator` | T + 2*slot_duration/3 (~T+8s) | **None** — no direct economic reward or penalty | Non-economic, deprioritize |

**Slot timing**: 12 seconds per slot, 32 slots per epoch (6.4 minutes).

## Environment

Set the Grafana API token:
```bash
export OBOL_GRAFANA_API_TOKEN="glsa_..."
```

## Scripts

### cluster_triage.py — First-Pass Health Check

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/cluster_triage.py "Cluster Name" [--network mainnet] [--hours 1]
```

Outputs JSON with: cluster config, health status (readyz), versions, consensus performance, per-peer participation rates, duty failure reasons, P2P connectivity, beacon node health, balance summary, and log availability.

### duty_analysis.py — Slot-Level Deep Dive

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/duty_analysis.py "Cluster Name" 13867535 [--duty attester] [--network mainnet]
```

Reconstructs a chronological timeline of consensus events for a specific slot from Loki logs. Shows per-peer: when consensus started, when pre-prepares arrived, round changes, BN call timings, and the final outcome.

### fleet_overview.py — Multi-Cluster Fleet View

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/fleet_overview.py [--network mainnet] [--hours 1]
```

Aggregates across all clusters: version distribution, BN/VC client diversity, failure rates by reason, worst-performing clusters, and Loki log coverage.

### Manual Queries (if scripts unavailable)

If the agent cannot execute scripts, use these Prometheus queries directly via the Grafana API:

**Cluster health**: `app_monitoring_readyz{cluster_name="X",cluster_network="mainnet"}`
- Values: 1=ready, 2=BN down, 3=BN syncing, 4=insufficient peers, 5=VC not connected, 7=BN zero peers, 8=BN far behind

**Attester failure rate**: `sum(rate(core_tracker_failed_duties_total{cluster_name="X",duty="attester"}[1h])) / sum(rate(core_tracker_expect_duties_total{cluster_name="X",duty="attester"}[1h]))`

**Per-peer participation**: `sum(rate(core_tracker_participation_missed_total{cluster_name="X",duty="attester"}[1h])) by (cluster_peer, peer) * 3600`

**Failure reasons**: `sum(rate(core_tracker_failed_duty_reasons_total{cluster_name="X"}[1h])) by (duty, reason) * 3600`

**Consensus timeouts**: `sum(rate(core_consensus_timeout_total{cluster_name="X",duty="attester"}[1h])) by (cluster_peer) * 3600`

## Triage Workflow

When a user reports a cluster issue, follow this sequence:

### Step 1: Identify the Cluster
Get the cluster name and network (default: mainnet). Run `cluster_triage.py`.

### Step 2: Check Readyz
If any peer has `readyz != 1`, that's the first thing to report:
- **2**: Beacon node is down — check BN container/process
- **3**: Beacon node is syncing — wait for sync to complete
- **4**: Quorum peers not connected — check P2P connectivity, firewall, relay URLs
- **5**: Validator client not connected — check VC is running and pointed at Charon port 3600
- **7**: Beacon node has zero peers — BN is network-isolated, check BN P2P config
- **8**: Beacon node is far behind (>320 slots) — BN needs time to sync or has resource issues

### Step 3: Check Consensus Performance
Compare attester timeout rate to decision rate. If `timeout / (timeout + decisions) > 5%`, the cluster has a consensus problem. Check:
- Which peers have the highest timeout rates (per-peer breakdown)
- What round decisions happen in (round > 1 means round 1 leader was slow)
- Consensus duration p99 (should be <2s for attester)

### Step 4: Identify Struggling Peers
Look at per-peer participation rates. The peer with the lowest success rate is likely the bottleneck. Common causes:
- **High BN latency** (check `app_eth2_latency_seconds` for `attestation_data` endpoint) — Teku BNs have ~170ms median, Lighthouse ~5ms
- **Low BN peer count** (check `app_beacon_node_peers`) — low count means blocks arrive late
- **Old charon version** — check versions, recommend latest stable
- **Relay-only connections** (no direct P2P) — higher latency, check firewall rules

### Step 5: Map Failure Reasons to Fixes
Use the failure reason reference below to provide actionable guidance.

### Step 6: Deep Dive if Needed
If the issue is intermittent or slot-specific, use `duty_analysis.py` for a specific failing slot to reconstruct the timeline.

## Failure Reason Code Reference

### Beacon Node Issues
| Code | What Broke | What To Do |
|------|-----------|------------|
| `fetch_bn_error` | BN API call failed during fetch | Check BN health, syncing status, connectivity. Check `app_monitoring_readyz`. |
| `broadcast_bn_error` | BN rejected the broadcast submission | Check BN logs, version compatibility, disk space. |
| `not_included_onchain` | Duty was broadcast but not included on-chain | Check broadcast delay via `core_bcast_broadcast_delay_seconds`. Investigate BN network health and relay connectivity. |

### Consensus / P2P Issues
| Code | What Broke | What To Do |
|------|-----------|------------|
| `no_consensus` | QBFT consensus didn't complete | Check peer connectivity (`p2p_ping_success`), P2P latency, firewall rules. If one cluster: likely a slow/offline peer. If many clusters: likely a relay issue. |

### Local Validator Client Issues
| Code | What Broke | What To Do |
|------|-----------|------------|
| `no_local_vc_signature` | VC didn't submit a partial signature | Check VC is running, connected to Charon port 3600, keys loaded correctly. Check VC logs. |

### Peer Signature Issues
| Code | What Broke | What To Do |
|------|-----------|------------|
| `no_peer_signatures` | No signatures received from any peer | All peers offline or complete P2P failure. Check relay URLs, firewall. |
| `insufficient_peer_signatures` | Some but not enough signatures for threshold | Identify which peers are missing via `core_tracker_participation_missed_total`. |

### Proposer Dependency Chain (block proposal failed because RANDAO failed)
| Code | What Broke | What To Do |
|------|-----------|------------|
| `failed_proposer_randao` | Prerequisite RANDAO duty failed | Fix the RANDAO failure first — likely peer connectivity issue. |
| `proposer_insufficient_randaos` | Not enough partial RANDAO signatures | Some VCs didn't sign RANDAO. Check VC connectivity. |
| `proposer_zero_randaos` | Zero RANDAO signatures from local VCs | Local VC not signing. Check VC health. |
| `proposer_no_external_randaos` | No RANDAO signatures from peers | P2P exchange failed. Check peer connectivity. |

### Aggregator Dependency Chain (non-economic, lower priority)
| Code | What Broke | What To Do |
|------|-----------|------------|
| `failed_aggregator_selection` | Prepare aggregator duty failed | Non-economic. Check if underlying attester duty also failed. |
| `insufficient_aggregator_selections` | Not enough partial beacon committee selections | Non-economic. VC connectivity issue. |
| `zero_aggregator_prepares` | Zero selections from local VCs | Non-economic. VC not participating. |
| `no_aggregator_selections` | No selections received from peers | Non-economic. P2P exchange issue. |
| `missing_aggregator_attestation` | Attestation data unavailable for aggregation | The underlying attester duty failed. Fix attester first. |

### Sync Committee Issues
| Code | What Broke | What To Do |
|------|-----------|------------|
| `sync_contribution_no_sync_msg` | Prerequisite sync message duty failed | Check sync message consensus. |
| `sync_contribution_few_prepares` | Insufficient sync contribution selections | VC connectivity. |
| `sync_contribution_zero_prepares` | Zero sync contribution selections | VC not participating. |
| `sync_contribution_failed_prepare` | Prepare sync contribution failed | Check underlying duty. |
| `sync_contribution_no_external_prepares` | No selections from peers | P2P exchange. |
| `par_sig_db_inconsistent_sync` | Inconsistent sync committee signatures | **Known limitation** — expected in current versions. Not a bug. |

### Software Bugs (report to Obol)
| Code | What Broke | What To Do |
|------|-----------|------------|
| `bug_fetch_error` | Unexpected fetch error | Report to Obol with version, cluster name, slot. |
| `bug_par_sig_db_inconsistent` | Inconsistent partial signatures (non-sync) | Report to Obol. |
| `bug_par_sig_db_external` | Failed to store external signatures | Report to Obol. |
| `bug_par_sig_db_internal` | ParSigDB didn't trigger exchange | Report to Obol. May occur due to expiry race. |
| `bug_sig_agg` | BLS threshold aggregation failed | Report to Obol. Inconsistent signed data. |
| `bug_aggregation_error` | Failed to store aggregated signature | Report to Obol. |
| `bug_duty_db_error` | Failed to store in DutyDB | Report to Obol. |

## Key Metrics Reference

### Health & Readiness
- `app_monitoring_readyz` — Operational status. Values 1-8 (see Step 2 above).

### Duty Success Tracking
- `core_tracker_expect_duties_total{duty="..."}` — Total expected duties
- `core_tracker_success_duties_total{duty="..."}` — Successfully completed
- `core_tracker_failed_duties_total{duty="..."}` — Failed duties
- `core_tracker_failed_duty_reasons_total{duty="...",reason="..."}` — By reason code

### Per-Peer Participation
- `core_tracker_participation_total{duty="...",peer="..."}` — Peer participated
- `core_tracker_participation_missed_total{duty="...",peer="..."}` — Peer missed
- This is the single most useful metric for identifying which peer is the bottleneck.

### Consensus
- `core_consensus_timeout_total{duty="...",timer="..."}` — Consensus failures (the duty timed out entirely)
- `core_consensus_decided_rounds{duty="..."}` — Rounds needed to decide (1 is ideal)
- `core_consensus_duration_seconds{duty="..."}` — Time to reach consensus
- Timer type `eager_dlinear` = EagerDoubleLinear (default). Round N budget = N seconds from duty start time.

### Beacon Node Performance
- `app_eth2_latency_seconds{endpoint="..."}` — BN API latency. Key: `attestation_data` (should be <50ms for Lighthouse, ~170ms for Teku)
- `app_beacon_node_peers` — BN's own peer count. <50 is concerning.
- `app_beacon_node_version{version="..."}` — BN software version.
- `app_eth2_errors_total{endpoint="..."}` — BN API errors by endpoint.

### P2P Connectivity
- `p2p_ping_latency_secs{peer="..."}` — Latency per peer. <100ms good, >500ms problematic.
- `p2p_ping_success{peer="..."}` — 1=connected, 0=not. Best proxy for live connectivity.
- `p2p_peer_connection_types{peer="...",type="...",protocol="..."}` — `direct` (good) or `relay` (higher latency).

### Versions & Configuration
- `app_version{version="..."}` — Charon version per peer.
- `core_validatorapi_vc_user_agent{user_agent="..."}` — VC client. Missing UA = likely Lighthouse VC.
- `cluster_operators` — **Authoritative cluster size** (from lock file). Use this, NOT count of reporting peers.
- `cluster_threshold` — Minimum signatures needed.
- `cluster_validators` — Number of validators in cluster.
- `app_feature_flags{feature_flags="..."}` — Custom-enabled features. **Absence does NOT mean feature is off** — stable features (EagerDoubleLinear, ConsensusParticipate, ProposalTimeout, FetchOnlyCommIdx0) are on by default without this metric.

### Balance
- `core_scheduler_validator_balance_gwei{pubkey="...",pubkey_full="..."}` — Per-validator balance in gwei.
- **Gotcha**: All peers report the same pubkey balances. To get cluster total: sum across unique pubkeys from ONE peer, divide by 1e9 for ETH. Do NOT sum across peers.

### Broadcast
- `core_bcast_broadcast_total{duty="..."}` — Successful broadcasts per duty type.
- `core_bcast_broadcast_delay_seconds{duty="..."}` — Delay from slot start to broadcast.

## Loki Log Patterns

**Base selector**: `{cluster_name="X",cluster_network="mainnet"}`

**Timestamp handling**: Always parse the embedded `ts=` field (e.g., `ts=2026-03-09T20:53:59.123Z`). Loki receipt timestamps can skew 1-2 seconds due to batching. The `ts=` field is the application-level timestamp.

**Log presence detection**: Use the Loki `/series` endpoint with `match[]={cluster_name="X"}` to check which peers send logs. Do NOT rely on `query_range` with `limit=1`.

### Key Search Patterns
| Event | LogQL filter |
|-------|-------------|
| Slot start | `\|= "Slot ticked"` |
| Consensus start | `\|= "QBFT consensus instance starting"` |
| Pre-prepare received | `\|= "QBFT upon rule triggered"` |
| Round change | `\|= "QBFT round changed"` |
| Consensus decided | `\|= "QBFT consensus decided"` |
| Consensus timeout | `\|= "consensus timeout"` |
| BN call finished | `\|= "Beacon node call finished"` |
| Slow BN call | `\|= "Beacon node call took longer"` |
| Duplicate signatures | `\|= "Ignoring duplicate partial signature"` |
| Signature aggregated | `\|= "Successfully aggregated partial signatures"` |
| Attestation submitted | `\|= "Successfully submitted v2 attestations"` |

## Known Issues & Client Characteristics

### BN Client Latency Profiles
| Client | attestation_data p50 | Notes |
|--------|---------------------|-------|
| Lighthouse | ~5ms | Fast, most common |
| Teku | ~170ms | Significantly slower, can cause round 1 misses in tight clusters |
| Prysm | ~5ms | Fast |
| Nimbus | ~5-10ms | Generally fast |
| Lodestar | ~5ms | Fast |
| Grandine | ~5ms | Fast |

### Consensus Timer Budgets (EagerDoubleLinear, default)
- Timer uses **absolute deadlines** based on slot start time
- Round N has N seconds from duty start time
- When leader's pre-prepare is received, timer doubles (gives 2N seconds total)
- Attester duty start = slot_start + 4s, so round 1 deadline = slot_start + 5s, doubled = slot_start + 6s
- If all peers have fast BNs and good P2P, consensus decides in round 1 within ~100ms

### Version Notes
- Always recommend the latest stable release
- Pre-v1.9.2: Loki client used an unbuffered channel. Under high log volume, this could stall consensus goroutines and cause timeouts. Upgrade to v1.9.2+ resolves this.
- Check `app_log_loki_dropped_total` metric — if non-zero, the Loki buffer is overflowing (better than blocking, but indicates high log volume)

### Common Gotchas
1. **Cluster size**: Use `cluster_operators` metric, NOT count of observed peers. Some nodes don't send metrics.
2. **Unknown peers**: `cluster_operators` - observed peers = unknown/offline nodes. Report them explicitly.
3. **Aggregator failures are non-economic**: Don't alarm on high aggregator timeout rates. Focus on attester and proposer.
4. **VC user agent missing**: Lighthouse VC doesn't send a user-agent header. Infer from absence.
5. **Feature flags absent from metrics**: Stable features default on. Only custom-enabled features appear in `app_feature_flags`.
6. **`not_included_onchain`**: Investigate — check broadcast delay metrics and BN connectivity.
7. **Balance deduplication**: All peers report the same validator balances. Sum pubkeys from one peer only.
8. **Loki timestamps**: Use embedded `ts=` field, not Loki receipt timestamp (can skew 1-2s).

## External References

- [Obol Overview](https://docs.obol.org/next/learn/intro/obol-overview)
- [Quickstart Guide](https://docs.obol.org/next/run/start/quickstart-overview)
- [Configuration Reference](https://docs.obol.org/next/adv/configuration)
- [CDVN Repo](https://github.com/ObolNetwork/charon-distributed-validator-node) — Standard deployment
- [LCDVN Repo](https://github.com/ObolNetwork/lido-charon-distributed-validator-node) — Lido-specific deployment
- [Charon Source](https://github.com/ObolNetwork/charon) — Charon source code
```
