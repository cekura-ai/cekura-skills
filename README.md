# Cekura AI Skills

AI-powered skills for building and improving voice agent tests and metrics on the [Cekura](https://cekura.ai) platform. Works with Claude Code, Codex, Cursor, and other AI coding assistants.

## What's Included

### 3 Plugins, 12 Commands

| Plugin | Skills | Commands | Purpose |
|--------|--------|----------|---------|
| **cekura** | `onboarding`, `create-agent`, `coordinator` | `setup-mcp`, `upgrade-skills`, `report-bug` | Platform setup, agent onboarding, skill routing |
| **cekura-metrics** | `metric-design`, `labs-workflow` | `create-metric`, `list-metrics`, `evaluate-calls`, `improve-metric` | Create, improve, and validate call quality metrics |
| **cekura-evals** | `eval-design` | `manual-create-update-eval`, `autogen-eval`, `list-evals`, `run-evals`, `eval-results` | Create, run, and analyze test suites for voice agents |

These encode best practices from real client deployments — proactive guardrails, real transcript grounding, iterative improvement loops, coverage planning, and anti-pattern detection.

## Prerequisites

- **Cekura account** — Sign up at [app.cekura.ai](https://app.cekura.ai)
- **Cekura API key** — Found under Settings > API Keys in the Cekura dashboard

---

## Setup by Platform

### Claude Code (VS Code Extension)

1. Open the Claude Code chat panel
2. Click **Manage Plugins** > **Marketplaces** tab
3. Paste `https://github.com/cekura-ai/claude-skills.git` and click **Add**
4. Switch to the **Plugins** tab > search for `cekura` > install all three plugins
5. Set your API key:
   ```bash
   # Add to ~/.zshrc or ~/.bashrc
   export CEKURA_API_KEY="your-key-here"
   ```
6. Restart VS Code to pick up the environment variable
7. In the Claude Code chat, run `/setup-mcp` to configure the MCP server

All skills and commands are now available. Try `/onboarding` to get started or ask "what can Cekura do?" to see everything available.

### Claude Code (Terminal CLI)

1. Inside a Claude Code session, run `/plugins`
2. Go to the **Marketplaces** tab > select **Add Marketplace**
3. Paste `https://github.com/cekura-ai/claude-skills.git` and confirm
4. Go to the **Discover** tab > search for `cekura` > install all three plugins
5. Set your API key:
   ```bash
   # Add to ~/.zshrc or ~/.bashrc
   export CEKURA_API_KEY="your-key-here"
   ```
6. Restart your terminal and Claude Code session
7. Run `/setup-mcp` to configure the MCP server

> **Tip:** If you've already cloned the repo locally, you can paste the local path instead of the GitHub URL.

### Codex

Codex doesn't support Claude Code plugins directly. Two options:

**Option A: Install skills (recommended)**

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo cekura-ai/claude-skills \
  --path plugins/cekura/skills/onboarding \
         plugins/cekura/skills/create-agent \
         plugins/cekura-metrics/skills/metric-design \
         plugins/cekura-metrics/skills/labs-workflow \
         plugins/cekura-evals/skills/eval-design
```

Restart Codex after install. Skills are loaded automatically based on conversation context.

**Option B: Behavior preset (quick start)**

Copy the single-file behavior preset into your repo:

```bash
curl -o AGENTS.md https://raw.githubusercontent.com/cekura-ai/claude-skills/main/codex/AGENTS.md
```

This gives Codex all the domain knowledge (metric design, eval design, API reference, anti-patterns) in one file.

### Cursor

Copy the behavior preset into your project root:

```bash
curl -o .cursor/rules/cekura.md https://raw.githubusercontent.com/cekura-ai/claude-skills/main/codex/AGENTS.md
```

Or add it as a global rule in Cursor Settings > Rules.

### Windsurf / Other AI Agents

Copy `codex/AGENTS.md` to wherever your agent reads context files from (project root, `.windsurf/rules/`, etc.):

```bash
curl -o AGENTS.md https://raw.githubusercontent.com/cekura-ai/claude-skills/main/codex/AGENTS.md
```

The file contains all Cekura domain knowledge in a single portable format that works with any agent.

---

## MCP Server

All plugins connect to the Cekura API through an MCP (Model Context Protocol) server. This gives structured access to 84+ Cekura API operations as typed tools.

**For Claude Code users:** Run `/setup-mcp` after installing the plugins. It walks you through:
1. Setting the `CEKURA_API_KEY` environment variable
2. Starting the MCP server
3. Verifying connectivity

**For other platforms:** The MCP server is optional. The `AGENTS.md` behavior preset includes API reference with curl examples as a fallback.

**How it works:** Each plugin has a `.mcp.json` file that auto-configures the connection. When Claude Code starts, it reads these files and connects to the MCP server at `http://localhost:8001/mcp`. All `mcp__cekura__*` tools become available automatically.

---

## Upgrading

### Claude Code

Run the `/upgrade-skills` command in any Claude Code session. It pulls the latest from GitHub and reports what changed.

```
/upgrade-skills
```

If you have local modifications, it will warn you before pulling. You can also upgrade manually:

```bash
cd ~/.claude/plugins/marketplaces/cekura-skills
git pull origin main
```

Restart Claude Code after upgrading to pick up new skills and commands.

### Codex

Re-run the skill installer to pull the latest versions:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo cekura-ai/claude-skills \
  --path plugins/cekura/skills/onboarding \
         plugins/cekura/skills/create-agent \
         plugins/cekura-metrics/skills/metric-design \
         plugins/cekura-metrics/skills/labs-workflow \
         plugins/cekura-evals/skills/eval-design
```

### Cursor / Windsurf / Other

Re-download the behavior preset:

```bash
curl -o AGENTS.md https://raw.githubusercontent.com/cekura-ai/claude-skills/main/codex/AGENTS.md
```

---

## Quick Reference

### Key Commands

| Command | What it Does |
|---------|-------------|
| `/setup-mcp` | Configure MCP server (run once after install) |
| `/upgrade-skills` | Pull latest skill updates from GitHub |
| `/report-bug` | Report a bug — files GitHub issue, optionally attempts a fix |
| `/onboarding` | Guided platform setup for new users |
| `/create-agent` | Set up a voice AI agent with provider, tools, KB |
| `/metric-design` | Design custom metrics with best practices |
| `/create-metric` | Create or update a metric |
| `/eval-design` | Design test scenarios and coverage strategy |
| `/autogen-eval` | Auto-generate evaluators (or bulk create from CSV/JSON) |
| `/manual-create-update-eval` | Create or update a single evaluator with full field walkthrough |
| `/run-evals` | Execute test scenarios |
| `/improve-metric` | Improve metric accuracy: feedback, labs, auto-improve |

### Getting Started Flow

1. `/setup-mcp` — Configure API access
2. `/onboarding` — Set up project and agent
3. `/create-agent` — Configure provider, mock tools, knowledge base
4. `/autogen-eval` — Auto-generate test scenarios
5. `/run-evals` — Run your first tests
6. `/metric-design` — Create custom metrics based on results

---

## Platform Compatibility

| Platform | Method | Full Plugin Support | MCP Tools | Slash Commands |
|----------|--------|-------------------|-----------|---------------|
| **Claude Code (VS Code)** | Marketplace install | Yes | Yes | Yes |
| **Claude Code (CLI)** | `/plugins` install | Yes | Yes | Yes |
| **Codex** | Skill installer | Skills only | No | No |
| **Cursor** | Rules file | Behavior preset | No | No |
| **Windsurf** | Rules file | Behavior preset | No | No |
| **Other agents** | Copy AGENTS.md | Behavior preset | No | No |

---

## Links

- **Cekura Dashboard:** [app.cekura.ai](https://app.cekura.ai)
- **API Docs:** [docs.cekura.ai/api-reference](https://docs.cekura.ai/api-reference)
- **LLM-friendly Docs:** [docs.cekura.ai/llms.txt](https://docs.cekura.ai/llms.txt)
- **Concepts:** [docs.cekura.ai/documentation/key-concepts](https://docs.cekura.ai/documentation/key-concepts/)
