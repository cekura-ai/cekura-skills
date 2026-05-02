# Cekura Skills — Developer Guide

## Repository Structure

This is a Claude Code **marketplace** that doubles as an **Agent Skills package** — a collection of plugins and skills that encode domain expertise for the [Cekura](https://cekura.ai) voice AI testing and evaluation platform.

```
cekura-skills/
  plugins/
    cekura/
      .claude-plugin/plugin.json   # Plugin manifest
      .mcp.json                    # MCP auto-config
      skills/                      # Single source of truth for skills
        cekura-coordinator/
        cekura-onboarding/
        cekura-create-agent/
      commands/                    # Slash commands (Claude Code only)
      hooks/                       # MCP failure detection (Claude Code only)
    cekura-metrics/
      skills/
        cekura-metric-design/
        cekura-metric-improvement/
      commands/
    cekura-evals/
      skills/
        cekura-eval-design/
      commands/
      agents/
  codex/
    AGENTS.md                      # Single-file behavior preset for Codex/Cursor/other agents
  package.json                     # npm package metadata (used by Agent Skills validators)
  README.md                        # User-facing installation and platform setup guide
  CLAUDE.md                        # This file — developer context for contributors
```

### Two install paths, one source of truth

The 6 SKILL.md files inside `plugins/<plugin>/skills/` are the **only** source of skill content. Both install paths consume the same files:

1. **Claude Code plugin marketplace** (`/plugin marketplace add cekura-ai/cekura-skills`) — gets skills + slash commands + MCP auto-config + hooks. Full functionality.
2. **Agent Skills via npx** (`npx skills add cekura-ai/cekura-skills`) — gets skills only. Works with any Agent Skills-compatible client (Cursor, Codex, Windsurf, OpenCode, etc.).

The upstream `vercel-labs/skills` CLI reads `.claude-plugin/marketplace.json`, follows the `source` paths, and discovers all 6 skills with no subpath needed. The bare URL works cleanly.

### Skill content rules

Every `plugins/<plugin>/skills/<name>/SKILL.md`:
- `name` field must be lowercase kebab-case (`cekura-foo`) matching the directory name (per Agent Skills spec)
- `description` includes trigger phrases for skill activation
- `compatibility` field set to: `Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.`
- Body is **public-facing**: no `mcp__cekura__*` tool references, no internal endpoints (e.g., `localhost:8001`), no MCP-bug curl workarounds
- Public API endpoint paths (e.g., `POST /test_framework/v1/...`) are fine — those are user-facing
- Public provider names (VAPI, Retell, ElevenLabs, LiveKit, Pipecat, SIP) are fine — they're documented at https://docs.cekura.ai/documentation/integrations/
- Aim for under 500 lines per file (Agent Skills spec recommendation)

Operational MCP tool references belong in **command files** (`plugins/<plugin>/commands/*.md`), which are Claude Code–specific and only loaded by the plugin marketplace path. The `npx skills add` path doesn't fetch commands.

### Update workflow

Once installed, npx users have three ways to stay current:

| Goal | Command |
|---|---|
| Refresh existing skills only | `npx skills update` |
| Refresh existing AND install any new skills (recommended) | `npx skills add cekura-ai/cekura-skills --all` |
| Install one specific newly-released skill | `npx skills add cekura-ai/cekura-skills --skill <name>` |

`update` alone does NOT discover newly-added skills — when you publish a new skill, mention `--all` or `--skill <name>` in the release notes.

### Adding a new public skill (contributor checklist)

1. Pick which plugin owns it: `cekura`, `cekura-metrics`, or `cekura-evals`
2. Create `plugins/<plugin>/skills/cekura-<kebab-name>/SKILL.md` with spec-compliant frontmatter (`name` must be `cekura-<kebab-name>`, matching the directory)
3. Body must be public-facing — no `mcp__cekura__*` references, no internal endpoints
4. Stay under 500 lines per file
5. Bump `package.json` version
6. Update the "What's Included" table and Quick Reference table in `README.md`
7. If the skill needs an operational counterpart, also add a slash command in `plugins/<plugin>/commands/`
8. In the release notes / commit message, name the new skill so users know what to pass to `--skill`

## MCP Integration

All three plugins use the Cekura MCP server as the **primary** API access path. Each plugin has a `.mcp.json` that auto-configures the `cekura-api` MCP server at `http://localhost:8001/mcp`.

MCP is the default. If MCP tools aren't available, users run `/setup-mcp` to configure the server.

When writing or updating skills/commands:
- Reference MCP tools by name (e.g., `mcp__cekura__metrics_create`)
- Use the standard API Access section format (see any SKILL.md for the pattern)
- Include `mcp__cekura__*` tool names in command `allowed-tools` frontmatter

### Known MCP Limitations

Two MCP endpoints have issues that require `curl` workarounds:

1. **`mcp__cekura__aiagents_create` — 414 URI Too Long on large payloads.** The MCP server encodes params as URL query strings, not JSON bodies. Agent descriptions (10-60KB) exceed nginx's URI limit. **Workaround:** Use `curl -X POST` with a JSON body for any agent creation with a description longer than ~4KB.

2. **`mcp__cekura__aiagents_tools_create` — Not exposed by MCP.** The tool search doesn't return this endpoint. **Workaround:** Use `curl -X POST` to `https://api.cekura.ai/test_framework/v1/aiagents/{id}/tools/`.

Both workarounds use `$CEKURA_API_KEY` in the `X-CEKURA-API-KEY` header. See the create-agent skill's "Known MCP Limitations & Curl Workarounds" section for full curl examples. Skills that hit these endpoints should include `Bash` in their `allowed-tools` frontmatter.

## Plugin Overview

### cekura (core)
| Component | Type | Purpose |
|-----------|------|---------|
| `cekura-onboarding` | skill | Walk new users through full platform setup |
| `cekura-create-agent` | skill | Set up a voice AI agent — provider, mock tools, KB, dynamic vars |
| `cekura-coordinator` | skill | Route users to the right skill/command |
| `setup-mcp` | command | Configure the MCP server for all plugins |
| `upgrade-skills` | command | Pull latest from GitHub |
| `report-bug` | command | Collect bug context, file GitHub issue, optionally attempt fix |
| MCP failure hook | hook | Auto-detects `mcp__cekura__*` failures, logs them, suggests `/report-bug` |

### cekura-metrics
| Component | Type | Purpose |
|-----------|------|---------|
| `cekura-metric-design` | skill | Core metric design patterns and best practices |
| `cekura-metric-improvement` | skill | Metric improvement through feedback iteration (formerly `labs-workflow`) |
| `cekura-predefined-metrics` | skill | Catalog of all predefined metrics — what each does, costs, constraints, configuration |
| `create-metric` | command | Create or update a metric (absorbed `update-metric`) |
| `list-metrics` | command | List metrics for an agent or project |
| `evaluate-calls` | command | Run metrics on specific calls |
| `improve-metric` | command | Full improvement cycle: feedback, labs, auto-improve (absorbed `leave-feedback`, `add-to-labs`) |
| `metric-reviewer` | agent | Reviews metric quality |

### cekura-evals
| Component | Type | Purpose |
|-----------|------|---------|
| `cekura-eval-design` | skill | Evaluator design, test profiles, conditional actions, session memory |
| `manual-create-update-eval` | command | Create or update a single evaluator with full field walkthrough (replaced `create-eval`) |
| `autogen-eval` | command | Auto-generate evaluators or bulk create from CSV/JSON (replaced `generate-evals` + `bulk-create-evals`) |
| `list-evals` | command | List evaluators for an agent or project |
| `run-evals` | command | Execute evaluators (run test scenarios) |
| `eval-results` | command | Check results from a test run |
| `eval-suite-planner` | agent | Coverage matrix design from agent descriptions |

## AGENTS.md (Codex/Cursor)

`codex/AGENTS.md` is a single-file distillation of all three plugins' domain knowledge — metric design, eval design, anti-patterns, and API reference. It's designed for agents that don't support the Claude Code plugin system (Codex, Cursor, Windsurf, etc.).

When updating skills, keep AGENTS.md in sync with major changes (new patterns, API changes, new anti-patterns). It doesn't need every detail — just the core guidance that makes a meaningful difference in output quality.

## Conventions

- **Skill versions** follow semver in the SKILL.md frontmatter. Bump minor for new sections/patterns, patch for fixes.
- **Plugin versions** are in `.claude-plugin/plugin.json`. Bump when adding new skills/commands.
- **Marketplace version** is in `.claude-plugin/marketplace.json` at the repo root. Bump when adding new plugins.
- **Command frontmatter** must include `allowed-tools` listing the specific `mcp__cekura__*` tools the command needs.
- **Skills** should have a `## API Access — Cekura MCP Server` section with prerequisites, tool table, docs lookup, and troubleshooting.

## Bug Reporting & Auto-Fix

### How It Works

Two mechanisms for catching issues:

1. **Hook (`PostToolUseFailure`)** — The cekura plugin registers a hook on all `mcp__cekura__*` tool failures. When any MCP tool fails, the hook:
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
plugins/cekura/
  hooks/
    hooks.json           # Hook registration (PostToolUseFailure → mcp__cekura__.*)
    on-mcp-failure.sh    # Logs failure, returns additionalContext to Claude
```

The hook uses `$PLUGIN_DIR/hooks/on-mcp-failure.sh` as the command path. It reads JSON from stdin (tool name, error, session ID), writes to the log, and returns a JSON response with `additionalContext` that Claude sees as a system message.

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
