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
  version: "0.5.0"
---

<!-- cekura-ack-tag: ack:cekura-eval-design:7k3m4q -->
> **Cekura skill verification tag:** `ack:cekura-eval-design:7k3m4q`
> When you call a Cekura scenario or test-profile write tool from this skill (`scenarios_*` / `test_profiles_*` create and update calls), pass this exact string as the `skill_ack` argument on that tool call. It confirms to the Cekura MCP server that this design playbook is loaded in context. Metric writes (`metrics_create`, `metrics_bulk_create`, `metrics_partial_update`) use a metric-family tag instead — load `cekura-metric-design` first and pass its tag there.

Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="cekura-eval-design"`, `verification_tag="ack:cekura-eval-design:7k3m4q"`, and `plugin_version="0.9.0"`. It returns immediately and lets Cekura see which skills are in use.

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

**Always use test profiles.** Never hardcode identity data (names, DOBs, account IDs, addresses, phone numbers, service addresses, discrepancy amounts — anything persona-related) in scenario instructions. This includes **caller choices and confirmations** — a plan, tier, or option the caller selects or agrees to is still caller data ("Select {{test_profile.delivery_speed}} when asked", not "Select express shipping"). Create a test profile with the data and reference it via `{{test_profile.field}}` placeholders, using the same token at every mention.

**Building test profiles from real data:**
The best approach is to pull call history from observability and/or past eval runs and use data that is known to work:
1. Fetch recent call transcript_json records from the API
2. Analyze toolcall inputs and outputs from real calls
3. Build a memory document mapping existing data (names, account IDs, appointment IDs, etc.)
4. Create test profiles using this verified data
This ensures test profiles work against production tools.

**Always check for existing test profiles first.** Clients often pre-build profiles that are tested against their mock backend — reuse these rather than creating from scratch.

**Custom headers (SIP / WebSocket runs):** keys in `main_agent_variables` starting with `X-` are sent over the wire as custom SIP headers (SIP runs) or WebSocket connection headers to the agent under test. For SIP runs this is the **only** way to pass custom headers — they cannot be set on the agent record or in the run request; create a test profile with the `X-` keys and attach it to the run via `test_profile_ids`. (WebSocket runs can also carry static headers via the agent's `websocket_headers`; the profile's `X-` keys are merged on top.) Cekura always appends `X-Run-Id`, `X-Scenario-Id`, and `X-Result-Id`; those names are reserved and cannot be overridden.

**Template variables in instructions:** Use `{{test_profile.field_name}}` or `{{test_profile['key']}}` for dynamic injection. For nested data: `{{test_profile.address.city}}`. Note: in voice scenarios, the simulated caller reads from the instruction text directly — the profile data is there for the caller to reference, not injected as hidden context.

See `references/test-data-design.md` for the full profile creation guide, decision matrix for new vs. reuse, and the data-extraction workflow.

## Writing Instructions

Instructions tell the testing agent what to do. Write in **first person** from the testing agent's perspective.

### Instruction Style

- First person: "State your name when asked" NOT "The caller should state their name"
- Behavioral, not scripted: "Report fever and cough, request same provider" NOT "Say exactly: I have a fever"
- Reference test profile data: "Provide {{test_profile.date_of_birth}} when asked for verification" (the actual DOB comes from the test profile)

### Step-Writing Rules (the short version)

Full rulebook with examples: **`references/instruction-patterns.md` § Step-Writing Rules** — load it before authoring. The essentials:

1. **Every step = one caller action + a passive "when …" trigger.** "State the reason for calling when asked for the reason of the call." Never unconditional actions, and never the words "agent", "AI", "bot", "system" in a step — describe what the step asks about, not who asks it.
2. **Trigger precision** — name the exact question or offer ("when asked for a preferred appointment time"), never bare "when asked" or vague context.
3. **One action per step.** Two joined actions ⇒ the second is silently dropped. Exception: the volunteer pattern ("when asked X, answer and also mention Z") is one turn.
4. **No passive/non-verbal steps** — no Wait/Listen/Interrupt/Remain silent/Mumble/Acknowledge. Those are personality attributes. Hangup IS a valid step.
5. **Data read-backs use the verify format**: "Verify [item] when asked to confirm [item] and correct if wrong." — the last phrase is required.
6. **Last step is always** "End the call when <specific condition naming the result of the final scripted action>." — unless the scenario ends in a terminal transfer (then accepting the transfer is the last step) or the user asked not to end the call.
7. **Stop at the fork** — only script steps whose triggers the agent description guarantees; when the description doesn't mandate the agent's next reaction, end the scenario there. A short deterministic scenario beats a long speculative one. Never premise a scenario on non-controllable state (backend conditions no mock fixes, or the main agent misbehaving — test forbidden behavior via outcomes demanding its absence).
8. **Placeholders for ALL caller-provided data — including choices.** Anything the caller provides, selects, agrees to, or confirms uses `{{test_profile.field}}` ("Select {{test_profile.delivery_speed}} when asked for a delivery speed"), the same token at every mention, and every placeholder must exist in the attached profile. Don't fabricate placeholders for one-shot topics — those go inline.
9. **If the caller must lead** (reactive main agent), put the opening request in `first_message`, not a step, and key each trigger to the response to the previous step — never to the caller's own state.

### Good Instructions Pattern

Wrap instructions in `<scenario>` tags with a step-by-step format:

```
<scenario>
SCENARIO: [Brief scenario name]

