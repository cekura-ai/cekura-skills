---
name: Cekura Coordinator
description: >
  This skill should be used when the user asks "what can Cekura do", "what commands are available",
  "help me with Cekura", "what skills do I have", "show me Cekura features",
  "what's available", "how do I use the Cekura plugins", "list Cekura commands",
  or needs guidance on which Cekura skill or command to use for their task.
  Also relevant as the entry point when a user has just installed the cekura-skills
  marketplace for the first time.
version: 0.2.0
---

# Cekura Coordinator

## Purpose

Route users to the right Cekura skill or command based on what they need. This is the "front desk" — it knows everything available across all Cekura plugins and helps users find the right tool.

## When This Skill Loads

- User just installed cekura-skills and asks "what can I do?"
- User asks for help or doesn't know which command to use
- User describes a task and you need to route them

## Available Plugins & Skills

### cekura (this plugin)
Core platform utilities and agent onboarding.

| Component | Type | Trigger |
|-----------|------|---------|
| `/onboarding` | skill | New to Cekura, first-time setup, platform walkthrough |
| `/create-agent` | skill | Set up a voice AI agent on Cekura — provider, mock tools, KB, dynamic vars |
| `/setup-mcp` | command | Configure the Cekura MCP server for all plugins |
| `/upgrade-skills` | command | Update all Cekura skills to latest version |
| `/report-bug` | command | Report a bug — files GitHub issue, optionally attempts fix |

### cekura-metrics
Create, improve, and validate metrics for call quality evaluation.

| Component | Type | Trigger |
|-----------|------|---------|
| `/metric-design` | skill | Design new metrics, improve existing ones, metric best practices |
| `/labs-workflow` | skill | Improve metric accuracy through feedback cycle |
| `/create-metric` | command | Create or update a metric via API |
| `/list-metrics` | command | List metrics for an agent or project |
| `/evaluate-calls` | command | Run metrics on specific calls |
| `/improve-metric` | command | Full improvement cycle: collect feedback, run labs, auto-improve |

### cekura-evals
Create, run, and analyze test suites for voice agent testing.

| Component | Type | Trigger |
|-----------|------|---------|
| `/eval-design` | skill | Design evaluators, test suites, coverage strategy |
| `/manual-create-update-eval` | command | Create or update a single evaluator with full field walkthrough |
| `/autogen-eval` | command | Auto-generate evaluators (or bulk create from CSV/JSON) |
| `/list-evals` | command | List evaluators for an agent or project |
| `/run-evals` | command | Execute evaluators (run test scenarios) |
| `/eval-results` | command | Check results from a test run |

## Routing Guide

When the user describes what they need, route them:

| User Need | Route To |
|-----------|----------|
| "I'm new to Cekura" / first-time setup | **onboarding** skill |
| "Set up my agent" / "connect my voice agent" | **create-agent** skill |
| "Configure MCP" / "MCP not working" | `/setup-mcp` command |
| "Create metrics for my agent" | **metric-design** skill |
| "My metrics are giving wrong results" | `/improve-metric` command (or **labs-workflow** skill for full cycle) |
| "I need to test my agent" | **eval-design** skill |
| "Generate test scenarios" | `/autogen-eval` command |
| "Create a specific test scenario" | `/manual-create-update-eval` command |
| "Run my tests" | `/run-evals` command |
| "Check test results" | `/eval-results` command |
| "Create a metric that checks X" | `/create-metric` command (or **metric-design** skill for complex metrics) |
| "Update this metric" | `/create-metric` command (handles both create and update) |
| "Evaluate calls against metrics" | `/evaluate-calls` command |
| "Update my skills" | `/upgrade-skills` command |
| "What metrics should I have?" | **metric-design** skill (baseline metrics section) |
| "Help me improve this metric" | `/improve-metric` command |
| "Leave feedback on a metric result" | `/improve-metric` command (Phase 1: feedback collection) |
| "Set up production monitoring" | **onboarding** skill (Phase 6) + observability docs |
| "Add mock tools" / "set up tools" | **create-agent** skill (Phase 4) |
| "Upload knowledge base" | **create-agent** skill (Phase 5) |
| "Something's broken" / "file a bug" | `/report-bug` command |

## Typical User Journeys

### Journey 1: Brand New User
1. `/setup-mcp` → Configure MCP server for API access
2. **onboarding** → Set up account and project
3. **create-agent** → Add agent with provider, mock tools, KB, dynamic vars
4. **onboarding** → Enable pre-defined metrics, generate first evaluators
5. **onboarding** → Run first tests, review results
6. **metric-design** → Create custom metrics based on what they learned
7. **eval-design** → Build targeted test suites

### Journey 2: Has Agent, Needs Testing
1. **eval-design** → Design test suite
2. `/autogen-eval` → Auto-generate evaluators
3. `/run-evals` → Execute tests
4. `/eval-results` → Review results

### Journey 3: Has Metrics, Needs Improvement
1. `/improve-metric` → Full cycle: collect feedback, check readiness, auto-improve
2. `/evaluate-calls` → Validate changes

### Journey 4: Production Monitoring
1. **metric-design** → Design observability metrics
2. `/create-metric` → Deploy metrics (create or update)
3. `/evaluate-calls` → Validate on sample calls

## MCP Server

All Cekura plugins use the Cekura MCP server for API operations. Each plugin has a `.mcp.json` file that configures it automatically.

If MCP tools (`mcp__cekura__*`) are not available, run `/setup-mcp` to configure the server.

**Quick check:** Try calling any `mcp__cekura__*` tool (e.g., `mcp__cekura__list_available_tools`). If it responds, MCP is working.

## Documentation

- Full API docs: https://docs.cekura.ai/api-reference
- LLM-friendly index: https://docs.cekura.ai/llms.txt
- Concepts: https://docs.cekura.ai/documentation/key-concepts/
