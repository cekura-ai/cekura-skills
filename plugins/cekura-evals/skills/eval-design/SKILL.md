---
name: Cekura Eval Design
description: >
  Useful when the user asks to "create an evaluator", "write a test scenario", "design a test case",
  "build eval coverage", "plan a test suite", "test my agent", "create red team tests",
  "write workflow tests", "improve eval quality", "what evals do I need", "create test profiles",
  "conditional actions", "run evals",
  or discusses evaluator design, test coverage strategy, scenario instructions,
  expected outcomes, personality selection, test profiles, conditional actions,
  execution modes, or eval best practices for Cekura voice AI agents. Covers creating
  individual evals, planning test suites, configuring test infrastructure (profiles, mocks),
  and designing different eval types (workflow, red-team, edge case, deterministic/unit, etc.).
version: 0.1.0
---

# Cekura Eval Design

## Purpose

Guide the creation of effective Cekura evaluators (test scenarios) that thoroughly exercise AI voice agent capabilities. Evaluators simulate callers to test the main agent — they are NOT metrics (which evaluate transcripts after the fact).

## Core Terminology

- **Main agent**: The client's AI voice agent being tested
- **Testing agent**: Cekura's simulated caller that exercises the main agent
- **Evaluator/Scenario**: A test case defining what the simulated caller does and what success looks like
- **Metric**: A post-call evaluation that scores a transcript (separate concept — see cekura-metrics plugin)
- **Personality**: Voice, language, accent, and behavioral traits for the simulated caller
- **Test Profile**: Identity and context data passed to testing agent AND main agent (for chat/websocket runs)
- **Conditional Action**: Structured, deterministic testing agent behavior with adaptive fallback

## The Eval Design Workflow

1. **Understand the agent** — Read the agent description to identify all workflows, decision points, and edge cases
2. **Determine testing type** — Does the user need adaptive evals (behavioral instructions) or deterministic evals (conditional actions for unit testing)? Ask if not obvious.
3. **Set up test infrastructure** — Check existing test profiles first, then create new ones from real call data
4. **Map coverage categories** — Group scenarios by workflow area
5. **Write evals** — Instructions + expected outcomes + test profiles + tags
6. **Run and validate** — Execute, review transcripts, iterate

## Test Profiles — Always Use Them

**Test profiles are the backbone of reliable evals.** They serve three critical purposes:
1. **Memory persistence** — The testing agent reliably uses profile data during calls. Data in instructions often leads to hallucinations.
2. **Dynamic variables** — For outbound and websocket runs, test profile fields are sent to the main agent as caller context, mimicking what production systems provide. This lets you test the full end-to-end flow.
3. **Single source of truth** — No risk of name in test profile saying "Sarah" while instructions say "John", which causes the testing agent to hallucinate.

**Always use test profiles.** Never hardcode identity data (names, DOBs, account IDs, addresses, phone numbers, service addresses, discrepancy amounts — anything persona-related) in scenario instructions. Instead, create a test profile with the data and let the instructions reference it generically (e.g., "State your name when asked").

**Building test profiles from real data:**
The best approach is to pull call history from observability and/or past eval runs and use data that is known to work:
1. Fetch recent call transcript_json records from the API
2. Analyze toolcall inputs and outputs from real calls
3. Build a memory document mapping existing data (names, account IDs, appointment IDs, etc.)
4. Create test profiles using this verified data
This ensures test profiles work against production tools.

**Always check for existing test profiles first.** Clients often pre-build profiles that are tested against their mock backend — reuse these rather than creating from scratch.

**Template variables in instructions:** Use `{{test_profile.field_name}}` or `{{test_profile['key']}}` for dynamic injection. For nested data: `{{test_profile.address.city}}`. Note: in voice scenarios, the simulated caller reads from the instruction text directly — the profile data is there for the caller to reference, not injected as hidden context.

See `references/test-profiles.md` for full details and the data-extraction workflow.

## Writing Instructions

Instructions tell the testing agent what to do. Write in **first person** from the testing agent's perspective.