YOUR BEHAVIOR:
1. State your intent to [action] when asked for the reason of the call
2. Confirm you are the patient when asked if you are the patient
3. Say and spell {{test_profile.first_name}} when asked for your name for verification
4. Provide {{test_profile.date_of_birth}} when asked for your date of birth
5. Say you are flexible with timing when told no slots are available
6. End the call when the appointment confirmation is provided

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

Full worked bad-vs-good examples (wrong-number scenario, new-patient scheduling) live in **`references/instruction-patterns.md`** — load it before authoring behavioral scenarios.

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

4. **Language-specific personalities may not be enabled per-project** — Non-English personalities may return "Personality is not enabled" errors. Always try the language-matched personality first (via `personalities_list` with `language=<code>`, or a multilingual `language=multi` personality when the scenario mixes languages); only on that error fall back to personality 693 (Normal Male English) and rely on `scenario_language` to drive TTS and pronunciation. See "Checking Available Personalities" under the Personality section.

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

4. **Personality** — For **conditional-actions** scenarios, default to the normal personality for the target language (693 ONLY for purely English scenarios; for other languages pick the language-matched "Normal" personality via `personalities_list language=<code>`, or a multilingual `language=multi` one when the scenario mixes languages) — behavioral logic is in the conditions, not the personality. For **behavioral** scenarios, propose a mix: ~60% normal, ~20% challenging (interrupter/background noise), ~10% non-native, ~10% edge cases. Confirm with the user before using anything other than the normal default. See "Picking the Right Personality" above.

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

- **Mock data first**: design mock tool entries before creating the test profile; derive all profile values from mock outputs (never edit an entry to match a story value — derive in that direction only)
- **Input = caller-provided trigger keys, output = returned values**: lookup steps have the caller provide `{{test_profile.<input_field>}}`; verification steps have the caller state back `{{test_profile.<output_field>}}`
- **Entry only when a step completes the trigger**: a caller asking a question ≠ a tool call; offered ≠ completed; an empty entry list is often correct. Conversely, every completed tool-backed step MUST have an entry.
- **One input → one output**: a different outcome needs a different input — never two entries with the same input
- **Identical values everywhere**: the same fact in mock entries, test profile, and dynamic variables must be the identical string (only the deliberate validation-failure pattern mismatches). Every registered dynamic variable gets a non-empty value on every scenario.
- **Per-input branching**: one mapping per distinct input the agent might send; not one mapping per tool
- **Phone format variants**: always add 10-digit, 11-digit-with-1, and E.164 forms (mismatches cause 404s)
- **Append-not-replace**: PATCHing `information` REPLACES the array; always GET → merge → PATCH
- **Fuzzy match variation**: new mock entries must be sufficiently distinct from existing ones so Cekura's closest-match lookup doesn't return the wrong user
- **Test profile completeness**: if an existing profile covers only a subset of required fields, create a new complete profile — never use a partial one

