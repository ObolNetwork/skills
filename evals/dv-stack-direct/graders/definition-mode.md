---
type: llm
weight: 2
---

After the definition exists, each operator's dv-pod is (re)configured, in the same release (values.yaml + `obol app sync`, or a `--reset-then-reuse-values` upgrade), with `mode=definition` and exactly one of `dkg.definition.configHash` (from `--publish`), `dkg.definition.url`, or `dkg.definition.configMap`; no operator address is required for this mode. The DKG then runs automatically in the pods when all four are online at the same time.
