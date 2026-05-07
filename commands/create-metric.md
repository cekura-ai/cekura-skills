---
name: create-metric
description: Create or update a Cekura metric for evaluating voice AI agent calls
argument-hint: "[metric description, requirements, or metric ID to update]"
allowed-tools: ["Read", "Write", "Edit", "Grep", "Glob", "AskUserQuestion", "WebFetch", "mcp__cekura__call_logs_list", "mcp__cekura__call_logs_retrieve", "mcp__cekura__metrics_create", "mcp__cekura__metrics_list", "mcp__cekura__metrics_retrieve", "mcp__cekura__metrics_partial_update", "mcp__cekura__aiagents_retrieve"]
---

# Create or Update a Cekura Metric

Create a new metric or update an existing one on the Cekura platform. The metric-design skill provides detailed guidance — load it for comprehensive patterns.

## Determine Mode: Create or Update

- **Create**: User says "create", "new", "add", or describes a metric to build
- **Update**: User provides a metric ID, says "update", "edit", "change", or wants to modify an existing metric

For **updates**: fetch the current metric with `mcp__cekura__metrics_retrieve` and show the user the current state (name, description/prompt, eval type, trigger config). Then ask what to change. Apply changes with `mcp__cekura__metrics_partial_update` — only send the fields being changed, not the full payload. After updating, fetch again to verify.

## Process (Create)

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
   Use `mcp__cekura__call_logs_list` to find recent calls, then `mcp__cekura__call_logs_retrieve` to read full transcripts.

4. **Design the metric prompt**: Follow the LLM judge prompt structure:
   - INPUTS section (only relevant template variables)
   - Evaluation criteria with pass/fail examples
   - Safeguarding instructions (spirit vs letter principle)
   - Output instructions with timestamp requirements
   - N/A conditions where appropriate

4. **Review with user**: Present the draft metric for approval before creating. Show the full prompt and field values.

5. **Create via API**: Use `mcp__cekura__metrics_create` with the full payload including `name`, `description` (the prompt), `type`, `eval_type`, `project` or `agent`, and trigger fields.

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

## Process (Update)

1. **Identify the metric**: Get the metric ID. If not provided, use `mcp__cekura__metrics_list` to find it.

2. **Fetch current state**: Use `mcp__cekura__metrics_retrieve` with the metric ID. Display the current configuration.

3. **Determine changes**: What the user wants to modify:
   - Prompt/description text
   - Eval type
   - Trigger configuration (evaluation_trigger, evaluation_trigger_prompt)
   - Custom code
   - Name
   - Observability/simulation enabled

4. **Apply changes**: Confirm with user before updating. Use `mcp__cekura__metrics_partial_update` with only the changed fields.

5. **Verify**: Fetch the metric again to confirm changes applied.

6. **Offer to re-evaluate**: After prompt changes, suggest re-running the metric on recent calls to validate the update works as intended.

**Key update reminders:**
- PATCH only sends the fields being changed, not the full payload
- If updating the prompt, follow metric design best practices (spirit vs letter, safeguarding, etc.)
- After prompt changes, consider re-running the metric on recent calls to validate
- If the metric has copies on other projects, the user may need to update ALL copies — copies are independent objects

## Environment

- API key: `CEKURA_API_KEY` env var (configured via .mcp.json)
- Base URL: `https://api.cekura.ai`
- Create: `POST /test_framework/v1/metrics/`
- Update: `PATCH /test_framework/v1/metrics/{id}/`