**See `references/test-data-design.md`** for the full approach-selection guide, decision matrix for new vs. reuse, fuzzy-match variation rules, chain dependency design, dynamic variable wiring, and API reference.

## Tagging Strategy

Format: `tags: ["Category", "priority-level", "scenario-ID"]`. Category codes: S=Scheduling, RS=Rescheduling, CN=Cancellation, V=Verification, SA=Safety, RT=RedTeam, etc.

## Expected Outcomes

Focus on the main agent's behavior, not the caller's experience:
- **One atomic statement per line** — each line starts "The main agent should…" and makes ONE verifiable demand; split "and"-joined aggregates. 2–6 lines per scenario; short scenarios get few lines — never pad.
- **Every line must be fired by a written step** — an outcome whose condition the scripted flow never produces returns "blocked" on every run.
- **Verb AND object must be licensed** by the agent description (or a mock output / KB fact): "ask for X" does not license "explain X"; "transfer" does not license "transfer to a manager" unless the description says so. When a behavior isn't licensed, omit the line.
- **Offering is not executing** — if the flow doesn't complete the action (deferral, hang-up, terminal transfer first), demand only the partial state reached ("offered", "gathered"), never "booked".
- **Never grade who hung up** — end-call mechanics are structural; don't test them unless explicitly asked.
- **Binary verifiability, no subjective words** — ban "appropriately", "professionally", "warmly", "politely"; semantic content, not verbatim phrasing (except exact KB facts like phone numbers).
- **Copy placeholder tokens from the steps** — an outcome referencing a profile value uses the identical `{{test_profile.field}}` token; a prose paraphrase still counts as hardcoding.

**See `references/expected-outcomes.md`** for the full writing rules, scoring model, prioritization hierarchy, metric variable support (`{{test_profile.*}}`, `{{agent.*}}`, etc.), and good/bad examples.

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


---

# Reference — expected-outcomes.md (bundled from the cekura-eval-design skill)

# Expected Outcomes Reference

## What Is Expected Outcome

`expected_outcome_prompt` is a string field on each evaluator that describes what the main agent should achieve in the test. After each run, an LLM judge reads the call transcript and checks every statement against what actually happened.

Key facts:
- **Transcript-only** — the judge has no access to audio; it cannot evaluate tone, pronunciation, or speech quality
- **Requires the metric** — the `expected_outcome_prompt` field alone does nothing; you must also attach the **Expected Outcome** predefined metric to the evaluator
- **Speaker labels** — always refer to speakers as **"main agent"** and **"testing agent"**; never "user", "bot", "AI", or "assistant"

---

## Scoring Model

The judge evaluates each statement independently and assigns an alignment status:

| Alignment | Meaning |
|-----------|---------|
| `yes` | The main agent's behavior satisfies the requirement |
| `no` | The main agent violated or failed to meet the requirement |
| `blocked` | The prerequisite for this requirement never occurred in the call |

Final score:

| Outcome | Score |
|---------|-------|
| All statements `yes` | **100** — pass |
| Any statement `no` | **0** — fail |
| Any statement `blocked`, none `no` | **50** — needs review |

**When to expect "blocked":** Use sparingly. It applies when the condition that would trigger the tested behavior never arose — e.g., `"The main agent should transfer the call when the testing agent asks about prescriptions"` will be blocked if no prescription question was asked. When the testing agent ends the call before the agent can act, that is also blocked, not a failure.

