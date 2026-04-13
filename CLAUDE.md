# Cekura Skills — Developer Guide

## Repository Structure

This is a Claude Code **marketplace** — a collection of plugins that encode domain expertise for the [Cekura](https://cekura.ai) voice AI testing and evaluation platform.

```
cekura-skills/
  plugins/
    cekura/              # Core plugin — onboarding, agent setup, coordination
    cekura-metrics/      # Metrics — create, improve, validate call quality metrics
    cekura-evals/        # Evaluators — create, run, analyze test suites
  codex/
    AGENTS.md            # Single-file behavior preset for Codex/Cursor/other agents
  README.md              # User-facing installation and platform setup guide
  CLAUDE.md              # This file — developer context for contributors
```

Each plugin follows the Claude Code plugin structure:
- `.claude-plugin/plugin.json` — Plugin manifest (name, version, description)
- `.mcp.json` — MCP server auto-configuration (connects to Cekura API)
- `skills/<name>/SKILL.md` — Design knowledge and interactive workflows
- `commands/<name>.md` — Slash commands for specific operations
- `agents/<name>.md` — Subagent definitions
- `references/` and `examples/` — Supporting docs within each skill

## MCP Integration

All three plugins use the Cekura MCP server as the **only** API access path. Each plugin has a `.mcp.json` that auto-configures the `cekura-api` MCP server at `http://localhost:8001/mcp`.

**There are no bash scripts or curl fallbacks.** If MCP tools aren't available, users run `/setup-mcp` to configure the server.

When writing or updating skills/commands:
- Reference MCP tools by name (e.g., `mcp__cekura__metrics_create`)
- Use the standard API Access section format (see any SKILL.md for the pattern)
- Never add bash/curl code blocks as "fallback" — MCP is the only path
- Include `mcp__cekura__*` tool names in command `allowed-tools` frontmatter

## Plugin Overview

### cekura (core)
| Component | Type | Purpose |
|-----------|------|---------|
| `onboarding` | skill | Walk new users through full platform setup |
| `create-agent` | skill | Set up a voice AI agent — provider, mock tools, KB, dynamic vars |
| `coordinator` | skill | Route users to the right skill/command |
| `setup-mcp` | command | Configure the MCP server for all plugins |
| `upgrade-skills` | command | Pull latest from GitHub |
| `report-bug` | command | Collect bug context, file GitHub issue, optionally attempt fix |
| MCP failure hook | hook | Auto-detects `mcp__cekura__*` failures, logs them, suggests `/report-bug` |

### cekura-metrics
| Component | Type | Purpose |
|-----------|------|---------|
| `metric-design` | skill | Core metric design patterns and best practices |
| `labs-workflow` | skill | Metric improvement through feedback iteration |
| `create-metric` | command | Create or update a metric (absorbed `update-metric`) |
| `list-metrics` | command | List metrics for an agent or project |
| `evaluate-calls` | command | Run metrics on specific calls |
| `improve-metric` | command | Full improvement cycle: feedback, labs, auto-improve (absorbed `leave-feedback`, `add-to-labs`) |
| `metric-reviewer` | agent | Reviews metric quality |

### cekura-evals
| Component | Type | Purpose |
|-----------|------|---------|
| `eval-design` | skill | Evaluator design, test profiles, conditional actions, session memory |
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
