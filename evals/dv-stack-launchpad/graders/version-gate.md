---
type: llm
weight: 1
---

The response checks charon version compatibility before the DKG: every operator's node must run the same charon minor version (e.g. v1.11.x) and the cluster definition's version must be compatible, or it tells the user to confirm this with the cluster creator / other operators. Missing any mention of charon version compatibility fails.