**Transfer attempts count as success:** If the expected outcome requires a transfer and the agent attempted one (even if the call dropped), the judge marks it `yes`.

**Volunteered information counts:** If the testing agent volunteered information the main agent was supposed to ask for, the judge treats the requirement as met.

---

## Writing Rules

Every statement must start with **"The main agent should"**. Beyond that, these rules apply:

### 0. One statement per line
Write each statement on its own line. Separate multiple statements with a newline — do NOT concatenate them into a single paragraph separated by ". ".

✅ Correct:
```
The main agent should respond to the DTMF input 123 sent with the hash terminator.
The main agent should respond to DTMF input 45 sent without a terminator after the 2 second timeout flush.
The main agent should respond to DTMF input 7 as a single digit flushed after 2 seconds.
```

❌ Wrong:
```
The main agent should respond to the DTMF input 123 sent with the hash terminator. The main agent should respond to DTMF input 45 sent without a terminator after the 2 second timeout flush. The main agent should respond to DTMF input 7 as a single digit flushed after 2 seconds.
```

### 1. Atomic statements — one verifiable demand per line
Prefer exactly one verifiable demand per statement; never more than two distinct actions. Split every "and"-joined aggregate ("confirms the booking **and** mentions the document requirement" → two lines). Splitting never creates new obligations — each fragment must itself be required by the agent description, and a fragment may not be NARROWER than the description's wording.

Keep the list short: 2–6 statements for a typical scenario, up to 5 for legacy suites. A short scenario that ends at its last deterministic point gets FEW lines — never pad to a target count.

### 1a. Every statement must be fired by a written step
Each outcome must be triggered by an explicit scenario step (or the opening). Drop conditional lines whose condition the script never produces — they will come back `blocked` on every run. If the scenario offers multiple valid branches, accept any of them in one either/or line rather than demanding one side.

### 1b. Verb AND object must both be licensed
Both the action verb and its object must come from the same source — the agent description, a mock-tool output the agent verbalizes, or a KB fact. "Transfer" being mentioned doesn't license "transfer **to a manager**" if the description only defines transfers elsewhere. Adjacent workflow steps license only timing, never new content: "ask for X" does NOT license "explain X", "handle refusal of X", or "reassure about X". Topics the caller may raise don't license the agent raising them. When a behavior isn't licensed, omit the line — never invent a fallback.

### 1c. Offering is not executing — match the tool state
If the action doesn't complete in the scripted flow (caller hesitates, defers, hangs up, or a terminal handoff happens first), describe only the partial state reached — "offered", "gathered", "discussed" — never "booked"/"completed". For a terminal transfer, outcomes end at "the main agent transfers the call with appropriate context"; nothing post-transfer.

### 1d. Never grade who hung up
Write no outcome for the end-call step, hangup attribution, or call-end reason unless the user explicitly asked to test termination. Grade only a mandated verbal closing phrase, if the description requires one. (End-call is structural, not behavior under test.)

### 1e. Order lines
When the description mandates X before Y within the scenario's deterministic span, write ONE order line naming both events with scenario-scoped anchors ("The main agent should ask for the date of birth before providing any account details"). The order line evaluates order only — the events themselves get their own atomic lines if independently required.

### 2. Semantic content only — except for fact lookups
Outcomes test functional intent, not verbatim wording. The agent paraphrasing a response is still a pass. Do not quote expected sentences.

**Exception — KB/fact lookups:** When the test is verifying that the agent retrieved and stated a specific piece of data (phone number, address, name, date), the exact value is required. Use backticks to mark the expected data point:
```
The main agent should state the office address as `123 Medical Lane, Suite 100`
```
For descriptive KB data (policies, how-to explanations), check core meaning — phrasing variation is acceptable:
```
The main agent should explain that appointments can be cancelled up to 24 hours in advance
```
Specific names and identifiers are acceptable in lookup statements because the fact itself is what's being tested.

