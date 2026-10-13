---
type: llm
weight: 2
---

The plan installs the opt-in stewardship skills into Hermes (`obol agent skills add dv-steward`, optionally with `distributed-validators`), configures Telegram so that the user enters the bot token themselves (never pasted into the chat), and insists on `TELEGRAM_ALLOWED_USERS` (the user's Telegram ID) because the Stack's Hermes allows all gateway users by default; it also sets a home channel for delivery.
