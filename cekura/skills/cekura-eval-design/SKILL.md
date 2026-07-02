---
name: cekura-eval-design
description: >
  Use when the user asks to "create an evaluator", "create evals", "create a scenario",
  "write a test scenario", "design a test case", "test my agent", "build eval coverage",
  "plan a test suite", "create red team tests", "set up test profiles", "configure conditional
  actions", "write a conditional action evaluator", "build a deterministic test", "design an
  IVR test", "IVR navigation test", "write a unit test for a voice agent", "build a regression
  test", "scripted scenario", "scripted voice test", "structured evaluator", "exact flow test",
  "sequential conditions", "fixed sequence test", or "run evals". Covers individual evaluator design, suite coverage
  strategy, test profiles, mock-tool data design, conditional actions (deterministic / unit
  test / regression / IVR navigation flows), and best practices for workflow / red-team /
  edge-case / deterministic test types.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.4.1"
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
5. **Author evaluators — pick the path based on the mode** (per "Choosing Authoring Mode" below):
   - **Behavioral mode (default):** start with auto-generate via `POST /test_framework/v1/scenarios/generate-bg/`. Provide category-level guidance in `extra_instructions`. If using Cekura mock tools, the generator creates tool-aware scenarios automatically. See "Auto-Generation" section below.
   - **Conditional-actions mode:** auto-gen can produce either behavioral or conditional-action scenarios — check the `scenario_type` of generated output and proceed accordingly. When you need full structural control (verbatim phrasing, exact-sequence regression, IVR/voicemail/DTMF flows), author each scenario directly via `POST /test_framework/v1/scenarios/` with `scenario_type: "conditional_actions"` and the `conditional_actions` payload. See "Designing Conditional Actions" below.
6. **Review and fix generation artifacts (only if you ran auto-gen in step 5)** — Check the `scenario_type` of each generated scenario and inspect the corresponding payload (`instructions` for behavioral, `conditional_actions` for conditional-action). PATCH `scenario_language` for non-English scenarios (defaults to "en" regardless of content). PATCH `first_message` if auto-gen added greetings instead of exact questions. Check for partial completion (generation may produce fewer than requested).
7. **Supplement manually** — Add edge cases, red-team scenarios, and deterministic tests that the generator didn't cover, or author additional scenarios directly when you need full structural control.
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

**See `references/test-data-design.md`** for full workflow, key questions to ask, and validation guidance for each approach.

## Choosing Authoring Mode

The default authoring mode is **behavioral instructions** (free-form, first-person scenario instructions). Switch to **conditional actions** in two situations:

### Switch immediately, no confirmation, when the user says any of:

"conditional actions", "structured scenario", "scripted scenario", "scripted test", "deterministic test", "unit test", "regression test", "exact flow", "fixed sequence", "compliance test", "infra test", "infrastructure test", "pipeline test", "CI test", "CI gate", "infra scenario". The user has stated their authoring intent — proceed straight to designing conditional actions (see "Designing Conditional Actions" below).

**Infrastructure and pipeline tests always use conditional actions.** If the user is building tests for STT, VAD, LLM, TTS, interruption handling, idle timers, DTMF, or any other pipeline-layer behavior — switch to conditional actions immediately, no confirmation needed. Behavioral instructions are not deterministic enough to reliably trigger specific pipeline behaviors at the right moment. See the **cekura-infra-test-suite** skill for the full workflow.

### Ask first when the user mentions a tag-supported feature without specifying a mode:

"voicemail", "voicemail test", "IVR menu", "IVR navigation", "DTMF entry", "DTMF input", "hold music", "interruption test", "network simulation", "packet loss", "background noise". Conditional actions support these via dedicated XML tags (`<voicemail>`, `<dtmf>`, etc.) and produce higher-fidelity tests, but a behavioral instruction may also be acceptable. Ask one short question:

> "This involves [voicemail / IVR / DTMF / etc.]. Conditional actions support `<voicemail>` / `<dtmf>` / `<...>` tags directly for high-fidelity testing — should I author this as a conditional-actions evaluator (structured turn-by-turn with the right tags), or behavioral instructions (free-form, looser)?"

### Stay in behavioral mode for:

