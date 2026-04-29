---
name: cekura-coordinator
description: >
  Use when the user asks "what can Cekura do", "what commands are available",
  "help me with Cekura", "what skills do I have", "show me Cekura features",
  "what's available", "how do I use Cekura", or needs guidance on which Cekura
  skill to use for their task. Also relevant as the entry point when a user
  has just installed cekura-skills for the first time.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.3.0"
---

# Cekura Coordinator

## Purpose

Route users to the right Cekura skill or command based on what they need. This is the "front desk" — it knows everything available across all Cekura plugins and helps users find the right tool.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

## When This Skill Loads

- User just installed cekura-skills and asks "what can I do?"
- User asks for help or doesn't know which command to use
- User describes a task and you need to route them

## Available Skills & Commands

Skills activate when the user describes a relevant task. Commands are slash commands available only in Claude Code with the plugin installed.

### cekura plugin
Core platform utilities and agent onboarding.

| Component | Type | Use when |
|-----------|------|----------|
| `cekura-onboarding` | skill | New to Cekura, first-time setup, platform walkthrough |
| `cekura-create-agent` | skill | Set up a voice AI agent — provider, mock tools, KB, dynamic vars |
| `/setup-mcp` | command | Configure the Cekura MCP server (Claude Code only) |
| `/upgrade-skills` | command | Update all Cekura skills to latest version |
| `/report-bug` | command | Report a bug — files GitHub issue, optionally attempts fix |

### cekura-metrics plugin
Create, improve, and validate metrics for call quality evaluation.

| Component | Type | Use when |
|-----------|------|----------|
| `cekura-metric-design` | skill | Design new metrics, improve existing ones, metric best practices |
| `cekura-metric-improvement` | skill | Improve metric accuracy through feedback cycle (labs workflow) |
| `/create-metric` | command | Create or update a metric via API |
| `/list-metrics` | command | List metrics for an agent or project |
| `/evaluate-calls` | command | Run metrics on specific calls |
| `/improve-metric` | command | Full improvement cycle: collect feedback, run labs, auto-improve |

### cekura-evals plugin
Create, run, and analyze test suites for voice agent testing.

| Component | Type | Use when |
|-----------|------|----------|
| `cekura-eval-design` | skill | Design evaluators, test suites, coverage strategy |
| `/manual-create-update-eval` | command | Create or update a single evaluator with full field walkthrough |
| `/autogen-eval` | command | Auto-generate evaluators (or bulk create from CSV/JSON) |
| `/list-evals` | command | List evaluators for an agent or project |
| `/run-evals` | command | Execute evaluators (run test scenarios) |
| `/eval-results` | command | Check results from a test run |

## Routing Guide

When the user describes what they need, route them:

| User Need | Route To |
|-----------|----------|
| "I'm new to Cekura" / first-time setup | **cekura-onboarding** skill |
| "Set up my agent" / "connect my voice agent" | **cekura-create-agent** skill |
| "Configure MCP" / "MCP not working" | `/setup-mcp` command |
| "Create metrics for my agent" | **cekura-metric-design** skill |
| "My metrics are giving wrong results" | `/improve-metric` command (or **cekura-metric-improvement** skill for full cycle) |
| "I need to test my agent" | **cekura-eval-design** skill |
| "Generate test scenarios" | `/autogen-eval` command |
| "Create a specific test scenario" | `/manual-create-update-eval` command |
| "Run my tests" | `/run-evals` command |
| "Check test results" | `/eval-results` command |
| "Create a metric that checks X" | `/create-metric` command (or **cekura-metric-design** skill for complex metrics) |
| "Update this metric" | `/create-metric` command (handles both create and update) |
| "Evaluate calls against metrics" | `/evaluate-calls` command |
| "Update my skills" | `/upgrade-skills` command |
| "What metrics should I have?" | **cekura-metric-design** skill (baseline metrics section) |
| "Help me improve this metric" | `/improve-metric` command |
| "Leave feedback on a metric result" | `/improve-metric` command (Phase 1: feedback collection) |
| "Set up production monitoring" | **cekura-onboarding** skill (Phase 6) + observability docs |
| "Add mock tools" / "set up tools" | **cekura-create-agent** skill (Phase 4) |
| "Upload knowledge base" | **cekura-create-agent** skill (Phase 5) |
| "Something's broken" / "file a bug" | `/report-bug` command |

## Typical User Journeys

### Journey 1: Brand New User
1. `/setup-mcp` → Configure MCP server for API access (Claude Code plugin users)
2. **cekura-onboarding** → Set up account and project
3. **cekura-create-agent** → Add agent with provider, mock tools, KB, dynamic vars
4. **cekura-onboarding** → Enable pre-defined metrics, generate first evaluators
5. **cekura-onboarding** → Run first tests, review results
6. **cekura-metric-design** → Create custom metrics based on what they learned
7. **cekura-eval-design** → Build targeted test suites

### Journey 2: Has Agent, Needs Testing
1. **cekura-eval-design** → Design test suite
2. `/autogen-eval` → Auto-generate evaluators
3. `/run-evals` → Execute tests
4. `/eval-results` → Review results

### Journey 3: Has Metrics, Needs Improvement
1. `/improve-metric` → Full cycle: collect feedback, check readiness, auto-improve
2. `/evaluate-calls` → Validate changes

### Journey 4: Production Monitoring
1. **cekura-metric-design** → Design observability metrics
2. `/create-metric` → Deploy metrics (create or update)
3. `/evaluate-calls` → Validate on sample calls

## API Access

For Claude Code plugin users: each plugin auto-configures access to the Cekura API. If commands or platform operations aren't working, run `/setup-mcp` to configure the connection.

For other clients (Cursor, Codex, npx skills installs, etc.): use the Cekura dashboard at https://dashboard.cekura.ai or call the API directly using your API key.

## Documentation

- Full API docs: https://docs.cekura.ai/api-reference
- LLM-friendly index: https://docs.cekura.ai/llms.txt
- Concepts: https://docs.cekura.ai/documentation/key-concepts/
