![Obol Logo](https://obol.tech/obolnetwork.png)
# Obol Agent Skills

A Claude Code plugin with skills for running decentralised infrastructure with Obol.

## Installation

### As a Claude Code Plugin (Recommended)

**From inside the Claude Code REPL:**

```
/plugin marketplace add ObolNetwork/skills
/plugin install obol@obol
```

Reload plugins if needed:
```
/reload-plugins
```

**From your terminal (without starting the REPL):**

```bash
claude plugin marketplace add ObolNetwork/skills
claude plugin install obol@obol
```

The plugin is installed for your user by default. Use `--scope project` or `--scope local` to install it only for the current project.

### Staying up to date

Claude Code only auto-updates official marketplaces, so **turn on auto-update for `obol`** after installing: `/plugin` → **Marketplaces** → `obol` → **Enable auto-update**.

To update manually:
```bash
claude plugin marketplace update obol
claude plugin update obol@obol
```

The plugin also checks for a newer release once a day at session start and tells you if you're behind. Set `OBOL_SKILLS_NO_UPDATE_CHECK=1` to turn this off.

**For teams/admins:** enable auto-update for everyone via managed settings:
```json
{
  "extraKnownMarketplaces": {
    "obol": {
      "source": { "source": "github", "repo": "ObolNetwork/skills" },
      "autoUpdate": true
    }
  }
}
```

### Manual Installation

Copy the `skills/` directory into your project's `.claude/skills/` folder.

## Configuration

### Required for `obol-monitoring` skill: Grafana API Token

Set the `OBOL_GRAFANA_API_TOKEN` environment variable. The Obol core team can provide one for Obol's hosted Grafana. The skill only works against that hosted environment, so your cluster must [push metrics and logs to Obol](https://docs.obol.org/run-a-dv/start/obol-monitoring). Tokens from a self-hosted Grafana won't work. For a DVpod, use `dvpod-monitoring` instead.

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

Claude picks the right skill from your request, or you can call one directly with `/obol:<skill-name>`. Full docs, prerequisites, and example prompts: **[docs.obol.org/agent-skills](https://docs.obol.org/agent-skills)**.

| Skill | Use it to | Needs |
| --- | --- | --- |
| [`create-cluster-invitation`](skills/create-cluster-invitation/SKILL.md) | Create a DV cluster invitation and coordinate the DKG | Docker (`charon` image), or the Obol SDK |
| [`test-a-dv-cluster`](skills/test-a-dv-cluster/SKILL.md) | Run `charon alpha test` suites against a node or cluster | A running Charon, or Docker |
| [`dvpod`](skills/dvpod/SKILL.md) | Deploy, upgrade, back up, and troubleshoot a DV on Kubernetes | `kubectl`, `helm`, a beacon node |
| [`dvpod-monitoring`](skills/dvpod-monitoring/SKILL.md) | Query a deployed DVpod's metrics and logs (read-only) | `kubectl`, `helm` |
| [`obol-monitoring`](skills/obol-monitoring/SKILL.md) | Triage cluster health and duty failures in Obol's hosted Grafana | Python 3.6+, `OBOL_GRAFANA_API_TOKEN` |
| [`run-obol-stack`](skills/run-obol-stack/SKILL.md) | Install, operate, and sell paid agent services from the Obol Stack | Docker, a model provider |

Try, for example:

```text
Help me create a 4-operator DV cluster on Hoodi with my friends, inviting them by Ethereum address.
Run the Charon test suites against my node and tell me if anything needs fixing before activation.
Give me a health snapshot of my DVpod and explain any Charon errors from the last hour.
Install the Obol Stack on this machine and help me sell my first paid agent service.
```

> [!WARNING]
> An AI agent can make mistakes. Always check withdrawal addresses, fee recipients, operator sets, and the target network yourself before depositing. Never paste private keys or mnemonics into an AI chat.

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

## Releasing

Users install the plugin from the release tag that `.claude-plugin/marketplace.json` points at (`"ref": "v<version>"`), not from `main`. Merging changes to `main` ships nothing; moving that `ref` is the release. `main` requires linear history, so tags are always cut from `main` after merge:

1. **Change PR:** make your changes and bump `version` in `.claude-plugin/plugin.json` (semver: patch for fixes, minor for new skills or behaviour, major for breaking changes). Leave the marketplace `ref` alone. Merge.
2. **Tag `main`:**
   ```bash
   git switch main && git pull
   git tag -a v<version> -m "obol <version>"
   git push origin v<version>
   ```
3. **Release PR:** set the marketplace `ref` to the new tag. Merging this publishes it to users.

CI checks that the marketplace `ref` is a `vX.Y.Z` tag that exists on GitHub, sits on `main`, and contains that version in `plugin.json`.