Open-ended persona dialogue, exploratory red-team without specific attack scripts, soft-skill / tone / empathy testing, general edge-case quality probing where the conversation path isn't predictable. The "Writing Instructions" section below is the primary guide for this mode.

### Concrete examples (which mode for which scenario)

| Scenario the user describes | Default mode | Why |
|---|---|---|
| Appointment scheduling happy path | **Behavioral** | Path is predictable but doesn't need exact phrasing; behavioral lets the testing agent improvise naturally. |
| Appointment scheduling — exact-sequence regression test | **Conditional actions** | "Regression test" is a direct trigger phrase. |
| Compliance disclosure / account-number readback | **Conditional actions** | Verbatim phrasing required (`fixed_message: true` + `<spell>`); "compliance" is a direct trigger phrase. |
| Identity verification with name + DOB + last 4 SSN | **Conditional actions** | Each turn's action is data-bound (read from test profile); structure prevents drift. |
| Inbound IVR menu navigation | **Ask first** | Mentions IVR — could be conditional (high-fidelity, `<dtmf>`) or behavioral (looser); confirm with user. |
| Voicemail handling test | **Ask first** | Mentions voicemail — `<voicemail>` tag is purpose-built but behavioral can work. |
| Angry caller / de-escalation | **Behavioral** | Tone-driven, exploratory; no fixed sequence. |
| Red-team prompt injection (a single attack pattern) | **Conditional actions** | Specific scripted attack; one evaluator per expected outcome. |
| Red-team free-form probing | **Behavioral** | Path not predictable; the agent improvises attacks. |
| Multi-language tone testing | **Behavioral** | Soft-skill evaluation; `scenario_language` set on either mode. |
| Multi-language compliance verification | **Conditional actions** | Verbatim disclosures + language-specific phrasing. |
| Network degradation under packet loss | **Ask first** | Mentions network simulation — `<network_simulation>` tag is purpose-built. |
| Tool failure recovery flow (specific failure + recovery path) | **Conditional actions** | Specific failure trigger + specific recovery step. |
| General "test my agent's quality" | **Behavioral** | No structural commitment specified. |
| Infra / pipeline test (STT, VAD, LLM timeout, interruption, idle timer, DTMF) | **Conditional actions** | Pipeline behaviors must be triggered at exact moments with exact timing — behavioral instructions cannot guarantee this. |

## Test Profiles — Always Use Them

**Test profiles are the backbone of reliable evals.** They serve three critical purposes:
1. **Memory persistence** — The testing agent reliably uses profile data during calls. Data in instructions often leads to hallucinations.
2. **Dynamic variables** — For outbound and websocket runs, the profile's `main_agent_variables` section is sent to the agent under test as dynamic variables (mimicking production); the `testing_agent_variables` section stays with Cekura's simulator as persona/context only.
3. **Single source of truth** — No risk of name in test profile saying "Sarah" while instructions say "John", which causes the testing agent to hallucinate. `test_profile.information.main_agent_variables` is the single source of truth for dynamic variables at call time.

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

See `references/test-data-design.md` for the full profile creation guide, decision matrix for new vs. reuse, and the data-extraction workflow.

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
- **Hardcoding profile data in instructions** — Names, DOBs, addresses, account numbers belong in test profiles, not instructions. When data is in both places and they differ, the testing agent hallucinates. This is the single most common mistake across clients.
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

## Auto-Generation

The `POST /test_framework/v1/scenarios/generate-bg/` endpoint is the preferred workflow for bulk scenario creation. Generated scenarios may come back as either behavioral (`scenario_type: "instruction"`) or conditional-action (`scenario_type: "conditional_actions"`) — check what was created and proceed accordingly. When you need full structural control (verbatim phrasing, exact-sequence regression, IVR/voicemail/DTMF flows), author conditional-action evaluators directly via the create endpoint — see "Designing Conditional Actions" below.

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

4. **Language-specific personalities may not be enabled per-project** — Non-English personalities may return "Personality is not enabled" errors. Workaround: use personality 693 (Normal Male English) and rely on `scenario_language` to drive TTS and pronunciation. See "Checking Available Personalities" under the Personality section.

5. **Mock tool awareness** — When mock tools are enabled on an agent, the generate endpoint creates tool-aware scenarios automatically.

## Personality — Required, Controls Voice Characteristics

