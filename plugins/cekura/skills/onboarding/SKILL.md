---
name: Cekura Onboarding
description: >
  This skill should be used when the user says "get started with Cekura", "set up Cekura",
  "onboard to Cekura", "I'm new to Cekura", "help me set up my agent", "how do I use Cekura",
  "walk me through Cekura", "configure my project", "first time using Cekura",
  or needs guidance on initial platform setup, agent configuration, provider integration,
  first evaluators, or first metrics. Also relevant when a user has just installed the
  cekura-skills marketplace and needs to understand what's available.
version: 0.2.0
---

# Cekura Platform Onboarding

## Purpose

Walk a new user through the complete Cekura setup — from account creation to their first successful test run. This is an interactive, step-by-step guide. At each phase, confirm with the user before proceeding and help them with the actual API calls or UI steps.

## How to Use This Skill

This is an **interactive walkthrough**, not a reference doc. Guide the user through each phase conversationally:

1. Ask where they are in the process (some may already have an account/agent)
2. Skip phases they've already completed
3. Use the Cekura MCP tools or API to perform actions on their behalf
4. Validate each step before moving to the next
5. Hand off to specialized skills (metric-design, eval-design) when appropriate

## Phase 1: Account & Project Setup

### 1.1 Verify Account Access

Ask the user:
- "Do you already have a Cekura account?"
- "Do you have an API key?"

If they have an API key, verify it works by calling `mcp__cekura__metrics_list`. A successful response (even empty) confirms the key is valid.

If they don't have an account, direct them to sign up at https://app.cekura.ai and create a project.

**If MCP tools aren't available:** Run `/setup-mcp` first to configure the MCP server.

### 1.2 Project Setup

Ask: "Do you already have a project, or do we need to create one?"

**If creating:** Use `mcp__cekura__projects_create` or guide them through the UI.

**Project organization guidance:**
- Small teams: single project for multiple agents
- Enterprises: separate projects by team and environment (staging vs production)
- Each project gets its own metrics, evaluators, and observability data

## Phase 2: Agent Configuration

### 2.1 Create or Connect an Agent

Ask: "Do you already have a voice AI agent deployed? What provider (VAPI, Retell, LiveKit, ElevenLabs, custom)?"

**If they have an agent:** Get the agent details and create it on Cekura using `mcp__cekura__aiagents_create` with the agent name, project ID, and description.

For detailed agent setup (provider integration, mock tools, KB, dynamic variables), hand off to the **create-agent** skill: "Let's use `/create-agent` to configure your agent with all the details."

**Critical: Agent description is essential.** It enables automatic evaluator generation and powers metrics that reference `{{agent.description}}`. Ask the user to paste their agent's full system prompt.

### 2.2 Provider Integration

Based on their provider, guide them through connecting:

**VAPI:**
- Need: VAPI API Key + Assistant ID
- In Cekura: Agent Settings → Provider → VAPI → enter credentials

**Retell:**
- Need: Retell API Key + Assistant ID
- In Cekura: Agent Settings → Provider → Retell → enter credentials
- Optionally enable auto-sync of prompts (every 30s)

**LiveKit:**
- Need: LiveKit agent deployment details
- Calls include `metadata.raw_metrics` for latency tracking

**Other (SIP, custom WebSocket, chat):**
- Guide based on their specific setup
- Refer to https://docs.cekura.ai/documentation/integrations/ for provider-specific docs

### 2.3 Dynamic Variables (if applicable)

Ask: "Does your agent use dynamic variables — per-call data like customer names, account IDs, or configuration flags?"

If yes:
- Cekura auto-detects `{{variableName}}` patterns in the agent description
- These become available in metrics as `{{dynamic_variables.keyName}}`
- Useful for multi-agent flows where each node has its own system prompt

### 2.4 Mock Tools (if applicable)

Ask: "Does your agent call external APIs or tools during calls?"

If yes:
- Auto-fetch from provider (recommended): Cekura pulls tool definitions automatically
- Manual setup: Add tool names, descriptions, and input/output mappings
- Mock tools let you test without hitting real backends
- See eval-design skill for detailed mock tool configuration

## Phase 3: Metrics Setup

### 3.1 Enable Pre-defined Metrics

**Always recommend selecting ALL pre-defined metrics** for comprehensive analysis:

| Category | Metrics |
|----------|---------|
| Accuracy | Expected Outcome, Hallucination, Relevancy, Response Consistency, Tool Call Success, Transcription Accuracy, Voicemail Detection |
| Quality | Interruption counts, Response latency, Silence detection, Call termination appropriateness |
| Customer Experience | CSAT, Sentiment, Dropoff nodes, Topic categorization |
| Speech Quality | Pitch, Speaking rate, Gibberish detection, Pronunciation verification |

Guide: "Go to your project's Metrics section and enable all pre-defined metrics. This gives you a comprehensive baseline."

**Two-step activation:** Metrics must be (1) toggled on at the project level AND (2) attached to individual evaluators.

