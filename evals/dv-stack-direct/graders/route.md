---
type: llm
weight: 2
---

The response chooses the direct-definition route: ENR mode. Each operator first installs a dv-pod (with `network=hoodi`, a pinned chart `--version`, via `obol helm`) and shares the pod's public ENR from its `<fullname>-enr` ConfigMap; the creator then runs `charon create dkg --network hoodi --num-validators 1 --withdrawal-addresses 0x111… --fee-recipient-addresses 0x111… --operator-enrs <4 ENRs>` (via a pinned `obolnetwork/charon:vX.Y.Z` image, not `latest`). It must not route them through the Launchpad or ask for operator addresses as the identity.
