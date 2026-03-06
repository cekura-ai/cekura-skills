# Cekura Claude Code Plugins

Claude Code plugins that encode domain expertise for building and improving AI voice agent tests and metrics on the [Cekura](https://cekura.ai) platform.

## Plugins

### cekura-metrics

Create, improve, and validate metrics for AI voice agent call quality evaluation.

**Skills:** `metric-design`, `labs-workflow`
**Commands:** `create-metric`, `list-metrics`, `update-metric`, `delete-metric`, `generate-trigger`, `bulk-create-metrics`, `evaluate-calls`, `leave-feedback`, `add-to-labs`, `improve-metric`
**Agents:** `metric-reviewer`

### cekura-evals

Create, run, and analyze test suites (evaluators/scenarios) for AI voice agent testing.

**Skills:** `eval-design`
**Commands:** `create-eval`, `list-evals`, `delete-eval`, `generate-evals`, `create-eval-from-transcript`, `bulk-create-evals`, `run-evals`, `eval-results`, `list-personalities`
**Agents:** `eval-suite-planner`

## Installation

This repo is a Claude Code **marketplace**. Add it once, then install the plugins.

### VSCode (Claude Code extension)

1. Open the Claude Code chat panel
2. Click **Manage Plugins** → **Marketplaces** tab
3. Paste `https://github.com/cekura-ai/claude-skills.git` in the input and click **Add**
4. Switch to the **Plugins** tab and install `cekura-metrics` and `cekura-evals`

### Terminal CLI

```
/plugins add marketplace https://github.com/cekura-ai/claude-skills.git
/plugins install cekura-metrics
/plugins install cekura-evals
```

Both plugins are now available in all your Claude Code sessions.

## Prerequisites

- **Claude Code** — [Install Claude Code](https://code.claude.com/docs/en/overview) if you haven't already
- **Cekura API key** — Set `CEKURA_API_KEY` environment variable

## MCP Server Setup (Optional)

For the best experience, connect the Cekura MCP server to get structured API access with 84+ tools:

```bash
claude mcp add cekura-api http://localhost:8000/mcp --transport http --header "X-CEKURA-API-KEY:$CEKURA_API_KEY"
```

Without MCP, all commands use bash/curl helpers as a fallback — everything still works.

## How It Works

These plugins don't just provide CRUD commands — they encode best practices learned from real client deployments to guide users from v0 metrics/evals to production-quality v9s through iterative improvement:

1. **Proactive guardrails** — Prevents common mistakes (hardcoded identity data, missing tools, wrong metric types) before they happen
2. **Real transcript grounding** — Always fetches and studies actual call data before writing metrics
3. **Labs improvement loop** — Structured feedback → auto-improve → validate → deploy cycle for metrics
4. **Coverage planning** — Agent for analyzing agent descriptions and designing comprehensive test suites
5. **Anti-pattern detection** — Warns about issues like missing baseline metrics, overly specific expected outcomes, and instruction vs personality confusion

## Codex / Other Agents

A Codex-compatible version is available in [`codex/AGENTS.md`](codex/AGENTS.md). Copy it into your repo root to give Codex (or any agent that reads `AGENTS.md`) the same domain expertise:

```bash
cp codex/AGENTS.md ./AGENTS.md
```

## Compatibility

| Agent | How to Use |
|-------|-----------|
| **Claude Code (VSCode)** | Manage Plugins → Marketplaces → Add `https://github.com/cekura-ai/claude-skills.git` → install plugins |
| **Claude Code (CLI)** | `/plugins add marketplace https://github.com/cekura-ai/claude-skills.git` then `/plugins install cekura-metrics` |
| **Codex** | Copy `codex/AGENTS.md` to repo root |
| **Cursor / Other** | Copy `codex/AGENTS.md` to repo root or equivalent rules file |
