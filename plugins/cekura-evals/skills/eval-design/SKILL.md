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
version: 0.3.0
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

1. **Understand the agent** — Read the agent description (use `mcp__cekura__aiagents_retrieve`) to identify all workflows, decision points, and edge cases
2. **Choose a tool strategy** — Ask the user which approach they want for handling the agent's external tool calls. This is a fundamental decision that shapes everything else. See "Tool Strategy — Three Approaches" below.
3. **Always create a folder first** — Before generating or creating scenarios, create a folder to organize them. Never dump scenarios into the root. Use `mcp__cekura__scenarios_create_folder_create` with `name`, `project_id`, and optionally `parent_path`. Then pass the `folder_path` to the generate endpoint or set it on individual scenarios.
4. **Run the pre-creation checkpoint** — Confirm all key decisions with the user before building anything. See "Pre-Creation Checkpoint" below.
5. **Start with generate API (primary path)** — Use `POST /test_framework/v1/scenarios/generate-bg/` to auto-generate evaluators. Provide category-level guidance in `extra_instructions`. If using Cekura mock tools, the generator creates tool-aware scenarios automatically. See "Auto-Generation" section below.
6. **Review and fix generation artifacts** — PATCH `scenario_language` for non-English scenarios (defaults to "en" regardless of content). PATCH `first_message` if auto-gen added greetings instead of exact questions. Check for partial completion (generation may produce fewer than requested).
7. **Supplement manually** — Add edge cases, red-team scenarios, and deterministic tests that the generator doesn't cover
8. **Set up test infrastructure** — Check existing test profiles first, then create new ones. Configure tool data according to the chosen tool strategy.
9. **Attach metrics** — ALWAYS include baseline metrics (Expected Outcome, Infrastructure Issues, Tool Call Success, Latency) on every evaluator. Without metrics, runs only report call completion, not correctness.
10. **Run and validate** — Execute via `run_scenarios`, review transcripts, iterate

## Tool Strategy — Three Approaches

**Ask the user early:** "Does your agent call external tools during calls? If so, how do you want to handle tool data for testing?"

The answer determines the entire test infrastructure setup. Present these three options:

### Approach A: Client-Side Mock Data

The client manages their own mock backend (staging API, test database, etc.). Cekura doesn't mock the tools — the agent calls the real (staging) endpoints. Your job is to **align test profiles with the client's mock data** so the agent gets expected responses.

**When to use:** Client already has a staging/test environment, doesn't want to replicate their data in Cekura, or their tool behavior is too complex to mock (multi-step state machines, database transactions).

**Workflow:**
1. Ask the user for their mock/staging data — what inputs produce what outputs in their system
2. Create test profiles that match those inputs exactly (names, IDs, phone numbers, dates — all must match what the staging system expects)
3. Verify data formats align: if the client's system expects `MM/DD/YYYY` for DOB, the test profile must use that format, not `YYYY-MM-DD`
4. Scenarios reference test profile data generically ("provide your date of birth when asked") — the testing agent reads from the profile, the agent sends it to the real staging backend
5. No Cekura mock tools needed — leave them disabled

**Key questions to ask the user:**
- "What test data exists in your staging environment? (test users, accounts, etc.)"
- "What format does your system expect for dates, phone numbers, IDs?"
- "Are there specific test accounts I should use, or can we create new ones?"

**Validation:** Run a scenario and check transcript — if the agent says "I couldn't find your account" or gets authentication errors, the test profile data doesn't match the staging system.

### Approach B: Cekura Mock Tools

Cekura intercepts the agent's tool calls and returns pre-configured mock responses. The agent never hits a real backend. Your job is to **set up mock tool mappings and ensure test profiles match the mock outputs**.

**When to use:** No staging environment, want fully isolated tests, need predictable responses for every scenario, or the agent's tools are simple enough to mock (lookups, bookings, CRUD operations).

**Workflow:**
1. **Auto-fetch tools** (recommended for VAPI/Retell/ElevenLabs): In Cekura UI, go to Agent Settings → Mock Tools → Auto-Fetch. Cekura pulls all tool definitions from the provider and generates sample I/O data. Then enable mock mode per tool.
2. **Review auto-fetched mappings** — Use `mcp__cekura__aiagents_tools_list` to see what was created. Each tool has an `information` array of input/output pairs.
3. **Add per-scenario mappings** — Auto-fetch creates illustrative examples, not exhaustive data. For each scenario you'll test, add the specific input/output pairs that scenario needs. If a tool accepts different parameters (different users, topics, actions), each variant needs its own mapping. See "Mock Tool Data Design" below.
4. **Create test profiles FROM the mock data** — Derive all profile fields from mock tool outputs. If `get_user_info` returns `{"first_name": "John", "dob": "01/15/1990"}`, the test profile must have those exact values. Never create profile data independently.
5. **Use auto-gen with mock awareness** — When mock tools are enabled on the agent, the generate endpoint creates tool-aware scenarios automatically. Scenarios will reference the mocked tools in their instructions.
6. **Validate runs** — After running, check transcripts for: tool calls returning expected data, agent using the mock data correctly, no "tool not found" or format mismatch errors.

