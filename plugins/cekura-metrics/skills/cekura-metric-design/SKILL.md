---
name: cekura-metric-design
description: >
  Use when the user asks to "create a metric", "write a metric", "design a metric",
  "build a metric for", "evaluate agent performance", "measure call quality", "track a KPI",
  "add a workflow metric", "improve my metric", "fix a metric", "debug metric results",
  "set up quality scoring", or "what metrics do I need". Also relevant when discussing
  LLM judge prompts, custom code metrics, evaluation triggers, VALID_SKIP patterns,
  section extraction, or metric best practices for Cekura voice AI agents. Covers both
  creating new metrics and reviewing, iterating on, or troubleshooting existing ones.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.3.0"
---

# Cekura Metric Design

## Purpose

Guide the creation of effective Cekura metrics that accurately evaluate AI voice agent call quality. Metrics measure call quality after the fact by evaluating transcripts against defined criteria. Each metric targets a specific workflow or KPI that needs tracking per call.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

## Core Terminology

- **Main agent**: The client's AI voice agent being tested
- **Testing agent**: Cekura's simulated caller that exercises the main agent
- **Metric**: A post-call evaluation that scores a transcript
- **Evaluator/Scenario**: A test case that simulates a caller (separate concept — see cekura-eval-design skill)

## The Metric Creation Workflow

Follow this workflow every time. Skipping steps (especially step 2) leads to metrics that miss edge cases.

1. **Gather context** — Understand the client's use case, what they care about, get sample conversation IDs with expected outcomes
2. **Fetch real transcripts** — Pull 3-5 actual `transcript_json` records from the Cekura API. Study: what roles appear (`Main Agent`, `User`, `Function Call`, `Function Call Result`), what timestamps are available, how tool calls are structured, what the conversation flow looks like in practice. Metrics written without reading real data will miss edge cases.
3. **Identify the signal** — What specific thing in the transcript indicates pass vs fail? A tool call, a timestamp gap, a phrase, a behavioral pattern?
4. **Write the prompt** — Use proven structures (see below), grounded in what the real transcripts look like
5. **Deploy and test** — Create the metric via API, run on sample conversations, compare to expected outcomes
6. **Iterate** — Adjust the prompt based on results, re-run, repeat until the metric matches expectations on all samples. Plan for at least one iteration — the first run reveals measurement issues.

## Metric Types

### llm_judge (preferred default)

An LLM evaluates the prompt in the `description` field against the call transcript. **Prefer llm_judge over custom_code.** Custom_code seems appealing for "objective" checks (timestamps, tool call presence) but is brittle in practice. Voice AI transcripts have messy timing — agents transfer mid-tool-chain, background tasks complete after speech resumes, timestamps overlap. An LLM reading the transcript handles these nuances naturally. Express measurements in natural language, not code.

**Critical:** The evaluation prompt goes in the `description` field, NOT the `prompt` field.

### custom_code (Python on Lambda)

Python code in `custom_code` field. Has access to `data` dict, `evaluate_basic_metric()`, and upstream metric results. Reserve for cases that genuinely need programmatic logic.

**Use only when:**
- Gating on upstream metric results (`data.get("Exact Metric Name")`)
- Section extraction from agent description (Pythonic pattern)
- Multiple LLM calls with different prompts based on conditions
- N/A short-circuiting before calling the LLM

## Metric Evolution Path

Start as `llm_judge` for rapid iteration. Once the prompt is validated (through labs/feedback), convert to `custom_code` with section extraction for production. Cekura allows a metric to have both `description` (llm_judge prompt) AND `custom_code` — the active type is toggled. This means the LLM prompt can be refined through labs, then the custom_code version uses that same prompt with targeted context extraction.

## Eval Types

| Eval Type | Output | Use For |
|-----------|--------|---------|
| `binary_qualitative` | TRUE/FALSE | Soft skills, quality assessments |
| `binary_workflow_adherence` | TRUE/FALSE | Flow compliance checks |
| `enum` | String from defined values | Classification tasks |
| `numeric` | Float score | Scoring tasks |
| `continuous_qualitative` | Continuous score | Continuous quality assessment |

## LLM Judge Prompt Structure

Two proven structures exist. See `references/prompt-patterns.md` for full templates.

