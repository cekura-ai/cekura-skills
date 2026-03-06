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

---

# PART 1: METRIC DESIGN

## The Metric Creation Workflow

Follow this every time. Skipping steps (especially step 2) leads to metrics that miss edge cases.

1. **Gather context** — Understand what the user cares about, get sample conversation IDs with expected outcomes
2. **Fetch real transcripts** — Pull 3-5 actual `transcript_json` records. Study: what roles appear (`Main Agent`, `User`, `Function Call`, `Function Call Result`), what timestamps are available, how tool calls are structured. Metrics written without reading real data will miss edge cases.
3. **Identify the signal** — What specific thing in the transcript indicates pass vs fail?
4. **Write the prompt** — Use proven structures (see below), grounded in what the real transcripts look like
5. **Deploy and test** — Create the metric via API, run on sample conversations, compare to expected outcomes
6. **Iterate** — Adjust the prompt based on results. Plan for at least one iteration.

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

### Structure A: Sectioned (best for multi-criteria metrics)
1. **INPUTS** — Only relevant template variables
2. **SECTIONS** — Numbered evaluation criteria with pass/fail examples
3. **SAFEGUARDING NOTES** — Spirit vs letter overrides
4. **OUTPUT INSTRUCTIONS** — Return format, timestamps for failures

### Structure B: Narrative (best for behavioral/timing metrics)
1. **CONTEXT** — What this call type looks like, why the metric matters
2. **WHAT TO LOOK FOR** — Specific items in the transcript (tool names, phrases, patterns)
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
| `{{dynamic_variables}}` | Custom variables from calls |
| `{{agent.description}}` | Main agent's system prompt |
| `{{metadata}}` | Call metadata |
| `{{call_end_reason}}` | How the call ended |

Include only variables relevant to the specific metric.

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

When uncertain about intent, **ask the user** to clarify before encoding it.

## Baseline Metrics — Always Recommend

Every agent should have these predefined metrics enabled:

| Metric | Purpose |
|--------|---------|
| **Expected Outcome** | Checks if the agent achieved the scenario's expected result |
| **Infrastructure Issues** | Flags silent periods, connection drops, agent non-response |
| **Tool Call Success** | Monitors whether tool calls succeed or fail |
| **Latency** | Measures response time |

**Two-step activation required:** (1) toggled on at project level AND (2) added to individual evaluators. Missing either step means metrics won't fire.

## Common Custom Metrics Worth Suggesting

- **Question stacking / information dumping** — Agent asking 3+ unrelated questions or dumping large blocks of info
- **Workflow adherence** — Agent follows the defined flow steps in order
- **Soft skills** — Tone, empathy, not exposing system internals
- **Business context accuracy** — Agent provides correct business info (hours, addresses, pricing)
- **Transfer/callback handling** — Agent follows proper protocol for transfers

## Trigger Design

| Trigger Type | When to Use |
|-------------|-------------|
| `"always"` | Metrics that apply to every call |
| `"custom"` with `llm_judge` trigger | Conditional metrics (fires when specific intent detected) |
| `"automatic"` | Let Cekura auto-determine (less control) |

## Key Patterns

### VALID_SKIP Pattern
For legitimate deviations where the metric should not apply. The LLM returns "VALID_SKIP:" prefix and the custom_code wrapper converts to `_result = None`.

### Gated Metrics
Access upstream metric results via `data.get("Exact Metric Name")`. Key must match exactly.

### N/A Conditions
Every metric should define when it returns N/A:
- Immediate transfer/human request within first 1-2 exchanges
- Caller hangup before flow begins
- Out-of-scope caller (wrong number, sales call)
- Infrastructure failure preventing flow execution

## Output Requirements

All metrics must require:
- Brief explanation of the result
- For failures: specific timestamps in MM:SS format
- For metadata-based checks: reference the specific metadata fields examined

## Metric Pitfalls

- Writing metrics without reading real transcripts first
- Putting the prompt in `prompt` field instead of `description` for llm_judge
- Using deprecated types (`basic`, `custom_prompt`)
- Using `custom_code` for checks the LLM can handle naturally
- Not matching upstream metric name exactly for gated metrics
- Passing full agent description when only a section is relevant
- No N/A conditions for conditional metrics
- Taking agent description instructions literally instead of capturing their spirit
- Omitting timestamps in failure explanations

## Labs Improvement Cycle

The workflow for improving metric accuracy through iteration:

