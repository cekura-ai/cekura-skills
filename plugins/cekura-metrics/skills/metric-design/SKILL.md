---
name: Cekura Metric Design
description: >
  Useful when the user asks to "create a metric", "write a metric", "design a metric",
  "build a metric for", "evaluate agent performance", "measure call quality", "track a KPI",
  "add a workflow metric", "improve my metric", "fix a metric", "debug metric results",
  "set up quality scoring", or "what metrics do I need". Also relevant when discussing
  LLM judge prompts, custom code metrics, evaluation triggers, VALID_SKIP patterns,
  section extraction, or metric best practices for Cekura voice AI agents. Covers both
  creating new metrics and reviewing, iterating on, or troubleshooting existing ones.
version: 0.1.0
---

# Cekura Metric Design

## Purpose

Guide the creation of effective Cekura metrics that accurately evaluate AI voice agent call quality. Metrics measure call quality after the fact by evaluating transcripts against defined criteria. Each metric targets a specific workflow or KPI that needs tracking per call.

## Core Terminology

- **Main agent**: The client's AI voice agent being tested
- **Testing agent**: Cekura's simulated caller that exercises the main agent
- **Metric**: A post-call evaluation that scores a transcript
- **Evaluator/Scenario**: A test case that simulates a caller (separate concept — see cekura-evals plugin)

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

### Structure A: Sectioned (best for multi-criteria metrics like Elyos)
1. **INPUTS** — Only relevant template variables
2. **SECTIONS** — Numbered evaluation criteria with pass/fail examples
3. **SAFEGUARDING NOTES** — Spirit vs letter overrides
4. **OUTPUT INSTRUCTIONS** — Return format, timestamps for failures

### Structure B: Narrative (best for behavioral/timing metrics like Traba)
1. **CONTEXT** — What this call type looks like, why the metric matters
2. **WHAT TO LOOK FOR** — Specific items in the transcript (tool names, phrases, patterns)
3. **PASS behaviors** — Concrete examples of what good looks like
4. **FAIL behaviors** — Concrete examples of what bad looks like
5. **NUANCES** — Edge cases, overrides, things that look like fails but aren't
6. **OUTPUT** — TRUE/FALSE/N/A with timestamps and evidence

Being explicit about PASS vs FAIL with real examples from actual conversations is the single most impactful thing for prompt quality. Vague criteria like "agent should be responsive" produce inconsistent results.

### Available Template Variables

| Variable | Description |
|----------|-------------|
| `{{transcript}}` | Full conversation text |
| `{{transcript_json}}` | Structured transcript with timestamps |
| `{{dynamic_variables}}` | Custom variables from calls |
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

## API Access

**Preferred: Cekura MCP server** — If the `cekura-api` MCP server is connected, use its tools directly for all API operations (metrics CRUD, call logs, evaluation, reviews). MCP tools provide structured input/output and proper error handling.

**Fallback: bash scripts** — If MCP is not available, use `source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh` for curl-based API calls.

**Docs lookup:** Use the `SearchCekura` MCP tool or fetch `https://docs.cekura.ai/llms.txt` to look up API details, field schemas, or feature documentation when the plugin references don't cover something.

See `references/api-reference.md` for complete endpoint documentation and field schemas.

## Additional Resources

### Reference Files

- **`references/prompt-patterns.md`** — Full LLM judge prompt templates with real examples
- **`references/pythonic-patterns.md`** — Section extraction utility and custom_code patterns
- **`references/api-reference.md`** — Complete Cekura metrics API endpoints and schemas

### Example Files

- **`examples/llm-judge-metric.md`** — Complete llm_judge metric example (Global Soft Skills, sectioned structure)
- **`examples/narrative-metric.md`** — Complete llm_judge metric example (Transcript Sender Performance, narrative structure)
- **`examples/custom-code-metric.py`** — Complete custom_code metric with gating and VALID_SKIP
- **`examples/section-extraction-metric.py`** — Pythonic metric with agent description scoping
