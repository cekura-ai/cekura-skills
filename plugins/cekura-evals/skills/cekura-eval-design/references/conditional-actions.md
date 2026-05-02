# Conditional Actions Reference

## What They Are

Conditional actions create structured, repeatable test flows — **unit tests for voice agents**. The testing agent follows a predefined sequence of triggers and responses but adapts if the main agent deviates from the expected flow. Use them when a developer would write the test as code; use behavioral instructions when they would describe a persona.

| Signal | Use Conditional Actions | Use Adaptive Instructions |
|---|---|---|
| Goal | Exact flow validation, regression | Natural conversation, quality |
| Repeatability | Identical each run | May vary between runs |
| Conversation structure | Predictable, sequential | Branching, dynamic |
| Use case | Unit test, IVR nav, compliance | Edge cases, red-team, exploratory |
| Example | "Always press 1, then say DOB, then confirm" | "Act confused about billing" |

## Top-Level Shape

The `instructions` field of the scenario payload becomes a JSON object (not a string):

```json
{
  "instructions": {
    "role": "You are a patient calling to cancel their upcoming appointment",
    "conditions": [...]
  }
}
```

- **`role`**: one-sentence persona for the testing agent (system-prompt-equivalent)
- **`conditions`**: ordered array of condition-action pairs, one per turn

## Condition Fields — All Five Required

| Field | Type | Notes |
|---|---|---|
| `id` | integer | Unique. First condition must be `0`. |
| `condition` | string \| integer | `"FIRST_MESSAGE"` (literal string) for `id:0`, **always required even when the main agent speaks first**. Trigger description for `standard`. Prior condition's integer `id` for `action_followup`. |
| `action` | string | Verbatim text (`fixed_message: true`) or behavioral instruction (`fixed_message: false`). May be empty `""` only on `id:0` when the main agent speaks first. |
| `type` | string | `"standard"` or `"action_followup"`. **Required — no default.** Omitting returns a validation error. |
| `fixed_message` | boolean | `true` = spoken verbatim; `false` = natural-language instruction. Required. |

**The `id: 0` first condition is special:**
- `condition` must be the literal string `"FIRST_MESSAGE"` — not `""` (the older convention is wrong).
- `fixed_message` must be `true`.
- If the main agent speaks first (IVR or voicemail scenarios), set `action: ""` — the testing agent waits for the main agent to begin.

## Condition Types

- **`standard`** — fires when the conversation context matches the `condition` string. Write the trigger as a natural description of what the main agent will say or do.
- **`action_followup`** — fires immediately after a prior action regardless of what the main agent says next. `condition` is the integer `id` of the preceding condition. Use for multi-part responses and for `<interruption>`.

## fixed_message: true vs false

**Use `fixed_message: true` when:**
- Exact wording matters (name, DOB, account number, confirmation codes, compliance phrases)
- Using XML tags (IVR, DTMF, silence, hold, etc. — tags only parse when `true`)
- Running compliance or regression tests requiring verbatim output

**Use `fixed_message: false` when:**
- The caller should respond naturally
- You're giving behavioral instructions, not scripts
- Phrasing can vary without affecting the test

## XML Tags (fixed_message: true only)

XML tags are interpreted as syntax only when `fixed_message: true`. With `false`, the testing agent reads the angle brackets as literal instructions.

### Communication

| Tag | Behavior | Constraint |
|---|---|---|
| `<ivr text="..." />` | Uninterruptible IVR menu — full text plays to completion; main agent cannot speak over it | **Must be the entire action.** No surrounding text or other tags. |
| `<voicemail text="..." />` or `<voicemail />` | Uninterruptible voicemail greeting + auto-beep at end. `text` is optional (silent voicemail allowed). | **Must be the entire action.** Post-beep message goes in a separate `action_followup` condition. |
| `<endcall />` | Terminates the call | **May be combined with surrounding text** (the only "communication-class" tag that allows this — useful for natural sign-offs like `Thanks, that's all I needed <endcall />`). |

### Speech Control

| Tag | Behavior | Constraint |
|---|---|---|
| `<silence time="Xs" />` | Pause on the caller's turn — **interruptible** by the main agent; background noise continues; condition matching restarts after an interrupt | Embeddable mid-action |
| `<hold time="Xs" />` | Dead air — **not interruptible**; background noise stops | Multiple per action allowed |
| `<spell>TEXT</spell>` | Spell text letter-by-letter (no attributes) | Wrap target text |
| `<speed ratio="N" />` | Speech rate; ratio range **0.8–1.2** (0.8 = 20% slower, 1.2 = 20% faster) | **Must start the action** |
| `<volume ratio="N" />` | Volume; ratio range **0–2** (0 = silent, 1 = normal, 2 = double) | **Must start the action. Cartesia voices only.** |

