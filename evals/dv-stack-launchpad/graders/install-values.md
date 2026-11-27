---
type: llm
weight: 2
---

The dv-pod install command:
- uses the Stack's tools (`obol app install …` + `obol app sync`, or `obol helm …` / `obol kubectl …`), not plain `helm`/`kubectl` against the user's default kubeconfig;
- pins the chart version explicitly (`obol/dv-pod@0.24.0` or `--version 0.24.0`), not "latest";
- sets `network=hoodi` explicitly (never relies on the chart's mainnet default);
- sets `charon.operatorAddress=0xabc0000000000000000000000000000000000abc` exactly as given and `mode=launchpad` (or the Launchpad mode via the Stack example values);
- uses the in-cluster beacon `http://ethereum-beacon.ethereum-<id>.svc.cluster.local:5052`, either set in `charon.beaconNodeEndpoints` or relying on the chart's Stack default for `ethereum-hoodi` (stated as such, with how to override it if the node has another id).
All five are required to pass.
