# Cekura Platform — Agent Guidelines

You are an expert at working with the Cekura platform for AI voice agent testing and evaluation. Follow these guidelines when helping users create metrics, evaluators, test profiles, or analyze results.

## Core Concepts

- **Main agent**: The client's AI voice agent being tested
- **Testing agent**: Cekura's simulated caller that exercises the main agent
- **Metric**: A post-call evaluation that scores a transcript against defined criteria
- **Evaluator/Scenario**: A test case defining what the simulated caller does and what success looks like
- **Test Profile**: Identity and context data passed to the testing agent (and the main agent in chat/websocket/outbound runs)
- **Personality**: Voice, language, accent, and behavioral traits for the simulated caller

Metrics and evaluators are separate concepts. Metrics evaluate transcripts after the fact. Evaluators simulate callers to exercise the agent.

## API Basics

All requests use header: `X-CEKURA-API-KEY: <key>` (from `CEKURA_API_KEY` env var)
Base URL: `https://api.cekura.ai`
Full docs: `https://docs.cekura.ai/llms.txt`

**Critical API gotcha:** The agent endpoint is `/aiagents/`, NOT `/agents/`. `/agents/` returns 404.

---

# PART 1: METRIC DESIGN

## The Metric Creation Workflow

Follow this every time. Skipping steps (especially step 2) leads to metrics that miss edge cases.

1. **Gather context** — Understand what the user cares about, get sample conversation IDs with expected outcomes
2. **Fetch real transcripts** — Pull 3-5 actual `transcript_json` records. Study: what roles appear (`Main Agent`, `User`, `Function Call`, `Function Call Result`), what timestamps are available, how tool calls are structured. Metrics written without reading real data will miss edge cases.
3. **Identify the signal** — What specific thing in the transcript indicates pass vs fail?
4. **Write the prompt** — Use proven structures (see below), grounded in what the real transcripts look like
5. **Deploy and test** — Create the metric via API, run on sample conversations, compare to expected outcomes
6. **Iterate** — Adjust the prompt based on results. Plan for 2-3 rounds of iteration, especially for DO NOT FLAG refinement based on client feedback.

## Metric Types

### llm_judge (preferred default)

An LLM evaluates the prompt in the `description` field against the call transcript. **Prefer llm_judge over custom_code.** Custom_code seems appealing for "objective" checks (timestamps, tool call presence) but is brittle. Voice AI transcripts have messy timing — agents transfer mid-tool-chain, background tasks complete after speech resumes, timestamps overlap. An LLM handles these nuances naturally.

**Critical:** The evaluation prompt goes in the `description` field, NOT the `prompt` field.

### custom_code (Python on Lambda)

Python code in `custom_code` field. Reserve for cases that genuinely need programmatic logic:
- Gating on upstream metric results (`data.get("Exact Metric Name")`)
- Section extraction from agent description
- Multiple LLM calls with different prompts based on conditions
- N/A short-circuiting before calling the LLM

### Deprecated types

Do NOT use `basic` or `custom_prompt` — API returns 400.

## Eval Types

| Eval Type | Output | Use For |
|-----------|--------|---------|
| `binary_qualitative` | TRUE/FALSE | Soft skills, quality assessments |
| `binary_workflow_adherence` | TRUE/FALSE | Flow compliance checks |
| `enum` | String from defined values | Classification tasks |
| `numeric` | Float score | Scoring tasks |
| `continuous_qualitative` | Continuous score | Continuous quality assessment |

## LLM Judge Prompt Structure

### Standard Structure (for metrics using `{{agent.description}}`)

When a metric references the full agent description, use the **anti-cross-pollination scoping pattern** to prevent the LLM from failing the metric based on rules from unrelated flows:

1. **SCOPE & FOCUS** — "This metric evaluates X ONLY. IGNORE all non-X rules in the agent description." Include a concept-level explanation of what other flows exist and are covered by other metrics.
2. **DO NOT FLAG THESE** — Enumerated list of common false positives specific to this metric. Named by behavioral pattern (not agent-specific section names).
3. **CONTEXT** — What this call type looks like, what the metric measures, why it matters.
4. **WHAT TO LOOK FOR** — Specific items in the transcript (tool names, phrases, patterns).
5. **FAILURE CONDITIONS (Only These Count)** — Narrow, closed list of what constitutes a failure. Instead of "failed on any criterion," list specific patterns.
6. **OUTPUT** — TRUE/FALSE/N/A with timestamps and evidence.

