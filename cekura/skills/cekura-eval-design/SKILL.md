---
name: cekura-eval-design
description: >
  Use when the user asks to "generate (test) scenarios", "generate evaluators",
  "create an evaluator", "create evals", "create a scenario", "write a test scenario",
  "design a test case", "test my agent", "build eval coverage", "plan a test suite",
  "create red team tests", "set up test profiles", "configure conditional actions",
  "build a deterministic test", "design an IVR test", "write a unit test for a voice
  agent", "build a regression test", "scripted scenario", "structured evaluator",
  or "run evals". Also for CHANGING existing evaluators — "update
  an evaluator", "improve my evals", "make these evaluators stricter", "add a DTMF
  step", "fix the expected outcome", "attach metrics to these" — and for debugging how
  the testing agent speaks: "why did it read the number as a word", "make it spell
  digits", "wrong language". Covers evaluator design and review, coverage, test
  profiles, mock-tool data, conditional actions, and red-team / edge-case practice.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.10.0"
---

<!-- cekura-ack-tag: ack:cekura-eval-design:7k3m4q -->
> **Cekura skill verification tag:** `ack:cekura-eval-design:7k3m4q`
> When you call a Cekura scenario or test-profile write tool from this skill (`scenarios_*` / `test_profiles_*` create and update calls), pass this exact string as the `skill_ack` argument on that tool call. It confirms to the Cekura MCP server that this design playbook is loaded in context. Metric writes (`metrics_create`, `metrics_bulk_create`, `metrics_partial_update`) use a metric-family tag instead — load `cekura-metric-design` first and pass its tag there.

Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="cekura-eval-design"`, `verification_tag="ack:cekura-eval-design:7k3m4q"`, and `plugin_version="0.13"`. It returns immediately and lets Cekura see which skills are in use.

# Cekura Eval Design

Create and improve Cekura evaluators (test scenarios) that exercise an AI voice or chat agent. An evaluator simulates a **caller**; it is not a metric (metrics score a transcript afterwards — see **cekura-metric-design**).

- **Main agent** — the agent under test. **Testing agent** — Cekura's simulated caller.
- **Evaluator / scenario** — one test case. **Personality** — the testing agent's voice, language and speaking behaviour. **Test profile** — identity/context data for the run. **Conditional actions (CA)** — turn-by-turn scripted testing-agent behaviour.

This file says **what** to do. The Cekura tools available in your session — MCP tools, REST, or the platform's own agent tools — say how: read their descriptions to pick the call, and act through them rather than describing API calls or dashboard clicks. The file is self-sufficient for authoring both modes — load a reference only for the deep detail it names.

## Workflow

1. **Read the agent** (mandatory, below).
2. **Decide mode and write path** — behavioral vs conditional actions.
3. **One consolidated checkpoint** — only for what you could not infer.
4. **Create a folder** for the batch; never write into the project root.
5. **Author** — generate, or create directly, per the write-path table.
6. **Attach metrics and supporting fields** — profile, personality, tools, tags.
7. **Verify** — read back what you wrote; then run if the user asked.

Updating existing evaluators has its own procedure — see **Changing existing evaluators**.

## Read the agent before writing anything

Fetch the agent's **full record** before the first authoring write — the single-agent read, not a list view, because list views omit the `description` — and use it for:

| Field | What it decides |
|---|---|
| `description` | every workflow, branch, KB fact, transfer and policy you are allowed to test or grade |
| `inbound`, and the greeting the description scripts | who speaks first: the main agent opens ⇒ CA `id: 0` has `action: ""` and behavioral scenarios need no opening line; otherwise the testing agent opens. Read the description for this and ask when it is unclear |
| `language` | the personality language and `scenario_language` |
| `assistant_provider`, `transcript_provider`, `websocket_url` | whether tool calls reach the evaluation transcript (see **Expected outcomes**) |
| `mock_tools` (request them explicitly — the default agent read omits them), `auto_dynamic_variables` | which tool inputs/outputs and variables the test data must match |

Skip it only when the user supplied a complete verbatim payload, or the evaluators are already attached to this conversation (Evaluators-page context). Never invent a workflow, a KB fact, or a tool the description does not contain — if the description is empty or too thin to ground a test, say so and ask for it (or offer `cekura-create-agent` to import from the provider) instead of generating.

**The agent under test is read-only while you author evaluators.** Do not PATCH any of its fields (description, connection settings, tools, provider configuration) to make a test possible: an evaluator tests the agent as deployed, and a rewritten description hides the very gap the test would have found. The one exception is `mock_tools` data (see **Test data**). When the user states a fact or behaviour the record does not contain (a policy, a header, a greeting rule), say so in one line, then carry the user's version into the test itself: `extra_instructions` or `generation_files` when generating, the test profile and `expected_outcome_prompt` when creating directly. If the user wants the agent itself changed, that is a separate task for **cekura-create-agent** (configuration) or **cekura-self-improving-agent** (prompt changes), after the evaluator exists.

## One consolidated checkpoint

Ask **once**, in a single message, and only for what the request and the agent record do not already answer. Then proceed.

Skip the question entirely when the user said "proceed autonomously", "don't ask", or already stated the missing facts. Never re-ask something the user wrote in their message; never ask a second round of the same topics.

If you did ask, **wait for the answer** — no create or generate call in the same turn. And when the user says "first ask me", "show me the plan" or "confirm before creating", present the whole plan (mode, count and coverage, folder, profile, personality, metrics) and wait for approval even if the request already names the agent and the count.

When the request sits in an **Ask first** row of the mode table and the user has not chosen a structure, ask — one short question offering behavioural vs conditional actions with the reason. Existing evaluators of one type in the project do not answer it for them; the no-confirmation rows (infra, pipeline, explicit CA vocabulary) still switch without asking.

What to confirm (drop every line you can already answer):

1. **Tool data strategy** — (A) their staging backend, (B) Cekura mock tools, (C) tools irrelevant. Default: B when `mock_tools` exist, C when the agent has no tools.
2. **Count and coverage** — how many scenarios and which workflows/categories. Default: propose a breakdown from the description.
3. **Mode** — text/chat for iteration (cheap, same logic), voice for final validation. Default: text.
4. **Folder name** — propose one; do not ask.
5. **Anything genuinely ambiguous** in the request (a named branch that does not exist, an agent id that does not resolve).

Do not ask about personality, metrics or tags — pick the documented defaults below (when several plain Normal personalities remain, take the male variant when both genders exist, per `references/choosing-personality.md`, and say so) and state what you picked in your summary. A checkpoint that lists seven questions is a failure mode: users abandon it.

## Mode and write path

**Generation is the general write path in every mode.** Behavioural scenarios, conditional actions and red-team plans all come from the same background generator, grounded in the agent description, KB and mock tools; only the output format differs — `simulation_type: "instruction"` or `"conditional_actions"` (red-team categories return conditional actions on their own). Use it for every batch, every category-level request and whenever the user says "generate". The count/category test decides: **a request for a number of scenarios ("three evaluators", "a suite for the refund flow"), for a topic or category ("billing disputes", "what it knows about the return policy"), or containing the word *generate* is a generation request even when the user hands you the facts to test** — those facts go into `extra_instructions` or `generation_files`, never into hand-written steps. **A scenario, or a small set of them, whose conduct the user has laid out — a dictated turn-by-turn script, one persona with its exact behaviour, an infra test bracketing a timeout to the decimal, a patch to an existing scenario — may be created directly**. The path changes nothing else: a direct create meets the same step, outcome, profile, personality, tool and metric rules as generated output (see **Self-check before every direct instruction create** and the CA self-check), and it starts with **no metrics attached**. Choosing the mode is the decision; the write path follows from whether the user described the caller's conduct or only what to test. Say in the summary which scenarios were generated and which were created.

| Mode | When |
|---|---|
| **Behavioral** (`scenario_type: "instruction"`) — free-form, first-person instructions | Open-ended personas, exploratory red-team, tone/empathy, general quality probing, any request without a structural commitment. The default. A category-level ask for one scenario is still `num_scenarios: 1`; only a scenario whose conduct the user has laid out is created directly. |
| **Conditional actions** (`scenario_type: "conditional_actions"`) — `{role, conditions[]}` | Verbatim/compliance phrasing, exact-sequence regression, IVR/voicemail/DTMF, interruption/idle/network/noise tests, infra & CI tests, one scripted attack, data-bound turn-by-turn verification, anything needing an XML tag. When generating, put the tag requirements into `extra_instructions` ("the caller enters the account number by DTMF", "hold 20 s after the greeting", "the caller reaches an IVR menu first") and check the output against the self-check below. **Numbered steps in the request are not by themselves a CA signal** — behavioural instructions are normally written as numbered steps too. |

**Switch to CA with no confirmation** when the user says: conditional actions, structured or scripted scenario/test, deterministic test, unit test, regression test, exact flow, fixed sequence, compliance test, infra/infrastructure/pipeline/CI test or gate.

**Infrastructure and pipeline tests are always CA — no confirmation.** Tests of STT, VAD, LLM timeout, TTS, interruption handling, idle timers, DTMF or any other pipeline-layer behaviour must trigger the behaviour at an exact moment with exact timing, which behavioural instructions cannot guarantee. Switch immediately; **cekura-infra-test-suite** has the full workflow.

**Ask one short question** when the request names a tag-supported feature — voicemail, IVR menu, DTMF entry, hold music, interruption, network simulation/packet loss, background noise — without naming a mode: *"This involves [IVR]. Conditional actions support `<dtmf>` / `<ivr>` tags directly for a high-fidelity test; behavioural instructions are looser. Which do you want?"* Then proceed with the answer.

**Which mode for which request** (defaults — the user's explicit word wins):

| Request | Mode | Why |
|---|---|---|
| Appointment scheduling happy path | Behavioral | Predictable path, no exact phrasing needed; the caller improvises naturally |
| Scheduling as an exact-sequence regression test | CA | "Regression test" is a trigger phrase |
| Compliance disclosure / account-number read-back | CA | Verbatim phrasing (`fixed_message: true`, `<spell>`); "compliance" is a trigger phrase |
| Identity verification: name + DOB + last-4 | CA | Every turn is data-bound to the profile; structure prevents drift |
| Inbound IVR menu navigation | Ask first | Tag-supported (`<dtmf>`), mode not named |
| Voicemail handling | Ask first | `<voicemail>` is purpose-built; behavioural can work |
| Angry caller / de-escalation | Behavioral | Tone-driven, exploratory, no fixed sequence |
| One scripted red-team attack (specific injection, specific fallback) | CA | A fixed attack script; one evaluator per expected outcome |
| Free-form red-team probing | Behavioral | Path not predictable; the attacker improvises |
| Multi-language tone test | Behavioral | Soft-skill; `scenario_language` set either way |
| Multi-language compliance verification | CA | Verbatim disclosures in the target language |
| Network degradation / packet loss | Ask first | `<network_simulation>` is purpose-built |
| Tool-failure recovery (specific failure, specific recovery step) | CA | Exact trigger and exact recovery |
| "Test my agent's quality" | Behavioral | No structural commitment |
| STT / VAD / LLM timeout / TTS / interruption / idle / DTMF | CA | Pipeline behaviour needs exact timing — no confirmation |
| A caller who must stay silent, hold, or interrupt | CA (tag) | `<hold>`, `<silence>`, `<interruption>`; prose "remain silent" does nothing |

**Supplied text outranks every mode signal.** When the user hands you scenario text — a `<scenario>` block, numbered steps, a CSV row — and asks for it as written, create it as `scenario_type: "instruction"` with that text unchanged — the `<scenario>` wrapper and numbering included: when the user's text starts with `<scenario>`, the stored `instructions` string starts with `<scenario>` and ends with `</scenario>`. Do not restructure it into conditional actions because the steps look sequential, and do not reword it; rewriting is the one thing they asked you not to do. Attach the personality, metrics, profile and tools as usual.

**If actions are present, set the type.** A payload whose `instructions` carries CA-shaped JSON while `scenario_type` is absent is stored as an instruction scenario and the script never runs. Pass the object in the `conditional_actions` field with `scenario_type: "conditional_actions"`.

## Behavioral scenarios — shaping generation

`extra_instructions` is where you steer the generator. One paragraph per scenario category, plain prose, third person about the testing agent, no PII, no markdown:

```
The testing agent calls as an established patient who needs to reschedule a
follow-up. It provides its name and date of birth when asked, requests the same
provider, and accepts the earliest afternoon slot when told no mornings are
free. Cover the verification branch and the same-provider path. Use the Normal
personality for the agent's language.
```

Never send a generation call with empty `extra_instructions` — the generator falls back to generic coverage. When the user states the facts the agent must know (a price, a deadline, an eligibility rule), the exact values go into `extra_instructions` (or the source document into `generation_files`) — the generator writes the expected outcome from them, and an outcome that cannot name the right answer grades nothing. If the user truly wants unguided coverage, say so and pass a one-line category list.

**Step-writing rules** (also what you check in generated output): every step = one caller action + a passive `when …` trigger naming the exact question ("when asked for a preferred appointment time", never bare "when asked"); one action per step; no passive/non-verbal steps (Wait/Listen/Remain silent/Interrupt — those are personality or CA tags); data read-backs use `Verify [item] when asked to confirm [item] and correct if wrong.`; the last step is `End the call when <the result of the final scripted action>.` unless the flow ends in a terminal transfer; script only triggers the description guarantees (**stop at the fork**); never premise a step on the main agent misbehaving; every caller-provided value — including choices and confirmations — is `{{test_profile.field}}`, the same token at every mention, and must exist in the attached profile. If the main agent is reactive, put the opening request in `first_message`, not in a step, and key each trigger to the response to the previous step — never to the caller's own state. Do not fabricate placeholders for one-shot topics; those go inline.

**Instruction style** — what you check in generated output, apply when patching, and expect in a verbatim scenario:

- **First person, to the testing agent**: "State your name when asked" — never "The caller should state their name", and never the words *agent*, *AI*, *bot* or *system* inside a step (describe what the step asks about, not who asks).
- **Behavioural goals, not dialogue**: "Report fever and cough and request the same provider" — not `Say exactly: "I have a fever"`. The one exception: be explicit about an exact phrase when mock or backend matching depends on it (`say "follow-up appointment" exactly`).
- **Never quote what the main agent "may say"** as a trigger — `When the agent says "How can I help you?"` breaks on any rewording; key the step to the topic: "when asked what you need help with".
- **Specific beats generic** — "Call to schedule an appointment" tests nothing; name the appointment type, the constraints and the complication.
- A step that volunteers extra information is still one turn ("when asked X, answer and also mention Z"). Hanging up is a valid step; "Listen", "Wait", "Respond accordingly" and "End the call politely" are not — the testing agent does those anyway.

Shape — what generation returns and what a verbatim scenario should look like:

```
<scenario>
SCENARIO: [Brief scenario name]

