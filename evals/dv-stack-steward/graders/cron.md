---
type: llm
weight: 2
---

The plan creates a recurring Hermes cron job (e.g. `obol hermes cron create "every 15m" "<prompt>" --name … --skill dv-steward --deliver telegram`) whose prompt makes quiet runs silent (e.g. replying `[SILENT]` when nothing is wrong), and suggests confirming that a test alert arrives.
