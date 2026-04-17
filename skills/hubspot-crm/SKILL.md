```skill
---
name: hubspot-crm
description: Search, read, and update Obol's HubSpot CRM — contacts, companies, deals, notes, and properties
user-invokable: true
model: sonnet
---

# HubSpot CRM

Interact with Obol's HubSpot CRM. Use this skill for any CRM task: searching records, enriching contact data, managing deals, analyzing the pipeline, exporting data, and more.

## Setup (one-time per user)

### 1. Get the OAuth app credentials

Ask an Obol team admin for the HubSpot MCP Auth App **Client ID** and **Client Secret**. These are shared across the team — the app is created once in HubSpot under Development > MCP Auth Apps.

### 2. Set environment variables

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
export HUBSPOT_CLIENT_ID="<client-id-from-admin>"
export HUBSPOT_CLIENT_SECRET="<client-secret-from-admin>"
```

### 3. Authenticate

Run the interactive setup to authorize your HubSpot user account:

```bash
cd <skills-repo>/skills/hubspot-crm/scripts && python3 auth.py --setup
```

This will:
- Generate an OAuth authorization URL
- Prompt you to open it in your browser and grant permissions
- Ask you to paste back the authorization code
- Exchange it for access + refresh tokens, saved to `~/.claude/hubspot_tokens.json`

After this, token refresh is automatic (30-min TTL, refreshed with a 5-min buffer).

### If auth breaks

If you get refresh errors, re-run `python3 auth.py --setup`. The refresh token may have been revoked or expired after a long period of inactivity.

## Scripts

All scripts are in `skills/hubspot-crm/scripts/`. Run from that directory so imports resolve.

### auth.py — Token Management

```bash
# Print current valid access token (auto-refreshes if expired)
python3 auth.py

# Force refresh
python3 auth.py --refresh

# Re-run initial setup
python3 auth.py --setup
```

### crm.py — CRM Operations

```bash
# --- Contacts ---

# Search contacts (free-text search across name, email, company)
python3 crm.py search-contacts --query "kiln" --limit 10

# Get a specific contact with all default properties
python3 crm.py get-contact <contact-id>

# Get with specific properties
python3 crm.py get-contact <contact-id> -p firstname,lastname,email,jobtitle

# Update a contact property
python3 crm.py update-contact <contact-id> --property jobtitle --value "CTO"

# For multi-select (checkbox) properties, use semicolons to separate values
python3 crm.py update-contact <contact-id> --property tags --value "DAS2026;priority"

# --- Companies ---

# Search companies
python3 crm.py search-companies --query "kiln"

# List companies
python3 crm.py list-companies --limit 20

# Get a specific company
python3 crm.py get-company <company-id>

# Update a company property
python3 crm.py update-company <company-id> --property description --value "New description"

# Get notes on a company
python3 crm.py get-company-notes <company-id> --limit 10

# --- Notes ---

# Create a note and attach it to one or more records. Body can be plain text or HTML.
python3 crm.py create-note --body "Quick call summary..." --company <company-id>

# For long notes, read the body from a file (timestamp defaults to now; override with --timestamp ISO8601)
python3 crm.py create-note --body-file /tmp/meeting-notes.html \
    --company <company-id> --contact <contact-id> \
    --timestamp "2026-04-17T09:30:00Z"

# Update an existing note's body and/or timestamp
python3 crm.py update-note <note-id> --body-file /tmp/corrected-notes.html

# --- Associations (contact context) ---

# Get companies associated with a contact
python3 crm.py get-contact-companies <contact-id>

# Get notes on a contact
python3 crm.py get-contact-notes <contact-id>

# Get deals associated with a contact
python3 crm.py get-contact-deals <contact-id>

# --- Properties & Export ---

# List custom contact properties
python3 crm.py list-properties contacts --custom-only

# List all company properties
python3 crm.py list-properties companies

# Export all contacts to CSV
python3 crm.py export-contacts --output /tmp/contacts.csv

# Export with specific properties
python3 crm.py export-contacts -p firstname,lastname,email,company,jobtitle -o /tmp/contacts.csv
```

## Extending the Scripts

The `crm.py` script uses the HubSpot CRM v3 REST API via `api_request(method, path, data, params)`. To add new operations (e.g., creating contacts, batch updates, working with tickets), add a new function that calls `api_request` and wire it into the argparse CLI. The HubSpot API reference is at https://developers.hubspot.com/docs/reference/api.

For operations not yet in the script, you can also call the API directly:

```bash
TOKEN=$(python3 auth.py)
curl -s "https://api.hubapi.com/crm/v3/objects/contacts?limit=10" -H "Authorization: Bearer $TOKEN"
```

## Custom Contact Properties

| Property | Type | Purpose |
|----------|------|---------|
| `contact_preference` | Select | Preferred communication channel (Discord/Telegram/Slack/Email/Other) |
| `investor_advisor` | Boolean | Whether contact is investor/advisor |
| `tags` | Multi-checkbox | General tags |
| `discord_handle` | String | Discord username |
| `telegram_username` | String | Telegram username |

## Available OAuth Scopes

The token has read/write access to: contacts, companies, deals, tickets, notes, calls, emails, meetings, tasks, line items, invoices. Read-only: owners, users.

## API Limits

- HubSpot rate limit: 100 requests per 10 seconds per private app
- Search endpoint: max 10,000 results
- Batch operations: max 100 records per request
- Token TTL: 30 minutes (auto-refreshed by auth.py)

## Guidelines

- **Always confirm with the user before writing data** to HubSpot (updates, creates, deletes).
- When making bulk changes, present a summary for review first.
- Use search and associations to gather full context on a record before making decisions.
- **Fix transcription errors before committing meeting notes.** AI meeting transcription (Gemini, Otter, etc.) frequently mishears "Obol" — common misspellings include **OAL**, **Oval**, **Opal**, **O.B.O.L.**. Scan the source notes and replace these with "Obol" (or "Obol Association" where the context is the legal entity) before writing to HubSpot.
```