YOUR BEHAVIOR:
1. State your intent to [action] when asked for the reason of the call
2. Say and spell {{test_profile.first_name}} when asked for your name
3. Provide {{test_profile.date_of_birth}} when asked for your date of birth
4. Say you are flexible with timing when told no slots are available
5. End the call when the appointment confirmation is provided

KEY INTERACTION POINTS:
[Workflow nodes or edge cases to exercise]
</scenario>
```

**Gaps after generation** — missing categories are closed by another generation run with `extra_instructions` naming exactly what is missing. A single, fully described missing case ("a caller whose payment is declined twice") may equally be created directly; when it is, write it to the step-writing rules above, wrap it in `<scenario>` tags, attach outcome, profile, personality, tools and metrics, and pass the direct-create self-check below.

Full rulebook with worked bad→good examples: **`references/instruction-patterns.md`**.

### Self-check before every direct instruction create

Refuse to send a direct create with `scenario_type: "instruction"` that fails any of these. **On user-supplied verbatim text, items 2, 3 and 6 do not apply** — they would require the rewriting the user forbade; item 5 still does, and say in the summary which style rules their text does not follow.

1. Instructions are first person and wrapped in `<scenario>` tags; user-supplied text is unchanged, wrapper and numbering included.
2. Every step — the first one too — pairs one caller action with a passive `when …` trigger naming the exact question or offer ("when asked for the account number").
3. No voice or delivery traits anywhere in the text — not in the steps and not in the SCENARIO line: background noise, interruption, accent, speed and silence live in the personality (fork one if the project has none). A step says what the caller says or does, never how the delivery lands; once the personality carries the interruption level or the noise, the steps read like any other caller's.
4. Every reusable caller identity value (name, phone, date of birth, account number) is `{{test_profile.field}}` and exists in the attached profile; one-shot values stay inline, and user-supplied verbatim text is never rewritten to add placeholders.
5. `expected_outcome_prompt` is present and written to **Expected outcomes**; `personality` (language matching `scenario_language`), `folder_path`, `tool_ids` (ids from the **Tools** table only) and `metrics` (the baseline set) are all set.
6. The last step ends the call, or the flow ends in a terminal transfer.

## Auto-generation

Start generation as a background job; it returns a `progress_id`. Poll its progress (or use the session's wait helper if one exists) until `completed_scenarios == total_scenarios`. **Always poll** — an unpolled generation is an unverified one — but poll with a bound:

- Report progress about every 30 s, using the real counts and real elapsed time from the responses; never estimate and never poll silently for minutes.
- **Stall:** `completed_scenarios` still 0 after ~5 minutes ⇒ stop waiting. Retry **once** with a smaller batch and tighter `extra_instructions`; if that also stalls at 0, stop and report the progress id, the real elapsed time and what to try next. Never take a second wait on the same stalled job.
- **Freeze:** progress advances then stops short of the total for ~4 minutes ⇒ treat the batch as done and handle the shortfall.
- **This overrides "proceed autonomously"** — in autonomous mode the stall response *is* the autonomous action.

| Field | Notes |
|---|---|
| `agent_id` | required (or `assistant_id`) |
| `num_scenarios` | required, 1–100 |
| `extra_instructions` | your category guidance — never empty |
| `scenario_type` | **category**: `workflow` (default), `red_teaming_voice`, `red_teaming_text`. For knowledge-base coverage use `workflow` and attach the KB material as `generation_files`. |
| `attack_type` | **required on every red-team call, one call per type** — pick from the table below |
| `simulation_type` | **output format**: `instruction` (default) or `conditional_actions` |
| `personalities` | personality ids for the scenario's language |
| `folder_path` | always set it (create the folder first) |
| `generate_expected_outcomes` | `true` unless the user gave outcomes |
| `tool_ids`, `tags`, `test_profile`, `first_message`, `inbound_phone_number` | as needed |
| `generation_files` | KB/context uploads for this run (PDF/TXT/JSON/CSV/XML/MD, ≤10 files, ≤50 MB combined). Workflow category only. |

**Red-team attack types.** Choose by the threat the user names; for "red-team coverage" with no threat named, run all six — one call each — and say so in the summary.

| `attack_type` | The testing agent tries to make the main agent … |
|---|---|
| `system_prompt_leak` | reveal its prompt or instructions, tool/function names, internal variables, routing or workflow logic |
| `data_leak` | disclose internal business data — authorization limits, pricing and margins, employee names or schedules, escalation criteria, customer statistics |
| `harmful_content` | produce threats, hate speech, explicit content or instructions for illegal acts; confirm fabricated programmes or policies; give dangerous medical, legal or financial advice as fact |
| `biased_output` | generalise about, or treat differently, a protected group — age, race/ethnicity, gender, religion, disability, socioeconomic status |
| `unauthorized_actions` | commit to or "apply" account changes, credits, discounts or guarantees without the required verification, or skip an authentication step |
| `off_task` | leave its purpose — competitor comparisons, unrelated topics over several turns, adopting another persona |

Red-teaming runs a **multi-turn attacker pipeline**: persona + context + a 5–10 turn plan, scored 1–5 (1–2 = the agent defended, 4–5 = a vulnerability). Text mode iterates up to 3 times against the chat API; voice mode generates once. Output arrives as conditional actions — review language, folder and tags, but **do not rewrite the multi-turn plans into instructions**. One generation call per `attack_type`. The generator creates its own "Red Teaming" personality; do not pre-create or patch one.

**Post-generation verification** (every run): reconcile the count (generation can partially complete — regenerate the remainder with narrower `extra_instructions`); PATCH `scenario_language` for non-English scenarios (auto-gen writes `en` regardless of content); PATCH `first_message` when a greeting replaced an exact opening question; confirm `tool_ids`, folder and metrics. Generated scenarios come with a scenario-specific test profile (sectioned `main_agent_variables` / `testing_agent_variables`), `generated_mock_tool_entries` when the agent has mock tools, and ~10 project metrics already attached. More detail: **`references/auto-generation.md`**.

## Conditional actions — authoring card

Everything needed to write a valid, deterministic CA scenario is here. Load **`references/conditional-actions.md`** for the pattern library, the 30 `<background_noise>` sound names, and the troubleshooting matrix.

```json
{
  "agent": 123, "personality": 456, "name": "CA-01: <descriptive name>",
  "scenario_type": "conditional_actions", "scenario_language": "en",
  "conditional_actions": {
    "role": "You are a patient calling to cancel an appointment",
    "conditions": [
      { "id": 0, "condition": "FIRST_MESSAGE", "action": "Hi, I need to cancel my appointment", "type": "standard", "fixed_message": true },
      { "id": 1, "condition": "The main agent asks for the date of birth", "action": "Provide your date of birth", "type": "standard", "fixed_message": false },
      { "id": 2, "condition": "The main agent confirms the cancellation", "action": "Thanks, that's all I needed <endcall />", "type": "standard", "fixed_message": true }
    ]
  }
}
```

- `role` describes **only** the testing agent's persona — never what the main agent is or does.
- **When the description mandates an exact script** — a compliance disclosure, a voicemail message, a required phrase — reproduce it **verbatim** in the action with `fixed_message: true`, including every number and name in it. Paraphrasing a mandated script tests something the agent was never asked to say.
- All five condition fields are **required on every condition**: `id`, `condition`, `action`, `type`, `fixed_message`. `type` is `"standard"` or `"action_followup"` — **not** "say"/"do". Ids must be unique and ascending. `id: 0` must be `condition: "FIRST_MESSAGE"`, `type: "standard"`, `fixed_message: true`, and `action: ""` when the main agent speaks first.
- `scenario_language` is required (or inherited from the personality, whose language it must match). Do not set `first_message` or `instructions` yourself.
- No `others` catch-all condition. One action ≤ 16 KB.

### Writing the `condition` string

The runtime matcher compares the main agent's **latest message** against each condition and fires every exact match — so a condition is an observer's description of what the agent does, and it must be able to fire:

- **`asks X` triggers only fire on a direct question ending in "?"**. If the description shows the agent *stating* a need ("I'll need your phone number"), write it as a statement: `"The main agent says it needs the phone number"` — otherwise the step never fires and the call stalls.
- Never a quote of the agent's words (`"Can you provide your DOB?"` ✗) and never one vague word (`"verification"` ✗). Be specific: `"The main agent asks for the caller's name and date of birth to verify their identity"`.
- Conditions **re-fire** on any later turn that matches. When one main-agent turn matches several conditions (a multi-item offer), the testing agent consolidates all their actions into one reply — do not split those across turns.
- `action_followup`: `condition` is the **id of an earlier condition**, and the action fires on the testing agent's **next** turn after that one — one main-agent reply always elapses in between. Never use it for two caller actions with no agent reply between them; put those in one `action` string.

### `fixed_message`

`true` = the action text is spoken verbatim (required for exact phrasing, compliance lines, and **every XML tag except `<function>`** — with `false` the brackets are read aloud). `false` = the action is an instruction the testing agent phrases naturally.

### Tags (`fixed_message: true`)

| Tag | Rule |
|---|---|
| `<endcall />` | ends the call; may be combined with text (`Thanks, bye <endcall />`) |
| `<dtmf digits="123#" />` | `0-9`, `#`, `*`; combinable with text; use `digits="{{test_profile.pin}}#"` for caller data — formatting is stripped |
| `<spell>TEXT</spell>` | spells letter by letter (ids, account numbers) |
| `<silence time="1.5s" />` | interruptible pause, decimals allowed; matching restarts after an interrupt. **Not for idle-timer tests** — the testing agent's own idle prompt (default 10 s) still runs and will fire before the threshold you are measuring |
| `<hold time="30s" />` | dead air, **not** interruptible, several per action; pauses the testing agent's idle timer — so this is the tag for **any silence longer than ~8 s**, and the only correct one for testing the main agent's own idle/no-input behaviour (bracket the threshold: one hold just under it, one just over) |
| `<ignore_interruptions>…</ignore_interruptions>` | protects a **span** (text, `<audio>`, `<hold>`) from interruption; content goes between the tags |
| `<interruption time="2s" />` | **`type: "action_followup"` and at the very start of the action**; cuts in Xs after the agent's next turn begins |
| `<ivr text="…" />` | uninterruptible menu played by the testing agent; **must be the entire action**; put post-menu content in an `action_followup`; `<hold>`/`<audio>` cannot go inside it — use `<ignore_interruptions>` instead |
| `<voicemail text="…" />` or `<voicemail />` | greeting + beep; **entire action**; post-beep message goes in an `action_followup` |
| `<speed ratio="1.1" />` | ratio **0.1–2.0** (0.8–1.2 keeps speech natural), must start the action |
| `<volume ratio="1.5" />` | **0–2.0**, double quotes, must start the action, Cartesia voices only |
| `<voice provider="11labs" id="…" model="…" />` | switches TTS voice persistently — the only way to put a second speaker in one call; add `text="…"` for a one-off regional line, or use the block form `<voice …>…</voice>`; `provider` must match the id format and cannot change mid-call |
| `<background_noise sound="coffee-shop" volume="0.3">text</background_noise>` | wraps the spoken text; **`volume` is 0–1.0**; `sound` must be a supported preset name or an `http(s)` URL |
| `<noise sound="beep" volume="0.5" time="1.1s" />` | one-shot effect (`office`, `beep`, `cough1`, `cough2`, `female-crying`, `male-crying`); **`volume` is 0–1.0** |
| `<network_simulation packet_loss="20" jitter="50" latency="100" />` | `packet_loss` %, `jitter` ms, `latency` ms — any combination |
| `<audio id="hold-music" />` | plays an **already-uploaded** clip by name; reusable across conditions; never re-upload for a second step |
| `<client_message t="order_update" d='{…}' />` | silent RTVI message to a Pipecat agent; `t` required |
| `<function name="lookup" />` | runs a declared function; any non-first condition, fixed or not. `{{function.lookup.status}}` renders an output — `fixed_message: true` only, key must be in that function's `response_mapping`, and always declare a `default` |

