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
- [Reinstalling Cekura skills](#reinstalling-cekura-skills)
- [Links](#links)

---

## What's Included

### 10 Skills, 14 Commands in one plugin

| Skills | Commands |
|--------|----------|
| `cekura-coordinator` | `cekura-onboarding`, `setup-mcp`, `upgrade-skills`, `report-bug` |
| `cekura-onboarding` | `create-metric`, `list-metrics`, `evaluate-calls`, `improve-metric` |
| `cekura-create-agent` | `manual-create-update-eval`, `autogen-eval`, `list-evals`, `run-evals`, `eval-results`, `cekura-report` |
| `cekura-self-improving-agent` | |
| `cekura-metric-design` | |
| `cekura-metric-improvement` | |
| `cekura-predefined-metrics` | |
| `cekura-eval-design` | |
| `cekura-fixing-prod-issues` | |
| `cekura-infra-test-suite` | |

These encode best practices from real client deployments — proactive guardrails, real transcript grounding, iterative improvement loops, coverage planning, and anti-pattern detection.

> **Stuck after an upgrade?** If `/upgrade-skills` reports stale plugin entries or `/plugin install` fails with `Source path does not exist`, do a clean reinstall — see [Reinstalling Cekura skills](#reinstalling-cekura-skills) below.

## Prerequisites

- **Cekura account** — [Sign up here](https://dashboard.cekura.ai/sign-up). Sign in via OAuth or use an API key.
- **Cekura API key** *(only for the Claude Code plugin path / programmatic MCP access)* — Found under Settings > API Keys in the [Cekura dashboard](https://dashboard.cekura.ai). Not needed for `npx skills add`.

---

## Quick Install (`npx skills add`)

The fastest way to get Cekura skills into any [Agent Skills](https://agentskills.io)–compatible client (Claude Code, Cursor, Codex, Windsurf, OpenCode, and many more).

### Install

```bash
npx skills add cekura-ai/cekura-skills
```

The CLI prompts you to pick which skills to install and which agents to install them into. To install everything non-interactively:

```bash
npx skills add cekura-ai/cekura-skills --all
```

### Update

```bash
# Refresh existing skills
npx skills update

# Or stay fully current — refresh existing AND pick up any newly-added skills
npx skills add cekura-ai/cekura-skills --all
```

### Remove

```bash
npx skills remove cekura-coordinator   # one skill
npx skills remove --all                 # everything
```

### What gets installed

Nine skills, scoped to specific Cekura workflows:

| Skill | When it activates |
|---|---|
| `cekura-coordinator` | "What can Cekura do?" — routes you to the right skill |
| `cekura-onboarding` | "Get started with Cekura" — full platform walkthrough |
| `cekura-create-agent` | "Connect my voice agent to Cekura" |
| `cekura-self-improving-agent` | "Improve my agent / auto-tune from eval results" |
| `cekura-metric-design` | "Create a metric / measure call quality" |
| `cekura-metric-improvement` | "Improve a metric / fix metric accuracy" |
| `cekura-predefined-metrics` | "What predefined metrics are available / which built-in metrics should I use" |
| `cekura-eval-design` | "Design test scenarios for my voice agent" |
| `cekura-fixing-prod-issues` | "Fix a production call bug / reproduce and test a fix before raising a PR" |
| `cekura-infra-test-suite` | "Create CI/CD tests for my voice bot / test my voice AI infrastructure / E2E test my pipecat bot" |

### Want full functionality?

`npx skills add` gives you the **behavioral guidance layer** — the skills auto-activate when you describe relevant tasks. For slash commands and direct API integration, install the full Claude Code plugin marketplace below.

---

## Claude Code (VS Code)

Full plugin support — skills, slash commands, MCP tools, and auto-configured API access.

### Install

1. Open the Claude Code chat panel
2. Click **Manage Plugins** > **Marketplaces** tab
3. Paste `https://github.com/cekura-ai/cekura-skills.git` and click **Add**
4. Switch to the **Plugins** tab > search for `cekura` > install the plugin
5. Set your API key:
   ```bash
   # Add to ~/.zshrc or ~/.bashrc
   export CEKURA_API_KEY="your-key-here"
   ```
6. Restart VS Code to pick up the environment variable
7. In the Claude Code chat, run `/setup-mcp` to configure the MCP server

### Get Started

Ask "I'm new to Cekura, help me get started" for a guided walkthrough, or ask "what can Cekura do?" to see everything available.

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
4. Go to the **Discover** tab > search for `cekura` > install the plugin
5. Set your API key:
   ```bash
   # Add to ~/.zshrc or ~/.bashrc
   export CEKURA_API_KEY="your-key-here"
   ```
6. Restart your terminal and Claude Code session
7. Run `/setup-mcp` to configure the MCP server

> **Tip:** If you've already cloned the repo locally, you can paste the local path instead of the GitHub URL.

### Get Started

Ask "I'm new to Cekura, help me get started" for a guided walkthrough, or ask "what can Cekura do?" to see everything available.

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
  --path cekura/skills/cekura-onboarding \
         cekura/skills/cekura-create-agent \
         cekura/skills/cekura-self-improving-agent \
         cekura/skills/cekura-metric-design \
         cekura/skills/cekura-metric-improvement \
         cekura/skills/cekura-predefined-metrics \
         cekura/skills/cekura-eval-design \
         cekura/skills/cekura-fixing-prod-issues \
         cekura/skills/cekura-infra-test-suite
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
  --path cekura/skills/cekura-onboarding \
         cekura/skills/cekura-create-agent \
         cekura/skills/cekura-self-improving-agent \
         cekura/skills/cekura-metric-design \
         cekura/skills/cekura-metric-improvement \
         cekura/skills/cekura-predefined-metrics \
         cekura/skills/cekura-eval-design \
         cekura/skills/cekura-fixing-prod-issues \
         cekura/skills/cekura-infra-test-suite
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

**How it works:** The plugin ships a single `.mcp.json` file at the marketplace root that auto-configures the connection. When Claude Code starts, it reads the file and connects to the Cekura MCP server at `https://api.cekura.ai/mcp`. With `CEKURA_API_KEY` in your environment, all `mcp__cekura__*` tools become available automatically. Or use OAuth via `claude mcp add` for a key-free, one-click browser sign-in — see the [MCP overview](https://docs.cekura.ai/mcp/overview).

---

## Quick Reference

### Slash Commands (Claude Code plugin only)

| Command | What it Does |
|---------|-------------|
| `/cekura-onboarding` | Guided end-to-end setup — preflight, state-aware resume, walks through agent + metrics + first eval run |
| `/setup-mcp` | Configure MCP server (run once after install) |
| `/upgrade-skills` | Pull latest skill updates from GitHub |
| `/report-bug` | Report a bug — files GitHub issue, optionally attempts a fix |
| `/create-metric` | Create or update a metric |
| `/list-metrics` | List metrics for an agent or project |
| `/evaluate-calls` | Run metrics on specific calls |
| `/improve-metric` | Improve metric accuracy: feedback, labs, auto-improve |
| `/autogen-eval` | Auto-generate evaluators (or bulk create from CSV/JSON) |
| `/manual-create-update-eval` | Create or update a single evaluator with full field walkthrough |
| `/list-evals` | List evaluators for an agent or project |
| `/run-evals` | Execute test scenarios |
| `/eval-results` | Check results from a test run |
| `/cekura-report` | Full end-to-end quality report — generates 10 evals, runs them, produces structured analysis |

### Skills (load automatically — both install paths)

| Skill | When it activates |
|-------|-------------------|
| `cekura-coordinator` | "What can Cekura do?" — routes to the right skill |
| `cekura-onboarding` | First-time setup, end-to-end platform walkthrough |
| `cekura-create-agent` | Setting up an agent — provider, mock tools, KB, dynamic vars |
| `cekura-self-improving-agent` | Auto-tuning an agent prompt from eval results |
| `cekura-metric-design` | Designing or creating metrics |
| `cekura-metric-improvement` | Improving an existing metric via feedback iteration |
| `cekura-predefined-metrics` | Exploring built-in metrics — what each does, costs, constraints |
| `cekura-eval-design` | Designing test scenarios for a voice agent |
| `cekura-fixing-prod-issues` | Fixing a production call bug — debug, reproduce, fix, verify, regression test, PR |
| `cekura-infra-test-suite` | Generating a CI/CD infra test suite — STT→LLM→TTS, interruption, idle timers, DTMF, local bot orchestration |

### Getting Started Flow

1. `/setup-mcp` — Configure API access (Claude Code plugin only)
2. `/cekura-onboarding` — Guided platform setup (preflight + state-aware walkthrough). Or just ask "I'm new to Cekura" to activate the skill directly.
3. Ask "set up my agent" — activates `cekura-create-agent`
4. `/autogen-eval` — Auto-generate test scenarios
5. `/run-evals` — Run your first tests
6. Ask "create a metric for X" — activates `cekura-metric-design`
7. `/cekura-report` — Full end-to-end quality report for any agent

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

## Reinstalling Cekura skills

If `/upgrade-skills` reports stale plugin entries, or `/plugin install` fails with `Source path does not exist`, your Claude Code install needs a clean reinstall. Run these 4 commands in order in any Claude Code session:

1. `/plugin marketplace remove cekura-skills`
2. `/plugin marketplace add cekura-ai/cekura-skills`
3. `/plugin marketplace update cekura-skills`
4. `/plugin install cekura@cekura-skills`

Step 3 is the critical one — it forces Claude Code to re-read the marketplace manifest. After step 4, `claude plugin list` should show one `cekura@cekura-skills` entry, and all 14 slash commands resolve under `cekura:*`.

### Troubleshooting

**`/plugin install` errors with `Source path does not exist`:** Re-run step 3 (`/plugin marketplace update cekura-skills`) and retry step 4. If that doesn't clear it, fully restart Claude Code (close and reopen the session), then redo steps 2–4.

**`claude plugin list` shows zero cekura entries after upgrading:** you've removed the old plugins but haven't installed the new one. Run steps 2–4 above.

---

## Links

- **Cekura Dashboard:** [dashboard.cekura.ai](https://dashboard.cekura.ai)
- **Sign Up:** [dashboard.cekura.ai/sign-up](https://dashboard.cekura.ai/sign-up)
- **API Docs:** [docs.cekura.ai/api-reference](https://docs.cekura.ai/api-reference)
- **LLM-friendly Docs:** [docs.cekura.ai/llms.txt](https://docs.cekura.ai/llms.txt)
- **Concepts:** [docs.cekura.ai/documentation/key-concepts](https://docs.cekura.ai/documentation/key-concepts/)