1. **Identify misalignment** — Find calls where metric results seem wrong
2. **Leave feedback** — Vote agree/disagree with explanation on specific results (6+ needed)
3. **Run auto-improve** — Labs uses feedback to suggest metric prompt changes
4. **Validate** — Re-run improved metric on the same calls to verify
5. **Deploy** — Optionally convert to custom_code with section extraction for production

## Metrics API Reference

### Create Metric
```bash
curl -X POST "https://api.cekura.ai/test_framework/v1/metrics/" \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Metric Name",
    "description": "THE EVALUATION PROMPT GOES HERE",
    "type": "llm_judge",
    "eval_type": "binary_workflow_adherence",
    "agent": 12345,
    "evaluation_trigger": "always"
  }'
```

### Other Metric Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/test_framework/v1/metrics/` | List metrics (filter by agent/project) |
| GET | `/test_framework/v1/metrics/{id}/` | Get metric |
| PATCH | `/test_framework/v1/metrics/{id}/` | Update metric |
| DELETE | `/test_framework/v1/metrics/{id}/` | Delete metric |
| POST | `/test_framework/v1/metrics/generate_evaluation_trigger/` | Auto-generate trigger |
| POST | `/test_framework/v1/metrics/{id}/auto-improve/` | Run labs auto-improve |

### Evaluate Metrics on Calls
```bash
curl -X POST "https://api.cekura.ai/observability/v1/call-logs-external/evaluate_metrics/" \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"call_ids": [123, 456], "metric_ids": [789, 101]}'
```

### Leave Feedback
```bash
curl -X POST "https://api.cekura.ai/observability/v1/call-logs-external/{call_id}/mark_metric_vote/" \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"metric_id": 789, "vote": "disagree", "feedback": "Explanation of why this result is wrong"}'
```

---

# PART 2: EVALUATOR DESIGN

## The Eval Design Workflow

1. **Understand the agent** — Read the agent description to identify all workflows, decision points, and edge cases
2. **Determine testing type** — Adaptive evals (behavioral instructions) or deterministic evals (conditional actions for unit testing)?
3. **Set up test infrastructure** — Check existing test profiles first, then create new ones from real call data
4. **Map coverage categories** — Group scenarios by workflow area
5. **Write evals** — Instructions + expected outcomes + test profiles + tags
6. **Run and validate** — Execute, review transcripts, iterate

## Test Profiles — Always Use Them

**Never hardcode identity data in scenario instructions.** Names, DOBs, account IDs, addresses, phone numbers — all belong in test profiles, not instructions.

Test profiles serve three critical purposes:
1. **Memory persistence** — The testing agent reliably uses profile data. Data in instructions often leads to hallucinations.
2. **Dynamic variables** — For outbound and websocket runs, test profile fields are sent to the main agent as caller context.
3. **Single source of truth** — No conflicting data between profile and instructions.

**Always check for existing test profiles first.** Clients often pre-build profiles tested against their backend.

**Building from real data:** Pull call history, analyze toolcall inputs/outputs, and build profiles from data known to work.

**Template variables:** Use `{{test_profile.field_name}}` or `{{test_profile['key']}}` in instructions.

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

- **Hardcoding profile data in instructions** — The single most common mistake. When data is in both places and they differ, the testing agent hallucates.
- **Using instructions for voice characteristics** — "speak in a mumbling voice" does nothing. Use **personalities** for voice (accent, interruption level, background noise, speed).
- **Including examples of what the main agent "may say"** — Don't write `When the agent says "How can I help you"...`. Reference action points by topic instead.
- **Not providing enough context for multi-step flows** — The testing agent needs step-by-step context for complex processes.
- Third-person perspective instead of first person
- Too scripted (exact dialogue) instead of behavioral goals

## Tool Enablement — Critical for Credit Efficiency

| Tool | When to Enable | Why |
|------|---------------|-----|
| `TOOL_END_CALL` | Testing agent should terminate after completing objective | Without this, calls run until timeout, wasting credits |
| `TOOL_END_CALL_ON_TRANSFER` | Main agent transfers to a human/IVR | Prevents dead call time through hold music/voicemail |
| `TOOL_DTMF` | Flow involves IVR/phone menus | Allows touch-tone inputs |

**Always instruct the testing agent to end the call** after completing its objective.

## Personalities — Voice Characteristics

Use **personalities** (not instructions) for vocal style. Personalities manage: language/accent, voice model, interruption level, background noise, speech speed.

Instructions cannot alter speaking style — they only affect what the testing agent says, not how it sounds.

## Expected Outcomes

- Agent-centric: "Agent books appointment and provides arrival instructions"
- Specific and measurable: Include concrete actions
- **Keep them concise** — overly specific prompts (exact dates/times) cause false failures. Focus on behavioral outcomes.