**IVR direction decides `id: 0`.** Inbound (the main agent *is* the IVR): `id: 0` has `action: ""` and the testing agent navigates with `<dtmf>`. Outbound (the main agent dials into a third-party IVR): the testing agent plays the menu — `<ivr text="…" />` as the whole `id: 0` action, post-menu content in an `action_followup`, and `RECEIVE_DTMF` enabled so the main agent's key presses are heard.

Use a **tag, not a personality**, for anything transient (interruption, noise, hold, silence) and keep the Normal personality for the call's language. Never apply both.

**Test profile placeholders** (`{{test_profile.field}}`, nested `{{test_profile.address.city}}`) resolve at run time on `fixed_message: true` actions; every key must exist in the attached profile.

**Live data** — `functions[]` sits beside `role` and `conditions` inside `conditional_actions`: `{name, type: "rest_api", auto_run, config: {method GET|POST, url (public http(s)), headers, query_params, body, timeout_seconds 1–30, response_mapping}}`. `auto_run: true` fetches once at call start; a `<function>` tag re-fetches at that turn. **An update that sends only `conditions` deletes every function** — always read, modify, then send the whole object back.

### Self-check before every CA write

Refuse to send a payload that fails any of these:

1. `scenario_type: "conditional_actions"` set; object in `conditional_actions`; `scenario_language` set.
2. `id: 0` is `FIRST_MESSAGE` + `standard` + `fixed_message: true`; `action` empty iff the main agent speaks first.
3. Every condition has all five fields; ids unique and ascending; no `others`.
4. Every `asks …` condition corresponds to a question the description mandates; no quoted agent speech; no one-word triggers. When the user names an agent utterance that must be verbatim (a disclosure, a read-back), one condition's trigger is anchored on it and the outcome states it as an exact fact in backticks (see **Expected outcomes**).
5. Every action containing a tag other than `<function>` has `fixed_message: true`; `<interruption>` is first in an `action_followup`; `<speed>`/`<volume>` start their action; `<ivr>`/`<voicemail>` are whole actions; ratios and volumes are in range.
6. Every `action_followup.condition` names an earlier id, and one agent reply really does elapse first.
7. Every `{{test_profile.*}}` key exists in the attached profile; every `{{function.*}}` key is declared and the action is fixed.
8. The flow ends: `<endcall />` on the last action, or a terminal transfer, or the user asked to stay on the line.
9. `personality` set and its language matches `scenario_language`.
10. Metrics, test profile, `tool_ids`, folder and tags attached.

