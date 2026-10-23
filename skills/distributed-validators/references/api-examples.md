# Obol API: example lookups and responses

Each section names the Obol MCP tool and the API endpoint it calls; the response is the same either way. Shapes were
checked against the production API (October 2026). Values are illustrative; long hex strings are shortened with `…`.

---

## Cluster lock: `obol_cluster_lock_by_hash` · `GET /v1/lock/{lockHash}`

```
obol_cluster_lock_by_hash(lock_hash="0x0b06666a…bd03c0")
```

```json
{
  "cluster_definition": {
    "name": "my-dv-cluster",
    "uuid": "a9fb1078-…",
    "version": "v1.10.0",
    "num_validators": 4,
    "threshold": 3,
    "fork_version": "0x00000000",
    "config_hash": "0xe0155440…",
    "operators": [
      { "address": "0xAbCd…1234", "enr": "enr:-HW4Q…", "config_signature": "0x…", "enr_signature": "0x…" }
    ],
    "validators": [
      { "fee_recipient_address": "0x388C…9297", "withdrawal_address": "0xb9d7…293f" }
    ]
  },
  "distributed_validators": [
    { "distributed_public_key": "0xa6ef600c…", "public_shares": ["0x…", "0x…", "0x…", "0x…"] }
  ],
  "lock_hash": "0x0b06666a…bd03c0",
  "is_current": true,
  "superseded_by": null
}
```

- The network is in `cluster_definition.fork_version`: `0x00000000` mainnet,
  `0x10000910` hoodi, `0x90000069` sepolia, `0x00000064` gnosis.
- `public_shares` has one entry per operator, in operator order.
- `is_current: false` with `superseded_by` set means the cluster was later replaced
  (e.g. after adding or replacing operators); look up the newer lock.
- Large clusters (Lido clusters can have 1,000+ validators) are megabytes of JSON. The MCP tool
  truncates long lists and gives the real counts in `_obol_mcp_truncated.lists`; with `curl`,
  summarise with a script instead of printing the response.

**Tell the user:** "Your cluster `my-dv-cluster` on mainnet has 4 operators with a
threshold of 3 and runs 4 validators."

---

## Effectiveness: `obol_cluster_effectiveness` · `GET /v1/effectiveness/{lockHash}`

```
obol_cluster_effectiveness(lock_hash="0x4d6e…")
```

```json
{
  "0xb3a2c1…": { "all": 0.987 },
  "0xc4d3e2…": { "all": 0.612 }
}
```

- Keys are validator pubkeys; `all` is lifetime effectiveness from 0 to 1.
- Above about 0.95 is healthy. Low values on every validator point at cluster-wide
  problems (operators offline, peer connectivity); low values on one validator only are
  rarer and worth checking against its status.
- A 404 `Cluster effectiveness not found` means there is no data yet, e.g. the validators
  are not active.

---

## Validator states: `obol_cluster_validator_states` · `GET /v1/state/{lockHash}`

```
obol_cluster_validator_states(lock_hash="0x5d045aab…")
```

```json
{
  "0xafda2e2d…": {
    "index": "795269",
    "status": "active_ongoing",
    "balance": "32.0123",
    "effective_balance": "32.0",
    "withdrawal_credentials": "0x0100…6c7c332a…",
    "pending_partial_withdrawals": "0.0",
    "pending_partial_deposits": "0.0",
    "is_not_within_committee": false,
    "credentials_conflict": false
  }
}
```

- Balances are already in **ETH** (strings), not Gwei.
- `withdrawal_credentials` starting `0x01` are ETH1 withdrawal credentials, `0x02`
  compounding.
- An empty object `{}` means none of the cluster's validators are on chain yet.

---

## Exit status summary: `obol_cluster_exit_status_summary` · `GET /v1/exp/exit/status/summary/{lockHash}`

```
obol_cluster_exit_status_summary(lock_hash="0x4d6e…")
```

```json
{
  "operator_exits": {
    "0xAbCd…1234": 4,
    "0xEfGh…5678": 4,
    "0xIjKl…9012": 1,
    "0xMnOp…3456": 0
  },
  "ready_exits": 1
}
```

- `operator_exits`: how many validators each operator has uploaded a partial exit for.
- `ready_exits`: validators with at least `threshold` partial exits stored.
- A cluster with no exits yet can return an empty-string key (`{"": 0}`); ignore it.

**Tell the user:** "1 validator has enough signatures to exit. `0xIjKl…` and `0xMnOp…`
still need to sign exits for the others."

---

## Exit status detail: `obol_cluster_exit_status` · `GET /v1/exp/exit/status/{lockHash}`

