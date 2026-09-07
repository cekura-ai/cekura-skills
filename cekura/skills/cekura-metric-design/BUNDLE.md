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

> **Condensed skill bundle** — loaded on the fly because the Cekura plugin is not installed in this session.
> Full reference files included at the end of this document: `prompt-patterns.md`, `advanced-patterns.md`.
> Any other `references/…` file mentioned below ships only with the installed plugin — install it for the complete set: https://docs.cekura.ai/mcp/overview

<!-- cekura-ack-tag: ack:cekura-metric-design:6n2q5r -->
> **Cekura skill verification tag:** `ack:cekura-metric-design:6n2q5r`
> When you call a Cekura metric write tool from this skill (`metrics_create`, `metrics_bulk_create`, `metrics_partial_update`), pass this exact string as the `skill_ack` argument on that tool call. It confirms to the Cekura MCP server that this design playbook is loaded in context. Scenario / test-profile writes use an eval-family tag instead — load `cekura-eval-design` first and pass its tag there.

Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="cekura-metric-design"`, `verification_tag="ack:cekura-metric-design:6n2q5r"`, and `plugin_version="0.16"`. It returns immediately and lets Cekura see which skills are in use.

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
| `binary` | TRUE/FALSE | Pass/fail checks — flow compliance, soft-skill/quality assessments |
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



---

## Appended reference — prompt-patterns.md

# LLM Judge Prompt Patterns

## Standard Prompt Template

Every llm_judge metric prompt should follow this structure. The SCOPE & FOCUS and DO NOT FLAG layers are **mandatory** when the metric uses `{{agent.description}}` — they prevent cross-pollination from unrelated flows.

```
SCOPE & FOCUS
This metric evaluates [specific behavior] ONLY.
IGNORE all rules in the agent description related to [other flows — use generic concepts, not section names].
Other metrics cover: [list what other metrics handle, so this one doesn't duplicate].

---------
DO NOT FLAG THESE (Common False Positives)
- [Behavioral pattern that looks like a fail but isn't for THIS metric]
- [Another pattern — e.g., "Standard booking steps not followed" for an Emergency metric]
- [Short calls / hang-ups / voicemails where the flow never started]

---------
INPUTS:
- {{transcript}}
- {{relevant_variable_1}}
- {{relevant_variable_2}}

---------
SECTION 1: [CHECK NAME]

[Evaluation criteria with specific pass/fail examples]

PASS examples:
- [Concrete example with explanation]
- [Another example]

FAIL examples:
- [Concrete example with explanation]
- [Another example]

---------
SECTION 2: [CHECK NAME]

[More evaluation criteria...]

---------
FAILURE CONDITIONS (Only These Count)
Only mark as FALSE if ONE of these specific patterns occurs:
1. [Specific failure pattern]
2. [Another specific failure pattern]
3. [Another — keep this list narrow and closed]

If the issue does not match any of these patterns, return TRUE.

---------
OUTPUT INSTRUCTIONS

Return: [TRUE | FALSE | N/A] (or appropriate return type)

If FALSE:
- Provide a brief explanation of what went wrong
- Include timestamps in MM:SS format for each violation
- Reference specific transcript excerpts

If TRUE:
- Brief summary of key positive observations

If N/A:
- State which N/A condition was met
```

## Safeguarding Pattern

Include safeguarding instructions before the output section to prevent over-literal interpretation:

```
---------
IMPORTANT SAFEGUARDING NOTES

The agent description defines INTENDED behavior. Do not evaluate literally.
Capture the SPIRIT of each instruction:

- "Ask one question at a time" → Spirit: prevent cognitive overload
  PASS: "Can I get your name and date of birth?" (related data cluster)
  PASS: "Is this new or existing?" (A/B rephrasing = single question)
  FAIL: "What's your name? Also, have you used our service before?" (unrelated topics)

- "Always confirm the appointment" → Spirit: ensure caller has correct information
  PASS: Summarizing key details and asking for confirmation
  PASS: Confirming via a different phrasing ("So that's Thursday at 2pm?")
  FAIL: Skipping confirmation entirely and ending call

[Add specific safeguards for this metric's criteria]
```

## Binary Qualitative Pattern (Soft Skills)

Used for quality assessments like tone, professionalism, conversational style.

```
INPUTS:
- {{transcript}}
- {{agent.description}}

---------
SECTION 1: HARD GUARDRAILS (automatic fail)

Check for banned language that exposes internal systems:
- Technical jargon: "json", "api", "endpoint", "backend", "function call"
- System internals: "internal reasoning", "system action", "processing request"

Exception: "Just pulling up your details" is PASS (natural human-like phrasing)
"I am executing a function call" is FAIL (exposes system internals)

---------
SECTION 2: CONVERSATIONAL QUALITY

Evaluate against the main agent's conversational style rules extracted from
{{agent.description}}. Focus on:

1. Question Stacking & Cognitive Load
   - One topic per turn (related sub-questions are fine)
   - No unrelated question bundling

2. Natural vs Robotic Language
   - Filler words and acknowledgments are fine ("Sure thing", "Of course")
   - Overly formal scripted language is a flag

3. Courtesy & Empathy
   - Appropriate tone for the situation
   - Acknowledgment of caller frustration or urgency

4. Turn Management
   - Not interrupting unnecessarily
   - Smooth transitions between topics

---------
SAFEGUARDING NOTES
[Spirit vs letter examples specific to this metric]

---------
OUTPUT INSTRUCTIONS
Return: TRUE | FALSE

If FALSE: Brief explanation + MM:SS timestamps for violations
If TRUE: Brief summary of quality observations
```

## Binary Workflow Adherence Pattern (Flow Compliance)

Used for checking if the agent followed a specific workflow correctly.

```
SCOPE & FOCUS
This metric evaluates [specific workflow] adherence ONLY.
IGNORE all rules in the agent description related to other workflows (e.g., standard bookings, cancellations, general conduct).
Other metrics handle: [list — e.g., "booking flow, cancellation flow, soft skills"].

---------
DO NOT FLAG THESE
- Rules from adjacent workflows (e.g., booking steps in a cancellation metric)
- End-of-call courtesies or protocol that don't affect this workflow's core steps
- Minor behavioral variations that achieve the same outcome (spirit vs letter)

---------
INPUTS:
- {{transcript}}
- {{agent.description}}
- {{dynamic_variables}}

---------
SECTION 1: N/A CONDITIONS (check first)

Return N/A immediately if ANY of these apply:
- Caller requested human transfer within first 2 exchanges
- Caller hung up before flow could begin
- Critical tool failure prevented flow execution
- This workflow type was not relevant to the call

---------
SECTION 2: CRITICAL TOOL FAILURES

If tools failed during the flow but the agent attempted recovery:
- Check if agent acknowledged the issue appropriately
- Check if agent offered alternatives (callback, manual process)
- If recovery was reasonable → VALID_SKIP: [explanation]
- If agent ignored failure and continued incorrectly → FALSE

---------
SECTION 3: WORKFLOW CRITERIA

Extract the relevant workflow from {{agent.description}} and evaluate:

Step 1: [First required step]
- What to check
- Pass/fail criteria

Step 2: [Second required step]
- What to check
- Pass/fail criteria

[Continue for all steps...]

---------
FAILURE CONDITIONS (Only These Count)
Only mark as FALSE if ONE of these specific patterns occurs:
1. [Critical step completely skipped AND call continued]
2. [Wrong workflow executed entirely]
3. [Agent gave incorrect information that affected the outcome]

Do NOT fail for: minor ordering variations, extra courtesies, or rules from other workflows.

---------
SAFEGUARDING NOTES
[Specific to this workflow]

---------
OUTPUT INSTRUCTIONS
Return: TRUE | FALSE | N/A

If FALSE: Brief explanation + MM:SS timestamps for each step violation
If TRUE: Confirm which workflow steps were completed successfully
If N/A: State which N/A condition was met
```

## Enum Classification Pattern

Used for categorizing calls into defined buckets.

```
INPUTS:
- {{transcript}}
- {{agent.description}}

---------
CLASSIFICATION CRITERIA

Classify this call into one of: [value_1 | value_2 | value_3 | N/A]

**value_1** — [criteria for this classification]
Signals: [what to look for in the transcript]

**value_2** — [criteria for this classification]
Signals: [what to look for in the transcript]

**value_3** — [criteria for this classification]
Signals: [what to look for in the transcript]

**N/A** — Return when:
- [Condition where classification doesn't apply]
- [Another condition]

---------
PRIORITY RULES

When multiple classifications could apply:
1. [Highest priority rule]
2. [Second priority rule]
3. [Default behavior]

---------
OUTPUT INSTRUCTIONS
Return: [value_1 | value_2 | value_3 | N/A]

Provide brief explanation of classification reasoning.
```

## Conditional Trigger Prompt Pattern

For metrics that should only fire on certain call types. Always use the positive-then-negative pattern:

```
Evaluate whether this call involves [specific scenario].

Return TRUE if ANY of these indicators are present in the transcript:
- [Indicator 1, e.g., "caller mentions wanting to book an appointment"]
- [Indicator 2, e.g., "agent initiates booking workflow"]
- [Indicator 3, e.g., "discussion of available time slots"]

Do NOT trigger if ANY of these apply:
- Call is under 30 seconds or contains no substantive interaction beyond a greeting
- Line disconnection / voicemail / outbound non-engagement
- [Specific exclusion, e.g., "Emergency-flow transfers (covered by separate Emergency metric)"]
- [Another exclusion, e.g., "Caller only asks about [scenario] hypothetically without proceeding"]

Be inclusive — if there's reasonable evidence the scenario occurred, return TRUE.
```

The negative exclusions are critical — they catch calls that superficially look relevant but shouldn't be evaluated (preventing false failures downstream). Always include the short-call exclusion (under 30 seconds).

## Dynamic Variable-Driven Metric Pattern

For clients that inject per-call system prompts or configuration via `dynamic_variables`:

```
You are evaluating whether a voice AI agent followed its [Node Name] system prompt.

<system_prompt>
{{dynamic_variables.nodeNamePrompt}}
</system_prompt>

TRANSCRIPT:
{{transcript_json}}

EVALUATION TASK:
Evaluate whether the agent adhered to the system prompt above during the [node name] phase of the call.

Focus areas:
- [Key behavior 1 specific to this node]
- [Key behavior 2]
- [Core question/step coverage]

N/A CONDITIONS:
Return N/A if:
- The dynamic variable is empty or not present (this agent node was not active)
- The call ended before reaching this phase
- The transcript shows no interaction matching this agent node

FAILURE CONDITIONS (Only These Count):
1. [Major deviation from the system prompt]
2. [Missed core step that the prompt explicitly requires]
3. [Wrong information provided that contradicts the prompt]

Do NOT fail for: minor phrasing variations, extra courtesies, or rules from OTHER agent nodes.

OUTPUT:
Return: TRUE | FALSE | N/A
Include timestamps and specific evidence.
```

Each metric references ONLY its specific `{{dynamic_variables.promptName}}` — never the full `{{dynamic_variables}}` blob or `{{agent.description}}`.

## Tool Call Hallucination Pattern

For agents with detailed tool definitions — evaluates whether the agent called the correct tool for each situation:

```
SCOPE & FOCUS
This metric evaluates TOOL CALL CORRECTNESS ONLY.
Does NOT evaluate: tone, soft skills, flow ordering, information accuracy, or any non-tool behavior.
Focus on: was the right tool called, with the right arguments, at the right time?

TOOL-TO-SCENARIO MAPPING (from {{agent.description}}):
- [Tool A] → used when [scenario]. Required arguments: [list]. Must be called AFTER [prerequisite].
- [Tool B] → used when [scenario]. Required arguments: [list].
- [Tool C] → used when [scenario]. NOT to be confused with [Tool D] which handles [different scenario].

DO NOT FLAG:
- API errors or server-side failures (the agent called the right tool but it failed — not the agent's fault)
- Known server-side quirks (e.g., success responses with error-like messages)
- Fallback/default tool usage when the primary tool fails or the query is ambiguous
- Tool calls that return unexpected data but the agent handled it gracefully

FAILURE CONDITIONS (Only These Count):
1. Wrong tool for user's intent (e.g., called payment tool when user asked about balance)
2. Missing mandatory arguments on a tool call (e.g., no loanId on make_payment)
3. Calling account-specific tools BEFORE authentication/identity verification
4. Confusing similar but distinct workflows (e.g., scheduled payment vs promise-to-pay)
5. Including incorrect data in tool arguments (e.g., including fees in payment amount when fee is separate)
6. Skipping prerequisite tool calls (e.g., making payment without first fetching payment methods)

OUTPUT:
Return: TRUE | FALSE | N/A
For each tool call in the transcript, note: tool name, arguments, whether it was correct, and why.
Include MM:SS timestamps for any violations.
```



---

## Appended reference — advanced-patterns.md

# Advanced Metric Design Patterns

Patterns that build on the core metric design workflow in `SKILL.md`. Read these when designing metrics that involve dynamic variables, tool-call correctness, or multi-flow agents.

## Anti-Cross-Pollination Scoping (Critical for `{{agent.description}}` metrics)

When a metric uses `{{agent.description}}`, the LLM reads the entire description and can fail based on rules from unrelated flows. For example, an Emergency metric fails because the agent didn't follow a Booking Flow rule. **This is the most common source of false failures.**

**Three-layer scoping pattern (mandatory when using `{{agent.description}}`):**

1. **SCOPE & FOCUS** — Explicit "evaluates X ONLY" + "IGNORE all non-X rules in the agent description" with a concept-level explanation of what other flows exist and are covered by other metrics.
2. **DO NOT FLAG THESE** — Enumerated list of common false positives specific to this metric. Named by behavioral pattern (e.g., "Standard booking steps not followed"), not by agent-specific section names.
3. **FAILURE CONDITIONS (Only These Count)** — Narrow, closed list of what actually constitutes a failure. Instead of "failed on any criterion" (which invites the LLM to find creative reasons from other flows), it's "only flag if ONE of these specific patterns occurs."

**Critical rule: All scoping must be generic/concept-based, never hardcode section names from a specific agent's description.** Use "the emergency sections of the agent description" not "the Emergency Flow section". Use "standard bookings, rescheduling, cancellations" as concept examples, not "Service Booking Flow, Updating Appointment Flow". This ensures metrics can be cross-applied across agents without modification.

## Dynamic Variable-Driven Generalized Metrics

When a client injects per-call data via `dynamic_variables`, create metrics that adapt to each call's context instead of hardcoding expected behavior. This is the most powerful pattern for clients with multi-agent flows or per-call configuration.

**Pattern: One metric per injected prompt variable.** If a client sends 11 different system prompts as dynamic variables (one per agent node), create 11 metrics — each referencing only its specific `{{dynamic_variables.promptName}}`. This keeps the LLM's context tight and prevents hallucination from irrelevant instructions meant for other agent nodes.

**Example prompt structure:**
```
You are evaluating whether a voice AI agent followed its [Node Name] system prompt.

<system_prompt>
{{dynamic_variables.nodeNamePrompt}}
</system_prompt>

TRANSCRIPT:
{{transcript_json}}

[EVALUATION TASK — focus areas specific to this agent node]
[OUTPUT — TRUE/FALSE/N/A]
```

Each metric references ONLY the dynamic variable for that agent node, not `{{agent.description}}` or the full `{{dynamic_variables}}` blob.

**Beyond prompts — dynamic variables for triggers and scoping:**
Dynamic variables aren't limited to system prompts. Clients may inject employment types, feature flags, client identifiers, or call metadata. Use these in triggers to scope metrics to specific call types.

**Discovery workflow:** Fetch 3-5 sample calls, inspect `dynamic_variables` to see what the client sends. Look for: system prompts (long strings with instructions), configuration flags (booleans), identifiers (strings), and contextual data (prior call summaries). Each meaningful variable is a candidate for metric scoping.

## Tool Call Hallucination Metrics

A distinct metric archetype for agents with detailed tool definitions. This evaluates whether the agent called the **correct tool for each situation** — "action hallucination" (agent doing the wrong thing) vs "fact hallucination" (agent stating wrong info).

**Pattern:**
1. Extract every tool name + when to use it + required arguments + sequencing rules from the agent description
2. Encode as explicit FAILURE CONDITIONS (closed list)
3. Include a DO NOT FLAG section for API errors, known server-side quirks, and fallback tool usage

**Structure:**
```
SCOPE: Evaluates tool call correctness ONLY. Does NOT evaluate tone, flow adherence, or information accuracy.

TOOL-TO-SCENARIO MAPPING (from agent description):
- [Tool A] → used when [scenario], requires [arguments]
- [Tool B] → used when [scenario], must be called AFTER [Tool A]

DO NOT FLAG:
- API errors / server-side failures (not the agent's fault)
- Known quirks (e.g., success responses with error-like messages)
- Fallback/default tool usage when appropriate

FAILURE CONDITIONS (Only These Count):
1. Wrong tool for intent (e.g., called payment tool when user asked about balance)
2. Missing mandatory arguments
3. Calling account tools before authentication
4. Confusing similar workflows (e.g., scheduled payment vs promise-to-pay)
```

**Without explicit failure conditions**, the LLM judge either passes everything (too lenient) or invents creative failures from unrelated description sections (same cross-pollination problem).