**Key questions to ask the user:**
- "Can I auto-fetch your tools from the provider, or do we need to set them up manually?"
- "For each tool, what are the different inputs the agent might send?" (per-input branching)
- "Do any tools depend on data from other tools?" (chain dependencies)

### Approach C: No Mock Data

The agent either doesn't use external tools, or the tools aren't relevant to what you're testing. Use test profiles for caller identity but don't worry about tool responses.

**When to use:** Agent is conversational only (no tool calls), testing soft skills/tone/adherence rather than tool-dependent workflows, or tools are optional and the scenario focuses on the dialog path.

**Workflow:**
1. Create test profiles with caller identity data (name, DOB, etc.)
2. Write scenarios focused on conversational behavior, not tool outcomes
3. Expected outcomes should not reference tool results — focus on what the agent says and does
4. If the agent attempts tool calls, they'll hit the real backend (or fail if there's no backend). Decide with the user whether that's acceptable.

**Key questions to ask the user:**
- "Does your agent use any external tools during calls?"
- "Are we testing the tool-dependent workflows, or just the conversational quality?"

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

## Mock Tool Data Design (Approach B Details)

This section applies when the user chose **Approach B: Cekura Mock Tools** in the tool strategy. Skip if using Approach A (client-side) or Approach C (no mocks).

### Per-Input Branching — The Core Concept

Cekura matches incoming tool calls to the closest input in the mock's `information` array and returns the corresponding output. **A single input/output mapping per tool is NOT enough.** If a tool accepts different parameters that should return different results, each variant needs its own mapping.

Example: a `get_user_info` tool needs separate mappings for each test user, plus phone format variants:
```json
"information": [
  {"input": {"phone": "8645239892"}, "output": {"id": "B001", "name": "John Doe", "dob": "01/15/1990"}},
  {"input": {"phone": "18645239892"}, "output": {"id": "B001", "name": "John Doe", "dob": "01/15/1990"}},
  {"input": {"phone": "5551234567"}, "output": {"id": "B002", "name": "Jane Smith", "dob": "03/22/1985"}}
]
```

**Think through the full data graph:** user lookup → account data → transaction history → payment methods. All IDs and references must be consistent across tools.

### Setting Up Mock Tools

1. **List existing tools:** `mcp__cekura__aiagents_tools_list` — check what's already configured
2. **Auto-fetch (if available):** For VAPI/Retell/ElevenLabs, use the UI: Agent Settings → Mock Tools → Auto-Fetch → enable mock mode per tool. This creates tool definitions with sample mappings.
3. **Add per-scenario mappings:** Auto-fetch creates illustrative examples, not exhaustive data. Add the specific input/output pairs each scenario needs via `mcp__cekura__aiagents_tool_partial_update`.
4. **Validate:** Run one scenario and check the transcript — tool calls should return the expected mock data.

### Critical: Append-Not-Replace

When PATCHing a tool's `information` array, you must GET the existing mappings first, append new ones, then PATCH the full combined array. A PATCH with only new mappings **replaces ALL existing mappings**. Always use the GET → merge → PATCH pattern.

### Phone Number ↔ Mock Data Linkage

For inbound agents, the `inbound_phone_number` on the scenario is the number Cekura calls FROM. The agent sees this as `{{customer.number}}` and uses it to look up the caller. **Critical gotcha: phone format mismatches cause 404s.** Add mappings for ALL format variants:
- 10-digit: `8645239892`
- 11-digit with leading 1: `18645239892`
- Full E.164: `+18645239892`

**Backup phone pattern:** When the primary inbound phone doesn't match, add a fallback:
1. Add a simple 555-XXX-XXXX backup phone to mock mappings pointing to the same data
2. Add instruction: "If the agent says they cannot find your account, provide the alternate number XXX-XXX-XXXX"
3. Update test profile with both `customer_phone_number` and `backup_phone_number`

### Test Profile ↔ Mock Data Alignment

Test profiles must have ALL credentials the testing agent needs. If the agent asks for DOB + SSN last 4 + first name + last name, ALL must be in the test profile. Missing fields = the testing agent improvises or fails authentication.

**Always derive test profile values FROM mock data, not independently.** If `get_user_info` returns `{"dob": "01/15/1990"}`, the test profile must have `"dob": "01/15/1990"` — same format, same value. Creating them separately guarantees mismatches.

### Phone Number Pool

