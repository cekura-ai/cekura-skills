---
name: cekura-eval-design
description: >
  Use when the user asks to "create an evaluator", "write a test scenario", "design a test case",
  "test my agent", "build eval coverage", "plan a test suite", "create red team tests",
  "set up test profiles", "configure conditional actions", or "run evals". Covers individual
  evaluator design, suite coverage strategy, test profiles, mock-tool data design, conditional
  actions, and best practices for workflow / red-team / edge-case / deterministic test types.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.3.0"
---

# Cekura Eval Design

## Purpose

Guide the creation of effective Cekura evaluators (test scenarios) that thoroughly exercise AI voice agent capabilities. Evaluators simulate callers to test the main agent — they are NOT metrics (which evaluate transcripts after the fact).

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

## Core Terminology

- **Main agent**: The client's AI voice agent being tested
- **Testing agent**: Cekura's simulated caller that exercises the main agent
- **Evaluator/Scenario**: A test case defining what the simulated caller does and what success looks like
- **Metric**: A post-call evaluation that scores a transcript (separate concept — see cekura-metrics plugin)
- **Personality**: Voice, language, accent, and behavioral traits for the simulated caller
- **Test Profile**: Identity and context data passed to testing agent AND main agent (for chat/websocket runs)
- **Conditional Action**: Structured, deterministic testing agent behavior with adaptive fallback

## The Eval Design Workflow

1. **Understand the agent** — Read the agent description (GET the agent record) to identify all workflows, decision points, and edge cases
2. **Choose a tool strategy** — Ask the user which approach they want for handling the agent's external tool calls. This is a fundamental decision that shapes everything else. See "Tool Strategy — Three Approaches" below.
3. **Always create a folder first** — Before generating or creating scenarios, create a folder to organize them. Never dump scenarios into the root. POST to the scenarios folder endpoint with `name`, `project_id`, and optionally `parent_path`. Then pass the `folder_path` to the generate endpoint or set it on individual scenarios.
4. **Run the pre-creation checkpoint** — Confirm all key decisions with the user before building anything. See "Pre-Creation Checkpoint" below.
5. **Start with generate API (primary path)** — Use `POST /test_framework/v1/scenarios/generate-bg/` to auto-generate evaluators. Provide category-level guidance in `extra_instructions`. If using Cekura mock tools, the generator creates tool-aware scenarios automatically. See "Auto-Generation" section below.
6. **Review and fix generation artifacts** — PATCH `scenario_language` for non-English scenarios (defaults to "en" regardless of content). PATCH `first_message` if auto-gen added greetings instead of exact questions. Check for partial completion (generation may produce fewer than requested).
7. **Supplement manually** — Add edge cases, red-team scenarios, and deterministic tests that the generator doesn't cover
8. **Set up test infrastructure** — Check existing test profiles first, then create new ones. Configure tool data according to the chosen tool strategy.
9. **Attach metrics** — ALWAYS include baseline metrics (Expected Outcome, Infrastructure Issues, Tool Call Success, Latency) on every evaluator. Without metrics, runs only report call completion, not correctness.
10. **Run and validate** — Execute via `run_scenarios`, review transcripts, iterate

## Tool Strategy — Three Approaches

**Ask the user early:** "Does your agent call external tools during calls? If so, how do you want to handle tool data for testing?"

| Approach | When to use | Your job |
|---|---|---|
| **A. Client-side mock data** | Client has staging API/test DB | Align test profiles with their mock data |
| **B. Cekura mock tools** | No staging, want predictable isolated tests | Set up mock mappings + match test profiles to outputs |
| **C. No mock data** | Conversational-only agents, testing tone/soft skills | Use test profiles for identity only |

**Critical rule for Approach B**: derive test profile values FROM mock outputs (same format, same values). Creating them independently guarantees mismatches.

**See `references/tool-strategies.md`** for full workflow, key questions to ask, and validation guidance for each approach.

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

- **Filler steps that add nothing** — NEVER write steps like "Listen to the agent's response", "Wait for the agent to speak", "End the call politely", or "Respond accordingly". The testing agent already does these things automatically. Every step must describe a **specific action the caller takes** — information they provide, a decision they make, or a behavior they exhibit. If a step doesn't tell the caller to DO something specific, delete it.
- **Hardcoding profile data in instructions** — Names, DOBs, addresses, account numbers belong in test profiles, not instructions. When data is in both places and they differ, the testing agent hallucates. This is the single most common mistake across clients.
- **Using instructions for voice characteristics** — Instructions like "speak in a mumbling voice" or "be interruptive" don't change the testing agent's vocal style. Use **personalities** for that — they control actual voice model parameters (accent, interruption level, background noise, speed).
- **Including examples of what the main agent "may say"** — Don't write `When the agent says "How can I help you", respond with...`. Instead, reference action points by topic: `When asked about what you need help with, explain that you need help with your billing address.` The former is brittle; the latter works regardless of exact agent phrasing.
- **Not providing enough context for multi-step flows** — If a scenario involves a complex process (scheduling, onboarding), the testing agent needs step-by-step context to avoid hallucinating after the first few steps. For structured flows, use conditional actions instead.
- **Vague or generic instructions** — "Call to schedule an appointment" is useless. Be specific: what type of appointment, what constraints, what complications should arise. The more specific the scenario, the more useful the test.
- Third-person perspective instead of first person
- Too scripted (exact dialogue) instead of behavioral goals
- Missing edge case triggers