### 3. No subjective descriptors
Ban: "appropriately", "warmly", "empathetically", "politely", "professionally", "briefly", "clearly", "naturally". Replace with functional descriptions of what the agent says or does.

### 4. Binary verifiability
Every statement must be objectively True/False from the transcript. If a reasonable reader could disagree on whether the transcript satisfies the requirement, rewrite it.

### 5. Agent-centric
Focus on what the **main agent** does — not what the caller experiences, feels, or receives. "The caller will feel helped" is not a valid outcome.

### 6. No call closing / farewells
Do not test goodbye or farewell statements unless the `extra_instructions` explicitly require testing that behavior. The last testable outcome is the agent's response to the testing agent's final substantive statement.

### 7. No test-setup rationale
The expected outcome describes only what the judge should observe in the transcript. Do not explain how or why the test is structured — dynamic variable values, timeout thresholds, hold durations, or any other test-design context belong in the scenario **Instructions**, not the expected outcome.

✅ Correct:
```
The main agent should confirm the booking and provide a reference number.
```

❌ Wrong:
```
The main agent should confirm the booking. retryCount=3 is set via dynamic variable so the retry loop reliably exercises the fallback path.
```

---

## Prioritization Hierarchy

When choosing which statements to include, follow this priority order — if you need to cut, sacrifice lower-priority items first:

1. **Core Test Goal** — the primary functional or behavioral objective of this specific test; always present
2. **Critical Prerequisites** — steps the main agent must complete to enable the core goal (e.g., collecting required data before booking); fully represent these
3. **The Hard Stop** — the main agent's final verbal action within the test's scope
4. **Other Key Functional Steps** — other mandatory actions from the agent description that fall within the test's scope

> **Behavioral tests:** If the test goal is to verify how the agent handles a specific caller behavior (e.g., unprofessionalism, confusion, hostility), at least one statement must explicitly test that behavioral reaction — e.g., `"The main agent should proceed with the next question without reacting to the testing agent's unprofessional comment."`

---

## Metric Variables in Expected Outcome

`expected_outcome_prompt` supports `{{variable_name}}` substitution — the same system used in LLM Judge metric prompts. This is useful when the expected outcome depends on test-profile data or dynamic call context.

> **Already injected automatically** — `{{transcript}}`, `{{call_end_reason}}`, and call duration are provided to the judge automatically. Do not include them in your prompt.

### Available Variables

#### System Variables (available everywhere)
| Variable | Description |
|----------|-------------|
| `{{date}}` | Current date as YYYY-MM-DD |
| `{{timestamp}}` | ISO 8601 timestamp with timezone |

#### Simulation Variables
| Variable | Description |
|----------|-------------|
| `{{test_profile.*}}` | Structured test profile data — names, DOB, phone, addresses, etc. |
| `{{metadata.*}}` | Custom key-value pairs plus system fields like `ringing_duration` |
| `{{provider_call_data.*}}` | Complete call details from VAPI, Retell, ElevenLabs, etc. |
| `{{evaluator.*}}` | Evaluator instructions and conditional action details |
| `{{agent.*}}` | Agent configuration — name, description, language code, inbound status, contact number |

Variables are **case-sensitive**. Access nested fields with dot notation: `{{test_profile.caller_name}}` or `{{metadata.customer_id}}`. Not all variables exist in every call context — handle missing values appropriately.

### Example

```
The main agent should greet the caller using the name {{test_profile.caller_name}} and ask for their date of birth to proceed with verification
```

This lets the expected outcome stay accurate across different test profiles without hardcoding identity data.

**Copy the token, don't paraphrase.** When a scenario step uses `{{test_profile.field}}`, any outcome referencing that value must use the IDENTICAL token — do not re-describe the value in prose. A paraphrase ("should confirm the caller's premium plan") still counts as hardcoding and breaks when the profile changes; write "should confirm the caller's {{test_profile.selected_plan}}".

---

## Good vs Bad Examples