Phone numbers are a shared resource. `GET /test_framework/v1/phone-numbers/?project=<id>` — filter for unassigned ones (`scenario_name: null`), US format (`+1` prefix, 12 chars). Assign via `PATCH /scenarios/{id}/` with `inbound_phone_number: <phone_id>`. Each scenario should get a unique phone to avoid mock data collisions.

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

## API Access — Cekura MCP Server

This plugin uses the Cekura MCP server for all API operations. The `.mcp.json` file in this plugin configures it automatically.

**Prerequisites:**
1. Set the `CEKURA_API_KEY` environment variable with your Cekura API key
2. Start the Cekura MCP server: `cd /path/to/cekura-mcp-server && python3 openapi_mcp_server.py` (runs on `http://localhost:8001/mcp`)
3. The plugin's `.mcp.json` handles the rest — Claude Code connects to the server and makes the `mcp__cekura__*` tools available

**Key MCP tools used by this plugin:**
| Operation | MCP Tool |
|-----------|----------|
| List/get agents | `mcp__cekura__aiagents_list`, `mcp__cekura__aiagents_retrieve` |
| Scenario CRUD | `mcp__cekura__scenarios_create`, `mcp__cekura__scenarios_list`, `mcp__cekura__scenarios_partial_update`, `mcp__cekura__scenarios_destroy` |
| Generate scenarios | `mcp__cekura__scenarios_generate_bg_create`, `mcp__cekura__scenarios_generate_progress_retrieve` |
| Run scenarios | `mcp__cekura__scenarios_run_scenarios_create`, `mcp__cekura__scenarios_run_scenarios_text_create` |
| Results | `mcp__cekura__results_list`, `mcp__cekura__results_retrieve` |
| Test profiles | `mcp__cekura__test_profiles_list`, `mcp__cekura__test_profiles_create` |
| Call logs | `mcp__cekura__call_logs_list`, `mcp__cekura__call_logs_retrieve` |
| Personalities | `mcp__cekura__personalities_list` |

**Docs lookup:** Use the `mcp__cekura__search_cekura` tool or fetch `https://docs.cekura.ai/llms.txt` to look up API details, field schemas, or feature documentation when the plugin references don't cover something.

**Troubleshooting:** If MCP tools are not available, verify: (1) `CEKURA_API_KEY` is set, (2) the MCP server is running on port 8001, (3) restart Claude Code to pick up the `.mcp.json` config.

See `references/api-reference.md` for complete endpoint documentation including test profiles.

## Create Evaluator from Transcript

Cekura can create an evaluator directly from a real call transcript. This is useful when:
- You have a production call that demonstrates an important scenario
- You want to reproduce a specific customer interaction as a repeatable test
- You want to build regression tests from real-world edge cases

**Endpoint:** `POST /test_framework/v1/scenarios/create_scenario_from_transcript/`

**MCP tool:** `mcp__cekura__scenarios_create_scenario_from_transcript_create`

**How it works:** Pass an observability call log ID and the endpoint analyzes the transcript, extracts the caller's behavior, and creates an evaluator that replays a similar conversation. The generated scenario captures the caller's intent, actions, and conversational flow — not an exact script replay.

**When to use:** After reviewing production calls in observability, identify calls that represent important test scenarios (edge cases, failures, complex workflows) and convert them directly into evaluators. This is faster and more accurate than manually writing instructions to reproduce the scenario.

**Post-creation:** Always review the generated evaluator — the auto-extraction may need refinement. Attach metrics, assign a test profile if identity data is involved, set the folder path, and enable tools.

## Session Memory Document

When working on a multi-session eval project, offer to create a **session memory document** for the user. This persistent file captures key decisions made during the session so future conversations can pick up where you left off.

**Ask early in the session:** "Would you like me to create a session memory doc? It logs key decisions (eval strategy, mock tool approach, test profile mappings, etc.) so future sessions don't have to rediscover this context."

**If yes, create a file** in the user's working directory (or wherever they prefer) with this structure:

```markdown
# [Project Name] — Eval Session Notes

## Key Decisions
- **Tool strategy:** [A/B/C — with rationale]
- **Mock tool approach:** [auto-fetch / manual / N/A]
- **Default personality:** [ID and name]
- **Default run mode:** [text / voice]
- **Folder structure:** [how scenarios are organized]

## Test Profiles Created
| Profile | ID | Key Fields | Used By |
|---------|----|-----------| --------|

## Scenarios Created
| Name | ID | Type | Status |
|------|----|----|--------|

## Mock Tool Mappings
[Summary of what data exists for which tools]

## Open Items
- [Things to do next session]

## Session Log
- [Date]: [What was done]
```

**Update throughout the session:** As decisions are made, scenarios created, or mock data configured, append to the relevant section. At the end of the session, summarize what was accomplished.

**In future sessions:** Read this file first to restore context. If the user says "continue from last session" or "pick up where we left off", check for this document.

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
