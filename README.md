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
| `cekura-self-improving-agent` | "Improve my agent / auto-tune from eval results" — **also** "fix a production call bug / reproduce and test a fix before raising a PR" |
| `cekura-metric-design` | "Create a metric / measure call quality" |
| `cekura-metric-improvement` | "Improve a metric / fix metric accuracy" |
| `cekura-predefined-metrics` | "What predefined metrics are available / which built-in metrics should I use" |
| `cekura-eval-design` | "Design test scenarios for my voice agent" |
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

Run `/upgrade-skills` in any Claude Code session — it refreshes the marketplace and re-pins the plugin to the latest version, then prompts you to run `/reload-plugins` (no restart needed in the common case).

To upgrade manually:

```bash
claude plugin marketplace update cekura-skills   # refresh catalog from GitHub
claude plugin update cekura@cekura-skills          # move the installed pin to latest
```

Then run `/reload-plugins` in your session to apply it. A plain `git pull` of the marketplace checkout does **not** move the version pin, so it won't upgrade you on its own — use the commands above.

#### Auto-update (optional)

To have Claude Code pull new Cekura versions automatically at launch (it still prompts you to `/reload-plugins`), add this to your `~/.claude/settings.json` — or just run `/setup-mcp`, which offers to enable it for you:

```json
{
  "extraKnownMarketplaces": {
    "cekura-skills": {
      "source": { "source": "github", "repo": "cekura-ai/cekura-skills" },
      "autoUpdate": true
    }
  }
}
```

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

Run `/upgrade-skills` in any Claude Code session — it refreshes the marketplace and re-pins the plugin to the latest version, then prompts you to run `/reload-plugins` (no restart needed in the common case).

To upgrade manually:

```bash
claude plugin marketplace update cekura-skills   # refresh catalog from GitHub
claude plugin update cekura@cekura-skills          # move the installed pin to latest
```

Then run `/reload-plugins` to apply it. A plain `git pull` of the marketplace checkout does **not** move the version pin. To pull new versions automatically at launch, see [Auto-update (optional)](#auto-update-optional) under Claude Code (VS Code), or run `/setup-mcp`.

---

## Codex

Native plugin support — skills **and** MCP tools. (Codex plugins don't carry slash commands; the skills cover those workflows — they activate by context or when you invoke one with `@`.)

### Install (recommended)

Three steps — add the marketplace, install the plugin, then authenticate the MCP:

```bash
# 1. Add the marketplace
codex plugin marketplace add cekura-ai/cekura-skills

# 2. Install the plugin (cekura plugin from the cekura marketplace)
codex plugin add cekura@cekura

# 3. Authenticate the Cekura MCP — opens a browser for OAuth sign-in (no API key)
codex mcp login cekura
```

Prefer the TUI? Run `codex`, open `/plugins` to install **cekura**, then `/mcp` to authenticate.

Verify it worked:

```bash
codex plugin list   # cekura should be listed as installed
codex mcp list      # cekura should show as connected after login
```

> If you added the marketplace before a recent release, refresh it first so the latest manifest is picked up: `codex plugin marketplace upgrade cekura`.
>
> **API-key alternative:** the bundled MCP config is OAuth-only. To use a key instead, add the server to `~/.codex/config.toml` with `http_headers = { "X-CEKURA-API-KEY" = "your-key" }` (or `env_http_headers` to read it from an env var).

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
         cekura/skills/cekura-infra-test-suite
```

**Behavior preset** — single-file domain knowledge (metric design, eval design, API reference, anti-patterns):

```bash
curl -o AGENTS.md https://raw.githubusercontent.com/cekura-ai/cekura-skills/main/codex/AGENTS.md
```

### Get Started

Ask Codex to help with Cekura metrics or evals — skills load automatically when the conversation matches, or invoke one explicitly with `@`.

### Upgrade

```bash
codex plugin marketplace upgrade cekura   # refresh the marketplace snapshot from GitHub
codex plugin add cekura@cekura            # re-pin to the new version (required — not optional)
```

Both steps are needed: `marketplace upgrade` only refreshes the snapshot, and `codex plugin add` re-pins the installed plugin to it. Running just the first leaves you on the old version. Confirm with `codex plugin list` — the `cekura@cekura` row should show the new version.

**Auto-update (optional).** The plugin ships a `SessionStart` hook that runs the two commands above automatically on each launch (throttled to once/day), so you stay current without typing them. Codex requires you to trust the hook once: run `codex`, open `/hooks`, and trust the Cekura **SessionStart** hook. After that it's automatic; the manual commands above remain available to force an update immediately.

For the fallbacks, re-run the skill installer / re-download `AGENTS.md`.

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

**Team-wide auto-install (Teams/Enterprise):** a workspace admin can mark the Cekura plugin **Required** for a distribution group in the Team Marketplace settings — that installs and keeps it updated for everyone automatically, no per-developer action. This is an admin dashboard setting, not something the plugin declares.

---

## Gemini CLI

Extension support — MCP tools plus the Cekura context file. (Gemini discovers extension skills from a root `skills/` directory, so this extension doesn't bundle the nested `cekura/skills/`; native Gemini skill bundling is deferred.)

### Install

```bash
gemini extensions install https://github.com/cekura-ai/cekura-skills --auto-update
```

The `--auto-update` flag lets the extension self-check GitHub on each launch and apply the new version on the next restart — no manual updates needed. Omit it if you prefer to update manually.

On first use of a Cekura MCP tool, Gemini runs an OAuth sign-in flow. The extension loads `GEMINI.md` — all Cekura domain knowledge (metric design, eval design, API reference, anti-patterns) — as context.

### Upgrade

If you installed with `--auto-update`, new versions are pulled automatically (restart to apply). To update manually, or to force it now:

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

**For Codex, Cursor, and Gemini CLI:** the MCP server is wired up natively through each platform's plugin/extension manifest, authenticating via OAuth (no API key stored). The sign-in step differs per platform — in **Codex** run `codex mcp login cekura`; **Cursor** prompts for OAuth when you connect the server; **Gemini** runs the OAuth flow on first tool use. For agents using only the `AGENTS.md` behavior preset (Windsurf, etc.), the MCP server is optional — the preset includes API reference with curl examples as a fallback.

**How it works:** Claude, Codex, and Cursor read the bundled `cekura/.mcp.json`, which points at the Cekura MCP server at `https://api.cekura.ai/mcp`; Gemini declares the same remote endpoint inline in `gemini-extension.json`. By default it authenticates via OAuth — on first use the client opens a browser for a one-click sign-in, with no API key stored. To use an API key instead, run `/setup-mcp` and choose the API-key path. See the [MCP overview](https://docs.cekura.ai/mcp/overview).

---

## Quick Reference

### Slash Commands (Claude Code plugin only)

| Command | What it Does |
|---------|-------------|
| `/cekura-onboarding` | Guided end-to-end setup — preflight, state-aware resume, walks through agent + metrics + first eval run |
| `/setup-mcp` | Configure MCP server (run once after install) |
| `/upgrade-skills` | Re-pin the plugin to the latest version, then `/reload-plugins` |
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
| `cekura-self-improving-agent` | Auto-tuning an agent prompt from eval results — **and** fixing a production call bug end-to-end (auto-build reproduction harness, must-fail-first gate, fix, stochastic verify, regression sweep, PR / summary) |
| `cekura-metric-design` | Designing or creating metrics |
| `cekura-metric-improvement` | Improving an existing metric via feedback iteration |
| `cekura-predefined-metrics` | Exploring built-in metrics — what each does, costs, constraints |
| `cekura-eval-design` | Designing test scenarios for a voice agent |
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