#### `<silence>` vs `<hold>`

| | `<silence>` | `<hold>` |
|---|---|---|
| Interruptible by main agent | ✅ Yes | ❌ No |
| Background noise during pause | ✅ Continues | ❌ Stops |

### Interaction

| Tag | Behavior | Constraint |
|---|---|---|
| `<dtmf digits="..." />` | Send touch-tone digits. Supports digits, `#`, and `*` (e.g. `digits="123"`, `digits="456#"`, `digits="*9"`). | Combinable with text |
| `<send_sms text="..." />` | Trigger an SMS for testing SMS-driven workflows | `text` required |
| `<interruption time="Xs" />` | Cuts in `Xs` after the **main agent starts its next turn** (shorter = more aggressive) | **Must be `type: "action_followup"` AND must appear at the very start of the action string.** |

### Environmental

| Tag | Behavior | Constraint |
|---|---|---|
| `<background_noise sound="NAME" volume="0.x">spoken text</background_noise>` | Continuous ambient sound behind the caller's voice | Wraps the spoken text. `volume` optional. |
| `<noise sound="NAME" volume="N" time="Xms" />` | One-shot sound effect at a point in the action | `volume` and `time` (milliseconds) are optional |
| `<network_simulation packet_loss="N" />` | Simulate degraded connection (percentage value, e.g. `packet_loss="5"`) | **Only `packet_loss` is supported.** `jitter` and `latency` are silently ignored. |

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

`office`, `beep`, `cough1`, `cough2`

## Test Profile Template Variables (fixed_message: true only)

Inject test-profile fields directly into verbatim text. Substitution happens at runtime before the message is spoken.

| Pattern | Example |
|---|---|
| Simple field | `{{test_profile.first_name}}` |
| Bracket notation (keys with spaces or special chars) | `{{test_profile['account_id']}}` |
| Nested field | `{{test_profile.address.city}}` |
| Combined with XML tag | `<spell>{{test_profile.account_number}}</spell>` |

Two ways to use profile data in conditions:

- **Behavioral instruction (`fixed_message: false`):** `"Provide your full name and date of birth for verification"` — the testing agent reads from the profile and phrases it naturally.
- **Template variable in a fixed message (`fixed_message: true`):** `"My name is {{test_profile.first_name}} {{test_profile.last_name}} and my date of birth is {{test_profile.dob}}"` — exact phrasing AND the real profile value both matter (compliance, IVR account-number entry).

Never hardcode values that come from a test profile unless the value is intentionally fixed for that specific test (e.g., known-bad input).

## Worked Examples

### 1. Linear Verification Flow

```json
{
  "role": "You are an established patient calling to check your appointment status",
  "conditions": [
    { "id": 0, "condition": "FIRST_MESSAGE", "action": "Hi, I'd like to check on my upcoming appointment", "type": "standard", "fixed_message": true },
    { "id": 1, "condition": "The agent asks for your name", "action": "My name is Sarah Johnson", "type": "standard", "fixed_message": true },
    { "id": 2, "condition": "The agent asks for your date of birth", "action": "January first, nineteen ninety", "type": "standard", "fixed_message": true },
    { "id": 3, "condition": "The agent confirms your identity and provides appointment details", "action": "Thank you, that's all I needed <endcall />", "type": "standard", "fixed_message": true }
  ]
}
```

### 2. IVR Navigation

```json
{
  "role": "You are a caller trying to reach the billing department through an IVR",
  "conditions": [
    { "id": 0, "condition": "FIRST_MESSAGE", "action": "<ivr text='Thank you for calling Acme Corp. Press 1 for appointments, press 2 for billing, press 3 for technical support.' />", "type": "standard", "fixed_message": true },
    { "id": 1, "condition": "The IVR menu finishes playing", "action": "<dtmf digits='2' /> I pressed 2 for billing", "type": "standard", "fixed_message": true },
    { "id": 2, "condition": "The agent greets you and asks how they can help", "action": "I have a question about a charge on my last bill", "type": "standard", "fixed_message": true },
    { "id": 3, "condition": "The agent resolves your billing question", "action": "Thanks, that clears it up <endcall />", "type": "standard", "fixed_message": true }
  ]
}
```

### 3. Voicemail with Post-Beep Message

```json
{
  "role": "You are calling a clinic that has gone to voicemail",
  "conditions": [
    { "id": 0, "condition": "FIRST_MESSAGE", "action": "", "type": "standard", "fixed_message": true },
    { "id": 1, "condition": "The call goes to voicemail", "action": "<voicemail text=\"Hi, you've reached our office. Please leave a message after the beep.\" />", "type": "standard", "fixed_message": true },
    { "id": 2, "condition": 1, "action": "Hi, this is Sarah Johnson calling to confirm my appointment tomorrow. Please call me back.", "type": "action_followup", "fixed_message": true }
  ]
}
```

