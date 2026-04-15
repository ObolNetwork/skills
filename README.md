![Obol Logo](https://obol.tech/obolnetwork.png)
# Obol Agent Skills

A Claude Code plugin with skills for running decentralised infrastructure with Obol.

## Installation

### As a Claude Code Plugin (Recommended)

```
/plugin marketplace add ObolNetwork/skills
/plugin install obol
```

Reload plugins if needed:
```
/reload-plugins
```

### Manual Installation

Copy the `skills/` directory into your project's `.claude/skills/` folder.

## Configuration

### Required for obol-monitoring skill: Grafana API Token

Set the `OBOL_GRAFANA_API_TOKEN` environment variable. The Obol Core team can provide you with one.

**Option 1 — Shell profile** (recommended):
```bash
# Add to ~/.bashrc or ~/.zshrc
export OBOL_GRAFANA_API_TOKEN="glsa_..."
```

**Option 2 — Project `.env` file** (see `.env.sample`):
```bash
OBOL_GRAFANA_API_TOKEN=glsa_...
```

## Available Skills

### obol-monitoring

Monitor and diagnose Obol DVT cluster performance using Grafana (Prometheus metrics + Loki logs).

**Scripts:**
- `cluster_triage.py` — First-pass cluster health check
- `duty_analysis.py` — Deep slot-level failure analysis with timeline reconstruction
- `fleet_overview.py` — Multi-cluster fleet view with version/client diversity

**Usage:** Ask Claude to triage a cluster, analyze duty failures, or get a fleet overview. The skill guides Claude through the appropriate diagnostic workflow.

See [skills/obol-monitoring/SKILL.md](skills/obol-monitoring/SKILL.md) for the full reference including failure reason codes, metrics guide, and triage workflow.

### hubspot-crm

Search, read, and update Obol's HubSpot CRM contacts, companies, deals, and notes.

**Scripts:**
- `auth.py` — OAuth token management with auto-refresh
- `crm.py` — CRM operations (search, get, update, export contacts/companies/deals/notes)

**Usage:** Ask Claude to search contacts, categorize customers, enrich records, or export CRM data. The skill handles authentication and provides structured access to the HubSpot API.

See [skills/hubspot-crm/SKILL.md](skills/hubspot-crm/SKILL.md) for the full reference including categorization workflow and API details.

## Requirements

- Python 3.6+ (stdlib only, no pip packages needed)
- `OBOL_GRAFANA_API_TOKEN` environment variable (for obol-monitoring)
- HubSpot OAuth tokens in `~/.claude/hubspot_tokens.json` (for hubspot-crm)

## Adding New Skills

Create a new directory under `skills/` with a `SKILL.md` file:
```
skills/
├── obol-monitoring/
│   ├── SKILL.md
│   └── scripts/
└── your-new-skill/
    ├── SKILL.md
    └── ...
```