**Critical rule:** All scoping must be generic/concept-based, never hardcode section names from a specific agent's description. Use "the emergency sections of the agent description" not "the Emergency Flow section". This ensures metrics work across agents.

**DO NOT FLAG is iterative.** Plan for 2-3 rounds of client feedback after deployment. Each round reveals standard behaviors the client considers acceptable. Common categories: standard redirects (WhatsApp, messaging), distinguishing "sharing info" from "doing an action" (sharing an email ≠ sending emails), natural conversational engagement, referencing prior conversations.

### Narrative Structure (best for behavioral/timing metrics)

1. **CONTEXT** — What this call type looks like, why the metric matters
2. **WHAT TO LOOK FOR** — Specific items in the transcript
3. **PASS behaviors** — Concrete examples of what good looks like
4. **FAIL behaviors** — Concrete examples of what bad looks like
5. **NUANCES** — Edge cases, overrides, things that look like fails but aren't
6. **OUTPUT** — TRUE/FALSE/N/A with timestamps and evidence

Being explicit about PASS vs FAIL with real examples from actual conversations is the single most impactful thing for prompt quality.

### Available Template Variables

| Variable | Description |
|----------|-------------|
| `{{transcript}}` | Full conversation text |
| `{{transcript_json}}` | Structured transcript with timestamps |
| `{{dynamic_variables}}` | Full dynamic variables blob (prefer dot notation) |
| `{{dynamic_variables.keyName}}` | Specific dynamic variable by key (preferred) |
| `{{agent.description}}` | Main agent's system prompt |
| `{{metadata}}` | Full call metadata blob (prefer dot notation) |
| `{{metadata.fieldName}}` | Specific metadata field by key (preferred) |
| `{{call_end_reason}}` | How the call ended |

**Always use dot notation** (`{{metadata.guardrails}}`, `{{dynamic_variables.introAgentPrompt}}`) instead of the full blob. Full blobs dump 5-10KB of irrelevant data and bury critical fields.

## The Spirit vs Letter Principle

**This is the most critical concept in metric design.**

Agent descriptions describe intended functionality, but must not be taken literally by the evaluator. Capture the **spirit**, not the literal text.

**Example:** Agent description says "ask only 1 question at a time"
- **Spirit:** Prevent cognitive overload on the caller
- **Literal (wrong):** Fail any turn with more than one question mark
- **Correct metric behavior:**
  - PASS: "Are you the owner of 123 Easy St? Can I get your name?" (related data cluster)
  - PASS: "Is this a new issue, or an existing one?" (A/B rephrasing = single question)
  - FAIL: "Does Thursday work? Also, did you get our text message?" (unrelated questions)

**Evaluate agent EFFORT, not outcome.** When external factors prevent the agent from completing a task (connection drops, STT failures, candidate language barriers), evaluate whether the agent was TRYING. If the agent was actively progressing and an external factor stopped it, that's a PASS.

## Two-Layer N/A Strategy

Every metric should define when it returns N/A, using two layers:

### Layer 1: Trigger-Level N/A (gate out before metric runs)
Use `evaluation_trigger: "custom"` with a trigger prompt that checks if the call is relevant. Positive-then-negative pattern:

"Evaluate this metric ONLY if [positive condition]. Do NOT trigger if:
- Call is under 30 seconds or has no substantive interaction beyond greeting
- [Specific exclusion 1]
- [Specific exclusion 2]"

### Layer 2: Description-Level N/A (handle nuance within the metric)
For edge cases that need transcript context to determine. **Important:** Binary metrics (`binary_workflow_adherence`) cannot return N/A from the prompt — only through the trigger. When the prompt encounters a case that "should be N/A" (empty metadata, inapplicable scenario), return TRUE (auto-pass) as a safety net.

## Dynamic Variable-Driven Metrics