### 4. Multi-Part Response with action_followup

```json
{
  "role": "You are a customer calling to update your contact information",
  "conditions": [
    { "id": 0, "condition": "FIRST_MESSAGE", "action": "I need to update my email address on file", "type": "standard", "fixed_message": true },
    { "id": 1, "condition": "The agent asks for your account information to verify your identity", "action": "Provide your name and account number for verification", "type": "standard", "fixed_message": false },
    { "id": 2, "condition": "The agent asks for your new email address", "action": "My new email is john.smith@example.com", "type": "standard", "fixed_message": true },
    { "id": 3, "condition": 2, "action": "And please make sure that's lowercase, all one word", "type": "action_followup", "fixed_message": true },
    { "id": 4, "condition": "The agent confirms the email update", "action": "Perfect, thanks for your help <endcall />", "type": "standard", "fixed_message": true }
  ]
}
```

### 5. Mid-Flow Pivot (Cancel → Reschedule)

```json
{
  "role": "You are a patient who calls to cancel but changes their mind and reschedules",
  "conditions": [
    { "id": 0, "condition": "FIRST_MESSAGE", "action": "I need to cancel my appointment for next Tuesday", "type": "standard", "fixed_message": true },
    { "id": 1, "condition": "The agent asks for verification", "action": "Provide your name and date of birth for verification", "type": "standard", "fixed_message": false },
    { "id": 2, "condition": "The agent confirms the appointment you want to cancel", "action": "Actually, could I reschedule instead of cancelling?", "type": "standard", "fixed_message": true },
    { "id": 3, "condition": "The agent offers available reschedule slots", "action": "Select the earliest available morning slot", "type": "standard", "fixed_message": false },
    { "id": 4, "condition": "The agent confirms the new appointment", "action": "That works perfectly, thank you <endcall />", "type": "standard", "fixed_message": true }
  ]
}
```

### 6. Interruption Mid-Sentence

```json
{
  "conditions": [
    { "id": 3, "condition": "The agent starts explaining the cancellation policy", "action": "I understand, please go ahead", "type": "standard", "fixed_message": true },
    { "id": 4, "condition": 3, "action": "<interruption time='2s' /> Sorry to interrupt — I actually just have a quick question", "type": "action_followup", "fixed_message": true }
  ]
}
```

### 7. Degraded Connection Simulation

```json
{
  "role": "You are a caller testing the agent's ability to handle poor audio quality",
  "conditions": [
    { "id": 0, "condition": "FIRST_MESSAGE", "action": "<network_simulation packet_loss='10' /> Hello, I'm having trouble hearing you", "type": "standard", "fixed_message": true },
    { "id": 1, "condition": "The agent asks how they can help", "action": "I need to reschedule an appointment <silence time='2s' /> Sorry, bad connection", "type": "standard", "fixed_message": true },
    { "id": 2, "condition": "The agent processes your reschedule request successfully", "action": "Great, thanks <endcall />", "type": "standard", "fixed_message": true }
  ]
}
```

## Anti-Patterns

- **Multiple branches in one evaluator.** Each path (success / failure / not-found) is a separate evaluator. Don't encode `if X then Y else Z` in a single conditions array.
- **Missing `type`.** `type` is required on every condition with no default — omitting it returns a validation error. Always set `"standard"` or `"action_followup"` explicitly.
- **Vague conditions.** `"condition": "verification"` is too ambiguous and may not trigger. Write `"condition": "The agent asks for your name and date of birth to verify your identity"`.
- **Hardcoding profile data.** When data is in both the test profile and the instructions and they differ, the testing agent hallucinates. Prefer `"Provide your date of birth for verification"` (reads from profile) over `"My DOB is March 15, 1985"`.
- **XML tags with `fixed_message: false`.** Tags only parse when `fixed_message: true`; otherwise the testing agent treats angle brackets as literal instructions.
- **`<ivr>` or `<voicemail>` combined with other text or tags.** Both tags must be the *entire* action. Surrounding text or additional tags causes a validation error. Use a separate `action_followup` for any post-IVR / post-beep content.
- **Text before `<interruption>`.** `<interruption>` must be the very first thing in the action string.
- **`<interruption>` as `type: "standard"`.** It only works as `action_followup`; on `standard` it has no effect because the timing mechanism needs a preceding action to anchor against.
- **Unsupported `<network_simulation>` attributes.** Only `packet_loss` is honored. `jitter` and `latency` are silently ignored.
- **No `<endcall />` at end.** Without an explicit termination, the call runs to timeout, wasting credits.
- **Conditions arrays longer than ~15 entries.** Split into multiple evaluators by phase (verification, scheduling, confirmation). Long arrays drift from the intended flow and are hard to debug.