### Bad vs Good Instructions

**BAD** (filler, vague, passive):
```
<scenario>
1. When the agent asks to confirm your identity and whether you are the intended person, clearly state: "No, you have the wrong number."
2. Listen to the agent's response.
3. End the call politely.
</scenario>
```

**GOOD** (every step is a specific caller action):
```
<scenario>
SCENARIO: Wrong number — caller is not the intended recipient

YOUR BEHAVIOR:
1. When the agent asks for your name or tries to verify your identity, say this is the wrong number and you don't know the person they're looking for
2. If the agent asks for any additional information, decline — you have no connection to the intended person
3. If the agent apologizes and offers to remove your number, confirm that's fine
</scenario>
```

**BAD** (generic, no specifics):
```
<scenario>
1. Call to schedule an appointment.
2. Provide your information when asked.
3. Confirm the appointment.
</scenario>
```

**GOOD** (specific scenario with constraints):
```
<scenario>
SCENARIO: New adult patient scheduling with insurance

YOUR BEHAVIOR:
1. State you're a new patient and need to schedule a first visit with a primary care provider
2. When asked about insurance, say you have Blue Cross PPO
3. Provide your date of birth and spell your full name when asked for verification
4. Request a morning appointment if given timing options
5. If no morning slots are available, accept the earliest available afternoon slot
6. Confirm the appointment details when the agent reads them back

KEY INTERACTION POINTS:
- New patient registration flow
- Insurance verification
- Appointment slot selection with preference constraints
</scenario>
```

## Auto-Generation (Primary Path)

The `POST /test_framework/v1/scenarios/generate-bg/` endpoint is the preferred workflow for bulk scenario creation.

**Full schema:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | integer | Yes | Agent to generate scenarios for |
| `num_scenarios` | integer | Yes | How many to generate |
| `extra_instructions` | string | No | Category-level guidance (e.g., "focus on cancellation edge cases") |
| `personalities` | array[integer] | No | Personality IDs to use |
| `generate_expected_outcomes` | boolean | No | Auto-generate expected outcomes |
| `folder_path` | string | No | Folder to place generated scenarios in (**always set this** — create the folder first) |
| `tags` | array[string] | No | Tags to apply to all generated scenarios |
| `tool_ids` | array[string] | No | Tools to enable (e.g., `TOOL_END_CALL`) |

**Returns:** `{"progress_id": "<uuid>"}`. Poll with `GET /test_framework/v1/scenarios/generate-progress/?progress_id=<id>`.

**Response has:** `total_scenarios`, `completed_scenarios`, `failed_scenarios`, `scenarios_list`.

### Generation Gotchas

1. **Generation can partially complete** — May produce fewer scenarios than requested (e.g., 15/18) with the remainder stuck. After a reasonable timeout, generate the remainder in a smaller batch with more specific `extra_instructions`.

2. **`scenario_language` defaults to "en"** — Auto-gen sets all scenarios to English even when `extra_instructions` specify non-English languages. PATCH each scenario with the correct language code (`ru`, `hi`, `es`, `zh`, `ko`, `pt`, `de`, etc.) after generation. This is required for correct TTS voice/pronunciation.

3. **Auto-gen may add greetings to `first_message`** — When `extra_instructions` specify exact verbatim questions, some scenarios get a greeting (e.g., "Здравствуйте") as the `first_message` while the actual question is in instructions as a follow-up. PATCH `first_message` after generation.

4. **Language-specific personalities may not be enabled per-project** — Non-English personalities (e.g., ID 4566 for Russian) may return "Personality is not enabled" errors. Workaround: use personality 693 (Normal Male English) and rely on `scenario_language` + instructions to drive the language.

5. **Mock tool awareness** — When mock tools are enabled on an agent, the generate endpoint creates tool-aware scenarios automatically.

## Personality — Required Field

**`personality` is required on every scenario** — the API returns 400 if missing.

**Recommended defaults:**
- **English:** 693 (Normal Male, en/American)
- **Spanish:** 362 (Normal Spanish Male)
- **Other languages:** Use 693 + set `scenario_language` to the correct code. The platform uses `scenario_language` for TTS, not just personality.

List available personalities with `GET /test_framework/v1/personalities/`.

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

## Pre-Creation Checkpoint — Confirm Before Building

**Before creating scenarios or generating them, always pause and confirm key decisions with the user.** Do not assume defaults — present your plan and get explicit approval. AI agents that skip this step make costly assumptions that waste credits and require rework.

### What to Confirm

Present a checkpoint like this before proceeding:

1. **Tool strategy** — "How do you want to handle your agent's tool calls during testing?"
   - **A) Client-side mock data** — You manage your own staging backend; I'll align test profiles with your test data
   - **B) Cekura mock tools** — Cekura intercepts tool calls and returns mock responses; I'll set up the mappings
   - **C) No mock data** — Tools aren't relevant to these tests; we'll focus on conversational behavior

