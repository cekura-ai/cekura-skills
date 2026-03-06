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

## Quick Start

```bash
git clone https://github.com/cekura-ai/claude-skills.git
cd claude-skills
./setup.sh
```

This clones the repo and installs both plugins into Claude Code.

## Manual Installation

If you prefer to install plugins individually:

```bash
git clone https://github.com/cekura-ai/claude-skills.git
claude install-plugin ./claude-skills/cekura-metrics
claude install-plugin ./claude-skills/cekura-evals
```

## Prerequisites

- **Claude Code** — [Install Claude Code](https://docs.claude.com/en/docs/claude-code/overview) if you haven't already
- **Cekura API key** — Set `CEKURA_API_KEY` environment variable
- **Cekura MCP server** (optional, recommended) — Provides 84+ structured API tools. Plugins fall back to bash scripts when MCP is not available.

## MCP Server Setup (Optional)

For the best experience, connect the Cekura MCP server to get structured API access:

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

## Compatibility

These plugins are built for **Claude Code** using its plugin system (skills, commands, agents). They are not directly compatible with other coding agents (Codex, Cursor, etc.) since those use different plugin/extension architectures.

However, the knowledge content (skill files, reference docs, examples) is plain markdown and can be adapted for use with other tools — the domain expertise is transferable even if the plugin wiring is Claude Code-specific.