```
obol_cluster_exit_status(lock_hash="0x4d6e…", operatorAddress="0xMnOp…3456", page=1, limit=10)
```

```json
{
  "cluster_exit_status": [
    { "pubkey": "0xc4d3e2…", "exit_shares": ["0", "1"], "quorum": false, "all": false }
  ],
  "total_count": 3,
  "total_pages": 1
}
```

- `exit_shares` lists the operator indices (0-based, in lock order) that have signed.
- With `operatorAddress`, only validators that operator has **not** signed are returned.
- Pages are 1-indexed here.

---

## Cluster definition (pre-DKG): `obol_cluster_definition` · `GET /v1/definition/{configHash}`

```
obol_cluster_definition(config_hash="0xe0155440…")
```

```json
{
  "name": "my-dv-cluster",
  "config_hash": "0xe0155440…",
  "fork_version": "0x00000000",
  "threshold": 3,
  "num_validators": 4,
  "creator": { "address": "0x0cCE…7C70", "config_signature": "0x…" },
  "operators": [
    { "address": "0xAbCd…1234", "enr": "enr:-…", "config_signature": "0x…", "enr_signature": "0x…" },
    { "address": "0xEfGh…5678", "enr": "", "config_signature": "", "enr_signature": "" }
  ],
  "timestamp": "2024-03-14T08:00:00Z"
}
```

An operator with empty `enr` and `config_signature` has not accepted the definition yet.

**Tell the user:** "DKG can't start yet: `0xEfGh…` still has to accept the cluster
invite and submit their ENR."

---

## Techne: `obol_operator_techne` · `GET /v1/address/techne/{address}`

```json
{ "base": [ { "…": "…" } ], "bronze": [], "silver": [], "gold": [] }
```

Each tier is a list of credential tokens held; empty lists mean that tier is not held.

---

## Badges: `obol_operator_badges` · `GET /v1/address/badges/{address}`

```json
{
  "badges": [
    { "name": "Lido Mainnet", "description": "…", "image_url": "…", "qualified": true, "earned_at": "2024-05-01T00:00:00.000Z" },
    { "name": "Genesis Dappnode", "description": "…", "image_url": "…", "qualified": false, "earned_at": null }
  ]
}
```

Every known badge is listed; only those with `qualified: true` are held.

---

## Terms: `obol_terms_signed_status` · `GET /v1/termsAndConditions/{address}`

```json
{ "isTermsAndConditionsSigned": false }
```

---

## Network summary: `obol_network_summary` · `GET /v1/lock/network/summary/{network}`

```
obol_network_summary(network="mainnet")
```

```json
{ "eth_staked": 421925, "total_clusters": 25, "total_operators": 85 }
```

Other networks currently return 404 `No data found for network`.

---

## Listing clusters: `obol_locks_by_network` · `GET /v1/lock/network/{network}`

```
obol_locks_by_network(network="mainnet", sortBy="avg_effectiveness", sortOrder="desc", limit=10)
```

```json
{
  "cluster_locks": [ { "_id": "…", "lock_hash": "0xef134fbb…" } ],
  "total_count": 25,
  "total_pages": 3
}
```

Without `details` only lock hashes come back. With `details=true` each entry is a full lock
plus `operators_count`, `active_validators_count`, `total_balance_eth`, `avg_effectiveness`,
`cluster_apr` and `cluster_pool`; pages are capped at 5 because full locks are large.
`sortBy` accepts `avg_effectiveness`, `active_validators_count` or `operators_count`;
`pool` accepts `lido` or `etherfi`.

---

## Example conversations

**"My cluster 0x4d6e… is performing badly, what's wrong?"**
→ Ask for the full lock hash if it's shortened. Call `obol_cluster_effectiveness` and
`obol_cluster_validator_states`; report low scores and any status other than
`active_ongoing`, and use the operator list from `obol_cluster_lock_by_hash` to suggest
which operators to check.

**"How do I exit validator 0xb3a2…?"**
→ Exits are signed with `charon exit sign` by each operator (not possible from here). Use
`obol_cluster_exit_status` with `validatorPubkey` to show who has signed so far.

**"Is 0xAbCd… a good operator?"**
→ `obol_operator_techne`, `obol_operator_badges`, `obol_operator_clusters` and
`obol_terms_signed_status`; summarise without overstating what the credentials mean.

**"Which mainnet clusters perform best?"**
→ `obol_locks_by_network(network="mainnet", sortBy="avg_effectiveness", sortOrder="desc", details=true, limit=5)`.
Don't follow up by fetching every cluster individually.