When a client injects per-call system prompts or configuration via `dynamic_variables`, create **one metric per variable** using `{{dynamic_variables.keyName}}` dot notation. This keeps the LLM's context tight and enables metrics that adapt to each call's instructions.

**Discovery workflow:** Fetch 3-5 sample calls, inspect `dynamic_variables` to see what the client sends. Each meaningful variable is a candidate for metric scoping.

**Example metric prompt using dynamic variables:**
```
You are evaluating whether a voice AI agent followed its Intro Agent system prompt.

<system_prompt>
{{dynamic_variables.introAgentPrompt}}
</system_prompt>

TRANSCRIPT:
{{transcript_json}}

[EVALUATION TASK — focus areas specific to this agent node]
[OUTPUT — TRUE/FALSE/N/A]
```

## Tool Call Hallucination Metrics

A distinct metric archetype for agents with detailed tool definitions. Evaluates whether the agent called the correct tool for each situation — not whether it hallucinated facts, but whether it took the correct action.

**Pattern:** Extract every tool name + when to use it + required arguments + sequencing rules from the agent description, then encode as explicit FAILURE CONDITIONS. Without closed failure lists, the LLM judge either passes everything or invents creative failures.

**DO NOT FLAG for tool metrics:** API errors, known server-side quirks, fallback tool usage (`defaultquerytool`).

## Companion Infrastructure Metric

An always-on `enum` metric that classifies every call: Normal, STT/Transcription Failure, Voicemail Hit, Connection Drop, No Engagement, N/A. Provides dashboard visibility AND informs other metrics' trigger logic.

## Baseline Metrics — Always Recommend

Every agent should have these predefined metrics enabled:

| Metric | Purpose |
|--------|---------|
| **Expected Outcome** | Checks if the agent achieved the scenario's expected result |
| **Infrastructure Issues** | Flags silent periods, connection drops, agent non-response |
| **Tool Call Success** | Monitors whether tool calls succeed or fail |
| **Latency** | Measures response time |

**Two-step activation required:** (1) toggled on at project level AND (2) added to individual evaluators.

## Cost Guard

**Never evaluate >100 calls without user confirmation.** Each evaluation costs real money. Before triggering bulk evaluation:
1. Query the call count first (use `page_size=1` and read the count)
2. Report the number to the user
3. If count > 100, stop and ask for explicit approval

Use `page_size` parameter (up to 200) instead of paginating through multiple pages. Use server-side filters (`agent_id`, `project`, `timestamp__gte`/`timestamp__lte`) to scope calls.

## Trigger Design

| Trigger Type | When to Use |
|-------------|-------------|
| `"always"` | Metrics that apply to every call |
| `"custom"` with `llm_judge` trigger | Conditional metrics — include negative exclusions |
| `"automatic"` | Let Cekura auto-determine (less control) |

**Best practice: include negative exclusions in triggers.** Don't just state what should trigger — list explicit "Do NOT trigger if..." cases. Short calls under 30 seconds, voicemails, wrong call types, and line disconnections should be gated in the trigger, not the metric prompt.

## Key Patterns

### VALID_SKIP Pattern
For legitimate deviations where the metric should not apply. The LLM returns "VALID_SKIP:" prefix and the custom_code wrapper converts to `_result = None`.

### Gated Metrics
Access upstream metric results via `data.get("Exact Metric Name")`. Key must match exactly.

### Metadata Field Migration
Clients rename fields without backfilling. When this happens, metrics must reference both old and new field names with priority logic. The trigger should fire if EITHER field is populated.

## Manual Fix First, Then Labs

When metrics have systemic issues (high false-fail rates), do NOT jump straight to labs feedback. Instead:
1. Read failure explanations and categorize root causes
2. Write manual prompt fixes targeting dominant failure categories (add SCOPE & FOCUS, DO NOT FLAG, narrow FAILURE CONDITIONS)
3. PATCH the updated descriptions via API
4. Re-evaluate a sample of 20-30 calls per metric to validate
5. THEN use labs feedback for remaining edge cases

## Labs Improvement Cycle

For edge case refinement after manual fixes are validated:

