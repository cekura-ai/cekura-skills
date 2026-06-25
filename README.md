# Cekura AI Skills

AI-powered skills for building and improving voice agent tests and metrics on the [Cekura](https://cekura.ai) platform. Works with Claude Code, Codex, Cursor, Gemini CLI, and other AI coding assistants.

## Table of Contents

- [What's Included](#whats-included)
- [Prerequisites](#prerequisites)
- [Quick Install (npx skills add)](#quick-install-npx-skills-add)
- [Claude Code (VS Code)](#claude-code-vs-code)
- [Claude Code (Terminal CLI)](#claude-code-terminal-cli)
- [Codex](#codex)
- [Cursor](#cursor)
- [Gemini CLI](#gemini-cli)
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

Ten skills, scoped to specific Cekura workflows:

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
5. In the Claude Code chat, run `/setup-mcp` to connect the MCP server. The default is OAuth — a browser opens for one-click sign-in; no API key or restart needed.
6. (Optional) For the API-key auth path or curl-based skill fallbacks, set your key and restart VS Code:
   ```bash
   # Add to ~/.zshrc or ~/.bashrc
   export CEKURA_API_KEY="your-key-here"
   ```

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
5. Run `/setup-mcp` to connect the MCP server. The default is OAuth — a browser opens for one-click sign-in; no API key or restart needed.
6. (Optional) For the API-key auth path or curl-based skill fallbacks, set your key and restart your terminal + Claude Code session:
   ```bash
   # Add to ~/.zshrc or ~/.bashrc
   export CEKURA_API_KEY="your-key-here"
   ```

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

Native plugin support — skills **and** MCP tools. (Codex plugins don't carry slash commands; the skills cover those workflows.)

### Install (recommended)

```bash
codex plugin marketplace add cekura-ai/cekura-skills
```

Then run `codex`, open `/plugins`, and install **cekura**. On first use of a Cekura MCP tool, Codex opens a browser for one-click OAuth sign-in — no API key stored.

### Fallbacks (no MCP)

**Skills only** — install the skill files directly:

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

**Behavior preset** — single-file domain knowledge (metric design, eval design, API reference, anti-patterns):

```bash
curl -o AGENTS.md https://raw.githubusercontent.com/cekura-ai/cekura-skills/main/codex/AGENTS.md
```

### Get Started

Ask Codex to help with Cekura metrics or evals — skills load automatically when the conversation matches.

### Upgrade

Re-run `codex plugin marketplace add cekura-ai/cekura-skills` (or, for the fallbacks, re-run the skill installer / re-download `AGENTS.md`).

---

## Cursor

Native plugin support — skills **and** MCP tools. (Cursor plugins don't carry Claude-style slash commands; the skills cover those workflows.)

### Install (recommended)

In Cursor, go to **Settings > Plugins > Team Marketplaces > Add Marketplace > Import from Repo**, point it at `https://github.com/cekura-ai/cekura-skills`, then install **cekura**. Authenticate the Cekura MCP via OAuth when prompted.

### Fallback (no MCP)

Use the behavior preset as a rules file:

```bash
curl -o .cursor/rules/cekura.md https://raw.githubusercontent.com/cekura-ai/cekura-skills/main/codex/AGENTS.md
```

Or add it as a global rule in Cursor Settings > Rules.

### Get Started

Ask Cursor to help with Cekura metrics or evals — skills load automatically when the conversation matches.

### Upgrade

**Manual:** re-import the marketplace from **Settings > Plugins > Team Marketplaces** (or re-download the rules-file fallback).

**Auto Refresh (optional)** — have Cursor pull new versions automatically:

1. Install the **Cursor GitHub App** on the `cekura-ai/cekura-skills` repository (Cursor prompts for this; it's required for Auto Refresh).
2. Go to **Settings > Plugins > Team Marketplaces** and locate the imported Cekura marketplace.
3. Toggle on **Auto Refresh** and save.

Cursor then re-indexes the marketplace at most once every ~10 minutes, picking up pushed updates to the installed plugin. Note: Auto Refresh updates the *existing* plugin only — if a brand-new plugin is added to the repo later, re-import the marketplace to pick it up.

---

## Gemini CLI

Extension support — MCP tools plus the Cekura context file. (Gemini discovers extension skills from a root `skills/` directory, so this extension doesn't bundle the nested `cekura/skills/`; native Gemini skill bundling is deferred.)

### Install

```bash
gemini extensions install https://github.com/cekura-ai/cekura-skills
```

On first use of a Cekura MCP tool, Gemini runs an OAuth sign-in flow. The extension loads `GEMINI.md` — all Cekura domain knowledge (metric design, eval design, API reference, anti-patterns) — as context.

### Upgrade

```bash
gemini extensions update cekura
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

**For Codex, Cursor, and Gemini CLI:** the MCP server is wired up natively through each platform's plugin/extension manifest — OAuth sign-in happens on first tool use, no key stored. For agents using only the `AGENTS.md` behavior preset (Windsurf, etc.), the MCP server is optional — the preset includes API reference with curl examples as a fallback.

**How it works:** Claude, Codex, and Cursor read the bundled `cekura/.mcp.json`, which points at the Cekura MCP server at `https://api.cekura.ai/mcp`; Gemini declares the same remote endpoint inline in `gemini-extension.json`. By default it authenticates via OAuth — on first use the client opens a browser for a one-click sign-in, with no API key stored. To use an API key instead, run `/setup-mcp` and choose the API-key path. See the [MCP overview](https://docs.cekura.ai/mcp/overview).

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

| Platform | Recommended method | Skills | MCP Tools | Slash Commands |
|----------|--------|--------|-----------|---------------|
| **Any Agent Skills client** | `npx skills add` | Yes | No | No |
| **Claude Code (VS Code)** | Marketplace install | Yes | Yes | Yes |
| **Claude Code (CLI)** | `/plugins` install | Yes | Yes | Yes |
| **Codex** | `codex plugin marketplace add` | Yes | Yes | No |
| **Cursor** | Plugin marketplace install | Yes | Yes | No |
| **Gemini CLI** | `gemini extensions install` | Context file only | Yes | No |
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