### Structure A: Sectioned (best for multi-criteria metrics)
1. **SCOPE & FOCUS** — What this metric evaluates ONLY + what to IGNORE
2. **DO NOT FLAG** — Common false positives: behavioral patterns that look like fails but aren't for THIS metric
3. **INPUTS** — Only relevant template variables
4. **SECTIONS** — Numbered evaluation criteria with pass/fail examples
5. **FAILURE CONDITIONS (Only These Count)** — Narrow, closed list of what constitutes a failure
6. **SAFEGUARDING NOTES** — Spirit vs letter overrides
7. **OUTPUT INSTRUCTIONS** — Return format, timestamps for failures

### Structure B: Narrative (best for behavioral/timing metrics)
1. **SCOPE & FOCUS** — What this metric evaluates ONLY + what to IGNORE
2. **DO NOT FLAG** — Common false positives specific to this metric
3. **CONTEXT** — What this call type looks like, why the metric matters
4. **WHAT TO LOOK FOR** — Specific items in the transcript (tool names, phrases, patterns)
5. **FAILURE CONDITIONS (Only These Count)** — Narrow, closed list of specific failure patterns
6. **NUANCES** — Edge cases, overrides, things that look like fails but aren't
7. **OUTPUT** — TRUE/FALSE/N/A with timestamps and evidence

Being explicit about PASS vs FAIL with real examples from actual conversations is the single most impactful thing for prompt quality. Vague criteria like "agent should be responsive" produce inconsistent results.

### Anti-Cross-Pollination Scoping (when using `{{agent.description}}`)

The most common source of false failures: a metric using `{{agent.description}}` fails based on rules from an unrelated flow (e.g., Emergency metric fails because of a Booking Flow rule).

**Three-layer scoping pattern**: SCOPE & FOCUS ("evaluates X ONLY"), DO NOT FLAG (enumerate false positives by behavioral pattern), FAILURE CONDITIONS (narrow closed list).

**See `references/advanced-patterns.md`** for full structure and the rule that all scoping language must be concept-based, never hardcoded to a specific agent's section names.

### Available Template Variables

| Variable | Description |
|----------|-------------|
| `{{transcript}}` | Full conversation text |
| `{{transcript_json}}` | Structured transcript with timestamps |
| `{{dynamic_variables}}` | Full blob of custom variables from calls |
| `{{dynamic_variables.keyName}}` | Specific dynamic variable by key (dot notation preferred) |
| `{{agent.description}}` | Main agent's system prompt |
| `{{metadata}}` | Call metadata |
| `{{call_end_reason}}` | How the call ended |

Include only variables relevant to the specific metric. Listing all variables creates noise and dilutes evaluation focus.

When using `{{metadata}}`, point to specific metadata fields the LLM judge should reference (e.g., "Check `metadata.appointment_id` to verify booking was created").

## The Spirit vs Letter Principle

**This is the most critical concept in metric design.**

Agent descriptions describe the intended functionality of the main agent, but must not be taken literally by the evaluator. Understand the **intent** behind each instruction and write the metric to capture the **spirit**, not the literal text.

**Example:** Agent description says "ask only 1 question at a time"
- **Spirit:** Prevent cognitive overload on the caller
- **Literal (wrong):** Fail any turn with more than one question mark
- **Correct metric behavior:**
  - PASS: "Are you the owner of 123 Easy St? Can I get your name?" (related data cluster)
  - PASS: "Is this a new issue, or an existing one?" (A/B rephrasing = single question)
  - FAIL: "Does Thursday work? Also, did you get our text message?" (unrelated questions)

When uncertain about the intent behind an instruction, **ask the user** to clarify before encoding it into the metric. Include explicit safeguarding examples in the prompt showing what should and should not be penalized.

## Trigger Design

| Trigger Type | When to Use |
|-------------|-------------|
| `"always"` | Metrics that apply to every call (soft skills, business context) |
| `"custom"` with `llm_judge` trigger | Conditional metrics (booking flow only fires when booking intent detected) |
| `"custom"` with `custom_code` trigger | Complex trigger logic requiring code |
| `"automatic"` | Let Cekura auto-determine (less control) |

Use the `generate_evaluation_trigger` endpoint (see `references/api-reference.md`) to auto-generate trigger prompts from metric descriptions. Triggers can be layered in specificity — e.g., one trigger fires on any onboarding call, another fires only when the user gets stuck.

### Two-Layer N/A Strategy

Triggers and metric descriptions handle N/A at different levels:

- **Trigger-level N/A (first defense):** The trigger gates out obviously irrelevant calls BEFORE the metric runs. This saves LLM cost. Example: a Booking Flow metric's trigger checks if booking intent exists — if not, the metric doesn't fire and outputs N/A.
- **Description-level N/A (nuanced cases):** The metric prompt itself handles edge cases that need transcript context to determine. Example: a call has booking intent (trigger fires) but the caller hangs up before the flow starts — the metric description returns N/A with "VALID_SKIP: caller disconnected before booking could begin."