| Bad | Good | Why |
|-----|------|-----|
| `"The main agent should state the message: 'The best next step would be to call the facility directly.'"` | `"The main agent should advise the testing agent to contact the facility directly."` | Verbatim phrases cause false failures when the agent paraphrases |
| `"The main agent should ask for the caller's name, ask for their mother's date of birth, and state no appointment was found."` | `"The main agent should ask for the caller's name and the mother's date of birth."` + `"The main agent should state that no appointment was found for the specified date."` | 3 actions → split into 2 statements |
| `"The main agent should warmly and professionally handle the request."` | `"The main agent should proceed with the next question without reacting to the testing agent's unprofessional comment."` | Subjective descriptors ("warmly", "professionally") are not verifiable |
| `"The main agent should provide the caller with a great experience."` | `"The main agent should book the appointment and provide arrival instructions."` | Caller experience is not agent-centric or measurable |
| `"The main agent should confirm the appointment for Thursday at 2pm."` | `"The main agent should confirm the appointment date and time with the testing agent."` | Hardcoded values cause false failures across different test data |
| `"The main agent should collect the caller's details. timeout=30 is passed as a dynamic variable so the silence window reliably triggers the fallback."` | `"The main agent should collect the caller's name and date of birth."` | Test-setup rationale (dynamic variable values, timeout thresholds) is not observable behavior; it belongs in the scenario Instructions |

---

## Common Pitfalls

- **Missing metric attachment** — the `expected_outcome_prompt` field alone does nothing; attach the Expected Outcome predefined metric to the evaluator
- **Including auto-injected variables** — `{{transcript}}`, `{{call_end_reason}}`, and call duration are provided automatically; adding them manually causes duplication
- **Wrong speaker labels** — always use "main agent" and "testing agent"; never "user", "assistant", "bot", or "AI"
- **Exact phrases or hardcoded values** — specifying exact dates, times, or verbatim sentences causes false failures when the agent paraphrases or uses different test data
- **Subjective descriptors** — "appropriately", "warmly", "professionally" are not verifiable; replace with functional descriptions
- **Testing call closing** — farewell statements are out of scope unless the test explicitly requires it
- **3+ actions in one statement** — split into multiple statements, each with max 2 distinct actions
- **Test-setup rationale in expected outcome** — dynamic variable values, timeout thresholds, hold durations, and explanations of why the test is structured a certain way are not observable behavior; move them to the scenario Instructions field
- **Outcomes no step triggers** — a line whose condition the scripted flow never produces returns `blocked` on every run; either add the causing step or delete the line
- **Bundled demands** — "and"-joined aggregates fail as a unit; one verifiable demand per line
- **Grading completion the flow never reaches** — if the caller defers or a transfer happens first, demand "offered/gathered", not "booked/completed"
- **Grading who hung up** — end-call mechanics are structural; don't test them unless explicitly asked
- **Paraphrased profile values** — restating a `{{test_profile.*}}` value in prose is still hardcoding; copy the token


---

# Reference — coverage-patterns.md (bundled from the cekura-eval-design skill)

# Test Coverage Patterns

## Coverage Strategy

A comprehensive eval suite covers all major workflows, their edge cases, and adversarial scenarios. This reference shows real-world coverage patterns from deployed agents.

## Diversity & Friction Distribution

When generating a batch of scenarios (auto-gen or manual), apply this distribution:

