---
name: cekura-onboarding
description: >
  Use when the user says "get started with Cekura", "set up Cekura", "onboard to Cekura",
  "I'm new to Cekura", "help me set up my agent", "how do I use Cekura",
  "walk me through Cekura", "configure my project", "first time using Cekura",
  or needs guidance on initial platform setup, agent configuration, provider
  integration, first evaluators, or first metrics.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.3.0"
---

# Cekura Platform Onboarding

## Purpose

Walk a new user through the complete Cekura setup — from account creation to their first successful test run. This is an interactive, step-by-step guide. At each phase, confirm with the user before proceeding and help them with the actual API calls or UI steps.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

## How to Use This Skill

This is an **interactive walkthrough**, not a reference doc. Guide the user through each phase conversationally:

1. Ask where they are in the process (some may already have an account/agent)
2. Skip phases they've already completed
3. Use the Cekura API or dashboard to perform actions on their behalf
4. Validate each step before moving to the next
5. Hand off to specialized skills (cekura-metric-design, cekura-eval-design) when appropriate

## Phase 1: Account & Project Setup

### 1.1 Verify Account Access

Ask the user:
- "Do you already have a Cekura account?"
- "Do you have an API key, or do you sign in via OAuth?"

If they have an API key, verify it works by calling the metrics list endpoint. A successful response (even empty) confirms the key is valid.

If they don't have an account, direct them to sign up at https://dashboard.cekura.ai/sign-up and create a project.

**For Claude Code plugin users:** If platform operations aren't working, run `/setup-mcp` to configure API access.

### 1.2 Project Setup

Ask: "Do you already have a project, or do we need to create one?"

**If creating:** Create the project via the Cekura dashboard or projects API.

**Project organization guidance:**
- Small teams: single project for multiple agents
- Enterprises: separate projects by team and environment (staging vs production)
- Each project gets its own metrics, evaluators, and observability data

## Phase 2: Agent Configuration

### 2.1 Create or Connect an Agent

Ask: "Do you already have a voice AI agent deployed? What provider (VAPI, Retell, LiveKit, ElevenLabs, custom)?"

**If they have an agent:** Get the agent details and create it on Cekura with the agent name, project ID, and description.

For detailed agent setup (provider integration, mock tools, KB, dynamic variables), hand off to the **cekura-create-agent** skill.

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

**Self-hosted / Custom (reached via SIP, WebSocket, or chat):**
- These are `assistant_provider: "self_hosted"` agents — SIP / WebSocket / chat are *connection modes*, not providers.
- Guide based on their specific setup.
- Refer to https://docs.cekura.ai/documentation/integrations/ for provider-specific docs.

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
- See cekura-eval-design skill for detailed mock tool configuration

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

For first-time users, skip custom metrics initially. Once they have test results, they can use the **cekura-metric-design** skill to create targeted custom metrics.

## Phase 4: First Evaluators

### 4.1 Auto-Generate Evaluators (Recommended)

The fastest path to first tests — use the scenario auto-generation endpoint:

```json
{
  "agent_id": <agent_id>,
  "num_scenarios": 10,
  "personalities": [<personality_id>],
  "generate_expected_outcomes": true,
  "tool_ids": ["TOOL_END_CALL", "TOOL_END_CALL_ON_TRANSFER"]
}
```

Poll progress at `scenarios_generate_progress`, then review the generated scenarios.

**Polling cadence — important.** Between successive `*_progress` calls
(scenario generation, prompt improvement, evaluation, anything
returning a `progress_id`), pause briefly via `bash sleep 10` (or
`bash sleep 5` for fast jobs you expect to finish in seconds). Do NOT
tight-loop polling — every poll costs an LLM turn and the backend is
unchanged for ~10s between updates anyway.

After ~5 polls of the same job with no progress, surface the current
state to the user ("Still in progress — N of M done; you can also
track progress in the UI") and either pause OR perform one more
check. Don't poll indefinitely.

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

Hand off to the **cekura-eval-design** skill for designing more targeted evaluators.

### 4.3 Attach Metrics

Every evaluator needs metrics attached. At minimum:
- **Expected Outcome** — Did the agent achieve the scenario's goal?
- **Infrastructure Issues** — Connection drops, silence, non-response

Use bulk-add via `actions → modify scenarios` in the UI.

## Phase 5: First Test Run

### 5.1 Execute

Run the scenarios with the agent ID and scenario IDs:

```json
{
  "agent_id": <agent_id>,
  "scenarios": [<scenario_ids>],
  "frequency": 1
}
```

**Start with 5-10 scenarios** for the first run. Voice calls take 1-3 minutes each.

### 5.2 Monitor

Check results via the results endpoint. Each run includes:
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

## Linking to the Cekura UI

When you reference results, runs, agents, or any other resource the
user can open in the Cekura UI, use the host the runtime gives you in
the run context (`/app/.context.json` → `frontend_url`). Construct
links as `{frontend_url}/{project_id}/results/{result_set_id}` (or
the equivalent path for agents / scenarios).

**Never invent host names.** Do not write `app.cekura.ai`,
`dashboard.cekura.ai`, or any other guessed URL — those are likely
wrong (the actual host varies by environment: dev / stage / prod /
custom domain). If `frontend_url` is not in the context, OMIT the link
entirely — describe the resource in prose ("result set id `139120`")
and let the user open it via their normal UI navigation.

The agent runtime post-processes your reply and removes any
`cekura.ai` URL whose host doesn't match the configured frontend, so
hallucinated hosts won't reach the user — but you should still avoid
emitting them in the first place.

## Phase 6: What's Next

After first successful test run, point the user to:

| Need | Skill | Description |
|------|-------|-------------|
| Better metrics | **cekura-metric-design** | Design custom metrics for specific workflows |
| More evaluators | **cekura-eval-design** | Design targeted test scenarios |
| Improve metrics | **cekura-metric-improvement** | Iterate metric quality through feedback |
| Production monitoring | Observability setup | Monitor real calls in production |
| CI/CD integration | GitHub Actions | Auto-test on code changes |
| Scheduled tests | Cron jobs | Recurring test suites |

## Documentation

- Public docs: https://docs.cekura.ai
- LLM-friendly docs: https://docs.cekura.ai/llms.txt
- Concepts: https://docs.cekura.ai/documentation/key-concepts/
- Integrations: https://docs.cekura.ai/documentation/integrations/

See `references/api-quickstart.md` for the essential endpoints used during onboarding.
