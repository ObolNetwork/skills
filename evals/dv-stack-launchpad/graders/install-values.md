---
type: llm
weight: 2
---

The dv-pod install command:
- uses the Stack's tools (`obol helm …` / `obol kubectl …`), not plain `helm`/`kubectl` against the user's default kubeconfig;
- pins the chart with an explicit `--version` (e.g. 0.22.0), not "latest";
- sets `network=hoodi` explicitly (never relies on the chart's mainnet default);
- sets `charon.operatorAddress=0xabc0000000000000000000000000000000000abc` exactly as given and `mode=launchpad` (or the Launchpad mode via the Stack example values);
- points `charon.beaconNodeEndpoints` at the in-cluster beacon `http://ethereum-beacon.ethereum-<id>.svc.cluster.local:5052`.
All five are required to pass.
