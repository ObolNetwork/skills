---
type: llm
weight: 2
---

The plan reads the dv-pod's own public ENR (from the `<fullname>-enr` ConfigMap or the chart's output — not from a Secret's private key, and not a newly generated ENR from `charon create enr` on the laptop) and tells the user to open the hoodi Launchpad link with the wallet for 0xabc…abc, paste exactly that pod ENR, and sign. It makes clear that the human signs on the Launchpad (the pod/sidecar never signs or "auto-accepts"), and that the DKG then runs automatically once every operator has signed, with all operators' pods online.
