# Cekura AI Skills

AI-powered skills for building and improving voice agent tests and metrics on the [Cekura](https://cekura.ai) platform. Works with Claude Code, Codex, Cursor, and other AI coding assistants.

## Table of Contents

- [What's Included](#whats-included)
- [Prerequisites](#prerequisites)
- [Quick Install (npx skills add)](#quick-install-npx-skills-add)
- [Claude Code (VS Code)](#claude-code-vs-code)
- [Claude Code (Terminal CLI)](#claude-code-terminal-cli)
- [Codex](#codex)
- [Cursor](#cursor)
- [Windsurf / Other Agents](#windsurf--other-agents)
- [MCP Server](#mcp-server)
- [Quick Reference](#quick-reference)
- [Platform Compatibility](#platform-compatibility)
- [Links](#links)

---

## What's Included

### 3 Plugins, 12 Commands

| Plugin | Skills | Commands | Purpose |
|--------|--------|----------|---------|
| **cekura** | `onboarding`, `create-agent`, `coordinator` | `setup-mcp`, `upgrade-skills`, `report-bug` | Platform setup, agent onboarding, skill routing |
| **cekura-metrics** | `metric-design`, `labs-workflow` | `create-metric`, `list-metrics`, `evaluate-calls`, `improve-metric` | Create, improve, and validate call quality metrics |
| **cekura-evals** | `eval-design` | `manual-create-update-eval`, `autogen-eval`, `list-evals`, `run-evals`, `eval-results` | Create, run, and analyze test suites for voice agents |

These encode best practices from real client deployments — proactive guardrails, real transcript grounding, iterative improvement loops, coverage planning, and anti-pattern detection.

## Prerequisites

- **Cekura account** — [Sign up here](https://dashboard.cekura.ai/sign-up)
- **Cekura API key** — Found under Settings > API Keys in the [Cekura dashboard](https://dashboard.cekura.ai)

---

## Quick Install (`npx skills add`)

The fastest way to get Cekura skills into any [Agent Skills](https://agentskills.io)–compatible client (Claude Code, Cursor, Codex, Windsurf, OpenCode, and many more).

### Install

```bash
npx skills add cekura-ai/cekura-skills/skills
```

> **Note the `/skills` suffix.** It scopes the install to the public skills layer. A bare `cekura-ai/cekura-skills` would also pull internal Claude Code plugin files.

The CLI prompts you to pick which skills to install and which agents to install them into. To install everything non-interactively:

```bash
npx skills add cekura-ai/cekura-skills/skills --all
```

### Update

```bash
# Refresh existing skills
npx skills update

# Or stay fully current — refresh existing AND pick up any newly-added skills
npx skills add cekura-ai/cekura-skills/skills --all
```

### Remove

```bash
npx skills remove cekura-coordinator   # one skill
npx skills remove --all                 # everything
```

### What gets installed

Six skills, scoped to specific Cekura workflows:

| Skill | When it activates |
|---|---|
| `cekura-coordinator` | "What can Cekura do?" — routes you to the right skill |
| `cekura-onboarding` | "Get started with Cekura" — full platform walkthrough |
| `cekura-create-agent` | "Connect my voice agent to Cekura" |
| `cekura-metric-design` | "Create a metric / measure call quality" |
| `cekura-metric-improvement` | "Improve a metric / fix metric accuracy" |
| `cekura-eval-design` | "Design test scenarios for my voice agent" |

### Want full functionality?

`npx skills add` gives you the **behavioral guidance layer** — the skills auto-activate when you describe relevant tasks. For slash commands and direct API integration, install the full Claude Code plugin marketplace below.

---

## Claude Code (VS Code)

Full plugin support — skills, slash commands, MCP tools, and auto-configured API access.

### Install

1. Open the Claude Code chat panel
2. Click **Manage Plugins** > **Marketplaces** tab
3. Paste `https://github.com/cekura-ai/cekura-skills.git` and click **Add**
4. Switch to the **Plugins** tab > search for `cekura` > install all three plugins
5. Set your API key:
   ```bash
   # Add to ~/.zshrc or ~/.bashrc
   export CEKURA_API_KEY="your-key-here"
   ```
6. Restart VS Code to pick up the environment variable
7. In the Claude Code chat, run `/setup-mcp` to configure the MCP server

### Get Started

Try `/onboarding` for a guided walkthrough or ask "what can Cekura do?" to see everything available.

### Upgrade

Run `/upgrade-skills` in any Claude Code session, or manually:

```bash
cd ~/.claude/plugins/marketplaces/cekura-skills
git pull origin main
```

Restart Claude Code after upgrading.

---

## Claude Code (Terminal CLI)

Same full plugin support as VS Code.

### Install

1. Inside a Claude Code session, run `/plugins`
2. Go to the **Marketplaces** tab > select **Add Marketplace**
3. Paste `https://github.com/cekura-ai/cekura-skills.git` and confirm
4. Go to the **Discover** tab > search for `cekura` > install all three plugins
5. Set your API key:
   ```bash
   # Add to ~/.zshrc or ~/.bashrc
   export CEKURA_API_KEY="your-key-here"
   ```
6. Restart your terminal and Claude Code session
7. Run `/setup-mcp` to configure the MCP server

> **Tip:** If you've already cloned the repo locally, you can paste the local path instead of the GitHub URL.

### Get Started

Try `/onboarding` for a guided walkthrough or ask "what can Cekura do?" to see everything available.

### Upgrade

Run `/upgrade-skills` in any Claude Code session, or manually:

```bash
cd ~/.claude/plugins/marketplaces/cekura-skills
git pull origin main
```

Restart Claude Code and your terminal after upgrading.

---

## Codex

Codex doesn't support Claude Code plugins directly. Skills are loaded automatically based on conversation context. No slash commands or MCP tools — uses curl-based API reference instead.

### Install

**Option A: Install skills (recommended)**

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo cekura-ai/cekura-skills \
  --path plugins/cekura/skills/onboarding \
         plugins/cekura/skills/create-agent \
         plugins/cekura-metrics/skills/metric-design \
         plugins/cekura-metrics/skills/labs-workflow \
         plugins/cekura-evals/skills/eval-design
```

Restart Codex after install.

**Option B: Behavior preset (quick start)**

Copy the single-file behavior preset into your repo:

```bash
curl -o AGENTS.md https://raw.githubusercontent.com/cekura-ai/cekura-skills/main/codex/AGENTS.md
```

This gives Codex all the domain knowledge (metric design, eval design, API reference, anti-patterns) in one file.

### Get Started

Ask Codex to help with Cekura metrics or evals — skills load automatically when the conversation matches.

### Upgrade

Re-run the skill installer:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo cekura-ai/cekura-skills \
  --path plugins/cekura/skills/onboarding \
         plugins/cekura/skills/create-agent \
         plugins/cekura-metrics/skills/metric-design \
         plugins/cekura-metrics/skills/labs-workflow \
         plugins/cekura-evals/skills/eval-design
```

---

## Cursor

Uses the behavior preset as a rules file. No slash commands or MCP tools — all domain knowledge is embedded in the rules file.

### Install

Copy the behavior preset into your project:

```bash
curl -o .cursor/rules/cekura.md https://raw.githubusercontent.com/cekura-ai/cekura-skills/main/codex/AGENTS.md
```

Or add it as a global rule in Cursor Settings > Rules.

### Get Started

Ask Cursor to help with Cekura metrics or evals — the rules file provides all the domain context.

### Upgrade

Re-download the behavior preset:

```bash
curl -o .cursor/rules/cekura.md https://raw.githubusercontent.com/cekura-ai/cekura-skills/main/codex/AGENTS.md
```

---

## Windsurf / Other Agents

Copy `codex/AGENTS.md` to wherever your agent reads context files from (project root, `.windsurf/rules/`, etc.):

### Install

```bash
curl -o AGENTS.md https://raw.githubusercontent.com/cekura-ai/cekura-skills/main/codex/AGENTS.md
```

The file contains all Cekura domain knowledge in a single portable format that works with any agent.

### Upgrade

Re-download:

```bash
curl -o AGENTS.md https://raw.githubusercontent.com/cekura-ai/cekura-skills/main/codex/AGENTS.md
```

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
| **Any Agent Skills client** | `npx skills add` | Skills only | No | No |
| **Claude Code (VS Code)** | Marketplace install | Yes | Yes | Yes |
| **Claude Code (CLI)** | `/plugins` install | Yes | Yes | Yes |
| **Codex** | Skill installer | Skills only | No | No |
| **Cursor** | Rules file | Behavior preset | No | No |
| **Windsurf** | Rules file | Behavior preset | No | No |
| **Other agents** | Copy AGENTS.md | Behavior preset | No | No |

---

## Links

- **Cekura Dashboard:** [dashboard.cekura.ai](https://dashboard.cekura.ai)
- **Sign Up:** [dashboard.cekura.ai/sign-up](https://dashboard.cekura.ai/sign-up)
- **API Docs:** [docs.cekura.ai/api-reference](https://docs.cekura.ai/api-reference)
- **LLM-friendly Docs:** [docs.cekura.ai/llms.txt](https://docs.cekura.ai/llms.txt)
- **Concepts:** [docs.cekura.ai/documentation/key-concepts](https://docs.cekura.ai/documentation/key-concepts/)