1. **Identify misalignment** — Find calls where metric results seem wrong
2. **Leave feedback** — Vote agree/disagree with explanation on specific results (6+ needed)
3. **Run auto-improve** — Labs uses feedback to suggest metric prompt changes
4. **Validate** — Re-run improved metric on the same calls to verify
5. **Deploy** — Optionally convert to custom_code with section extraction for production

## Output Requirements

All metrics must require:
- Brief explanation of the result
- For failures: specific timestamps in MM:SS format
- For metadata-based checks: reference the specific metadata fields examined

## Metrics API Reference

### Key Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/metrics/` | Create metric |
| GET | `/test_framework/v1/metrics/` | List metrics (filter by agent/project) |
| GET | `/test_framework/v1/metrics/{id}/` | Get metric |
| PATCH | `/test_framework/v1/metrics/{id}/` | Update metric |
| DELETE | `/test_framework/v1/metrics/{id}/` | Delete metric |
| POST | `/test_framework/v1/metrics/generate_evaluation_trigger/` | Auto-generate trigger |
| POST | `/observability/v1/call-logs/evaluate_metrics/` | Evaluate metrics on calls |
| POST | `/observability/v1/call-logs-external/{id}/mark_metric_vote/` | Leave feedback |
| POST | `/test_framework/metric-reviews/process_feedbacks/` | Run labs auto-improve |
| GET | `/test_framework/metric-reviews/process_feedbacks_progress/` | Poll improvement progress |
| POST | `/test_framework/test-sets/create_from_call_log/` | Create test set from call |

### Metric Score Interpretation
On `evaluation.metrics[]` entries: `score` field (0 = FAIL, 5 = PASS, None = N/A). `trigger_failed: true` in `extra` means the trigger didn't fire (N/A before metric ran).

### Labs `create_from_call_log` Format
`metrics` must be an array of objects: `[{"metric": <id>, "feedback": "<text>"}]`, NOT bare IDs.

---

# PART 2: EVALUATOR DESIGN

## The Eval Design Workflow

1. **Understand the agent** — Read the agent description to identify all workflows, decision points, and edge cases
2. **Choose a tool strategy** — Ask the user which of the three approaches below
3. **Create a folder first** — Always create a folder before generating or creating scenarios
4. **Run the pre-creation checkpoint** — Confirm tool strategy, test profile, run mode, personality, adaptive vs conditional, folder, metrics
5. **Auto-generate first (recommended)** — Use the generate endpoint with `folder_path` set
6. **Review and fix** — PATCH `scenario_language` for non-English, fix `first_message` if auto-gen added greetings
7. **Set up test infrastructure** — Test profiles + tool data per chosen strategy
8. **Supplement manually** — Add edge cases, red-team, deterministic tests
9. **Attach metrics** — Always include baseline metrics
10. **Run and validate** — Execute, review transcripts, iterate

## Tool Strategy — Three Approaches

Ask the user early: "How do you want to handle your agent's tool calls during testing?"

### A) Client-Side Mock Data
Client manages their own staging backend. Cekura doesn't mock tools — the agent calls real (staging) endpoints. Your job: **align test profiles with the client's staging data** (names, IDs, date formats must match exactly). No Cekura mock tools needed.

### B) Cekura Mock Tools
Cekura intercepts tool calls and returns pre-configured responses. Your job: **auto-fetch tools, add per-scenario mappings, derive test profiles FROM mock outputs.** Use auto-gen with mock tools enabled for tool-aware scenarios. Validate runs by checking tool calls in transcripts.

### C) No Mock Data
Agent doesn't use tools, or tools aren't relevant to these tests. Use test profiles for caller identity only. Focus scenarios on conversational behavior, not tool outcomes.

## Auto-Generation (Primary Path)

The fastest path to test scenarios. Use the generate endpoint with category guidance:

```json
POST /test_framework/v1/scenarios/generate-bg/
{
  "agent_id": <id>,
  "num_scenarios": 10,
  "personalities": [693],
  "generate_expected_outcomes": true,
  "tool_ids": ["TOOL_END_CALL", "TOOL_END_CALL_ON_TRANSFER"],
  "extra_instructions": "Focus on: scheduling workflows, error handling, edge cases",
  "folder_path": "Generated Scenarios"
}
```

