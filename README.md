# Cekura AI Skills

AI-powered skills for building and improving voice agent tests and metrics on the [Cekura](https://cekura.ai) platform. Works with Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot, and other AI coding assistants.

## Table of Contents

- [What's Included](#whats-included)
- [Prerequisites](#prerequisites)
- [Quick Install (npx skills add)](#quick-install-npx-skills-add)
- [Claude Code (VS Code)](#claude-code-vs-code)
- [Claude Code (Terminal CLI)](#claude-code-terminal-cli)
- [Codex](#codex)
- [Cursor](#cursor)
- [Gemini CLI](#gemini-cli)
- [GitHub Copilot](#github-copilot)
- [Windsurf / Other Agents](#windsurf--other-agents)
- [MCP Server](#mcp-server)
- [Quick Reference](#quick-reference)
- [Platform Compatibility](#platform-compatibility)
- [Reinstalling Cekura skills](#reinstalling-cekura-skills)
- [Links](#links)

---

## What's Included

### 12 Skills, 14 Commands in one plugin

| Skills | Commands |
|--------|----------|
| `cekura-coordinator` | `cekura-onboarding`, `setup-mcp`, `upgrade-skills`, `report-bug` |
| `cekura-onboarding` | `create-metric`, `list-metrics`, `evaluate-calls`, `improve-metric` |
| `cekura-create-agent` | `manual-create-update-eval`, `autogen-eval`, `list-evals`, `run-evals`, `eval-results`, `cekura-report` |
| `cekura-self-improving-agent` | "Improve my agent / auto-tune from eval results" — **also** "fix a production call bug end-to-end". Works on dashboard-managed providers AND custom stacks (config in your repo/DB/prompt registry, runtime-created provider agents, custom mock servers) via a per-project capability manifest |
| `cekura-metric-design` | |
| `cekura-metric-improvement` | |
| `cekura-predefined-metrics` | |
| `cekura-eval-design` | |
| `cekura-infra-test-suite` | |
| `cekura-agent-benchmark-report` | |
| `cekura-flag-call-log-failures` | |
| `cekura-generate-scenarios` | |

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

> **GitHub Copilot:** Copilot loads skills from a repository's `.github/skills/` directory, so target it explicitly — `npx skills add cekura-ai/cekura-skills --all --agent github-copilot --output .github/skills`. For the Copilot CLI plugin (skills **and** MCP tools), see [GitHub Copilot](#github-copilot) below.

### What gets installed

Twelve skills, scoped to specific Cekura workflows:

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
| `cekura-infra-test-suite` | "Create a committed JSON CI/CD suite / add Tests-as-Code to my voice-agent repo / update test coverage for this PR" |
| `cekura-agent-benchmark-report` | "Benchmark my voice agent / run a 25-, 50-, 75-, or 100-call evaluation and create a report" |
| `cekura-flag-call-log-failures` | "Analyze the last N calls for issues / what % of calls have <problem>" |
| `cekura-generate-scenarios` | "Create scenarios from failed calls / regression-test the agent on prod issues" |

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

#### Auto-update

Installs from this marketplace (`cekura@cekura-skills`) keep themselves current: the plugin ships a `SessionStart` hook that runs Claude Code's own update commands at most once per day (best-effort — it never blocks or fails your session, and it no-ops for installs from any other marketplace). To also let Claude Code's native auto-update refresh the marketplace, add this to your `~/.claude/settings.json` — or just run `/setup-mcp`, which offers to enable it for you:

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
         cekura/skills/cekura-infra-test-suite \
         cekura/skills/cekura-agent-benchmark-report
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

## GitHub Copilot

Cekura installs on Copilot two different ways, and they cover different surfaces:

| Surface | Install | What you get |
|---|---|---|
| **Copilot CLI** | Marketplace plugin (below) | Skills **+** MCP tools, OAuth |
| **Coding agent, code review, IDE extensions** | Skills committed to `.github/skills/` | Skills; MCP is configured per repository |

Copilot reads its own registry at `.github/plugin/marketplace.json`, separate from the Claude manifest, so the two installs never interfere. Copilot plugins don't carry Claude-style slash commands — the skills cover those workflows.

### Install (Copilot CLI)

**1. Install the CLI and sign in** (needs a Copilot licence — Pro, Pro+, Business, or Enterprise):

```bash
npm install -g @github/copilot
```

Run `copilot` once and complete the sign-in prompt.

**2. Add the Cekura marketplace:**

```bash
copilot plugin marketplace add cekura-ai/cekura-skills
```

**3. Confirm Copilot can read it** — this should list one plugin, `cekura`:

```bash
copilot plugin marketplace browse cekura-skills
```

**4. Install the plugin:**

```bash
copilot plugin install cekura@cekura-skills
```

**5. Verify skills and MCP:**

```bash
copilot plugin list   # cekura listed as installed
```

```bash
copilot mcp list      # cekura listed as an MCP server
```

**6. Authenticate MCP** — nothing to configure. The first time Copilot calls a Cekura tool it opens a browser for OAuth sign-in; no API key is stored.

Prefer an interactive session? Run `copilot`, then `/plugin marketplace add cekura-ai/cekura-skills` followed by `/plugin install cekura@cekura-skills`.

### Copilot coding agent, code review, and the IDE extensions

Those surfaces load skills from a repository's `.github/skills/` directory rather than from CLI plugins. Install the skill files into the repo you want them active in and commit the result:

```bash
npx skills add cekura-ai/cekura-skills --all --agent github-copilot --output .github/skills
```

To give those surfaces Cekura MCP access as well, register `https://api.cekura.ai/mcp` in your repository's Copilot MCP configuration — see GitHub's docs on [configuring MCP servers for your repository](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/configure-mcp-servers). Note that the Copilot coding agent and Copilot code review don't support OAuth-authenticated remote MCP servers, so use the API-key credential there: send your key in an `X-CEKURA-API-KEY` header. (Copilot CLI does support OAuth — that path needs no key.)

### Get Started

Ask Copilot to help with Cekura metrics or evals — skills load automatically when the conversation matches. A good first prompt:

```plaintext
Use the Cekura skills and MCP. List my Cekura agents, pick one, and propose 3 evaluators I should create first. Do not create anything until I approve.
```

If Copilot answers in generic terms without naming your agents, the skills or the MCP server aren't loaded — re-check steps 3–5.

### Upgrade

```bash
copilot plugin update cekura
```

If a release adds a brand-new skill, refresh the marketplace snapshot first: `copilot plugin marketplace add cekura-ai/cekura-skills` (re-adding refreshes it), then `copilot plugin update cekura`. For the `.github/skills/` path, re-run the `npx skills add` command above. Copilot has no auto-update hook yet, so run the update command when you want the latest version.

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

**For Claude Code users:** the plugin auto-configures the MCP server; on first tool use you'll get a one-click browser OAuth sign-in (no API key stored). Run `/setup-mcp` if tools aren't available — it verifies connectivity and, if you prefer a key-based credential (e.g. for CI), walks you through the `X-CEKURA-API-KEY` setup.

**For Codex, Cursor, Gemini CLI, and GitHub Copilot:** the MCP server is wired up natively through each platform's plugin/extension manifest, authenticating via OAuth (no API key stored). The sign-in step differs per platform — in **Codex** run `codex mcp login cekura`; **Cursor** prompts for OAuth when you connect the server; **Gemini** and **Copilot CLI** run the OAuth flow on first tool use. For agents using only the `AGENTS.md` behavior preset (Windsurf, etc.), the MCP server is optional — the preset includes API reference with curl examples as a fallback.

**How it works:** Claude Code, Codex, and Copilot CLI read the bundled `cekura/.mcp.json`; Cursor and Gemini declare the endpoint inline in their own manifests. All five point at the Cekura MCP server at `https://api.cekura.ai/mcp` (CI asserts they stay in sync). By default it authenticates via OAuth — on first use the client opens a browser for a one-click sign-in, with no API key stored. To use an API key instead, run `/setup-mcp` and choose the API-key path. See the [MCP overview](https://docs.cekura.ai/mcp/overview).

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
| `cekura-infra-test-suite` | Creating or updating source-controlled Cekura JSON Tests-as-Code suites for a voice-agent repository |
| `cekura-agent-benchmark-report` | Running a cost-approved 25–100-call benchmark and producing an evidence-linked HTML comparison report |
| `cekura-flag-call-log-failures` | Triaging recent production call logs against KPIs — failure rates + outcome distribution |
| `cekura-generate-scenarios` | Turning flagged production failures into regression evaluator scenarios |

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
| **GitHub Copilot (CLI)** | `copilot plugin marketplace add` | Yes | Yes | No |
| **GitHub Copilot (coding agent / code review / IDE)** | `npx skills add --output .github/skills` | Yes | Repo MCP config | No |
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

## Data & privacy

The plugin talks only to your own Cekura account via the Cekura MCP server (`https://api.cekura.ai/mcp`), with every call mediated by your client's MCP permission system.

- **Skill-usage ping:** when a Cekura skill or command activates, it calls the `cekura_skill_started` MCP tool with the skill name, its verification tag, the plugin version, and (for some commands, when available) a conversation/session ID — so Cekura can see which skills are used and validate that the right playbook was loaded. Nothing else from your conversation is sent.
- **Local failure log:** failures of Cekura MCP tools are logged to `~/.claude/cekura-mcp-failures.log` (secret-redacted, capped at 100 lines, never leaves your machine on its own). The `/report-bug` command may include redacted excerpts in a GitHub issue — only after showing you the full issue body and getting your explicit OK.
- **Auto-update:** see the Auto-update sections above (Claude Code: daily self-update hook for installs from this marketplace; Codex: daily hook after a one-time `/hooks` trust).

See Cekura's [Privacy Policy](https://www.cekura.ai/privacy-policy) and [Terms of Service](https://www.cekura.ai/terms-of-service). Questions or issues: **support@cekura.ai**.

---

## Links

- **Cekura Dashboard:** [dashboard.cekura.ai](https://dashboard.cekura.ai)
- **Sign Up:** [dashboard.cekura.ai/sign-up](https://dashboard.cekura.ai/sign-up)
- **API Docs:** [docs.cekura.ai/api-reference](https://docs.cekura.ai/api-reference)
- **LLM-friendly Docs:** [docs.cekura.ai/llms.txt](https://docs.cekura.ai/llms.txt)
- **Concepts:** [docs.cekura.ai/documentation/key-concepts](https://docs.cekura.ai/documentation/key-concepts/)