Design triggers to catch the obvious non-applicable calls; design the metric prompt to handle the nuanced edge cases that require reading the transcript.

### Trigger Prompt Template

Write triggers with the positive-then-negative pattern:

```
Evaluate whether this call involves [specific scenario].

Return TRUE if ANY of these indicators are present:
- [Positive indicator 1]
- [Positive indicator 2]

Do NOT trigger if ANY of these apply:
- Call is under 30 seconds or contains no substantive interaction beyond a greeting
- Line disconnection / voicemail / outbound non-engagement
- [Specific exclusion for this metric — e.g., "Emergency-flow transfers (covered by Emergency metric)"]
- [Another exclusion]

Be inclusive — if there's reasonable evidence the scenario occurred, return TRUE.
```

**Always include the short-call exclusion.** Calls under ~30 seconds (hang-ups, wrong numbers, voicemails) produce false positives/negatives on every metric. Gate them out at the trigger level.

### Trigger Produces N/A Output

When `evaluation_trigger: "custom"` and the trigger returns false, the metric outputs N/A — it is not evaluated. This means even binary metrics (True/False) can have three outcomes: True, False, or N/A. This is correct behavior for conditional metrics.

## Key Patterns

### VALID_SKIP Pattern

For legitimate deviations where the metric should not apply (tool failures, user hangup before flow starts, caller requesting transfer immediately). The LLM returns explanation starting with "VALID_SKIP:" and the custom_code wrapper converts to `_result = None`.

### Gated Metrics

Access upstream metric results via `data.get("Exact Metric Name")`. The key must match the upstream metric's `name` field exactly. Use to branch evaluation logic based on prior classification.

### Pythonic Section Extraction

Extract only relevant sections from agent description before passing to LLM. Prevents context drift from irrelevant description sections and reduces token usage. See `references/pythonic-patterns.md` for the extraction utility.

### N/A Conditions

Check first for conditions where the metric should not apply:
- Immediate transfer/human request within first 1-2 exchanges
- Caller hangup before flow begins
- Out-of-scope caller (wrong number, sales call)
- Infrastructure failure preventing flow execution
- Agent description lacks the relevant section (for optional workflows)

### Dynamic Variable-Driven Generalized Metrics

For clients that inject per-call `dynamic_variables` (e.g., per-node system prompts, feature flags, employment types), create metrics that adapt to each call instead of hardcoding behavior. **Pattern: one metric per injected prompt variable.** Each metric references ONLY its specific `{{dynamic_variables.promptName}}`, not the full blob or `{{agent.description}}`.

**See `references/advanced-patterns.md`** for the example prompt structure and the discovery workflow for finding dynamic variables in real calls.

### Tool Call Hallucination Metrics

For agents with detailed tool definitions, build a metric that evaluates whether the agent called the **correct tool for each situation** — "action hallucination" (wrong action) vs "fact hallucination" (wrong information). Pattern: extract tool→scenario mapping from agent description, encode as explicit FAILURE CONDITIONS (closed list), DO NOT FLAG API errors / known quirks.

**See `references/advanced-patterns.md`** for the full prompt structure and TOOL-TO-SCENARIO MAPPING template.

## Baseline Metrics — Always Recommend

Every agent should have at minimum these predefined metrics enabled for both observability and simulations:

| Metric | Purpose | Why It Matters |
|--------|---------|----------------|
| **Expected Outcome** | Checks if the agent achieved the scenario's expected result | Without this, runs pass/fail based only on call completion — not correctness |
| **Infrastructure Issues** | Flags silent periods, connection drops, agent non-response | Catches issues like agent going silent for 10+ seconds that aren't visible in pass/fail |
| **Tool Call Success** | Monitors whether tool calls succeed or fail | Requires provider integration (assistant IDs + API keys) to get toolcall data in transcripts |
| **Latency** | Measures response time | Identifies performance degradation |

**Two-step activation required:** Metrics must be (1) toggled on for simulations at the project level AND (2) added to individual evaluators. Missing either step means metrics won't fire. Without metrics enabled, users get false passes and must manually review every run.