**`personality` is required on every scenario** — the API returns 400 if missing. Use **personalities (not instructions)** to control the testing agent's vocal style. Personalities manage:
- Language and accent
- Voice model and provider (ElevenLabs, Cartesia)
- Interruption level (how often the caller interrupts)
- Background noise (office, street, etc.)
- Speech speed and patterns

**Wrong:** putting `"speak in a mumbling voice and interrupt frequently"` in the instructions.
**Right:** select or create a personality with the desired interruption level and voice characteristics.

Instructions cannot alter actual speaking style — they only affect what the testing agent says, not how it sounds.

### Picking the Right Personality

See **`references/choosing-personality.md`** for full selection logic — sustained vs. temporary behaviors, interruption tiers, multilingual matching, enabled/disabled status checks, fallback defaults, and the first-message field.

## Tool Enablement — Critical for Credit Efficiency

Every evaluator should have the right tools enabled for the testing agent. Missing tools cause elongated calls, wasted credits, and false results.

| Tool | When to Enable | Why |
|------|---------------|-----|
| `TOOL_END_CALL` | Recommended by default — so the testing agent can hang up after completing its objective | Without this, the testing agent can't hang up — calls run until timeout, wasting credits |
| `TOOL_END_CALL_ONLY_ON_TRANSFER` | When the main agent transfers to a human/IVR | Without this, the testing agent stays on the line through hold music, voicemail, etc. |
| `TOOL_DTMF` | When the flow involves IVR/phone menus | Allows the testing agent to send touch-tone inputs |

**Always instruct the testing agent to end the call** after completing its objective if `TOOL_END_CALL` is enabled. Otherwise the call continues unnecessarily.

**Transfer scenarios:** If the expected outcome involves a transfer to a human, enable `TOOL_END_CALL_ONLY_ON_TRANSFER` to prevent dead call time after the transfer completes.

## Metrics — Always Attach Baseline Metrics

Every evaluator should have at minimum these metrics enabled:
1. **Expected Outcome** — Evaluates whether the agent achieved what the scenario expected
2. **Infrastructure Issues** — Flags silent periods, connection drops, agent non-response
3. **Tool Call Success** — Monitors whether tool calls succeed or fail
4. **Latency** — Measures response time

**Two-step process:** Metrics must be both (1) toggled on for simulations at the project level AND (2) added to the individual evaluators. Missing either step means the metric won't fire. Use `actions → modify scenarios` to bulk-add metrics to existing evaluators.

Without metrics, runs return success/failure based only on whether the call completed — not whether the agent actually did the right thing. This leads to false passes that require manual review.

## Designing Conditional Actions

When in conditional-actions mode (per "Choosing Authoring Mode" above), set `scenario_type: "conditional_actions"` on the scenario payload and pass `{ "role": "...", "conditions": [...] }` through the `conditional_actions` field — not through `instructions`. The testing agent walks the `conditions` array turn by turn.

### Authoring sequence

Follow these steps in order. Skipping any of them is the most common cause of avoidable rework:

1. **Confirm the path** — inbound vs outbound, who speaks first, what the structural test goal is. Especially for IVR, voicemail, and DTMF scenarios — see the inbound vs outbound split in `references/conditional-actions.md`.
2. **Define the role** — one sentence describing only what the testing agent is pretending to be ("You are a patient calling to cancel an appointment"). Never describe what the main agent is or does — the role is purely the testing agent's persona.
3. **Choose the first turn (`id: 0`)** — does the testing agent speak first (`action: "Hi, I need to..."`, `fixed_message: true`) or does the main agent speak first (`action: ""`, e.g., IVR/voicemail)?
4. **Write standard conditions** — one per agent prompt the testing agent must respond to. Each `condition` is a description of what the agent says; each `action` is the testing agent's response (verbatim with `fixed_message: true`, or behavioral with `false`).
5. **Add `action_followup` and tags as needed** — multi-part responses, interruptions, DTMF, voicemail, silence/hold, network simulation, background noise. Each tag has placement constraints — see the reference's XML Tags table. **Timing:** an `action_followup` fires on the testing agent's **next turn** after its referenced condition — one main-agent reply elapses in between, regardless of the reply's content. It never fires in the same turn as its parent. See `references/conditional-actions.md` for the full rule and worked examples.
6. **Attach the supporting fields on the scenario** — test profile (for any identity data), tools (`TOOL_END_CALL`, `TOOL_DTMF` for IVR, etc.), metrics (Expected Outcome + Infrastructure Issues + Tool Call Success + Latency), personality (`scenario_language` is inherited from it), folder.
7. **Run the validation checklist** — from `references/conditional-actions.md` § Validation Checklist. Catches missing FIRST_MESSAGE, missing `type`/`fixed_message`, XML tag misuse, etc., before you hit the API.