Poll progress at `GET /test_framework/v1/scenarios/generate-progress/?progress_id=<id>`.

**Gotchas:**
- `personality` is required (400 without it). Default: 693 (Normal Male, English)
- Generation can partially complete — check progress, generate remainder in smaller batch
- `scenario_language` defaults to "en" regardless of content — PATCH to correct code after generation
- Auto-gen may add greetings to `first_message` instead of exact questions — PATCH after

## Test Profiles — Always Use Them

**Never hardcode identity data in scenario instructions.** Names, DOBs, account IDs, addresses, phone numbers — all belong in test profiles.

**Always check for existing test profiles first.** Clients often pre-build profiles tested against their backend.

**Test profile data must match mock tool outputs exactly.** The DOB in the test profile must match the DOB in the mock tool output for that user.

## Writing Instructions

Write in **first person** from the testing agent's perspective. Wrap in `<scenario>` tags:

```
<scenario>
SCENARIO: [Brief scenario name]

YOUR BEHAVIOR:
1. State your intent to [action]
2. Confirm you are the patient when asked
3. Say and spell your first name when asked for verification
4. Provide your date of birth when asked
5. If the agent says no slots are available, say you are flexible with timing

KEY INTERACTION POINTS:
[Specific workflow nodes or edge cases to exercise]
</scenario>
```

### Common Instruction Mistakes

- **Hardcoding profile data in instructions** — When data is in both places and they differ, the testing agent hallucates
- **Using instructions for voice characteristics** — "speak in a mumbling voice" does nothing. Use **personalities**
- **Including examples of what the main agent "may say"** — Reference actions by topic instead
- **Voice-specific instructions in text scenarios** — "speak naturally" has zero effect on text-based testing
- **Multi-action steps** — Split "give wrong DOB, then correct it" into separate conditional steps

## Mock Tools

When the agent calls external APIs, mock tools provide predictable responses during testing.

### Auto-Fetch (Recommended for VAPI/Retell/ElevenLabs)
In Cekura UI: Agent Settings > Mock Tools > Auto-Fetch. Cekura pulls tool definitions from the provider.

### Manual Setup
Create mock tools with input/output mappings. **Critical rules:**
- `name` must exactly match the tool name in the agent description
- **Per-input branching is required** — A single input/output mapping per tool is NOT enough. If a tool accepts different parameters that should return different results (different users, topics, actions), each variant needs its own mapping. Without branching, every call returns the same output regardless of input.
- **Phone format variants** — Add mappings for ALL formats: 10-digit, 11-digit with leading 1, full E.164
- **Chain dependencies** — Downstream tools must have matching data for IDs returned by upstream tools
- **Append-not-replace** — When PATCHing `information` array, GET existing data first, merge, then PATCH

## Pre-Creation Checkpoint — Confirm Before Building

**Before creating or generating scenarios, always pause and confirm key decisions with the user.** Do not assume defaults:

1. **Tool strategy** — A (client-side staging), B (Cekura mock tools), or C (no mocks)?
2. **Test profile** — Show the full `information` dict. For A: match client's staging data formats. For B: derive FROM mock tool outputs. For C: caller identity only.
3. **Run mode** — Default to text/chat (cheapest, same logic coverage). Voice only when explicitly needed.
4. **Personality** — Default: 693 (Normal Male English). Note exceptions but don't change without asking.
5. **Adaptive vs conditional** — Default to adaptive. Only use conditional actions for explicit unit-test needs.
6. **Folder** — Name the folder.
7. **Metrics** — Confirm baseline metrics attachment.

Skipping this checkpoint leads to wrong tool strategy, data mismatches, wasted voice credits, and rework.

## Tool Enablement — Critical for Credit Efficiency

| Tool | When to Enable | Why |
|------|---------------|-----|
| `TOOL_END_CALL` | Testing agent should terminate after objective | Without this, calls run until timeout |
| `TOOL_END_CALL_ON_TRANSFER` | Main agent transfers to human/IVR | Prevents dead call time |
| `TOOL_DTMF` | Flow involves IVR/phone menus | Allows touch-tone inputs |

**VAPI agents use prefixed IDs** (e.g., `VAPI_TOOL_END_CALL`), not generic names.