## Validation Checklist

- [ ] `id: 0` exists with `condition: "FIRST_MESSAGE"` (literal string, always required) and `fixed_message: true`
- [ ] If the main agent speaks first, `id: 0` `action` is `""`
- [ ] All `id` values are unique integers
- [ ] Every condition has all five fields: `id`, `condition`, `action`, `type`, `fixed_message`
- [ ] `type` is explicitly `"standard"` or `"action_followup"` on every condition
- [ ] `action_followup` conditions have an integer (not string) in `condition`
- [ ] `<ivr>` and `<voicemail>` are the entire action on their condition (no surrounding text or other tags)
- [ ] `<interruption>` is at the very start of its action string AND uses `type: "action_followup"`
- [ ] `<network_simulation>` only uses `packet_loss`
- [ ] No XML tags used with `fixed_message: false`
- [ ] The last condition ends the conversation (via `<endcall />` or a natural close)
- [ ] `scenario_language` is set correctly (not left as default `"en"` for non-English tests)
- [ ] A `personality` is set (API returns 400 without one)

## Supporting Fields (When Creating the Scenario)

- **Name**: `"[ID]: [Brief description]"` — e.g. `"CA-01: Appointment verification — success path"`
- **Expected outcome**: what the main agent should do by the end (LLM-judged — keep behavioral, not over-specific on dates/times)
- **Personality**: 693 (Normal Male English) is the default; change for non-English or specific voice traits
- **Tools**: at minimum `TOOL_END_CALL`; add `TOOL_DTMF` for IVR flows, `TOOL_END_CALL_ON_TRANSFER` for transfer scenarios
- **Metrics**: attach Expected Outcome, Infrastructure Issues, Tool Call Success, and Latency to every evaluator
- **Folder**: place in an organized folder (create one first if needed)
- **Test profile**: pair every conditional-actions evaluator with a test profile for any identity data; prefer template variables (`{{test_profile.field}}`) when exact phrasing AND the real value both matter

## Quick Reference Card

```
Condition fields (ALL five required on every condition):
  id            integer       Unique. First condition must be 0.
  condition     str | int     "FIRST_MESSAGE" for id:0 (literal, always required, even when main agent speaks first).
                              Trigger string for standard. Prior id (integer) for action_followup.
  action        string        Verbatim text (fixed_message:true) or instructions (fixed_message:false).
                              May be "" only on id:0 when main agent speaks first.
  type          string        "standard" | "action_followup" — required, no default.
  fixed_message boolean       true = verbatim; false = instructions. Required.

XML tags (fixed_message:true only):
  <ivr text="..." />                Uninterruptible IVR — must be entire action
  <voicemail text="..." />          Uninterruptible + auto-beep at end — must be entire action;
   or <voicemail />                  use action_followup for the post-beep message
  <dtmf digits="..." />             Touch-tone input; supports digits, # and *
  <endcall />                       Terminate call — combinable with surrounding text
  <silence time="Xs" />             Pause on caller's turn — interruptible; bg noise continues
  <hold time="Xs" />                Dead air — NOT interruptible; bg noise stops; multiple per action
  <spell>TEXT</spell>               Spell text letter-by-letter
  <interruption time="Xs" />        Cut in Xs after agent starts speaking — MUST be action_followup
                                     AND at the very start of the action string
  <speed ratio="N" />               Speech rate 0.8–1.2; must start the action
  <volume ratio="N" />              Volume 0–2; must start the action; Cartesia only
  <send_sms text="..." />           Trigger SMS for SMS workflows
  <network_simulation packet_loss="N" />   Only packet_loss supported (% value); jitter/latency ignored
  <background_noise sound="NAME" volume="0.x">spoken text</background_noise>
  <noise sound="NAME" volume="N" time="Xms" />   One-shot: office | beep | cough1 | cough2

Background noise sounds:
  office-ambience, coffee-shop, kitchen-noise, home-chatter, restaurant, shopping-mall,
  train-station, rain-thunder, windy-day, air-conditioner, inside-car, inside-train,
  busy-street, airport-boarding, dog-barking, baby-crying, coughing, two-people-talking,
  keyboard-typing, background-printer, static-radio, fan-buzz, ship-humming,
  vacuum-cleaner, construction-site, quiet-room, stadium-crowd, standard-hiss,
  public-park, holding-on-song

Action types:
  standard         Fires when conversation context matches condition string
  action_followup  Fires immediately after condition id (int) — multi-part responses, <interruption>

Test profile variables (fixed_message:true only):
  {{test_profile.field_name}}                   Simple field
  {{test_profile['key']}}                       Bracket notation (keys with spaces/special chars)
  {{test_profile.address.city}}                 Nested field
  <spell>{{test_profile.account_number}}</spell>   Combined with XML tag
```
