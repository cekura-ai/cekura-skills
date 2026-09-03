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

### Skills

| Skill | Use when |
|-------|----------|
| `cekura-onboarding` | New to Cekura, first-time setup, platform walkthrough |
| `cekura-create-agent` | Set up a voice AI agent — provider, mock tools, KB, dynamic vars |
| `cekura-self-improving-agent` | Auto-tune agent prompts from eval results — diagnose → propose → apply → re-validate |
| `cekura-metric-design` | Design new metrics, improve existing ones, metric best practices |
| `cekura-metric-improvement` | Improve metric accuracy through feedback cycle (labs workflow) |
| `cekura-predefined-metrics` | Catalog of built-in metrics — what each does, costs, constraints, configuration |
| `cekura-eval-design` | Design evaluators, test suites, coverage strategy, conditional actions |
| `cekura-infra-test-suite` | Source-controlled JSON Tests-as-Code suite — repository discovery, deterministic CI coverage, safe dry-run validation |
| `cekura-flag-call-log-failures` | Triage recent production call logs against KPIs — failure rates + outcome distribution |
| `cekura-generate-scenarios` | Turn flagged production failures into regression evaluator scenarios |

### Commands

| Command | Use when |
|---------|----------|
| `/cekura-onboarding` | Run the guided onboarding flow (state-aware, picks up where you left off) |
| `/setup-mcp` | Configure the Cekura MCP server (Claude Code only) |
| `/upgrade-skills` | Update all Cekura skills to the latest version |
| `/report-bug` | Report a bug — files a GitHub issue, optionally attempts a fix |
| `/create-metric` | Create or update a metric via API |
| `/list-metrics` | List metrics for an agent or project |
| `/evaluate-calls` | Run metrics on specific calls |
| `/improve-metric` | Full improvement cycle: collect feedback, run labs, auto-improve |
| `/manual-create-update-eval` | Create or update a single evaluator with full field walkthrough |
| `/autogen-eval` | Auto-generate evaluators (or bulk create from CSV/JSON) |
| `/list-evals` | List evaluators for an agent or project |
| `/run-evals` | Execute evaluators (run test scenarios) |
| `/eval-results` | Check results from a test run |
| `/cekura-report` | Full end-to-end quality report — generates 10 evals, runs them, produces structured analysis |

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
| "Generate test scenarios" / any batch or category-level request, either format | **cekura-eval-design** skill (`/autogen-eval` for the walkthrough where slash commands exist) |
| "Create a specific test scenario" — scripted / deterministic / regression / IVR / DTMF / compliance flow | **cekura-eval-design** skill (conditional actions: generated for a category, created directly for a dictated script), `/manual-create-update-eval` for the field walkthrough where slash commands exist |
| "Create a specific test scenario" — natural conversation, edge case, red-team | **cekura-eval-design** skill: generate (`num_scenarios: 1`) for a category-level ask, create directly for a fully described case |
| "Update / duplicate an existing scenario" | **cekura-eval-design** skill (§ Changing existing evaluators), `/manual-create-update-eval` for the walkthrough where slash commands exist |
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
| "Add mock tools" / "set up tools" — defining the tools on the agent | **cekura-create-agent** skill (Phase 7) |
| "Mock tool data for a test" / "add a mock entry" / "create the test profile" — data an evaluator will use | **cekura-eval-design** skill (§ Test data) |
| "Upload knowledge base" | **cekura-create-agent** skill (Phase 8) |
| "Something's broken" / "file a bug" | `/report-bug` command |
| "Improve my agent" / "auto-tune from eval results" | **cekura-self-improving-agent** skill |
| "Which built-in metrics are available?" / "what does Hallucination Detection cost?" | **cekura-predefined-metrics** skill |
| "Fix this prod call bug" / "reproduce and test a fix" | **cekura-self-improving-agent** |
| "CI/CD tests for my voice bot" / "commit a JSON test suite" / "Tests-as-Code for my voice repo" / "update CI eval coverage for this PR" | **cekura-infra-test-suite** skill |
| "What % of calls have <problem>" / "analyze my recent calls" | **cekura-flag-call-log-failures** skill |
| "Create scenarios from failed calls" / "replay prod failures as tests" | **cekura-generate-scenarios** skill |
| "Run a full quality report" / "generate evals and run them end-to-end" | `/cekura-report` command |

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

## Next Steps

This skill routes — it doesn't perform tasks itself. After confirming the user's need, **invoke the matching skill**:

- New to Cekura → **cekura-onboarding**
- Connecting an agent → **cekura-create-agent**
- Auto-tuning an agent prompt from eval results → **cekura-self-improving-agent**
- Designing metrics → **cekura-metric-design**
- Improving metric accuracy → **cekura-metric-improvement**
- Picking which built-in metrics to use → **cekura-predefined-metrics**
- Designing test scenarios → **cekura-eval-design**
- Fixing a production call bug end-to-end → **cekura-self-improving-agent**
- Repository-owned JSON CI/CD test suite → **cekura-infra-test-suite**
- Triaging production call logs → **cekura-flag-call-log-failures**
- Turning prod failures into scenarios → **cekura-generate-scenarios**

## Documentation

- Full API docs: https://docs.cekura.ai/api-reference
- LLM-friendly index: https://docs.cekura.ai/llms.txt
- Concepts: https://docs.cekura.ai/documentation/key-concepts/