## Expected Outcomes

- Agent-centric: "Agent books appointment and provides arrival instructions"
- Specific and measurable: Include concrete actions
- **Keep concise** — overly specific prompts (exact dates/times) cause false failures

## Execution Modes

| Mode | Speed | Cost | Best For |
|------|-------|------|----------|
| Voice | Slow | High | Final validation |
| Text/Chat | Fast | Low | Logic testing, rapid iteration |
| WebSocket | Medium | Medium | Real-time agents |
| Pipecat | Medium | Medium | Pipecat framework agents |

## Evaluator API Reference

### Key Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/scenarios/` | Create evaluator |
| GET | `/test_framework/v1/scenarios/` | List evaluators |
| GET | `/test_framework/v1/scenarios/{id}/` | Get evaluator |
| PATCH | `/test_framework/v1/scenarios/{id}/` | Update evaluator |
| DELETE | `/test_framework/v1/scenarios/{id}/` | Delete evaluator |
| POST | `/test_framework/v1/scenarios/generate-bg/` | Auto-generate evaluators |
| GET | `/test_framework/v1/scenarios/generate-progress/` | Poll generation progress |
| POST | `/test_framework/v1/scenarios/run_scenarios/` | Run scenarios |
| POST | `/test_framework/v1/scenarios/create_folder/` | Create scenario folder |

### Other Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/test-profiles/` | Create test profile |
| GET | `/test_framework/v1/test-profiles/?agent_id=ID` | List profiles |
| GET | `/test_framework/v1/personalities/` | List personalities |
| GET | `/test_framework/v1/results/` | List run results |
| GET | `/test_framework/v1/results/{id}/` | Get run details |
| GET | `/observability/v1/call-logs-external/?agent=ID` | List calls |
| GET | `/observability/v1/call-logs-external/{id}/` | Get call + transcript |

### Agent Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/aiagents/` | Create agent |
| GET | `/test_framework/v1/aiagents/` | List agents |
| GET | `/test_framework/v1/aiagents/{id}/` | Get agent |
| PATCH | `/test_framework/v1/aiagents/{id}/` | Update agent |
| POST | `/test_framework/v1/aiagents/{id}/tools/` | Create mock tool |
| GET | `/test_framework/v1/aiagents/{id}/tools/` | List mock tools |

## Conditional Actions — Deterministic Evaluators

Use conditional actions when the user needs a scenario that runs identically each time: unit tests, regression tests, IVR navigation, compliance testing. For adaptive/exploratory scenarios use behavioral instructions instead.

**When to use:** Exact flow validation, deterministic regression, IVR nav, compliance.
**When NOT to use:** Natural conversation quality, edge cases, red-team — use behavioral instructions.

### Structure

The `instructions` field of the scenario payload becomes a JSON object (not a string):

```json
{
  "instructions": {
    "role": "You are a patient calling to cancel their appointment",
    "conditions": [...]
  }
}
```

### Condition Fields — All Five Required on Every Condition

| Field | Type | Notes |
|-------|------|-------|
| `id` | integer | Unique. First condition must be 0. |
| `condition` | string or integer | `"FIRST_MESSAGE"` for id:0 (always required, even when agent speaks first). Trigger description for standard. Prior condition's integer ID for action_followup. |
| `action` | string | Exact text (`fixed_message:true`) or behavioral instruction (`fixed_message:false`). |
| `type` | string | `"standard"` or `"action_followup"`. **Required — no default.** Omitting returns a validation error. |
| `fixed_message` | boolean | `true` = spoken verbatim; `false` = natural language instruction. Required. |

When the main agent speaks first (IVR/voicemail), set id:0 `action: ""` — the testing agent waits.

### Action Types

- **`standard`** — fires when conversation context matches the condition string
- **`action_followup`** — fires immediately after a prior action; `condition` is the integer ID of that prior condition. Use for multi-part responses and `<interruption>`.

### XML Tags (fixed_message:true only)