### Instruction Style

- First person: "State your name when asked" NOT "The caller should state their name"
- Behavioral, not scripted: "Report fever and cough, request same provider" NOT "Say exactly: I have a fever"
- Reference test profile data: "Provide your date of birth when asked for verification" (the actual DOB comes from the test profile)

### Good Instructions Pattern

Wrap instructions in `<scenario>` tags with a step-by-step format:

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

**Be explicit about exact phrases** when mock/backend behavior depends on them (e.g., `say "follow-up appointment" exactly` if the mock's reason-for-visit matching requires it).

### Common Instruction Mistakes

- **Hardcoding profile data in instructions** — Names, DOBs, addresses, account numbers belong in test profiles, not instructions. When data is in both places and they differ, the testing agent hallucates. This is the single most common mistake across clients.
- **Using instructions for voice characteristics** — Instructions like "speak in a mumbling voice" or "be interruptive" don't change the testing agent's vocal style. Use **personalities** for that — they control actual voice model parameters (accent, interruption level, background noise, speed).
- **Including examples of what the main agent "may say"** — Don't write `When the agent says "How can I help you", respond with...`. Instead, reference action points by topic: `When asked about what you need help with, explain that you need help with your billing address.` The former is brittle; the latter works regardless of exact agent phrasing.
- **Not providing enough context for multi-step flows** — If a scenario involves a complex process (scheduling, onboarding), the testing agent needs step-by-step context to avoid hallucinating after the first few steps. For structured flows, use conditional actions instead.
- Third-person perspective instead of first person
- Too scripted (exact dialogue) instead of behavioral goals
- Missing edge case triggers

## Tool Enablement — Critical for Credit Efficiency

Every evaluator should have the right tools enabled for the testing agent. Missing tools cause elongated calls, wasted credits, and false results.

| Tool | When to Enable | Why |
|------|---------------|-----|
| `TOOL_END_CALL` | When the testing agent should terminate the call after completing its objective | Without this, the testing agent can't hang up — calls run until timeout, wasting credits |
| `TOOL_END_CALL_ON_TRANSFER` | When the main agent transfers to a human/IVR | Without this, the testing agent stays on the line through hold music, voicemail, etc. |
| `TOOL_DTMF` | When the flow involves IVR/phone menus | Allows the testing agent to send touch-tone inputs |

**Always instruct the testing agent to end the call** after completing its objective if `TOOL_END_CALL` is enabled. Otherwise the call continues unnecessarily.

**Transfer scenarios:** If the expected outcome involves a transfer to a human, enable `TOOL_END_CALL_ON_TRANSFER` to prevent dead call time after the transfer completes.

## Personalities — Voice Characteristics

Use **personalities** (not instructions) to control the testing agent's vocal style. Personalities manage:
- Language and accent
- Voice model and provider (ElevenLabs, Cartesia)
- Interruption level (how often the caller interrupts)
- Background noise (office, street, etc.)
- Speech speed and patterns

**Wrong:** `In the instructions, write "speak in a mumbling voice and interrupt frequently"`
**Right:** Select or create a personality with high interruption level and the desired voice characteristics.

Instructions cannot alter actual speaking style — they only affect what the testing agent says, not how it sounds.

## Metrics — Always Attach Baseline Metrics

Every evaluator should have at minimum these metrics enabled:
1. **Expected Outcome** — Evaluates whether the agent achieved what the scenario expected
2. **Infrastructure Issues** — Flags silent periods, connection drops, agent non-response
3. **Tool Call Success** — Monitors whether tool calls succeed or fail
4. **Latency** — Measures response time

**Two-step process:** Metrics must be both (1) toggled on for simulations at the project level AND (2) added to the individual evaluators. Missing either step means the metric won't fire. Use `actions → modify scenarios` to bulk-add metrics to existing evaluators.

Without metrics, runs return success/failure based only on whether the call completed — not whether the agent actually did the right thing. This leads to false passes that require manual review.

## Conditional Actions — Deterministic Testing

Conditional actions create structured, repeatable test flows — essentially unit tests for voice agents. The testing agent follows a predefined structure but adapts if the main agent deviates.

**When to use:** When the user needs a scenario that performs the same way every run (unit testing, regression testing, exact flow validation).

**When NOT to use:** When testing adaptive behavior, general quality, or exploratory scenarios — use behavioral instructions instead.

**Structure:** A conditions array where each entry has an ID, trigger condition, action, type, and fixed_message flag. Supports XML tags for IVR, voicemail, DTMF, silence, and more.

See `references/conditional-actions.md` for full structure, XML tags, and patterns.

## Eval Types

### Workflow Evals (Core)
Happy path for each major workflow. See `references/coverage-patterns.md`.

### Deterministic/Unit Test Evals
Conditional actions for repeatable, structured testing of specific flows.

### Edge Case Evals
Tool failures, multiple items, confirmation rejection, retry exhaustion.

### Red Team Evals
Prompt injection, social engineering, information extraction, off-topic manipulation.

### Error Handling Evals
Angry caller, deceased patient, clinical questions, silent tool failures.

### Multi-Language Evals
Matching personality language to agent capabilities.

## Execution Modes

| Mode | Speed | Cost | Best For |
|------|-------|------|----------|
| **Voice** | Slow | High | Final validation, voice-specific testing (latency, interruptions, TTS quality) |
| **Text/Chat** | Fast | Low | Logic testing, rapid iteration, flow validation without voice overhead |
| **WebSocket** | Medium | Medium | Real-time agents, agents using WebSocket-based providers |
| **Pipecat** | Medium | Medium | Pipecat framework agents |

**Practical guidance:** Use text/chat for development iteration (fast, cheap, tests logic). Switch to voice for final validation before deployment. WebSocket for agents built on WebSocket providers.

**Test profiles in chat/websocket:** Test profile data is passed to the main agent in chat and websocket runs, enabling tool verification without voice calls.

## Tagging Strategy

```
tags: ["Category", "priority-level", "scenario-ID"]
```

**Category codes**: S=Scheduling, RS=Rescheduling, CN=Cancellation, V=Verification, SA=Safety, RT=RedTeam, etc.

## Expected Outcomes

Focus on the main agent's behavior, not the caller's experience:
- Agent-centric: "Agent books appointment and provides arrival instructions"
- Specific and measurable: Include concrete actions (book, transfer, cancel, inform)
- Include follow-up actions: What happens after the primary action
- **Keep them concise** — expected outcomes are evaluated by an LLM judge that checks whether each part was satisfied. Overly specific prompts (e.g., specifying exact dates/times) cause false failures. Focus on the behavioral outcome, not exact details.

## API Access

**Preferred: Cekura MCP server** — If the `cekura-api` MCP server is connected, use its tools directly for all API operations (scenarios CRUD, test profiles, execution, results, call logs). MCP tools provide structured input/output and proper error handling.

**Fallback: bash scripts** — If MCP is not available, use `source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh` for curl-based API calls.

**Docs lookup:** Use the `SearchCekura` MCP tool or fetch `https://docs.cekura.ai/llms.txt` to look up API details, field schemas, or feature documentation when the plugin references don't cover something.

See `references/api-reference.md` for complete endpoint documentation including test profiles.

## Additional Resources

### Reference Files

- **`references/api-reference.md`** — Complete API endpoints: scenarios, test profiles, results
- **`references/coverage-patterns.md`** — Test coverage category breakdowns from real deployments
- **`references/test-profiles.md`** — Test profile guide: creation from real data, template variables, best practices
- **`references/conditional-actions.md`** — Conditional actions: structure, XML tags, deterministic testing patterns

### Example Files

- **`examples/csv-eval-creation.md`** — CSV-to-evaluator workflow (Kouper BCHS pattern)
- **`examples/workflow-eval.md`** — Single workflow evaluator example
- **`examples/red-team-eval.md`** — Red-team evaluator example