## Execution Modes

| Mode | Speed | Cost | Best For |
|------|-------|------|----------|
| Voice | Slow | High | Final validation, voice-specific testing |
| Text/Chat | Fast | Low | Logic testing, rapid iteration |
| WebSocket | Medium | Medium | Real-time agents |
| Pipecat | Medium | Medium | Pipecat framework agents |

Use text/chat for development iteration. Switch to voice for final validation.

## Eval Types

- **Workflow** — Happy path for each major workflow
- **Deterministic/Unit test** — Conditional actions for repeatable testing
- **Edge case** — Tool failures, retries, boundary conditions
- **Red team** — Prompt injection, social engineering
- **Error handling** — Angry caller, wrong number, clinical questions
- **Multi-language** — Match personality language to agent capabilities

## Evaluator API Reference

### Create Evaluator
```bash
curl -X POST "https://api.cekura.ai/test_framework/v1/scenarios/" \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "S-01: New patient scheduling",
    "personality": 693,
    "agent": 12345,
    "instructions": "<scenario>...</scenario>",
    "expected_outcome_prompt": "Agent books appointment and provides confirmation",
    "metrics": [99637, 115939],
    "tags": ["Scheduling", "must-have", "S-01"],
    "test_profile": 9290,
    "tool_ids": ["TOOL_END_CALL"]
  }'
```

### Other Evaluator Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/test_framework/v1/scenarios/` | List evaluators |
| GET | `/test_framework/v1/scenarios/{id}/` | Get evaluator |
| PATCH | `/test_framework/v1/scenarios/{id}/` | Update evaluator |
| DELETE | `/test_framework/v1/scenarios/{id}/` | Delete evaluator |
| POST | `/test_framework/v1/scenarios/{id}/run-voice/` | Run as voice call |
| POST | `/test_framework/v1/scenarios/{id}/run-text/` | Run as text chat |

### Run Scenarios
```bash
curl -X POST "https://api.cekura.ai/test_framework/v1/scenarios/run_scenarios/" \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": 12345, "scenarios": [111, 222, 333]}'
```

### Test Profile CRUD
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/test-profiles/` | Create test profile |
| GET | `/test_framework/v1/test-profiles/?agent_id=ID` | List profiles |
| PATCH | `/test_framework/v1/test-profiles/{id}/` | Update profile |
| DELETE | `/test_framework/v1/test-profiles/{id}/` | Delete profile |

### Create Test Profile
```bash
curl -X POST "https://api.cekura.ai/test_framework/v1/test-profiles/" \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sarah Johnson - Scheduling",
    "agent": 12345,
    "information": {
      "name": "Sarah Johnson",
      "date_of_birth": "01/01/1990",
      "patient_id": "PT-12345"
    }
  }'
```

### Call Logs (for transcript analysis)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/observability/v1/call-logs-external/?agent=ID` | List calls |
| GET | `/observability/v1/call-logs-external/{id}/` | Get call + transcript |

### Personalities
```bash
curl -X GET "https://api.cekura.ai/test_framework/v1/personalities/" \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY"
```

---

# PART 3: COMMON ANTI-PATTERNS

These recurring mistakes are identified from real customer feedback. Proactively guard against them:

1. **Hardcoded identity data in instructions** — Names, DOBs, addresses hardcoded instead of using test profiles. Causes testing agent hallucinations when data conflicts.
2. **Missing end call tools** — `TOOL_END_CALL` / `TOOL_END_CALL_ON_TRANSFER` not enabled. Calls run until timeout, wasting credits on dead air.
3. **Using instructions for voice** — Writing "speak in a mumbling voice" in instructions. Has no effect — use personalities for voice characteristics.
4. **Missing baseline metrics** — No Expected Outcome metric attached. Runs report pass based on call completion, not whether the agent did the right thing.
5. **Including agent speech examples** — Writing `When the agent says "How can I help you"...`. Brittle — reference actions by topic instead.
6. **Missing test profiles for outbound/websocket** — Without profiles, the main agent has no caller context. Profile fields are sent as dynamic variables.
7. **Overly specific expected outcomes** — Specifying exact dates/times causes false failures. Focus on behavioral outcomes.
8. **Not checking existing test profiles** — Creating duplicates when clients already built and tested profiles against their backend.
9. **Using custom_code for checks the LLM handles naturally** — Voice AI transcripts have messy timing. LLMs handle nuances better than brittle Python parsing.
10. **Writing metrics without reading real transcripts** — Always fetch and study actual transcript_json before writing any metric prompt.
