---
name: create-metric
description: Create a new Cekura metric for evaluating voice AI agent calls
argument-hint: "[metric description or requirements]"
allowed-tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "AskUserQuestion", "WebFetch"]
---

# Create a Cekura Metric

Create a new metric on the Cekura platform following metric design best practices. The metric-design skill provides detailed guidance — load it for comprehensive patterns.

## Process

1. **Check baseline metrics first**: Before creating custom metrics, verify the agent has the baseline predefined metrics enabled:
   - **Expected Outcome** — checks if the agent achieved the scenario's expected result
   - **Infrastructure Issues** — flags silent periods, connection drops, agent non-response
   - **Tool Call Success** — monitors tool call success/failure
   - **Latency** — measures response time

   These require two-step activation: (1) toggled on at project level AND (2) added to evaluators. Without them, users get false passes.

2. **Understand the requirement**: Clarify what the user wants to measure. Determine:
   - What workflow or KPI does this metric track?
   - Which agent(s) will it apply to?
   - What eval type is appropriate (binary_qualitative, binary_workflow_adherence, enum, numeric)?
   - What trigger type (always, custom)?

3. **Identify the agent**: Ask for agent ID or project ID if not provided. Use the list-metrics command to check existing metrics and avoid duplication.

3. **Fetch real transcripts FIRST**: Before writing any prompt, pull 3-5 sample conversations and study the actual transcript_json structure. Understand what roles appear, what timestamps are available, how tool calls are structured, and what the conversation flow looks like.
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
list_calls "agent=AGENT_ID&limit=5"
get_call "CALL_ID"
```

4. **Design the metric prompt**: Follow the LLM judge prompt structure:
   - INPUTS section (only relevant template variables)
   - Evaluation criteria with pass/fail examples
   - Safeguarding instructions (spirit vs letter principle)
   - Output instructions with timestamp requirements
   - N/A conditions where appropriate

4. **Review with user**: Present the draft metric for approval before creating. Show the full prompt and field values.

5. **Create via API**: Use the Cekura API to create the metric.

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
create_metric '{"name": "METRIC_NAME", "description": "PROMPT", "type": "llm_judge", "eval_type": "EVAL_TYPE", "agent": AGENT_ID}'
```

6. **Verify**: Confirm creation was successful and show the metric ID.

## Common Custom Metrics Worth Suggesting

Beyond baseline metrics, these are commonly valuable:
- **Question stacking / information dumping** — Agent asking 3+ unrelated questions or dumping large blocks of info
- **Workflow adherence** — Agent follows the defined flow steps in order
- **Soft skills** — Tone, empathy, not exposing system internals
- **Business context accuracy** — Agent provides correct business info (hours, addresses, pricing)
- **Transfer/callback handling** — Agent follows proper protocol for transfers

## Key Reminders

- For `llm_judge` metrics: the evaluation prompt goes in the `description` field, NOT the `prompt` field
- Do NOT use deprecated types `basic` or `custom_prompt` — they return 400
- Capture the **spirit** of agent description rules, not the literal text
- Include safeguarding examples for nuanced criteria
- Always require explanations with MM:SS timestamps for failures
- Ask the user to clarify ambiguous agent description instructions before encoding them
- Prefer `llm_judge` over `custom_code` — voice AI transcripts have messy timing that LLMs handle naturally

## Environment

- API key: `CEKURA_API_KEY` env var or `.claude/cekura-metrics.local.md`
- Base URL: `https://api.cekura.ai`
- Endpoint: `POST /test_framework/v1/metrics/`
