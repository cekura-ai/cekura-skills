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

```bash
# Install both plugins
claude install-plugin /path/to/claude-skills/cekura-metrics
claude install-plugin /path/to/claude-skills/cekura-evals
```

Or copy the plugin directories into your project's `.claude-plugin/` folder.

## Prerequisites

- **Cekura API key** — Set `CEKURA_API_KEY` environment variable
- **Cekura MCP server** (optional, recommended) — Provides 84+ structured API tools. Plugins fall back to bash scripts when MCP is not available.

## MCP Server Setup (Optional)

```bash
claude mcp add cekura-api http://localhost:8000/mcp --transport http --header "X-CEKURA-API-KEY:$CEKURA_API_KEY"
```

## How It Works

These plugins don't just provide CRUD commands — they encode best practices learned from real client deployments to guide users from v0 metrics/evals to production-quality v9s through iterative improvement:

1. **Proactive guardrails** — Prevents common mistakes (hardcoded identity data, missing tools, wrong metric types) before they happen
2. **Real transcript grounding** — Always fetches and studies actual call data before writing metrics
3. **Labs improvement loop** — Structured feedback → auto-improve → validate → deploy cycle for metrics
4. **Coverage planning** — Agent for analyzing agent descriptions and designing comprehensive test suites
5. **Anti-pattern detection** — Warns about issues like missing baseline metrics, overly specific expected outcomes, and instruction vs personality confusion
