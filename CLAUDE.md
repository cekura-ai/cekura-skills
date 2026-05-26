# Cekura Skills — Developer Guide

## Repository Structure

This is a Claude Code **marketplace** that doubles as an **Agent Skills package** — a single plugin that encodes domain expertise for the [Cekura](https://cekura.ai) voice AI testing and evaluation platform.

```
cekura-skills/
  .claude-plugin/
    marketplace.json             # Marketplace registry (single plugin entry, source: "./cekura")
  cekura/                        # The plugin lives here (marketplace.json points to this dir)
    .claude-plugin/
      plugin.json                # Plugin manifest
    .mcp.json                    # MCP auto-config
    skills/                      # Single source of truth for skills
      cekura-coordinator/
      cekura-onboarding/
      cekura-create-agent/
      cekura-self-improving-agent/
      cekura-metric-design/
      cekura-metric-improvement/
      cekura-predefined-metrics/
      cekura-eval-design/
      cekura-fixing-prod-issues/
    commands/                    # Slash commands (Claude Code only)
    agents/                      # Sub-agent definitions (Claude Code only)
    hooks/                       # MCP failure detection (Claude Code only)
  _template/                     # SKILL.md.tmpl scaffold for new skills (dev-only)
  codex/
    AGENTS.md                    # Single-file behavior preset for Codex/Cursor/other agents
  package.json                   # npm package metadata (used by Agent Skills validators)
  README.md                      # User-facing installation and platform setup guide
  CLAUDE.md                      # This file — developer context for contributors
```

> **Note on the `cekura/` subdir:** Claude Code's marketplace validator rejects `"source": "."`, so the plugin contents live under `cekura/` and `marketplace.json` points to `"./cekura"`. The `.claude-plugin/marketplace.json` itself stays at the repo root; everything else (plugin.json, .mcp.json, skills/, commands/, agents/, hooks/) travels with the plugin root under `cekura/`.

### Two install paths, one source of truth

The 9 SKILL.md files inside `cekura/skills/` are the **only** source of skill content. Both install paths consume the same files:

1. **Claude Code plugin marketplace** (`/plugin marketplace add cekura-ai/cekura-skills`) — gets skills + slash commands + MCP auto-config + hooks. Full functionality.
2. **Agent Skills via npx** (`npx skills add cekura-ai/cekura-skills`) — gets skills only. Works with any Agent Skills-compatible client (Cursor, Codex, Windsurf, OpenCode, etc.).

The upstream `vercel-labs/skills` CLI reads `.claude-plugin/marketplace.json`, follows the `source` path (`./cekura`), and discovers all 9 skills under `cekura/skills/`. The bare repo URL works cleanly.

### Skill content rules

Every `cekura/skills/<name>/SKILL.md`:
- `name` field must be lowercase kebab-case (`cekura-foo`) matching the directory name (per Agent Skills spec)
- `description` includes trigger phrases for skill activation
- `compatibility` field set to: `Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.`
- Body is **public-facing**: no `mcp__cekura__*` tool references, no internal endpoints (e.g., `localhost:8001`), no MCP-bug curl workarounds
- Public API endpoint paths (e.g., `POST /test_framework/v1/...`) are fine — those are user-facing
- Public provider names (VAPI, Retell, ElevenLabs, LiveKit, Pipecat, SIP) are fine — they're documented at https://docs.cekura.ai/documentation/integrations/
- Aim for under 500 lines per file (Agent Skills spec recommendation)

Operational MCP tool references belong in **command files** (`cekura/commands/*.md`), which are Claude Code–specific and only loaded by the plugin marketplace path. The `npx skills add` path doesn't fetch commands.

### Update workflow

Once installed, npx users have three ways to stay current:

| Goal | Command |
|---|---|
| Refresh existing skills only | `npx skills update` |
| Refresh existing AND install any new skills (recommended) | `npx skills add cekura-ai/cekura-skills --all` |
| Install one specific newly-released skill | `npx skills add cekura-ai/cekura-skills --skill <name>` |

`update` alone does NOT discover newly-added skills — when you publish a new skill, mention `--all` or `--skill <name>` in the release notes.

### Adding a new public skill (contributor checklist)

1. Create `cekura/skills/cekura-<kebab-name>/SKILL.md` with spec-compliant frontmatter (`name` must be `cekura-<kebab-name>`, matching the directory)
2. Body must be public-facing — no `mcp__cekura__*` references, no internal endpoints
3. Stay under 500 lines per file
4. Bump `package.json` version
5. Update the "What's Included" table and Quick Reference table in `README.md`
6. If the skill needs an operational counterpart, also add a slash command in `cekura/commands/`
7. In the release notes / commit message, name the new skill so users know what to pass to `--skill`

## MCP Integration

The plugin uses the Cekura MCP server as the **primary** API access path. The plugin's `cekura/.mcp.json` auto-configures an MCP server pointing at `https://api.cekura.ai/mcp` and reads `${CEKURA_API_KEY}` for auth (or users can run `claude mcp add` for OAuth instead — see the [MCP overview docs](https://docs.cekura.ai/mcp/overview)).

MCP is the default. If MCP tools aren't available, users run `/setup-mcp` to configure the server.

When writing or updating skills/commands:
- Reference MCP tools by name (e.g., `mcp__cekura__metrics_create`)
- Use the standard API Access section format (see any SKILL.md for the pattern)
- Include `mcp__cekura__*` tool names in command `allowed-tools` frontmatter

### Known MCP Limitations

Some MCP endpoints have issues that require `curl` workarounds:

1. **Metric writes with large text/code fields — 400/414 Request Line Too Large.** `mcp__cekura__metrics_create`, `mcp__cekura__metrics_partial_update`, and `mcp__cekura__metrics_bulk_create` can fail when long `custom_code`, `description`, `prompt`, or `evaluation_trigger_custom_code` fields are serialized into the URL/query string. **Workaround:** Use `curl -X POST` / `curl -X PATCH` with a JSON body for large metric writes, then re-fetch through MCP to verify the exact fields changed.

2. **`mcp__cekura__aiagents_create` — 414 URI Too Long on large payloads.** The MCP server encodes params as URL query strings, not JSON bodies. Agent descriptions (10-60KB) exceed nginx's URI limit. **Workaround:** Use `curl -X POST` with a JSON body for any agent creation with a description longer than ~4KB.

3. **`mcp__cekura__aiagents_tools_create` — Not exposed by MCP.** The tool search doesn't return this endpoint. **Workaround:** Use `curl -X POST` to `https://api.cekura.ai/test_framework/v1/aiagents/{id}/tools/`.

All workarounds use `$CEKURA_API_KEY` in the `X-CEKURA-API-KEY` header. See the create-agent skill's "Known MCP Limitations & Curl Workarounds" section for full curl examples. Skills that hit these endpoints should include `Bash` in their `allowed-tools` frontmatter.

## Plugin Overview (single `cekura` plugin)

### Skills
| Component | Purpose |
|-----------|---------|
| `cekura-coordinator` | Route users to the right skill/command |
| `cekura-onboarding` | Walk new users through full platform setup |
| `cekura-create-agent` | Set up a voice AI agent — provider, mock tools, KB, dynamic vars |
| `cekura-self-improving-agent` | Auto-tune agent prompts from eval results — diagnose → propose → apply → re-validate loop |
| `cekura-metric-design` | Core metric design patterns and best practices |
| `cekura-metric-improvement` | Metric improvement through feedback iteration |
| `cekura-predefined-metrics` | Catalog of all predefined metrics — what each does, costs, constraints, configuration |
| `cekura-eval-design` | Evaluator design, test profiles, conditional actions, session memory |
| `cekura-fixing-prod-issues` | Debug a production call, write a fix, and verify it with two rounds of evaluator testing before raising a PR |

### Commands
| Component | Purpose |
|-----------|---------|
| `setup-mcp` | Configure the MCP server |
| `upgrade-skills` | Pull latest from GitHub |
| `report-bug` | Collect bug context, file GitHub issue, optionally attempt fix |
| `cekura-onboarding` | Guided platform setup |
| `create-metric` | Create or update a metric |
| `list-metrics` | List metrics for an agent or project |
| `evaluate-calls` | Run metrics on specific calls |
| `improve-metric` | Full improvement cycle: feedback, labs, auto-improve |
| `manual-create-update-eval` | Create or update a single evaluator with full field walkthrough |
| `autogen-eval` | Auto-generate evaluators or bulk create from CSV/JSON |
| `list-evals` | List evaluators for an agent or project |
| `run-evals` | Execute evaluators |
| `eval-results` | Check results from a test run |
| `cekura-report` | End-to-end quality report: generate 10 evals, run them, produce structured analysis |

### Agents
| Component | Purpose |
|-----------|---------|
| `metric-reviewer` | Reviews metric quality |
| `eval-suite-planner` | Coverage matrix design from agent descriptions |

### Hooks
| Component | Purpose |
|-----------|---------|
| MCP failure hook | Auto-detects `mcp__cekura__*` failures, logs them, suggests `/report-bug` |
| Self-improving stop hook | Detects when the self-improving-agent skill stops mid-loop |

## AGENTS.md (Codex/Cursor)

`codex/AGENTS.md` is a single-file distillation of the plugin's domain knowledge — metric design, eval design, anti-patterns, and API reference. It's designed for agents that don't support the Claude Code plugin system (Codex, Cursor, Windsurf, etc.).

When updating skills, keep AGENTS.md in sync with major changes (new patterns, API changes, new anti-patterns). It doesn't need every detail — just the core guidance that makes a meaningful difference in output quality.

## Conventions

- **Skill versions** follow semver in the SKILL.md frontmatter. Bump minor for new sections/patterns, patch for fixes.
- **Plugin version** is in `.claude-plugin/plugin.json`. Bump when adding new skills/commands.
- **Marketplace version** is in `.claude-plugin/marketplace.json`. Match the plugin version.
- **Command frontmatter** must include `allowed-tools` listing the specific `mcp__cekura__*` tools the command needs.
- **Skills** should have a `## API Access — Cekura MCP Server` section with prerequisites, tool table, docs lookup, and troubleshooting.

## Bug Reporting & Auto-Fix

### How It Works

Two mechanisms for catching issues:

1. **Hook (`PostToolUseFailure`)** — The plugin registers a hook on all `mcp__cekura__*` tool failures. When any MCP tool fails, the hook:
   - Logs the failure to `~/.claude/cekura-mcp-failures.log` (tool name, error, timestamp)
   - Returns context to Claude suggesting `/setup-mcp` (for config issues) or `/report-bug` (for skill bugs)
   - The log file is capped at 100 lines to avoid growth

2. **`/report-bug` command** — Users (or Claude, prompted by the hook) can run this to:
   - Collect environment info (Claude Code version, OS, MCP status, API key status, plugin version)
   - Read recent entries from the failure log
   - Identify the affected skill/command file
   - **Attempt a quick fix** if the issue is clearly fixable (typo, wrong tool name, stale reference)
   - File a GitHub issue on `cekura-ai/cekura-skills` via `gh issue create`
   - If the user has push access, create a fix branch and open a PR
   - Fall back to printing the formatted report if `gh` isn't available

### Hook Architecture

```
cekura/hooks/
  hooks.json           # Hook registration (PostToolUseFailure → mcp__cekura__.*; Stop → self-improving check)
  on-mcp-failure.sh    # Logs failure, returns additionalContext to Claude
  on-self-improving-stop.sh  # Self-improving-agent loop interruption detection
```

The MCP failure hook uses `${CLAUDE_PLUGIN_ROOT}/hooks/on-mcp-failure.sh` as the command path. It reads JSON from stdin (tool name, error, session ID), writes to the log, and returns a JSON response with `additionalContext` that Claude sees as a system message.

### For Maintainers

When an issue is filed via `/report-bug`:
- It lands in the `cekura-ai/cekura-skills` repo with the `bug` label
- Includes full environment context and recent MCP failure logs
- May include a suggested fix if Claude identified one
- May already have a PR attached if the user had push access

To process: read the issue, fix the skill/command, push to `main`. Users pick up the fix via `/upgrade-skills`.

## Upgrading

Users run `/upgrade-skills` which does a `git pull` on this repo. For contributors:
- All changes go through the `main` branch
- The marketplace is registered by URL (`https://github.com/cekura-ai/cekura-skills.git`) — users get updates by pulling
- Breaking changes (renamed commands, removed skills) should be noted in commit messages

### Stuck-install detection

`cekura/commands/upgrade-skills.md` checks `~/.claude/plugins/installed_plugins.json` after each pull and prints the 4-step reinstall instructions if it finds stale plugin entries (`cekura-evals@cekura-skills` or `cekura-metrics@cekura-skills`) — those names existed in earlier marketplace layouts and indicate Claude Code needs a fresh `marketplace remove → add → update → install` cycle. The user-facing reinstall steps live in README "Reinstalling Cekura skills".