**API payload skeleton (this is what to POST/PATCH to `/test_framework/v1/scenarios/`):**

```json
{
  "agent": 123,
  "personality": 456,
  "name": "CA-01: <descriptive name>",
  "scenario_type": "conditional_actions",
  "scenario_language": "en",
  "conditional_actions": {
    "role": "You are a [persona] calling to [goal]",
    "conditions": [
      { "id": 0, "condition": "FIRST_MESSAGE", "action": "Hi, I need to ...", "type": "standard", "fixed_message": true },
      { "id": 1, "condition": "The agent asks for X", "action": "Provide X", "type": "standard", "fixed_message": false },
      { "id": 2, "condition": "The agent confirms", "action": "Thanks, that's all I needed <endcall />", "type": "standard", "fixed_message": true }
    ]
  }
}
```

Three load-bearing top-level fields:
- **`scenario_type: "conditional_actions"`** — explicit, required. Without this the scenario is created as behavioral and your `conditional_actions` payload is ignored.
- **`conditional_actions`** — JSON object carrying `{role, conditions[]}`. Do not put this object in `instructions`.
- **`scenario_language`** — required for `conditional_actions`. Set explicitly, or rely on the assigned personality's language.

Do not set `first_message` or `instructions` when using `conditional_actions` — they are managed for you.

All five condition fields (`id`, `condition`, `action`, `type`, `fixed_message`) are required on every condition. `id: 0` must use `condition: "FIRST_MESSAGE"` (literal) and `fixed_message: true`; set `action: ""` if the main agent speaks first.

### XML tag constraints (the ones you'll hit most)

- **All XML tags require `fixed_message: true`.** With `false`, the testing agent reads angle brackets as literal text.
- **`<ivr text="..." />` and `<voicemail text="..." />`** (or `<voicemail />` for silent) **must be the entire action** — no surrounding text or other tags. Use a separate `action_followup` for post-IVR / post-beep content.
- **`<interruption time="Xs" />`** requires `type: "action_followup"` AND must be at the **very start** of the action string. It fires `Xs` after the main agent's next turn begins.
- **`<silence time="Xs" />`** is interruptible by the main agent; condition matching restarts after an interrupt. Supports decimal seconds (`"0.5s"`) for sub-second precision. **`<hold time="Xs" />`** is not interruptible; multiple `<hold>` tags allowed in one action.
- **`<dtmf digits="..." />`** supports `0–9`, `#`, `*`; combinable with surrounding text.
- **`<endcall />`** combinable with text — natural sign-offs like `Thanks, that's all I needed <endcall />` work.
- **`<spell>TEXT</spell>`** wraps text to spell letter by letter (good for IDs, account numbers).
- **`<speed ratio="N" />`** range **0.8–1.2**; **`<volume ratio="N" />`** range **0–2** (Cartesia voices only) — both must be at the **start** of the action.
- **`<network_simulation packet_loss="N" />`** — only `packet_loss` is supported.

### Worked example — Linear verification flow

```json
{
  "role": "You are an established patient calling to check your appointment status",
  "conditions": [
    { "id": 0, "condition": "FIRST_MESSAGE", "action": "Hi, I'd like to check on my upcoming appointment", "type": "standard", "fixed_message": true },
    { "id": 1, "condition": "The agent asks for your name", "action": "My name is {{test_profile.first_name}} {{test_profile.last_name}}", "type": "standard", "fixed_message": true },
    { "id": 2, "condition": "The agent asks for your date of birth", "action": "Provide your date of birth", "type": "standard", "fixed_message": false },
    { "id": 3, "condition": "The agent asks for your account number", "action": "My account number is <spell>{{test_profile.account_number}}</spell>", "type": "standard", "fixed_message": true },
    { "id": 4, "condition": "The agent confirms your identity and provides appointment details", "action": "Thank you, that's all I needed <endcall />", "type": "standard", "fixed_message": true }
  ]
}
```

