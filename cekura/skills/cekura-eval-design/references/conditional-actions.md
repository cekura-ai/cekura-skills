# Conditional Actions Reference

> **This file is the payload reference, not the authoring contract.** It says
> what a valid conditional-actions object looks like; it does not carry the
> root skill's write path, pre-write self-check, expected-outcome rules, tool
> direction table, or update procedure. Read on its own it produces valid
> payloads that are wrong evaluators — load `cekura-eval-design` and check
> against its rules before you write.

## What They Are

Conditional actions create structured, repeatable test flows — **unit tests for voice agents**. The testing agent follows a predefined sequence of triggers and responses but adapts if the main agent deviates from the expected flow. Use them when a developer would write the test as code; use behavioral instructions when they would describe a persona.

| Signal | Use Conditional Actions | Use Adaptive Instructions |
|---|---|---|
| Goal | Exact flow validation, regression | Natural conversation, quality |
| Repeatability | Identical each run | May vary between runs |
| Conversation structure | Predictable, sequential | Branching, dynamic |
| Use case | Unit test, IVR nav, compliance | Edge cases, red-team, exploratory |
| Example | "Always press 1, then say DOB, then confirm" | "Act confused about billing" |

## API Payload Shape — Two Required Fields

Conditional-actions evaluators use a dedicated `conditional_actions` field on the scenario create/update payload. Do not put the JSON object in `instructions`. Correct payload:

```json
POST /test_framework/v1/scenarios/
{
  "agent": 123,
  "personality": 456,
  "name": "CA-01: Appointment verification — success path",
  "scenario_type": "conditional_actions",
  "scenario_language": "en",
  "conditional_actions": {
    "role": "You are a patient calling to cancel their upcoming appointment",
    "first_message": "Hi, I need to cancel my appointment",
    "conditions": [
      { "when": "The agent asks for your name", "say": "Sarah Johnson" }
    ]
  }
}
```

Three fields are load-bearing:

- **`scenario_type`** — must be set to the literal string `"conditional_actions"` (default is `"instruction"`). Other valid values: `"instruction"`, `"real_world_smart"`, `"real_world_fixed"`. Set this explicitly — the type is not inferred from the payload shape.
- **`conditional_actions`** — JSON object carrying `{role, first_message, conditions[]}` (plus an optional `functions[]` array — see "Custom Functions" below). Use this field, not `instructions`.
- **`scenario_language`** — required when `scenario_type="conditional_actions"`. Set explicitly, or rely on the assigned `personality` to supply it (a personality's configured language is used when `scenario_language` is omitted).

The fields inside `conditional_actions`:

- **`role`** — one sentence describing only what the testing agent is pretending to be. Example: `"You are a patient calling to cancel their appointment"`. Do not describe what the main agent is, does, or how it should behave — the role is exclusively the testing agent's persona.
- **`first_message`** — what the testing agent says to open the call. `""` (or omitted) when the main agent speaks first.
- **`conditions`** — ordered array of `{when, say, then}` objects, one per triggered caller response.

**Fields not to set independently when using `conditional_actions`:**

- the scenario-level `first_message` — derived from `conditional_actions.first_message`. Anything you pass will be overwritten.
- `instructions` — managed for you. Leave it unset.

**Older id-based shape — accepted, deprecated.** Payloads written as `conditions: [{id, condition, action, type, fixed_message}]` with a `FIRST_MESSAGE` row at `id: 0` are still accepted on create/update for backwards compatibility. Do not write them. Reads (`instructions` on retrieve/list, suite exports) always return the `first_message` / `when` / `say` / `then` shape, whichever shape was written (a legacy script with no equivalent, such as two followups branching from one condition, is returned as stored) — anything that parses `instructions` must expect it. Mapping when converting an old payload: `{condition: X, action: A, fixed_message: true}` → `{"when": X, "say": A}`; `fixed_message: false` → `"say": "<ai_generated>A</ai_generated>"`; an `action_followup` chained to it → the next entry of that condition's `then`; the `FIRST_MESSAGE` row (and its followups) → `first_message`.

## Fields

| Field | Type | Notes |
|---|---|---|
| `first_message` | string \| `{say, then}` | Opening line, always verbatim — `<ai_generated>` is rejected here. `""` (or omitted) when the main agent speaks first. The object form adds `then` steps after the opener. |
| `conditions[].when` | string | Required. A third-person description of what the main agent does that triggers this condition. |
| `conditions[].say` | string | Required, non-empty. The step the testing agent delivers when the condition matches. |
| `conditions[].then` | string[] | Optional follow-up steps, in order — each fires on the testing agent's next turn. |

A condition accepts only `when`, `say` and `then`; `first_message` as an object accepts only `say` and `then`. Unknown fields (including the old `id`/`condition`/`action`/`type`/`fixed_message` mixed into a new-shape condition) are rejected.

**Every step — `first_message`, each `say`, each `then` entry — is spoken verbatim by default.** To let the testing agent improvise from it instead, wrap the **whole** step: `"<ai_generated>Ask about pricing</ai_generated>"`. Partial wrapping (`"Sure. <ai_generated>…</ai_generated>"`), nesting and an empty wrapper are rejected.

**The first message is special:**
- It is always verbatim — `<ai_generated>` is not allowed in `first_message` / `first_message.say` (its `then` steps may use it).
- If the main agent speaks first (IVR or voicemail scenarios), set `first_message: ""` — the testing agent waits for the main agent to begin.
- **It is sent once and is never retried.** It fires as the call connects. If the main agent's speech cuts it off, whatever had not played yet is dropped and never spoken later; matching then continues through the conditions as usual, and an `<ai_generated>` reply may paraphrase the lost opener. `<silence>` always gives way when the agent starts talking (spoken text gives way per the personality's interruption settings), so a greeting that lands during a leading `<silence>` drops the whole line. So a leading `<silence>` in `first_message` is almost always a mistake: to let the agent greet first and then say an exact line, set `first_message: ""` and put the line on a condition whose `when` matches the greeting.