### 3.2 Custom Metrics (optional, defer to later)

For first-time users, skip custom metrics initially. Once they have test results, they can use the **metric-design** skill to create targeted custom metrics.

Mention: "After your first test runs, we can create custom metrics tailored to your specific workflows. The `/metric-design` skill handles that."

## Phase 4: First Evaluators

### 4.1 Auto-Generate Evaluators (Recommended)

The fastest path to first tests — use `mcp__cekura__scenarios_generate_bg_create`:

```json
{
  "agent_id": <agent_id>,
  "num_scenarios": 10,
  "personalities": [693],
  "generate_expected_outcomes": true,
  "tool_ids": ["TOOL_END_CALL", "TOOL_END_CALL_ON_TRANSFER"]
}
```

Poll progress with `mcp__cekura__scenarios_generate_progress_retrieve`, then review the generated scenarios.

**After generation, check:**
- Are instructions specific and behavioral?
- Are expected outcomes concise and achievable?
- Are the right tools enabled?
- For non-English agents: PATCH `scenario_language` to correct code

### 4.2 Review and Supplement

Common gaps in auto-generated evals:
- Red-team / adversarial scenarios
- Edge cases specific to the client's domain
- Multi-language coverage
- Tool failure scenarios

Mention: "The `/eval-design` skill can help you design more targeted evaluators once you see what the auto-generator produces."

### 4.3 Attach Metrics

Every evaluator needs metrics attached. At minimum:
- **Expected Outcome** — Did the agent achieve the scenario's goal?
- **Infrastructure Issues** — Connection drops, silence, non-response

Use bulk-add via `actions → modify scenarios` in the UI.

## Phase 5: First Test Run

### 5.1 Execute

Use `mcp__cekura__scenarios_run_scenarios_create` with the agent ID and scenario IDs:

```json
{
  "agent_id": <agent_id>,
  "scenarios": [<scenario_ids>],
  "frequency": 1
}
```

**Start with 5-10 scenarios** for the first run. Voice calls take 1-3 minutes each.

### 5.2 Monitor

Check results with `mcp__cekura__results_list`. Each run includes:
- Full transcript
- Audio recording
- Metric scores
- Expected outcome pass/fail

### 5.3 Review Results

Guide the user through interpreting results:
- **70-80% pass rate** is realistic for a first iteration
- Review failures to identify: misunderstandings, missing info, technical issues
- **90-95%** after refinement is the target
- Don't aim for 100% — real conversations are unpredictable

## Phase 6: What's Next

After first successful test run, point the user to:

| Need | Skill/Command | Description |
|------|--------------|-------------|
| Better metrics | `/metric-design` | Design custom metrics for specific workflows |
| More evaluators | `/eval-design` | Design targeted test scenarios |
| Improve metrics | `/labs-workflow` | Iterate metric quality through feedback |
| Production monitoring | Observability setup | Monitor real calls in production |
| CI/CD integration | GitHub Actions | Auto-test on code changes |
| Scheduled tests | Cron jobs | Recurring test suites |

## API Access — Cekura MCP Server

This plugin uses the Cekura MCP server for all API operations. The `.mcp.json` file in this plugin configures it automatically.

**Prerequisites:**
1. Set the `CEKURA_API_KEY` environment variable with your Cekura API key
2. Start the Cekura MCP server: `cd /path/to/cekura-mcp-server && python3 openapi_mcp_server.py` (runs on `http://localhost:8001/mcp`)
3. The plugin's `.mcp.json` handles the rest — Claude Code connects to the server and makes the `mcp__cekura__*` tools available

**Key MCP tools used during onboarding:**
| Operation | MCP Tool |
|-----------|----------|
| List/create projects | `mcp__cekura__projects_list`, `mcp__cekura__projects_create` |
| Create/get agents | `mcp__cekura__aiagents_create`, `mcp__cekura__aiagents_retrieve`, `mcp__cekura__aiagents_list` |
| Update agent | `mcp__cekura__aiagents_partial_update` |
| Metrics | `mcp__cekura__metrics_list`, `mcp__cekura__metrics_create` |
| Generate scenarios | `mcp__cekura__scenarios_generate_bg_create`, `mcp__cekura__scenarios_generate_progress_retrieve` |
| Run scenarios | `mcp__cekura__scenarios_run_scenarios_create` |
| Results | `mcp__cekura__results_list`, `mcp__cekura__results_retrieve` |
| Personalities | `mcp__cekura__personalities_list` |

**Docs lookup:** Use the `mcp__cekura__search_cekura` tool or fetch `https://docs.cekura.ai/llms.txt` to look up API details, field schemas, or feature documentation when the plugin references don't cover something.

**Troubleshooting:** If MCP tools are not available, verify: (1) `CEKURA_API_KEY` is set, (2) the MCP server is running on port 8001, (3) restart Claude Code to pick up the `.mcp.json` config. Run `/setup-mcp` for guided setup.

See `references/api-quickstart.md` for the essential endpoints used during onboarding.