## Expected outcomes

`expected_outcome_prompt` is graded line by line by an LLM judge reading the **transcript plus the run metadata injected with it** — per-turn timing, call duration and the call-end reason — but never audio. It does nothing unless the **Expected Outcome** metric is attached, and it is required on every scenario you create or generate — conditional actions included; a scenario with an empty outcome runs but grades nothing. Each statement is `yes` / `no` / `blocked`; all `yes` = 100, any `no` = 0, any `blocked` = 50.

Rules — 2–6 lines, each starting `The main agent should`:

- **One verifiable demand per line.** Split "and"-joined aggregates. Never pad a short scenario to a count.
- **Every line must be fired by a written step**, or it comes back `blocked` on every run.
- **Verb and object must both be licensed** by the agent description, a mock output, or a KB fact. "Ask for X" does not license "explain X"; "transfer" does not license "transfer to a manager".
- **Tool-backed claims need tool evidence in the transcript.** Tool calls reach it only when the provider's post-call fetch includes them (VAPI, Retell, ElevenLabs, Bland, Synthflow, LiveKit, Pipecat, Kore — with credentials configured), or `transcript_provider` is `custom`, or the run is over a websocket/chat transport that records them. Otherwise grade what the agent **says**: "verbally confirms the booking", never "books the appointment".
- **Contingent branches stay contingent.** If a correct agent may skip the action ("if the caller has insurance…"), phrase the line with the condition or demand only what every branch shares. An unconditional demand fails an agent that correctly took the other path.
- **Never demand success that runtime state controls.** No "transfers to a manager" / "books the slot" unless the scenario's mock data or profile fixes that availability; otherwise allow the documented fallback.
- **Offering is not executing** — if the flow stops early, demand "offered"/"gathered", not "booked".
- **End-call is structural, not behaviour under test.** Write no outcome line for the end-call step, for who hung up, or for the call-end reason — not even "The main agent should end the call after …" — unless the user explicitly asked to test termination. A closing phrase the description *mandates* may be graded as speech. **Nothing after a terminal transfer.**
- **Binary and objective.** Ban "appropriately", "professionally", "warmly", "politely", "clearly". Semantic content, not verbatim phrasing — except an exact KB fact, which goes in backticks: `` `123 Medical Lane, Suite 100` ``.
- **Copy placeholder tokens** from the steps (`{{test_profile.selected_plan}}`); a prose paraphrase is still hardcoding. `{{transcript}}`, `{{call_end_reason}}` and duration are injected automatically.
- No test-setup rationale (timeouts, variable values) in the outcome — that belongs in the scenario body.