- **~30% happy-path** (cooperative caller completing the full workflow), **~70% friction** — with at least one happy-path scenario in any batch.
- **Every scenario opens with a DIFFERENT caller persona** inferred from the agent's domain (healthcare: worried patient, impatient caregiver, confused elderly caller). No two scenarios share the same opening persona.
- **Each scenario progresses through MULTIPLE workflow steps** — not just the first one or two.
- **Friction appears at DIFFERENT points across the batch**: some early-then-cooperative, some smooth-start-with-mid-flow pushback, some late friction (refuses to confirm, changes mind), some multi-point.
- **Friction must be SPECIFIC and behavioral**, never "the caller is difficult": refuses to confirm identity until told why it's needed; challenges a specific piece of information; asks the same question repeatedly despite an answer; suddenly asks for a human mid-flow.
- **Every scenario must be grounded** in an actual agent capability — a workflow branch in the description, a configured tool, a KB fact, or a general conduct policy (professionalism, safety, escalation). Reach the target count by permuting grounded branches, value variants, friction positions, and personas — never by inventing capabilities the agent doesn't have. Friction may never be premised on environment failures the scenario can't control or on the main agent misbehaving.
- **KB grounding**: when knowledge-base content exists, enrich scenarios with 1–2 concrete named facts from it ("asks whether the clinic accepts Blue Shield PPO", not "asks about insurance"). Not every scenario needs KB facts — workflow-only scenarios are equally valid. When NO KB exists, don't write scenarios expecting the agent to answer factual questions — the only valid expected behaviors are clarifying, saying it can't find that information, transferring, or redirecting to a defined workflow.

## Example: Medical Clinic Agent (BCHS/Kouper — 54 evaluators)

### Category Breakdown

| Category | Code | Count | Description |
|----------|------|-------|-------------|
| Scheduling | S | 10 | New/established patients, adult/pediatric, insurance/no-insurance, sliding scale |
| Rescheduling | RS | 6 | Same/different provider, no appointments, multiple appointments, tool failures |
| Cancellation | CN | 6 | Cancel + decline reschedule, cancel + rebook, no appointments, tool errors |
| Verification | V | 7 | Spouse/authorized rep, name spelling corrections, patient not found retries |
| Intake | I | 3 | Ambiguous visit reason, billing concerns, multiple insurance plans |
| Scheduling Edge Cases | SC | 4 | No slots, confirmation rejected, tool failures |
| Overall Flow | OF | 4 | FAQ-only, behavioral health transfer, billing transfer, human request |
| Safety | SA | 9 | Chest pain, emergency symptoms, suicidal ideation, symptom triage |
| Error | ER | 4 | Angry caller, deceased patient, clinical question, silent tool failure |
| Spanish | SP | 1 | Full scheduling call in Spanish |

### Priority Distribution

- **Must-have**: 39 evaluators (72%) — core workflows that must work correctly
- **Nice-to-have**: 15 evaluators (28%) — edge cases and enhancements

### Coverage Principles from BCHS

1. **Every workflow gets a happy path**: S-01 through S-10 cover all scheduling variants
2. **Every workflow gets error paths**: RS-06 (tool fails 3+ times), CN-05 (cancel tool error)
3. **Verification gets its own category**: Identity verification is critical for medical — 7 dedicated scenarios
4. **Safety is heavily covered**: 9 scenarios for medical emergency handling (highest consequence of failure)
5. **Cross-workflow scenarios exist**: CN-02 tests cancel → immediately rebook (two workflows in one call)

## Example: Staffing Platform Agent (Traba — 3 metrics, implicit eval patterns)

### Coverage Areas

| Area | What to Test |
|------|-------------|
| Interview Flow | Pay expectations, commute, availability, work experience questions |
| Tool Performance | evaluate_transcript_prod timing, tool chain stalls |
| Onboarding | App installation guidance, silence persistence, step-by-step navigation |
| Escalation | Get Help redirect when user is stuck |
| Multi-agent Transfer | Handoff between interview → evaluation → onboarding agents |

### Key Insight: Traba has fewer evals but more metrics

Traba's testing strategy relies more on metrics (measuring call quality on real production calls) than on simulated evals. This is appropriate for outbound calls where the agent initiates — you can't easily simulate the full multi-agent flow. Instead, real calls are evaluated by metrics.

## Building a Coverage Matrix

For any new agent, build coverage by:

1. **List all workflows** from the agent description (booking, cancellation, transfer, etc.)
2. **For each workflow, identify**:
   - Happy path (standard successful completion)
   - User variations (new vs existing, adult vs pediatric, etc.)
   - Error paths (tool failures, retries exhausted)
   - Edge cases (multiple items, confirmation rejection, user changes mind)