**Pattern → reference map.** For any of these scenario types, see `references/conditional-actions.md` § "Pattern Library by Use Case" for the full worked JSON:

- IVR menu navigation **(inbound vs outbound — patterns differ on whether `id:0 action` is empty or contains `<ivr>`)**, voicemail with post-beep, verification/compliance verbatim, multi-part response, mid-flow pivot, interruption mid-sentence, degraded connection, noisy environment, hostile caller, red-team prompt injection, scripted sequence, multi-language.

**Always load the reference before writing conditions** for: full XML tag rubric (placement, ranges, voice constraints), test profile template-variable syntax, the `<silence>` vs `<hold>` distinction, the 30 `<background_noise>` sound names, the full anti-patterns list, the post-authoring quality checklist, and the troubleshooting matrix.

The reference is `references/conditional-actions.md`. Read it once at the start of any conditional-actions authoring session, and the inline content above will be enough to draft. Re-read sections of the reference if validation errors come back.

## Pre-Creation Checkpoint — Confirm Before Building

**Before creating scenarios or generating them, always pause and confirm key decisions with the user.** Do not assume defaults — present your plan and get explicit approval. AI agents that skip this step make costly assumptions that waste credits and require rework.

### What to Confirm

Present a checkpoint like this before proceeding:

1. **Tool strategy** — "How do you want to handle your agent's tool calls during testing?"
   - **A) Client-side mock data** — You manage your own staging backend; I'll align test profiles with your test data
   - **B) Cekura mock tools** — Cekura intercepts tool calls and returns mock responses; I'll set up the mappings
   - **C) No mock data** — Tools aren't relevant to these tests; we'll focus on conversational behavior

2. **Test profile** — "Want me to create `<profile-name>` with these fields?" Show the full `information` dict. For Approach A: check existing profiles first; fields must match staging data formats exactly. For Approach B: check existing mock entries first — if they fit, find the corresponding profile; if the profile is missing fields, create a new complete one; if no mock data fits, design new entries then derive the profile from those outputs. For Approach C: only caller identity fields needed. Never use a partial profile — missing fields cause the testing agent to improvise.

3. **Run mode** — "Default to text/chat for the first pass? It's cheapest, and since tools are mocked the results are the same as voice for logic validation." Recommend text unless the user specifically needs voice testing (latency, interruption handling, TTS quality).

4. **Personality** — For **conditional-actions** scenarios, default to the normal personality for the target language (e.g., 693 for English) — behavioral logic is in the conditions, not the personality. For **behavioral** scenarios, propose a mix: ~60% normal, ~20% challenging (interrupter/background noise), ~10% non-native, ~10% edge cases. Confirm with the user before using anything other than the normal default. See "Picking the Right Personality" above.

5. **Authoring mode** — Default is **behavioral instructions**. Switch automatically when the user's request used a direct trigger phrase ("conditional actions", "structured", "scripted", "deterministic test", "regression test", "compliance test", "exact flow", "fixed sequence"). Ask the user when the scenario mentions a tag-supported feature (voicemail, IVR, DTMF, hold, interruption, network simulation, background noise) without specifying a mode. See "Choosing Authoring Mode" above.

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

A complete suite covers: **Workflow** (happy path), **Deterministic/Unit Test** (conditional actions for exact flows), **Edge Case** (tool failures, ambiguous inputs), **Red Team** (prompt injection, social engineering), **Error Handling** (hostile caller, clinical questions), **Multi-Language**.

**See `references/coverage-patterns.md`** for one-paragraph descriptions of each type, the tag-based naming convention, and category breakdowns from real deployments.

## Execution Modes

**Practical guidance:** use **text/chat** for development iteration (fast, cheap, tests logic), **voice** for final validation before deployment. **WebSocket** for agents built on WebSocket providers, **Pipecat** for Pipecat framework agents. Test profile data is passed to the main agent in chat and websocket runs, enabling tool verification without voice calls. Full speed/cost comparison table in `references/coverage-patterns.md`.

## Mock Tool Data, Test Profiles, and Dynamic Variables

These three form one cohesive test data set and must be designed together. Key principles for Approach B:

- **Mock data first**: design mock tool entries before creating the test profile; derive all profile values from mock outputs
- **Per-input branching**: one mapping per distinct input the agent might send; not one mapping per tool
- **Phone format variants**: always add 10-digit, 11-digit-with-1, and E.164 forms (mismatches cause 404s)
- **Append-not-replace**: PATCHing `information` REPLACES the array; always GET → merge → PATCH
- **Fuzzy match variation**: new mock entries must be sufficiently distinct from existing ones so Cekura's closest-match lookup doesn't return the wrong user
- **Test profile completeness**: if an existing profile covers only a subset of required fields, create a new complete profile — never use a partial one

**See `references/test-data-design.md`** for the full approach-selection guide, decision matrix for new vs. reuse, fuzzy-match variation rules, chain dependency design, dynamic variable wiring, and API reference.

**Expected mock tool calls (tool scenarios you author directly):** the mock data above makes mocks *fire*, but a scenario's expected mock tool calls (`generated_mock_tool_entries`) are populated only by platform auto-generation, not by the create/update call. If you author a tool-using scenario directly here and want its tool calls tracked for scoring/observability (e.g. the *Mock tool call accuracy* metric), populate them as a separate step (REST-only) using the `cekura-backfill-mock-manifests` skill. It's optional — skip it if you don't need tool-call scoring; it does not require any metric to be enabled.

## Tagging Strategy

Format: `tags: ["Category", "priority-level", "scenario-ID"]`. Category codes: S=Scheduling, RS=Rescheduling, CN=Cancellation, V=Verification, SA=Safety, RT=RedTeam, etc.

## Expected Outcomes

Focus on the main agent's behavior, not the caller's experience:
- **One statement per line** — write each "The main agent should…" statement on its own line; do not concatenate multiple statements into a single paragraph
- **Agent-centric**: "Agent books appointment and provides arrival instructions" — not "the caller has a great experience"
- **Specific and measurable**: Include concrete actions (book, transfer, cancel, inform)
- **Include follow-up actions**: What happens after the primary action
- **Keep them concise** — expected outcomes are evaluated by an LLM judge that checks whether each part was satisfied. Overly specific prompts (e.g., specifying exact dates/times) cause false failures. Focus on the behavioral outcome, not exact details.

**See `references/expected-outcomes.md`** for the full writing rules, prioritization hierarchy, metric variable support (`{{test_profile.*}}`, `{{agent.*}}`, etc.), and good/bad examples.

## Create Evaluator from Transcript

`POST /test_framework/v1/scenarios/create_scenario_from_transcript/` turns a real call (by observability call-log ID) into a replayable evaluator — useful for regression tests from real edge cases. Always review post-creation and attach metrics, profile, folder, tools. **See `references/coverage-patterns.md` § Create Evaluator from Transcript** for the workflow.

## Documentation

- Public docs: https://docs.cekura.ai
- LLM-friendly docs: https://docs.cekura.ai/llms.txt
- Concepts: https://docs.cekura.ai/documentation/key-concepts/
- Full API endpoints: `references/api-reference.md`

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

- **`references/choosing-personality.md`** — Full personality selection logic: sustained vs. temporary behaviors, interruption tiers, multilingual matching, enabled/disabled status, fallback rules
- **`references/test-data-design.md`** — Approach selection (A/B/C), mock tool data design (per-input branching, fuzzy-match variation, phone format variants, chain dependencies, append-not-replace), test profile creation and reuse decision matrix, dynamic variable wiring, data flow by mode, API reference
- **`references/conditional-actions.md`** — Conditional actions: field semantics, XML-tag constraints, worked examples, anti-patterns, validation checklist, quick-reference card
- **`references/expected-outcomes.md`** — Writing rules, prioritization hierarchy, metric variables, good/bad examples
- **`references/coverage-patterns.md`** — Test coverage category breakdowns
- **`references/session-memory.md`** — Multi-session project memory document template
- **`references/api-reference.md`** — Complete API endpoints: scenarios, profiles, results

### Example Files

- **`examples/csv-eval-creation.md`** — CSV-to-evaluator workflow
- **`examples/workflow-eval.md`** — Single workflow evaluator example
- **`examples/red-team-eval.md`** — Red-team evaluator example
