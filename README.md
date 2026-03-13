![Obol Logo](https://obol.tech/obolnetwork.png)
# Obol Agent Skills

A collection of Claude Code skills to help your Agents use Obol's products and services.

## Getting Started

Link the skills to your Claude agent by adding this repo to your project's skill search path, or copy the `skills/` directory into your `.claude/skills/` folder.

## Available Skills

### obol-monitoring

Use your agent to explore the monitoring and logging of your distributed validator fleet via Grafana.

Requires the following API Key to be set in your environment. The Obol Core team can provide you with one.
```bash
export OBOL_GRAFANA_API_TOKEN="your-grafana-service-account-token"
```

**Scripts:**
- `cluster_triage.py` — First-pass cluster health check
- `duty_analysis.py` — Deep slot-level failure analysis with timeline reconstruction
- `fleet_overview.py` — Multi-cluster fleet view with version/client diversity

**Usage:**
```bash
# Triage a specific cluster
python3 scripts/cluster_triage.py "Cluster Name" --network mainnet --hours 1

# Analyze a specific duty failure
python3 scripts/duty_analysis.py "Cluster Name" 13867535 --duty attester

# Fleet-wide overview
python3 scripts/fleet_overview.py --network mainnet --hours 1
```

See [skills/obol-monitoring/SKILL.md](skills/obol-monitoring/SKILL.md) for the full skill reference including failure reason codes, metrics guide, and triage workflow.
