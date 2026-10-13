---
type: llm
weight: 2
---

The plan installs and syncs a hoodi Ethereum node in the Stack (`obol network install ethereum --network hoodi …` then `obol network sync ethereum/<id>`) and explicitly waits until the node is synced (e.g. `obol network status ethereum/<id>` reporting `synced`, or EL `eth_syncing` false and CL `is_syncing` false / `el_offline` false) BEFORE installing the dv-pod. Fail if the dv-pod is installed before or in parallel with the sync without any gate (an explicitly user-accepted testnet exception using the publicnode fallback is acceptable only if it is stated as an exception).