**Expected Outcome is transcript-only — it cannot evaluate audio-layer behavior.** Expected Outcome reads the conversation text to determine whether the agent achieved its goal. It has no visibility into silences, interruptions, barge-ins, audio dropouts, or other voice-channel signals. Do not rely on Expected Outcome to catch these. For anything that depends on the audio stream rather than conversation content, use predefined metrics instead.

**Toolcall data prerequisite:** Tool Call Success and advanced monitoring require the agent to have its provider assistant ID configured on Cekura and complete call data being sent. If transcripts are missing toolcall data, recommend the user configure their provider integration.

## Output Requirements

All metrics must require:
- Brief explanation of the result (what happened and why)
- For failures: specific timestamps in MM:SS format where violations occurred
- For metadata-based checks: reference the specific metadata fields examined

## Common Custom Metrics Worth Suggesting

Beyond the baseline predefined metrics, these are commonly valuable custom metrics based on patterns seen across clients:

- **Question stacking / information dumping** — Agent asking 3+ unrelated questions in one turn or dumping large blocks of information. Poor UX that overwhelms callers.
- **Workflow adherence** — Agent follows the defined flow steps in order (booking, verification, cancellation, etc.)
- **Soft skills** — Tone, empathy, appropriate greetings, not exposing system internals
- **Business context accuracy** — Agent provides correct business information (hours, addresses, pricing)
- **Transfer/callback handling** — Agent follows proper protocol when transferring or scheduling callbacks

## Operational Rules

### Cost Guard — Never Evaluate >100 Calls Without Confirmation

Each evaluation costs the client real money. Before evaluating metrics on a batch of calls, ALWAYS query the call count first (use `page_size=1` and read the response) and report the number to the user. If count > 100, stop and ask for explicit approval before proceeding. Use `page_size` parameter (up to 200) instead of paginating, and use server-side filters (`agent_id`, `project`, `timestamp__gte`/`timestamp__lte`) to scope calls.

### Manual Fix First, Then Labs

When metrics have systemic issues (high false-fail rates), do NOT jump straight to labs feedback. Instead:
1. Read failure explanations and categorize root causes (e.g., extra_questions, end_protocol, should_be_na)
2. Write manual prompt fixes targeting the dominant failure categories
3. PATCH the updated descriptions via API
4. Re-evaluate a sample of 20-30 calls per metric to validate the fixes
5. THEN use labs feedback for remaining edge cases that manual fixes didn't catch

This avoids wasting labs iterations on issues that are clearly fixable by prompt editing.

## Common Pitfalls

- **Writing metrics without reading real transcripts first** — always fetch and study actual transcript_json before writing
- Putting the prompt in `prompt` field instead of `description` for llm_judge
- Using deprecated types (`basic`, `custom_prompt`) — API returns 400
- Using `custom_code` for checks the LLM can handle naturally (timestamps, tool call detection)
- Not matching upstream metric name exactly for gated metrics
- Passing full agent description when only a section is relevant (context drift)
- Missing VALID_SKIP handling in custom_code metrics
- No N/A conditions for conditional metrics
- Taking agent description instructions literally instead of capturing their spirit
- Not including safeguarding examples for nuanced evaluation criteria
- Omitting timestamps in failure explanations

## Next Steps

After creating a metric, the user typically needs:
- **Validate it on real calls** → use the evaluate-calls flow (see `references/api-reference.md`)
- **Iterate on accuracy** → invoke **cekura-metric-improvement** to run the labs feedback cycle
- **Design test scenarios that exercise this metric** → invoke **cekura-eval-design**

## Documentation

- Public docs: https://docs.cekura.ai
- LLM-friendly docs: https://docs.cekura.ai/llms.txt
- Concepts: https://docs.cekura.ai/documentation/key-concepts/

See `references/api-reference.md` for complete endpoint documentation and field schemas.

## Additional Resources

### Reference Files (loaded on demand)

- **`references/prompt-patterns.md`** — Full LLM judge prompt templates with real examples
- **`references/pythonic-patterns.md`** — Section extraction utility and custom_code patterns
- **`references/advanced-patterns.md`** — Anti-cross-pollination scoping, dynamic-variable-driven metrics, tool-call hallucination metrics
- **`references/api-reference.md`** — Complete Cekura metrics API endpoints and schemas

### Example Files

- **`examples/llm-judge-metric.md`** — Complete llm_judge metric example (sectioned structure)
- **`examples/narrative-metric.md`** — Complete llm_judge metric example (narrative structure)
- **`examples/custom-code-metric.py`** — Complete custom_code metric with gating and VALID_SKIP
- **`examples/section-extraction-metric.py`** — Pythonic metric with agent description scoping
