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
| [`dvpod`](skills/dvpod/SKILL.md) | Deploy, upgrade, back up, and troubleshoot a DV on Kubernetes or in the Obol Stack (Launchpad or direct-definition routes) | `kubectl`, `helm` (or `obol`), a synced beacon node |
| [`dvpod-monitoring`](skills/dvpod-monitoring/SKILL.md) | Query a deployed DVpod's metrics and logs (read-only) | `kubectl`, `helm` |
| [`obol-monitoring`](skills/obol-monitoring/SKILL.md) | Triage cluster health and duty failures in Obol's hosted Grafana | Python 3.6+, `OBOL_GRAFANA_API_TOKEN` |
| [`run-obol-stack`](skills/run-obol-stack/SKILL.md) | Install, operate, and sell paid agent services from the Obol Stack; sync a node and run your part of a DV in it | Docker, a model provider |
| [`autoresearch`](skills/autoresearch/SKILL.md) | Run autoresearch GPU experiments and publish/sell the best checkpoint | GPU, Python 3, `uv`, `ollama`; `obol` to sell |
| [`autoresearch-worker`](skills/autoresearch-worker/SKILL.md) | Sell GPU time as a paid autoresearch experiment worker | GPU host, Python 3 + `uv` or Docker, Obol Stack |
| [`autoresearch-coordinator`](skills/autoresearch-coordinator/SKILL.md) | Discover paid GPU workers via ERC-8004 and run experiments across them | Python 3; Obol Stack agent wallet to pay |
| [`distributed-validators`](skills/distributed-validators/SKILL.md) | Check DV cluster health, validator performance, operators and exits via the Obol API (read-only) | `curl` |
| [`dv-steward`](skills/dv-steward/SKILL.md) | Let the Obol Stack's Hermes agent watch your local node and dv-pods on a schedule and alert you (read-only) | Obol Stack, Hermes |

`distributed-validators` and `dv-steward` are written for the Obol Stack's Hermes agent: `obol agent skills add dv-steward distributed-validators`. They work as Claude Code plugin skills too.

Try, for example:

```text
Help me create a 4-operator DV cluster on Hoodi with my friends, inviting them by Ethereum address.
Run the Charon test suites against my node and tell me if anything needs fixing before activation.
Give me a health snapshot of my DVpod and explain any Charon errors from the last hour.
Install the Obol Stack on this machine and help me sell my first paid agent service.
Sync hoodi in my Obol Stack, install a dv-pod for my operator address, and join my group's Launchpad invite.
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

## Evals

`evals/` holds `claude plugin eval` cases (`prompt.md` + `graders/*.md`) for the DV-in-the-Stack flows. Run them locally with `claude plugin eval . --runs 1` (uses your own Claude credentials; results land in `evals/results/`, which is git-ignored).

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