2. **Test profile** — "Want me to create `<profile-name>` with these fields?" Show the full `information` dict. For Approach A: fields must match client's staging data formats. For Approach B: fields must match Cekura mock tool outputs exactly (derive FROM mock data). For Approach C: only caller identity fields needed.

3. **Run mode** — "Default to text/chat for the first pass? It's cheapest, and since tools are mocked the results are the same as voice for logic validation." Recommend text unless the user specifically needs voice testing (latency, interruption handling, TTS quality).

4. **Personality** — "Keep the default English personality (693) for all scenarios?" Note any scenarios that might benefit from a different personality (e.g., red-team scenarios with a more aggressive caller), but don't make that change without asking.

5. **Adaptive vs conditional** — "All scenarios above are adaptive (behavioral instructions). None need conditional actions since we're testing decision boundaries, not exact scripts. Confirm that matches your intent?" Only use conditional actions when the user explicitly wants deterministic/repeatable unit-test-style flows.

6. **Folder** — "I'll create a folder called `<name>` to organize these scenarios."

7. **Metrics** — "I'll attach the baseline metrics (Expected Outcome, Infrastructure Issues, Tool Call Success, Latency) to all scenarios."

### Why This Matters

Without checkpoints, the AI agent will:
- Pick the wrong tool strategy (setting up Cekura mocks when the client has a staging backend, or ignoring tools when they're critical)
- Create test profiles with fields that don't match mock/staging data (authentication failures)
- Default to voice mode when text would be 10x cheaper for the same coverage
- Use conditional actions when adaptive instructions are more appropriate
- Scatter scenarios without folder organization
- Skip metric attachment (producing useless runs)

**One checkpoint before creating saves multiple rounds of rework after.**

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

## Mock Tool Data Design

When using Approach B (Cekura mock tools), the mock-tool data design is critical and load-bearing. Key principles:

- **Per-input branching**: one mapping per distinct input the agent might send; not one mapping per tool
- **Phone format variants**: always add 10-digit, 11-digit-with-1, and E.164 forms (mismatches cause 404s)
- **Append-not-replace**: PATCHing `information` REPLACES the array; always GET → merge → PATCH
- **Test profile alignment**: derive profile values FROM mock outputs, not independently

**See `references/mock-tool-design.md`** for full guidance, examples, the backup-phone pattern, and the phone pool workflow.

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

## Documentation

- Public docs: https://docs.cekura.ai
- LLM-friendly docs: https://docs.cekura.ai/llms.txt
- Concepts: https://docs.cekura.ai/documentation/key-concepts/

See `references/api-reference.md` for complete endpoint documentation including test profiles.

## Create Evaluator from Transcript

Cekura can create an evaluator directly from a real call transcript. This is useful when:
- You have a production call that demonstrates an important scenario
- You want to reproduce a specific customer interaction as a repeatable test
- You want to build regression tests from real-world edge cases

**Endpoint:** `POST /test_framework/v1/scenarios/create_scenario_from_transcript/`

**How it works:** Pass an observability call log ID and the endpoint analyzes the transcript, extracts the caller's behavior, and creates an evaluator that replays a similar conversation. The generated scenario captures the caller's intent, actions, and conversational flow — not an exact script replay.

**When to use:** After reviewing production calls in observability, identify calls that represent important test scenarios (edge cases, failures, complex workflows) and convert them directly into evaluators. This is faster and more accurate than manually writing instructions to reproduce the scenario.

**Post-creation:** Always review the generated evaluator — the auto-extraction may need refinement. Attach metrics, assign a test profile if identity data is involved, set the folder path, and enable tools.

## Session Memory Document

For multi-session eval projects, offer to create a session memory document that captures key decisions (tool strategy, profiles, scenarios, open items) so future sessions don't re-derive context.

**See `references/session-memory.md`** for the template and update workflow.

## Next Steps

After completing eval design, the user typically needs:
- **Run the suite** → execute via the run-scenarios endpoints (see `references/api-reference.md`)
- **Review results** → check transcripts and metric scores
- **Add or improve metrics** → invoke **cekura-metric-design** for new metrics, **cekura-metric-improvement** to refine existing ones
- **Connect a new agent first** → invoke **cekura-create-agent**

## Additional Resources

### Reference Files (loaded on demand)

- **`references/tool-strategies.md`** — Full workflow for Approaches A/B/C
- **`references/mock-tool-design.md`** — Per-input branching, append-not-replace, phone-pool gotchas
- **`references/test-profiles.md`** — Profile creation from real data, template variables
- **`references/conditional-actions.md`** — Conditional actions: XML tags, deterministic patterns
- **`references/coverage-patterns.md`** — Test coverage category breakdowns
- **`references/session-memory.md`** — Multi-session project memory document template
- **`references/api-reference.md`** — Complete API endpoints: scenarios, profiles, results

### Example Files

- **`examples/csv-eval-creation.md`** — CSV-to-evaluator workflow
- **`examples/workflow-eval.md`** — Single workflow evaluator example
- **`examples/red-team-eval.md`** — Red-team evaluator example