| Tag | Behavior |
|-----|---------|
| `<ivr text="..." />` | Uninterruptible IVR message. **Must be entire action.** |
| `<voicemail text="..." />` | Uninterruptible + beep at end. **Must be entire action.** Post-beep message goes in a separate action_followup. |
| `<dtmf digits="..." />` | Send touch-tone digits |
| `<endcall />` | Terminate call |
| `<silence time="Xs" />` | Pause on caller's turn — interruptible; background noise continues |
| `<hold time="Xs" />` | Dead air — not interruptible; background noise stops |
| `<spell>TEXT</spell>` | Spell letter-by-letter |
| `<interruption time="Xs" />` | Cut in Xs after agent starts speaking. **Must be action_followup AND at start of action string.** |
| `<speed ratio="N" />` | Speech rate 0.8–1.2. Must start action. |
| `<volume ratio="N" />` | Volume 0–2. Must start action. Cartesia only. |
| `<network_simulation packet_loss="N" />` | Only `packet_loss` supported — `jitter`/`latency` are ignored. |
| `<background_noise sound="NAME" volume="0.x">text</background_noise>` | 29 sounds available (e.g. `coffee-shop`, `office-ambience`, `rain-thunder`) |
| `<noise sound="NAME" />` | One-shot effect: `office`, `beep`, `cough1`, `cough2` |

### Test Profile Variables in Fixed Messages

Inject test profile data into verbatim text: `"My name is {{test_profile.first_name}} {{test_profile.last_name}}"`. Also works nested (`{{test_profile.address.city}}`) and with XML tags (`<spell>{{test_profile.account_number}}</spell>`).

### Key Anti-Patterns

- **Multiple branches in one evaluator** — Each path (success/failure) is a separate evaluator
- **XML tags with `fixed_message:false`** — Tags only parse when `fixed_message:true`
- **`<ivr>` or `<voicemail>` combined with other text/tags** — Must be the entire action
- **`<interruption>` not at start of action or not as `action_followup`** — Both constraints required
- **`<network_simulation>` with `jitter`/`latency`** — Only `packet_loss` is supported
- **Missing `type` field** — Required on every condition, no default
- **No `<endcall />` at end** — Calls run to timeout without it

---

# PART 3: COMMON ANTI-PATTERNS

These recurring mistakes are identified from real customer feedback. Proactively guard against them:

1. **Hardcoded identity data in instructions** — Names, DOBs, addresses hardcoded instead of using test profiles. Causes testing agent hallucinations when data conflicts.
2. **Missing end call tools** — `TOOL_END_CALL` / `TOOL_END_CALL_ON_TRANSFER` not enabled. Calls run until timeout, wasting credits.
3. **Using instructions for voice** — "speak in a mumbling voice" in instructions has no effect — use personalities.
4. **Missing baseline metrics** — No Expected Outcome metric attached. Runs report pass based on call completion, not agent behavior.
5. **Including agent speech examples** — `When the agent says "How can I help you"...` is brittle — reference actions by topic.
6. **Missing test profiles for outbound/websocket** — Profile fields are sent as dynamic variables to the main agent.
7. **Overly specific expected outcomes** — Exact dates/times cause false failures. Focus on behavioral outcomes.
8. **Not checking existing test profiles** — Creating duplicates when clients already built and tested profiles.
9. **Using custom_code for checks LLMs handle naturally** — Voice AI has messy timing. LLMs handle nuances better.
10. **Writing metrics without reading real transcripts** — Always fetch and study actual transcript_json first.
11. **Cross-pollination in metrics using `{{agent.description}}`** — Without SCOPE & FOCUS + DO NOT FLAG + FAILURE CONDITIONS layers, the LLM reads the entire description and fails based on rules from unrelated flows.
12. **Using full `{{metadata}}` blob instead of dot notation** — Dumps 5-10KB of irrelevant data. Use `{{metadata.fieldName}}`.
13. **Evaluating agent outcome instead of effort** — External factors (connection drops, STT failures) aren't the agent's fault. Evaluate whether the agent was TRYING.
14. **Flow-specific metrics with `always` trigger** — Metrics that only apply to certain flows should use custom triggers to avoid evaluating every call.
15. **Empty agent descriptions** — Agent has description "." or empty, rendering `{{agent.description}}` metrics useless.
16. **Obs-enabled metrics on non-production projects** — Each obs-enabled metric costs ~0.2 credits per call. Audit all projects.