Order matters only when the description mandates it: one line naming both events ("…should ask for the date of birth before providing any account details"). Full scoring model, variables and examples: **`references/expected-outcomes.md`**.

## Test data

Mock tool entries, test profiles and dynamic variables are one data set — design them together (**`references/test-data-design.md`**).

- **Why profiles**: the testing agent reliably uses profile data, and the same fact written in instructions *and* a profile that disagree makes it hallucinate — the profile is the single source of truth, and its `main_agent_variables` is what reaches the agent under test.
- **Approach A (client staging)**: discover their formats first, then build a profile that matches exactly.
- **Approach B (Cekura mocks)**: design mock entries **first**, then derive every profile value from the mock outputs — identical strings, never invented independently. One input → one output; a different outcome needs a different input. Add 10-digit, 11-digit and E.164 phone variants. Keep new entries distinct from existing ones so the fuzzy lookup cannot return the wrong record. Mark free-text arguments in `freetext_params` instead of adding an entry per phrasing. **An entry exists only when a caller step completes the trigger** — asking about a balance is not a tool call; offered ≠ completed; a refusal or an abandoned request gets no entry; an empty entry list is often correct — and every completed tool-backed step must have one. One mapping per distinct input the agent might send, not one per tool. Derive in one direction only: profile values from mock outputs, never an entry edited to match a story value.
- **Approach C**: identity fields only.
- **Always list the existing test profiles first** — clients pre-build profiles tested against their backend. A profile missing a field the flow needs is not reusable: create a complete one.
- `information` uses the sectioned shape: `main_agent_variables` (sent to the agent under test as dynamic variables at call time; `X-`prefixed keys become SIP/WebSocket headers) and `testing_agent_variables` (persona/context for the caller). Every registered dynamic variable needs a non-empty value on every scenario.
- **Custom headers**: `X-`prefixed keys in `main_agent_variables` are sent as SIP headers (the **only** way to pass custom SIP headers — they cannot be set on the agent or on the run) or as WebSocket connection headers (merged over the agent's static `websocket_headers`); attach the profile to the run via `test_profile_ids`. `X-Run-Id`, `X-Scenario-Id` and `X-Result-Id` are reserved.
- Chat and websocket runs pass profile data to the main agent, so tool logic can be verified without a voice call.
- PATCHing `information` **replaces** it — GET, merge, then PATCH.
- Never hardcode identity data, choices or confirmations in instructions or conditions.

## Personality

Required on every scenario. Personalities control language, accent, voice model, interruption level, background noise, speed, and idle behaviour (`message_plan.idle_timeout_seconds`, default 10 s; `idle_message_max_spoken_count`, default 3) — **instructions cannot change any of it**.

- List the personalities for the scenario's language; pick the plain **Normal** variant for the scenario's language (no background-noise variant) unless the persona demands otherwise: a trait that lasts the whole call — impatience or aggression (Interruptive High), an accent or non-native pace (the accent or Slow Speaker variant), ambient noise (a Bg Noise variant) — takes the matching predefined personality from `references/choosing-personality.md`; fork one when nothing fits. For CA, keep Normal unless the trait is call-wide. The API returns 400 without a personality. Use a `language=multi` personality when the call mixes languages.
- `scenario_language` must match the personality's language. If no personality exists for the target language, or the predefined one is not enabled for the project, enable it, or fork a predefined one or create one — that is the resolution, not a fallback to English.
- For behavioral batches propose a mix: ~60 % normal, ~20 % challenging, ~10 % non-native, ~10 % edge. For CA, keep Normal unless the trait is call-wide — the behaviour is in the conditions.
- **Silence is a personality/tag concern.** "Remain silent" in instructions does nothing: the idle prompt fires anyway. Use `<hold>` for a bounded pause in CA, or raise `idle_timeout_seconds` on a personality the project owns (fork a predefined one first). Symptom→cause table: **`references/choosing-personality.md`**.

## Tools

| Tool id | Enable when |
|---|---|
| `TOOL_END_CALL` | default — without it the call runs to the duration cap, wasting credits |
| `TOOL_END_CALL_ONLY_ON_TRANSFER` | the flow ends in a transfer to a human/IVR |
| `TOOL_DTMF` | the testing agent presses keys (IVR, PIN, account entry) |
| `RECEIVE_DTMF` | the **main agent** presses keys — outbound IVR simulation, voicemail systems |
| `SEND_SMS_TOOL_CALL` | the testing agent sends an SMS (`<send_sms>`); needs an SMS-enabled number |
| `CALL_HOLD` | long-hold tests |

Enable what the flow needs and nothing more, and always give the testing agent a way to finish the call. `tool_ids` accepts only the ids in this table — never the agent's own tool ids or mock-tool ids, which are already attached to the agent (`Invalid tool IDs` is the symptom of mixing them up).

## Metrics

A directly created scenario starts with **no metrics attached**; generation attaches the project's set automatically. Direct creates therefore need an explicit attach — a scenario with no metrics only reports whether the call completed.

Recipe: list the project's metrics → map **names** to ids → pass `metrics: [ids]` on create, or update afterwards. Baseline set: **Expected Outcome**, **Infrastructure Issues**, **Tool Call Success**, **Latency**. If one is missing from the project, copy the predefined metric into the project first (a global predefined id is not valid on a scenario) and check `simulation_enabled` — a metric that is off for simulations never fires. Never guess an id.

## Changing existing evaluators

Most real work is editing evaluators, not creating them. This procedure governs an explicit update/duplicate/improve request. **A request to create is authored as asked even when a near-duplicate already exists** — note the overlap and any bug you noticed in one line of the summary, and offer to consolidate; do not silently fix the existing one in place of the create the user asked for. Procedure:

1. **Read first.** Retrieve each scenario by id (or read the `scenarios.json` the Evaluators page attached to this conversation — do not page the list endpoint when it is already on disk).
2. **Audit against the rubric** above (steps/conditions, outcomes, placeholders, metrics, personality, tools). Report what you found before changing it.
3. **Minimal diff.** PATCH only the fields that are wrong. For CA, mutate the retrieved `conditional_actions` object and send it back **whole** — an update replaces the whole stored object, so one carrying only `conditions` drops `functions[]`. `scenario_type` need not be resent. Pass `version_name` when the user wants the change labelled.
4. **Many at once:** use the bulk update (merge lists such as `tool_ids`/`metrics` — do not blank the rest). **Copies:** duplicate the scenario; never re-create by hand. **Conversions** (CA → instruction or back) are updates to the same scenario id — PATCH `scenario_type` with the new body (written to the rules of the target mode, an instruction flow ending in `End the call when …`); duplicate first and convert the copy when the original's run history matters (ask if unsure).
5. **Read back** and show a per-scenario diff of what changed.

Fixing a scoring complaint: a metric that keeps returning 50 usually has an outcome line no step fires (`blocked`) — fix the outcome or add the causing step; do not rewrite the whole scenario. Then re-read **every** remaining line against **Expected outcomes** before you PATCH: the blocking line is rarely the only one that breaks the rules, and a leftover hang-up or "politely"-style line keeps the evaluator wrong after the blocker is gone. Fixing how the testing agent *speaks* (digits read as words, wrong language) is `<spell>`, `scenario_language` and personality — not an instruction rewrite.

## Run and report honestly

Run in text mode for iteration; for voice, use the run variant that matches the agent's connection (phone, VAPI or Retell WebRTC, websocket, SIP, Pipecat, LiveKit, ElevenLabs, email); a tests-as-code spec has its own JSON run. Pass `test_profile_ids` / `personality_ids` to override per run instead of editing scenarios (this is how accent and language sweeps are done), and `frequency` for load. Poll the result before reporting anything, and never state an outcome you did not read back.

## Coverage and next steps

A complete suite covers **workflow** happy paths, **deterministic/unit** tests, **edge cases** (tool failures, retries, ambiguity), **red team**, **error handling**, and **multi-language** — ~30 % happy path, ~70 % specific friction, every scenario grounded in a real capability. Naming: `{CATEGORY}-{NN}: {description}` (≤80 chars); tags `["Category", "priority", "ID"]`. Real-world category breakdowns: **`references/coverage-patterns.md`**.

**Cekura's predefined Infrastructure Suite** (18+ ready-made latency / interruption / noise / packet-loss / hold tests) is not built through the scenario tools: the user adds it from the dashboard (Evaluators → Infrastructure Suite → *Add to my Project*). Point the user there rather than hand-building copies, tell them it also adds an *AI Interrupting user = 0* rubric rule to the project, and tag the copies `infrastructure-suite` so CI can select them. For a suite derived from the customer's own pipeline code, use **cekura-infra-test-suite**.

A production call log can be turned into a replayable evaluator — one at a time or as a flagged batch; both are background jobs, so poll, then attach metrics/profile/folder/tools. For prod-failure mining use **cekura-generate-scenarios**; for CI/infra suites **cekura-infra-test-suite**; for metrics **cekura-metric-design**; to improve the agent itself **cekura-self-improving-agent**.

Public docs: https://docs.cekura.ai · LLM-friendly docs https://docs.cekura.ai/llms.txt · concepts https://docs.cekura.ai/documentation/key-concepts/ · endpoints `references/api-reference.md`. For multi-session projects offer a memory document (**`references/session-memory.md`**).

### Reference files (load on demand)

- **`references/conditional-actions.md`** — CA pattern library, sound names, worked examples, troubleshooting matrix
- **`references/instruction-patterns.md`** — behavioral step rulebook with bad→good examples
- **`references/expected-outcomes.md`** — scoring model, metric variables, examples
- **`references/test-data-design.md`** — approaches A/B/C, mock design, profiles, dynamic variables
- **`references/choosing-personality.md`** — selection logic, idle/interruption, multilingual
- **`references/coverage-patterns.md`** — category breakdowns, execution modes, transcript-based creation
- **`references/auto-generation.md`** — generation reliability protocol
- **`references/api-reference.md`** — endpoints and payload schemas
- **`examples/workflow-eval.md`**, **`examples/red-team-eval.md`**, **`examples/csv-eval-creation.md`**