3. **Add cross-cutting concerns**:
   - Verification / authorization
   - Safety / emergency handling
   - Language support
   - Adversarial / red team scenarios
4. **Prioritize**: Must-have = workflows that handle real money, safety, or core business logic

## Naming Convention

Use consistent ID + name format for easy tracking:

```
{CATEGORY_CODE}-{NUMBER}: {Brief Description}
```

Examples:
- `S-01: New adult patient with insurance`
- `RS-03: No future appointments nothing to reschedule`
- `SA-07: Suicidal ideation immediate transfer`

Keep names under 80 chars (API limit on the `name` field).

## Eval Types

A complete suite has coverage across these categories. Each type can be authored as **behavioral** (free-form instructions) or **conditional actions** (structured `{role, conditions[]}`) — see "Choosing Authoring Mode" in `SKILL.md` for the decision rule.

### Workflow Evals (Core)

Happy path for each major workflow the agent supports — appointment booking, account lookup, password reset, etc. Cover every primary action the agent is supposed to perform end-to-end.

### Deterministic / Unit Test Evals

Conditional-actions evaluators for repeatable, structured testing of specific flows. Use when you need byte-identical behavior every run (regression, compliance verbatim, IVR navigation, DTMF entry).

### Edge Case Evals

Tool failures, multiple matching records, confirmation rejection, retry exhaustion, ambiguous user input. Each edge case is a separate evaluator with its own expected outcome.

### Red Team Evals

Prompt injection, social engineering, information extraction, off-topic manipulation, jailbreak attempts. Specific scripted attacks belong in conditional-actions evaluators (one evaluator per expected outcome — refusal vs compliance). Free-form probing stays behavioral.

### Error Handling Evals

Angry caller, deceased patient, clinical questions, silent tool failures, hostile callers. Tone-driven scenarios are usually behavioral; specific de-escalation flows can be conditional actions.

### Multi-Language Evals

Coverage across every language the agent supports. Set `scenario_language` and pair with a personality that matches. Behavioral covers tone/quality testing; conditional actions cover compliance-verbatim phrasing in the target language.

## Execution Modes

| Mode | Speed | Cost | Best For |
|------|-------|------|----------|
| **Voice** | Slow | High | Final validation, voice-specific testing (latency, interruptions, TTS quality) |
| **Text/Chat** | Fast | Low | Logic testing, rapid iteration, flow validation without voice overhead |
| **WebSocket** | Medium | Medium | Real-time agents, agents using WebSocket-based providers |
| **Pipecat** | Medium | Medium | Pipecat framework agents |

**Practical guidance:** Use text/chat for development iteration (fast, cheap, tests logic). Switch to voice for final validation before deployment. WebSocket for agents built on WebSocket providers.

**Test profiles in chat/websocket:** Test profile data is passed to the main agent in chat and websocket runs, enabling tool verification without voice calls.

## Create Evaluator from Transcript

Cekura can create an evaluator directly from a real call transcript. Useful when:
- A production call demonstrates an important scenario
- You want to reproduce a specific customer interaction as a repeatable test
- You're building regression tests from real-world edge cases

**Endpoint:** `POST /test_framework/v1/scenarios/create_scenario_from_transcript/`

**How it works:** Pass an observability call log ID. The endpoint analyzes the transcript, extracts the caller's behavior, and creates an evaluator that replays a similar conversation. The generated scenario captures the caller's intent, actions, and conversational flow — not an exact script replay.

**When to use:** After reviewing production calls in observability, identify calls that represent important test scenarios (edge cases, failures, complex workflows) and convert them directly into evaluators. This is faster and more accurate than manually writing instructions to reproduce the scenario.

**Post-creation:** Always review the generated evaluator — the auto-extraction may need refinement. Attach metrics, assign a test profile if identity data is involved, set the folder path, and enable tools.