## Conditions vs `then` Steps

- **A condition (`when` + `say`)** — fires when the conversation context matches `when`. Write the trigger as a natural description of what the main agent will say or do.
- **A `then` step** — fires on the **next turn** after the step before it (the condition's `say`, `first_message`, or the previous `then` entry), not immediately. Sequence: testing agent delivers the step → main agent replies → the `then` step fires. The main agent's reply is received but does not affect whether the step fires. Two uses: (1) multi-part responses across consecutive turns, and (2) **scripted sequences** — a `then` list (often on `first_message`) delivers an exact sequence of messages from the testing agent with no conditions to match at all.

  **One step fires per turn. A `then` step fires at the testing agent's next turn** — the turn after the main agent replies to the step before it. If two things must happen within the same testing-agent turn (no main agent reply between them), they belong in one step, not split across `say` and `then`. See "Turn-by-Turn Construction Rules" below for a wrong/correct example.

### Interruption behavior — a `then` step re-executes from the start

**When the main agent interrupts the testing agent mid-step, the consequence depends on where the step sits:**

- **`then` step → the testing agent re-executes the whole step from the start.** Because a `then` step has no trigger string to re-match against, the only deterministic behavior on interruption is to repeat the same scripted step. If the interruption keeps recurring (e.g., the main agent talks every time the testing agent pauses), the testing agent will loop on the same sentence, never reaching the rest of the step. Real failure mode observed in production: a `<silence time="15s" />` inside a `then` step got interrupted by the main agent every cycle, causing the testing agent to repeat its opening line indefinitely.
- **A condition's `say` → the testing agent re-evaluates all conditions against the new conversation context and matches the best fit.** This is the adaptive path: if the agent's response moved the conversation forward, a different condition can fire; if the original condition still matches, the same step re-fires (but now with updated context).

**Which steps are fully uninterruptible.** Four forms:
- Steps whose entire payload is `<ivr text="..." />` (must occupy the whole step by validation rule).
- Steps whose entire payload is `<voicemail text="..." />` or `<voicemail />` (must occupy the whole step by validation rule).
- Steps that lead with `<interruption time="Xs" />` (the testing agent is itself cutting in on the main agent, so the main agent cannot interrupt back — the spoken text after the tag is protected).
- Any content wrapped in `<ignore_interruptions>...</ignore_interruptions>` (span-scoped, so unlike `<ivr>`/`<voicemail>` it does NOT have to be the entire step — and the main agent's speech during the span is still transcribed for evaluation, just never acted on).

`<hold>` is **only** uninterruptible during the hold period itself; any spoken text before or after `<hold>` in the same step remains interruptible (so `"sentence <hold time=\"3s\" /> sentence"` is not safe as a `then` step).

**Practical rule:** put a step on its own condition (`when` + `say`) when the scenario is **intentionally designed to invite an interruption** — most commonly a step containing a long `<silence>` tag (or an opening-line-then-silence pattern) where the test is precisely whether the main agent will speak during the deliberate pause. As a `then` step it loops on the same sentence each time the interruption recurs, because there is no `when` to re-match against. `then` remains the right choice for ordinary multi-part responses, scripted sequences, and `<interruption>` placement — those steps fire and complete quickly and are rarely interrupted in practice. See "Anti-Patterns" and "Troubleshooting" for the failure signature.

## Writing the `when` String

`when` must describe the main agent's observable action from a **third-person observer** perspective. It must never be a verbatim quote or the agent's own words.

**Good — observer describes what the agent does:**
- `"The main agent asks for the date of birth"`
- `"When the main agent greets the caller"`
- `"The main agent asks to confirm the caller's identity"`
- `"When asked for the caller's zip code"`

**Bad — verbatim quoted speech:**
- `"The agent says 'Can you please provide your date of birth?'"` ✗
- `"The main agent said 'Hi, how are you doing today?'"` ✗

**Bad — the agent's words stated directly:**
- `"Hi, I am Olivia from Ahealth. How can I assist you today?"` ✗
- `"Can you please provide your date of birth?"` ✗

Think of conditions as stage directions: *what does the agent do that prompts the caller's `say`?*

**Specificity:** Avoid one-word or vague triggers — `"verification"` may not fire. Prefer `"The main agent asks for the caller's name and date of birth to verify their identity"`.

## Verbatim vs `<ai_generated>` Steps

**Use a verbatim step (the default) when:**
- Exact wording matters (name, DOB, account number, confirmation codes, compliance phrases)
- Using XML tags (IVR, DTMF, silence, hold, etc. — tags only work in verbatim steps)
- Running compliance or regression tests requiring verbatim output

**Wrap the step in `<ai_generated>…</ai_generated>` when:**
- The caller should respond naturally
- You're giving behavioral instructions, not scripts
- Phrasing can vary without affecting the test

## XML Tags (verbatim steps only)

XML tags only work in verbatim steps; an `<ai_generated>` step carrying a tag (other than `<function>`) is rejected at save time. Tags run left to right and are not nested, except inside a regional `<voice ...>...</voice>` block.

### Communication

| Tag | Behavior | Constraint |
|---|---|---|
| `<ivr text="..." />` | Uninterruptible IVR menu played **by the testing agent**. Can appear in any step. Use it with conditions that detect which digit the main agent pressed (e.g., `"The main agent pressed 1"`) — see **DTMF from the main agent** below. | **Must be the entire step.** No surrounding text or other tags. `<hold>` and `<audio>` inside `text` are rejected at save time — use `<ignore_interruptions>` for clip sequences. |
| `<voicemail text="..." />` or `<voicemail />` | Uninterruptible voicemail greeting + auto-beep at end. `text` is optional (silent voicemail allowed). | **Must be the entire step.** Post-beep message goes in a `then` step. |
| `<ignore_interruptions>...</ignore_interruptions>` | Protected playback span: everything inside — text, attached `<audio>` clips, `<hold>`/`<silence>` pauses, or any mix — plays to completion. The main agent's speech during the span **is still transcribed and evaluated**; it just never interrupts playback or triggers a reply. | Block tag scoped to a **span**: content goes between the tags (never in an attribute), it may appear more than once per step with text/tags before and after, and spans cannot nest. |
| `<endcall />` | Terminates the call | **May be combined with surrounding text** (the only "communication-class" tag that allows this — useful for natural sign-offs like `Thanks, that's all I needed <endcall />`). |
| `<voice provider="P" id="X" model="Y" />` | Changes the testing agent's TTS voice. Add `text="..."` to speak only that text in the selected voice, or use `<voice ...>...</voice>` for a regional block. | `provider` and `id` required; `model` optional. Provider must match the active voice provider. Self-closing without `text` persists until another voice tag; regional forms restore the prior voice afterward. `text` is self-closing only; use the block form for nested tags. |

### Speech Control

| Tag | Behavior | Constraint |
|---|---|---|
| `<silence time="Xs" />` | Pause on the caller's turn — **interruptible** by the main agent; background noise continues; condition matching restarts after an interrupt. Supports decimal seconds for sub-second precision (e.g., `time="0.5s"`). | Embeddable mid-step |
| `<hold time="Xs" />` | Dead air — **not interruptible**; background noise stops | Multiple per step allowed |
| `<spell>TEXT</spell>` | Spell text letter-by-letter (no attributes) | Wrap target text |
| `<speed ratio="N" />` | Speech rate; ratio range **0.1–2.0** — 0.8–1.2 keeps speech natural, beyond that it is a stress test. Add `text="..."` to apply the ratio to just those words. | Embeddable mid-step; applies from where it appears until the next `<speed>` tag or the end of the step. `text` scopes it instead and restores the prior rate. Self-closing only — no block form. |
| `<volume ratio="N" />` | Volume; ratio range **0–2** (0 = silent, 1 = normal, 2 = double). Add `text="..."` to apply the ratio to just those words. | Same placement and scoping rules as `<speed>`. Above 1.0 the output clips, so prefer `<= 1.0` unless distortion is the point. Self-closing only — no block form. |

#### `<voice>` — simulating multiple speakers

The one way to get more than one voice into a simulated call. Use it for a caller handing the
phone over ("let me get my husband"), a supervisor taking over, or a different person picking up.

Use the self-closing form without `text` to switch voices persistently: all later speech uses the
new voice until another persistent `<voice />` tag changes it. For a temporary voice, use either
`text="..."` or an opening/closing regional block; the prior voice resumes immediately afterward.
The `text` form must be self-closing and cannot be combined with the block form.

```json
{
  "when": "agent asks to speak to the account holder",
  "say": "Hold on, let me get my husband. <voice provider=\"11labs\" id=\"21m00Tcm4TlvDq8ikWAM\" /> Hi, this is Mark speaking."
}
```

For a single temporary line, use `text`:

```json
{
  "when": "agent asks to speak to the account holder again",
  "say": "<voice provider=\"11labs\" id=\"21m00Tcm4TlvDq8ikWAM\" text=\"Hi, this is Mark speaking.\" /> How can I help?"
}
```

For regional speech containing inline tags, use the block form. This is the allowed nesting
exception, so pauses and other inline tags remain inside the temporary voice region:

```json
{
  "when": "agent asks Mark for more details",
  "say": "<voice provider=\"11labs\" id=\"21m00Tcm4TlvDq8ikWAM\">Let me check. <silence time=\"1s\" /> Yes, that is correct.</voice> Thanks for waiting."
}
```

**`provider` and `id` must belong together** — a voice id is issued by one provider and is
meaningless to any other. A mismatched pair is rejected when you save the evaluator:

| Provider | Voice ID format | Example | Default model |
|---|---|---|---|
| `cartesia` | UUID | `b7d50908-b17c-442d-ad8d-810c63997ed9` | `sonic-3.5` |
| `11labs` | Alphanumeric, no dashes | `21m00Tcm4TlvDq8ikWAM` | `eleven_turbo_v2_5` |

**The provider cannot change mid-call.** `provider` states which provider the id belongs to; it
must be the provider the evaluator already runs on. To use a voice from a different provider,
change the evaluator's voice configuration instead.

Omit `model` to take the provider default from the table above.

Prefer `<voice>` over an attached audio clip when you only need a *different speaker* — a
recording also fixes the dialogue, so the testing agent can no longer adapt.

#### `<silence>` vs `<hold>`

| | `<silence>` | `<hold>` |
|---|---|---|
| Interruptible by main agent | ✅ Yes | ❌ No |
| Background noise during pause | ✅ Continues | ❌ Stops |
| Time precision | Decimal seconds — `"0.5s"`, `"2s"`, `"2.5s"` | Seconds — `"2s"`, `"10s"` |

### Interaction

| Tag | Behavior | Constraint |
|---|---|---|
| `<dtmf digits="..." />` | Send touch-tone digits. Supports digits, `#`, and `*` (e.g. `digits="123"`, `digits="456#"`, `digits="*9"`), or a `{{test_profile.key}}` placeholder for caller data (`digits="{{test_profile.pin}}#"`). | Combinable with text |
| `<send_sms text="..." />` | Trigger an SMS for testing SMS-driven workflows | `text` required |
| `<client_message t="..." d='...' />` | Send an app-defined RTVI client message to a Pipecat agent | `t` required; `d` optional; verbatim step |
| `<interruption time="Xs" />` | Cuts in `Xs` after the **main agent starts its next turn** (shorter = more aggressive) | **Must be in a `then` step (including `first_message.then`) — not `first_message` or a condition's `say` — AND must appear at the very start of the step.** Must be followed by spoken text or a sound clip (`<noise sound="cough1" />`, `<audio id="…" />`); a bare tag, or one followed only by `<silence>`/`<hold>`, is rejected. |

### Environmental

| Tag | Behavior | Constraint |
|---|---|---|
| `<background_noise sound="NAME" volume="N">spoken text</background_noise>` | Continuous ambient sound behind the caller's voice | Wraps the spoken text. `volume` optional, range **0–1.0** (e.g. `0.3`). |
| `<noise sound="NAME" volume="N" time="N" />` | One-shot sound effect at a point in the step | `volume` (range **0–1.0**, optional) and `time` (bare **milliseconds**, e.g. `"1100"` — not `"1.1s"`; truncates the clip, optional) |
| `<network_simulation packet_loss="N" jitter="N" latency="N" />` | Simulate a degraded connection: `packet_loss` percent (0–100), `jitter` ms, `latency` ms | Any combination of the three; at least one required. |

#### `<background_noise>` sound names

| Category | Sounds |
|---|---|
| Office / retail | `office-ambience`, `coffee-shop`, `kitchen-noise`, `home-chatter`, `restaurant`, `shopping-mall`, `train-station` |
| Nature / weather | `rain-thunder`, `windy-day`, `air-conditioner` |
| Transportation | `inside-car`, `inside-train`, `busy-street`, `airport-boarding` |
| People | `dog-barking`, `baby-crying`, `coughing`, `two-people-talking` |
| Technical | `keyboard-typing`, `background-printer`, `static-radio`, `fan-buzz`, `ship-humming`, `vacuum-cleaner`, `construction-site` |
| Ambient | `quiet-room`, `stadium-crowd`, `standard-hiss`, `public-park`, `holding-on-song` |

#### `<noise>` (one-shot) sound names

`office`, `beep`, `cough1`, `cough2`, `female-crying`, `male-crying`, `ringback`

The one-shot list is a growing catalog: sounds added to the platform after this
skill shipped are equally valid — if the scenario save accepts the name, it will
play. A direct `https://` URL to an audio file is also accepted as `sound=`.

`ringback` is ~6s of a phone ringback tone (one ring, the gap, the start of the next). `female-crying` / `male-crying` are ~10s clips of a person sobbing — use them to test whether the agent notices a caller in distress and checks in (`<noise sound="female-crying" time="6000" /> Sorry... I just got some bad news.`). Shorten with `time` if needed.

## Attached Audio (`<audio>` — reference an existing recording by name)

**Pre-recorded audio clips** belong to the scenario, and a verbatim step plays one by referencing it. One recording can be referenced from as many steps as needed, and more than once in a single step:

```json
{ "when": "The agent greets you", "say": "Before <audio id=\"hold-music\"/> <silence time=\"1s\"/> continue" }
```

**Only reference recordings that already exist.** Read the scenario's `condition_audio` map (returned by `GET /test_framework/v1/scenarios/{id}/`) for the available ids — each entry carries a ready-to-paste `tag` and the `steps` currently using it (paths such as `first_message` or `conditions[0].then[1]`, alongside numeric `condition_ids`). Reuse a recording rather than asking for the same audio twice.

- **Never invent an id.** Referencing a recording that does not exist saves fine but blocks every run of that scenario (`"references recording 'X', which does not exist"`). If the audio you want is not in `condition_audio`, write the step as ordinary text and tell the user which recording to upload.
- **Uploading** (only when you have the audio file): `POST /test_framework/v1/scenarios/{id}/condition-audio/`, multipart, `file` required, ≤25MB, wav/mp3/m4a/ogg/webm/flac. Omit `condition_id` to add the recording without touching any step, then reference it yourself; pass `condition_id` (with optional `action_template` carrying one `<audio />` marker) to have the tag inserted for you. `condition_id` numbers the steps from 0 in reading order: `first_message` is 0, then its `then` steps, then each condition's `say` followed by its `then` steps.
- **Naming.** Omit `name` and the id is derived from the filename using the same convention the editor proposes, so an evaluator you create matches one a person creates. Pass `name` only to override it, and follow the same shape: lowercase, hyphen-separated words, derived from what the clip *is* (`hold-music`, `clinic-greeting`, `ivr-menu-option-2`), letters/digits/`_`/`-` only, ≤64 characters (the editor keeps its own proposals ≤32), unique per scenario case-insensitively. Do not invent opaque ids — the id is what a human reads in the step text.
- `PUT .../condition-audio/{audio_id}/` replaces that recording's audio, so every step using it plays the new file. Send `name` to rename it at the same time — the ids follow filenames, so a new file usually means a new name — and every `<audio>` tag pointing at it is repointed for you; the response carries `previous_audio_id` and the rewritten `actions`. Omit `name` to keep the current id. `DELETE` removes the recording and every reference to it, returning 409 without deleting anything if that would leave a step other than the first message empty — so prefer `PUT` over delete-and-re-add for a clip several steps use.
- **Rules:** verbatim steps only; multiple recordings and sibling tags are allowed and run left to right; do not nest `<audio>` inside a wrapping tag (`<spell>`, `<background_noise>`, `<voicemail>`, `<ivr>`). Inside `<ignore_interruptions>` is fine — an uninterruptible clip sequence is that tag's main use.
- **Run gating:** a scenario can't run while a referenced recording is missing, or is not `ready` (pending/processing/failed all block).

## Test Profile Template Variables

Inject test-profile fields into a step. Substitution happens at run time, on **every** step, before the runtime looks at whether the step is verbatim — so a placeholder resolves in an `<ai_generated>` step too. What a verbatim step decides is whether the resolved value is *spoken verbatim*: in a verbatim step the rendered text is the line, in an `<ai_generated>` one it is guidance the testing agent rephrases. Use a verbatim step when the exact wording is itself the requirement (compliance phrasing, an account number read back, keypad entry); an `<ai_generated>` step is the right choice when the value matters and the phrasing does not. (A verbatim step is still required for XML tags and for `{{function.*}}` outputs — those are separate rules, not this one.)

| Pattern | Example |
|---|---|
| Simple field | `{{test_profile.first_name}}` |
| Bracket notation (keys with spaces or special chars) | `{{test_profile['account_id']}}` |
| Nested field | `{{test_profile.address.city}}` |
| Combined with XML tag | `<spell>{{test_profile.account_number}}</spell>` |

A placeholder is only as good as the profile behind it: a key that exists but holds an empty value renders to nothing, and the caller says a sentence with a hole in it. Check the attached profile has a real value for every key a step references before the scenario runs.

Two ways to use profile data in conditions:

- **Behavioral instruction (`<ai_generated>`):** `"<ai_generated>Provide your full name and date of birth for verification</ai_generated>"` — the testing agent reads from the profile and phrases it naturally.
- **Template variable in a verbatim step:** `"My name is {{test_profile.first_name}} {{test_profile.last_name}} and my date of birth is {{test_profile.dob}}"` — exact phrasing AND the real profile value both matter (compliance, IVR account-number entry).
- **Template variable in an `<ai_generated>` step:** `"<ai_generated>Provide your full name: {{test_profile.full_name}}</ai_generated>"` — the value is resolved and handed to the testing agent, which phrases the reply itself. Valid, and the right trade when you want the real value without scripting the sentence.

### Test Profile Rules (read before writing any step)

**Rule A — Key exists → use the placeholder.**
If a key exists in `test_profile`, you MUST use `{{test_profile.key}}` in the step. Apply **semantic mapping**: the agent may use a different variable name internally (e.g., the agent expects `firstName` but the profile has `customer_name`). If the profile key is semantically equivalent to the data the agent is asking for, use the profile key.

- ✗ `"Yes, this is John."` (when `test_profile` contains `customer_name`)
- ✓ `"Yes, this is {{test_profile.customer_name}}."`

**Rule B — Key absent → hardcode a realistic literal.**
If a key is absent from `test_profile` (and no semantically equivalent key exists), hardcode a realistic value. Never reference a placeholder for a key that does not exist.

- ✗ `"Hello, this is {{test_profile.firstName}}."` (will fail if key is missing)
- ✓ `"Hello, this is John."`

**Rule C — Intentionally wrong values are the exception.**
You MAY hardcode an incorrect value when the scenario explicitly requires the caller to give wrong information first. The subsequent correction MUST use the `{{test_profile.key}}` placeholder.

- Wrong DOB (intentional): `"It's May 10th, 1980."`
- Correction: `"Sorry, I meant {{test_profile.dateOfBirth}}."`

## Custom Functions — Live API Data (`functions[]`)

Functions let the testing agent call a REST API during the call and use the response in its replies — a real order status instead of an invented one. Declare them in an optional `functions` array inside `conditional_actions` (sibling of `role`, `first_message` and `conditions`):

```json
"functions": [
  {
    "name": "lookup",
    "type": "rest_api",
    "auto_run": true,
    "config": {
      "method": "GET",
      "url": "https://api.example.com/orders/{{test_profile.order_id}}",
      "timeout_seconds": 5,
      "response_mapping": {
        "status": { "path": "$.status", "default": "unknown" },
        "customer": "$.customer_name"
      }
    }
  }
]
```

**Function spec fields:**

| Field | Notes |
|---|---|
| `name` | Unique; `[A-Za-z0-9_-]`, ≤64 chars. Used in tags/placeholders. |
| `type` | `"rest_api"` — the only supported type. |
| `auto_run` | Optional boolean, **default `true`** = runs once at call start, in the background, so values are ready for every condition. `false` = runs only via a `<function>` tag. |
| `config.method` | `GET` or `POST`. |
| `config.url` | `http(s)` only; supports `{{test_profile.*}}`. Must be **publicly reachable** — localhost/private-network hosts pass create-time validation but are refused at call time. |
| `config.headers` / `config.query_params` | Flat objects; values must be strings or numbers. |
| `config.body` | POST only. Object/array → sent as JSON; string → sent raw. |
| `config.timeout_seconds` | 1–30; **10 if omitted**. Keep short — a tag-triggered call delays the turn waiting on it. |
| `config.response_mapping` | Output name → JSONPath string, or `{"path": ..., "default": ...}`. |

**Two references from a step:**

- `<function name="lookup"/>` — **invoking tag**: runs the function when the step fires. Allowed in any step except the first message itself — a condition's `say` or any `then` step (including `first_message.then`), verbatim or `<ai_generated>`.
- `{{function.lookup.status}}` — **value placeholder**: renders one mapped output into the spoken text. **Verbatim steps only**, and the key must be declared in that function's `response_mapping`.

**Choosing the trigger:** prefer `auto_run` for data the call will need — it fetches in the background at call start, so no turn waits on the API. Use the tag when timing matters (fetch only after some exchange) or to **re-fetch**: a tag always makes a fresh request, even for a function `auto_run` already ran.

**Trigger + use in one step:** put the tag before the placeholder in the same verbatim step — the function completes before the text is spoken:

```json
{ "when": "The agent asks what status you see", "say": "Let me check. <function name=\"lookup\"/> It shows as {{function.lookup.status}}." }
```

**AI-generated grounding:** in an `<ai_generated>` step, no placeholder is needed (or allowed) — the testing agent automatically receives the function's outputs and response and phrases its reply from them: `"<ai_generated>Mention the real order status when asked.</ai_generated>"`.

**Chaining:** a later function's `config` may reference an earlier function's outputs — `"url": "https://api.example.com/verify?name={{function.lookup.customer}}"`. The referenced function must have already run (`auto_run` or a tag on an earlier step).

**JSONPath subset:** dotted keys (`$.data.status`), array indices (`$.items[0]`, negative allowed), bracket keys (`$.meta["order-id"]`). No wildcards, filters, or recursion — one exact value per output.

**Failure behavior:** a timeout, error response, or unreachable URL never breaks the call. Mapped outputs fall back to their declared `default`; a placeholder with no default is spoken literally (audible in the transcript — always declare defaults for placeholder-referenced outputs); in `<ai_generated>` steps the testing agent is told the lookup failed so it doesn't invent values.

**Validation (rejected at create/update):** duplicate function names; unknown `type`; tag or placeholder in the first message; `{{function.*}}` in an `<ai_generated>` step; references to undefined functions; placeholder keys not declared in `response_mapping`; malformed placeholders (`{{function.lookup}}` — key part required); `timeout_seconds` outside 1–30; methods other than GET/POST; non-http(s) URLs.

### API / MCP flow (create → read → update)

- **Create** — `functions[]` rides inside the same `conditional_actions` object; there is no separate endpoint or field:

```json
POST /test_framework/v1/scenarios/
{
  "agent": 123,
  "personality": 456,
  "name": "CA-09: Order status — live lookup",
  "scenario_type": "conditional_actions",
  "scenario_language": "en",
  "conditional_actions": {
    "role": "You are a customer checking on an order",
    "functions": [
      { "name": "lookup", "type": "rest_api",
        "config": { "method": "GET", "url": "https://api.example.com/orders/{{test_profile.order_id}}",
          "response_mapping": { "status": { "path": "$.status", "default": "unknown" } } } }
    ],
    "first_message": "Hi, checking on my order.",
    "conditions": [
      { "when": "The agent asks for the order status you see", "say": "It shows as {{function.lookup.status}} on my side." }
    ]
  }
}
```

- **Read** — retrieval returns the scenario's `instructions` as a JSON **string** in the `role` / `first_message` / `conditions` (`when`/`say`/`then`) / `functions` shape — also for scenarios originally written in the old id-based shape. Parse it to inspect `functions[]`. There is no separate functions field on the response.
- **Update — full replace, so read-modify-write.** `conditional_actions` on an update rebuilds the stored object from exactly what you send. A PATCH that omits `functions` **silently deletes every function**. Always: parse the current `instructions`, apply the change, send the WHOLE object (role + first_message + conditions + functions) back.
- **Auto-generation never emits functions.** Generated scenarios (`scenarios_generate_bg` / auto-gen) will not contain `functions[]` — add them afterward with a read-modify-write update.

## Turn-by-Turn Construction Rules

Apply these rules when building the script:

- **One condition per required caller response.** Don't combine two separate agent prompts into one condition.
- **Proactive information.** If the caller answers the current question and proactively volunteers information for a *future* question in the same turn (e.g., "My DOB is X and my zip is Y"), combine both pieces into the current condition's `say`. Don't create a separate condition for the anticipated follow-up.
- **Self-correction.** If the caller misspeaks and immediately corrects themselves, model it as one condition: its `say` contains the wrong info, and a `then` step contains the correction.

  ```json
  { "when": "The agent asks for your date of birth", "say": "It's May 10th, 1980.", "then": ["Sorry, I meant {{test_profile.dateOfBirth}}."] }
  ```

- **Same-turn actions must share one step.** Before adding a new step, ask: **does the main agent produce a reply between the previous testing-agent step and this one?** If the main agent is silent (e.g., the call is on hold, the testing agent is mid-voicemail sequence, or two caller actions follow immediately), those actions must go in the same step. A `then` step only fires after the main agent replies — if the main agent doesn't reply, the step hangs and the call stalls.

- **Reproduce specified dialogue exactly.** Do not paraphrase or shorten scripted lines.

## Worked Examples

### 1. Linear Verification Flow

```json
{
  "role": "You are an established patient calling to check your appointment status",
  "first_message": "Hi, I'd like to check on my upcoming appointment",
  "conditions": [
    { "when": "The agent asks for your name", "say": "My name is Sarah Johnson" },
    { "when": "The agent asks for your date of birth", "say": "January first, nineteen ninety" },
    { "when": "The agent confirms your identity and provides appointment details", "say": "Thank you, that's all I needed <endcall />" }
  ]
}
```

### 2. IVR Navigation (Inbound — main agent IS the IVR)

This is the canonical pattern: the **main agent owns the IVR audio**. The testing agent (caller) waits silent (`first_message: ""`) and presses DTMF when prompted. The `<ivr>` tag is **not** used here — only `<dtmf>`.

```json
{
  "role": "You are a customer calling support; the company has an IVR menu before reaching a human",
  "first_message": "",
  "conditions": [
    { "when": "The IVR menu finishes playing the options", "say": "<dtmf digits=\"2\" />" },
    { "when": "The agent greets you and asks how they can help", "say": "<ai_generated>I have a question about a charge on my last bill</ai_generated>" },
    { "when": "The agent asks for your account number", "say": "<dtmf digits=\"{{test_profile.account_number}}#\" />" },
    { "when": "The agent resolves your billing question", "say": "Thanks, that clears it up <endcall />" }
  ]
}
```

Note the split between the two `<dtmf>` tags: the first is a **menu choice** the IVR itself dictates, so it stays a literal `2`. The third condition's is **caller data**, so it references the test profile — the same evaluator then works for every profile you run it against instead of needing a copy per account number. Applies to any keyed-in caller data: account/customer number, PIN, DOB, zip.

For the less-common case where the testing agent simulates an external IVR for the main agent to navigate (outbound flows), see "Worked Example 2b" below.

### 2b. IVR Simulation (Outbound — testing agent plays an external IVR)
Use this pattern only when the **main agent makes outbound calls** and the scenario simulates a third-party IVR the main agent must navigate. The `<ivr>` tag goes in the testing agent's step because the testing agent plays the IVR audio.

**DTMF from the main agent:** keys the main agent presses always reach the testing agent — this does not depend on an `<ivr>` tag being in the scenario. They arrive as a Main Agent turn of the form `DTMF: <digits>`: presses less than about 2 seconds apart are grouped into one turn, and `#` ends a group immediately. Each turn is matched against the conditions like speech, so write precise conditions naming the digit — `"The main agent pressed 1"` instead of the vague `"The agent presses or speaks a menu option"`. Several conditions with identical wording are resolved in script order (the earliest one not yet executed), so give each menu step its own wording — name the digit, and the menu it answers if the same digit is pressed at more than one menu.

```json
{
  "role": "You are simulating a third-party IVR system that the agent will encounter when calling out",
  "first_message": "<ivr text=\"Thank you for calling Acme Corp. Press 1 for sales, press 2 for support.\" />",
  "conditions": [
    { "when": "The main agent pressed 1", "say": "Connecting you to sales now" },
    { "when": "The agent states their reason for calling", "say": "I'll route your call. Thank you. <endcall />" }
  ]
}
```

### 2c. Uninterruptible Clip Sequence (multi-part IVR menu of attached audio)

Use when the testing agent must play several pre-recorded clips separated by pauses and nothing the main agent says may cut the sequence short. The main agent's speech during the span still lands in the transcript, so metrics can judge what it said over the menu.

```json
{
  "role": "You are simulating a third-party IVR system playing a recorded menu",
  "first_message": {
    "say": "",
    "then": ["<ignore_interruptions> <audio id=\"clip1\"/> <hold time=\"5s\" /> <audio id=\"clip2\"/> <hold time=\"5s\" /> <audio id=\"clip3\"/> </ignore_interruptions> <endcall />"]
  }
}
```

The `<audio>` ids come from the audio-upload flow (see "Attached Audio") — never hand-write them. `<endcall />` sits after the span so the call ends only once the full sequence has played.

### 3. Voicemail with Post-Beep Message

```json
{
  "role": "You are calling a clinic that has gone to voicemail",
  "first_message": "",
  "conditions": [
    {
      "when": "The call goes to voicemail",
      "say": "<voicemail text=\"Hi, you've reached our office. Please leave a message after the beep.\" />",
      "then": ["Hi, this is Sarah Johnson calling to confirm my appointment tomorrow. Please call me back."]
    }
  ]
}
```

### 4. Multi-Part Response with `then`

A `then` step fires on the **next turn** after the step before it — not immediately. Sequence: testing agent delivers the `say` → main agent replies → the first `then` step fires.

```json
{
  "role": "You are a customer calling to update your contact information",
  "first_message": "I need to update my email address on file",
  "conditions": [
    { "when": "The agent asks for your account information to verify your identity", "say": "<ai_generated>Provide your name and account number for verification</ai_generated>" },
    { "when": "The agent asks for your new email address", "say": "My new email is john.smith@example.com", "then": ["And please make sure that's lowercase, all one word"] },
    { "when": "The agent confirms the email update", "say": "Perfect, thanks for your help <endcall />" }
  ]
}
```

**Scripted sequence pattern:** a `then` list delivers an exact sequence of messages turn by turn, with no conditions to match — each step fires automatically after the main agent replies:

```json
{
  "role": "You are a customer providing multi-field information",
  "first_message": {
    "say": "I need to update my address",
    "then": [
      "My new street is 123 Main Street",
      "City is Springfield",
      "Zip code is 62701 <endcall />"
    ]
  }
}
```

### 5. Mid-Flow Pivot (Cancel → Reschedule)

```json
{
  "role": "You are a patient who calls to cancel but changes their mind and reschedules",
  "first_message": "I need to cancel my appointment for next Tuesday",
  "conditions": [
    { "when": "The agent asks for verification", "say": "<ai_generated>Provide your name and date of birth for verification</ai_generated>" },
    { "when": "The agent confirms the appointment you want to cancel", "say": "Actually, could I reschedule instead of cancelling?" },
    { "when": "The agent offers available reschedule slots", "say": "<ai_generated>Select the earliest available morning slot</ai_generated>" },
    { "when": "The agent confirms the new appointment", "say": "That works perfectly, thank you <endcall />" }
  ]
}
```

### 6. Interruption Mid-Sentence

```json
{
  "conditions": [
    {
      "when": "The agent starts explaining the cancellation policy",
      "say": "I understand, please go ahead",
      "then": ["<interruption time=\"2s\" /> Sorry to interrupt — I actually just have a quick question"]
    }
  ]
}
```

### 7. Degraded Connection Simulation

```json
{
  "role": "You are a caller testing the agent's ability to handle poor audio quality",
  "first_message": "<network_simulation packet_loss=\"10\" /> Hello, I'm having trouble hearing you",
  "conditions": [
    { "when": "The agent asks how they can help", "say": "I need to reschedule an appointment <silence time=\"2s\" /> Sorry, bad connection" },
    { "when": "The agent processes your reschedule request successfully", "say": "Great, thanks <endcall />" }
  ]
}
```

## Validation Rules

The Cekura API rejects requests that violate these rules, and each error names the exact place in your payload — `first_message`, `conditions[2].say`, `conditions[0].then[1]`. See "Troubleshooting" below for the exact wording.

1. **`scenario_type` must be `"conditional_actions"`** — explicit and required. The mode is not inferred from the payload shape; set it on every conditional-actions create/update request.
2. **The first message is verbatim** — `first_message` (and `first_message.say`) cannot contain `<ai_generated>`. Its `then` steps can.
3. **Every condition needs `when` and a non-empty `say`** — `when` is required, and every step except `first_message` must be a non-empty, non-whitespace string. `first_message` may be `""` when the main agent speaks first (e.g., IVR / voicemail flows).
4. **`<ai_generated>` wraps the whole step** — it cannot be partial, nested, or empty.
5. **Only known fields** — a condition accepts only `when`, `say`, `then`; `first_message` as an object accepts only `say`, `then`. `then` must be a list of strings.
6. **Tags need a verbatim step** — an `<ai_generated>` step carrying a tag (other than `<function>`) or a `{{function.*}}` placeholder is rejected; `<interruption>` must open a `then` step.
7. **`scenario_language` required** — Conditional Actions evaluators require a language. Set it via a personality with a configured language (inferred automatically) or set `scenario_language` explicitly. This also applies when changing an existing evaluator's type to Conditional Actions.
8. **`personality` required** — every scenario needs a personality assigned, conditional-actions or otherwise. The API returns 400 without one.
9. **`<audio>` tags must reference uploaded clips** — every id must reference a real uploaded clip and the step must be verbatim. Hand-written `<audio>` tags fail this. Don't author them — audio is attached via the [upload endpoint](#attached-audio-audio--managed-do-not-hand-author).

### Extra rules at generation time (LLM-generated scenarios only)

These additional rules apply when the platform's auto-generator produces a scenario. They are **not** enforced on manually-authored API requests, but following them is good practice:

- Only documented tags are accepted (unknown tags are rejected)
- Multiple sibling tags are allowed and run left to right; do not nest tags
- A step containing a tag must be verbatim (not `<ai_generated>`)
- `<speed>` and `<volume>` may appear anywhere in the step; neither has a block form
- "others" / catch-all conditions are rejected — write specific triggers

---

Continued in **`conditional-actions-patterns.md`**: the pattern library by use case, multi-turn probe and duration control (stall-proof positional chaining), anti-patterns, the validation checklist, troubleshooting (error message → fix), supporting fields and the quick reference card.
