---
name: Cekura Conditional Actions
description: >
  Use when the user wants to write a conditional action evaluator, build a
  deterministic test scenario, create a scripted voice test, design an IVR
  navigation test, write a structured unit test for a voice agent, build
  repeatable regression tests, or design branching conversation tests that
  follow a fixed sequence. Also triggers on phrases like "conditional actions",
  "structured evaluator", "scripted scenario", "deterministic test",
  "IVR test", "unit test for voice", "exact flow test", or "sequential conditions".
version: 0.1.0
---

# Cekura Conditional Actions Skill

## Purpose

Guide the design and creation of **conditional action evaluators** — deterministic, structured test scenarios for Cekura voice AI agents. Unlike adaptive evaluators (which give the testing agent behavioral instructions and let it improvise), conditional action evaluators follow a predefined sequence of triggers and responses, making them ideal for unit testing and regression testing.

## Decision: Conditional Actions vs Adaptive Instructions

Ask yourself (or the user) before starting:

| Signal | Use Conditional Actions | Use Adaptive Instructions |
|--------|------------------------|--------------------------|
| Goal | Exact flow validation, regression | Natural conversation, quality |
| Repeatability | Must be identical each run | Can vary between runs |
| Conversation structure | Predictable, sequential | Branching, dynamic |
| Use case | Unit test, IVR nav, compliance | Edge cases, red-team, exploratory |
| Example | "Always press 1 then say DOB then confirm" | "Act confused about billing" |

**Rule of thumb:** If a developer would write this as a unit test in code, write it as a conditional action evaluator. If they'd describe it as a persona or situation, use adaptive instructions.

## Interactive Workflow

Work through these steps in order. Confirm before moving on to the next.

### Step 1: Understand the Flow

Ask the user:
- "What exact sequence of steps do you want to test?"
- "Are there any branch points, or is this a single linear path?"
- "What is the agent expected to do at each step?"

Map the conversation as a sequence: `[caller says X] → [agent does Y] → [caller says Z]`.

If there are branches (agent succeeds vs fails), decide which path to test in this evaluator. **Each branch is a separate evaluator** — don't try to encode multiple paths in one condition set.

### Step 2: Define the Role

Write a one-sentence role that describes who the testing agent is and why they're calling. This is the system-prompt-equivalent for the testing agent.

```
"You are a patient calling to cancel their upcoming appointment"
"You are a first-time customer trying to set up a new account"
"You are a caller navigating an IVR to reach billing support"
```

Keep it concise. The role sets context for the entire conversation.

### Step 3: Design the Conditions Array

Build one condition per conversation turn. All five fields are required on every condition:

```json
{
  "id": <integer>,
  "condition": "<trigger description or FIRST_MESSAGE>",
  "action": "<what to say or do>",
  "type": "standard",
  "fixed_message": <true|false>
}
```

**Start with the opening message (id: 0) — always required:**
- `condition` must be the string `"FIRST_MESSAGE"` exactly (this is required even when the main agent speaks first)
- `fixed_message` must be `true`
- If the main agent speaks first (e.g., IVR or voicemail scenario), set `action` to `""` — the testing agent will wait for the main agent to start

**For all subsequent conditions:**
- Write the trigger as a natural description of what the main agent will say/do
- Write the action as either exact text (`fixed_message: true`) or behavioral instructions (`fixed_message: false`)
- `type` must be set explicitly — the backend no longer defaults it to `"standard"`; omitting it returns a validation error
- Use `type: "action_followup"` when this condition should fire immediately after a prior one (set `condition` to the integer ID of that prior condition)

### Step 4: Choose fixed_message per Condition

For each condition, decide:

**Use `fixed_message: true` when:**
- The exact wording matters (name, DOB, account number, confirmation codes)
- Using XML tags (IVR, DTMF, silence, hold, etc.)
- Running compliance or regression tests where verbatim output is required
- The caller would always say this exact thing

**Use `fixed_message: false` when:**
- The caller should respond naturally (like a real human would)
- You're giving behavioral instructions, not scripts
- The phrasing can vary without affecting the test

### Step 5: Add XML Tags Where Needed

XML tags only work with `fixed_message: true`. Each tag controls a distinct behavior — read the notes below before using them.

| Scenario | Tag | Example |
|----------|-----|---------|
| IVR message plays | `<ivr>` | `<ivr text="Press 1 for appointments" />` |
| Caller navigates IVR | `<dtmf>` | `<dtmf digits="1" /> I pressed 1` |
| Voicemail detected | `<voicemail>` | `<voicemail text="Please leave a message." />` |
| Caller pauses | `<silence>` | `<silence time="3s" /> Sorry, I was distracted` |
| Call goes on hold | `<hold>` | `<hold time="10s" />` |
| Caller spells name | `<spell>` | `My name is <spell>SZCZEPANSKI</spell>` |
| End call naturally | `<endcall>` | `Thanks, that's all I needed <endcall />` |
| Simulate bad connection | `<network_simulation>` | `<network_simulation packet_loss="10" />` |
| Background noise | `<background_noise>` | `<background_noise sound="coffee-shop" volume="0.05">I'm at a café</background_noise>` |
| Interrupt the agent | `<interruption>` | `<interruption time="2s" /> Wait, actually—` |

#### Tag behavior details

**`<ivr>`** — Simulates an uninterruptible IVR system message. The full text plays to completion; the main agent cannot speak over it or cut it short. Use this to model an automated phone menu the caller hears before reaching a live agent or bot.

**Constraint:** `<ivr>` must be the **entire** action — it cannot be combined with other text or tags in the same action string.

```json
{
  "id": 0,
  "condition": "FIRST_MESSAGE",
  "action": "<ivr text='Thank you for calling. Press 1 for appointments, press 2 for billing.' />",
  "type": "standard",
  "fixed_message": true
}
```

**`<voicemail>`** — Simulates an uninterruptible voicemail greeting. The text plays to completion, then a beep sounds automatically at the end. Use this to model the scenario where the main agent's outbound call goes to voicemail.

**Constraint:** `<voicemail>` must be the **entire** action — it cannot be combined with other text or tags. The message left after the beep should be a separate `action_followup` condition.

```json
{
  "id": 0,
  "condition": "FIRST_MESSAGE",
  "action": "",
  "type": "standard",
  "fixed_message": true
},
{
  "id": 1,
  "condition": "The call goes to voicemail",
  "action": "<voicemail text=\"Hi, you've reached our office. Please leave a message after the beep.\" />",
  "type": "standard",
  "fixed_message": true
},
{
  "id": 2,
  "condition": 1,
  "action": "Hi, this is Sarah Johnson calling to confirm my appointment tomorrow. Please call me back.",
  "type": "action_followup",
  "fixed_message": true
}
```

**`<interruption>`** — Must be used as `type: "action_followup"`, referencing the ID of the condition immediately before it. The `time` attribute controls how many seconds after the **main agent starts its next turn** before the testing agent cuts in. This simulates a caller interrupting mid-sentence.

**Constraint:** `<interruption>` must appear at the **very start** of the action string — nothing before it.

```json
{
  "id": 3,
  "condition": "The agent starts explaining the cancellation policy",
  "action": "I understand, please go ahead",
  "type": "standard",
  "fixed_message": true
},
{
  "id": 4,
  "condition": 3,
  "action": "<interruption time='2s' /> Sorry to interrupt — I actually just have a quick question",
  "type": "action_followup",
  "fixed_message": true
}
```

`time="2s"` means: wait 2 seconds into the agent's speech, then cut in. A shorter value is more aggressive; a longer value lets the agent get further before being interrupted.

**`<silence>`** — Adds a pause on the caller's turn before they speak. The main agent **can** interrupt this silence (it is interruptible). Background noise continues playing during the pause. After an interruption, condition matching restarts once the main agent finishes speaking.

**`<hold>`** — Simulates hold music or dead air. The testing agent goes silent for the specified duration and **cannot be interrupted** during this time. Background noise also stops during hold. Useful for testing how the main agent handles prolonged dead air.

| | `<silence>` | `<hold>` |
|---|---|---|
| Interruptible by main agent | ✅ Yes | ❌ No |
| Background noise during pause | ✅ Continues | ❌ Stops |

**`<speed>`** — Controls speech rate. Ratio range: **0.8–1.2** (0.8 = 20% slower, 1.2 = 20% faster). Must appear at the start of the action.

**`<volume>`** — Controls speech volume. Ratio range: **0–2** (0 = silent, 1 = normal, 2 = double). Must appear at the start of the action. Cartesia voices only.

**`<background_noise>`** — Adds ambient sound behind the caller's voice. Supported sound names:

| Category | Sounds |
|----------|--------|
| Office / retail | `office-ambience`, `coffee-shop`, `kitchen-noise`, `home-chatter`, `restaurant`, `shopping-mall`, `train-station` |
| Nature / weather | `rain-thunder`, `windy-day`, `air-conditioner` |
| Transportation | `inside-car`, `inside-train`, `busy-street`, `airport-boarding` |
| People | `dog-barking`, `baby-crying`, `coughing`, `two-people-talking` |
| Technical | `keyboard-typing`, `background-printer`, `static-radio`, `fan-buzz`, `ship-humming` |
| Ambient | `quiet-room`, `stadium-crowd`, `standard-hiss`, `public-park`, `holding-on-song` |

**`<noise>`** — Plays a one-shot sound effect at a point in the action. Supported sounds: `office`, `beep`, `cough1`, `cough2`.

**`<network_simulation>`** — Simulates a degraded connection. Only `packet_loss` is supported (percentage value, e.g. `packet_loss="5"` = 5% packet loss). `jitter` and `latency` attributes are not supported and will be ignored.

### Step 6: Validate Before Submitting

Run through this checklist:

- [ ] `id: 0` exists and has `"FIRST_MESSAGE"` as condition (always required, even when main agent speaks first)
- [ ] `id: 0` has `fixed_message: true`; if main agent speaks first, `action` is `""`
- [ ] All IDs are unique integers
- [ ] Every condition has all five fields: `id`, `condition`, `action`, `type`, `fixed_message`
- [ ] `type` is explicitly `"standard"` or `"action_followup"` on every condition — omitting it returns a validation error
- [ ] `action_followup` conditions have an integer (not string) in `condition`
- [ ] `<ivr>` and `<voicemail>` are the entire action on their condition (no surrounding text or other tags)
- [ ] `<interruption>` is at the very start of its action string and the condition uses `type: "action_followup"`
- [ ] `<network_simulation>` only uses `packet_loss` (not `jitter` or `latency`)
- [ ] No XML tags used with `fixed_message: false`
- [ ] The last condition ends the conversation (via `<endcall />` or a natural close)
- [ ] `scenario_language` is set correctly (not left as default `"en"` for non-English tests)
- [ ] A personality is set (API returns 400 without it)

### Step 7: Pair with a Test Profile

**Every conditional action evaluator should use a test profile** for any identity data (name, DOB, account number, phone number).

You have two ways to use test profile data in conditions:

**Option A — Behavioral instruction (`fixed_message: false`):** Tell the testing agent what to provide; it reads from the profile and phrases it naturally.
```json
{
  "action": "Provide your full name and date of birth for verification",
  "fixed_message": false
}
```

**Option B — Template variable in a fixed message (`fixed_message: true`):** Inject profile fields directly into verbatim text using `{{test_profile.field_name}}` syntax. The value is substituted at runtime before the message is spoken.
```json
{
  "action": "My name is {{test_profile.first_name}} {{test_profile.last_name}} and my date of birth is {{test_profile.dob}}",
  "fixed_message": true
}
```

Use Option B when exact phrasing AND the real profile value both matter — for example, compliance tests that must say the name in a specific format, or IVR flows where the caller needs to speak a precise account number.

**Template variable syntax:**
- Simple field: `{{test_profile.first_name}}`
- Bracket notation (for keys with spaces or special chars): `{{test_profile['account_id']}}`
- Nested field: `{{test_profile.address.city}}`

**Combine with XML tags** when needed:
```json
{
  "action": "My account number is <spell>{{test_profile.account_number}}</spell>",
  "fixed_message": true
}
```

Never hardcode values that come from a test profile unless the value is intentionally fixed for that specific test (e.g., testing a known-bad input).

### Step 8: Set Supporting Fields

Before creating the scenario, confirm:

- **Name**: `"[ID]: [Brief description]"` e.g., `"CA-01: Appointment verification — success path"`
- **Expected outcome**: What the main agent should do by the end of the conversation
- **Personality**: Use 693 (Normal Male English) as default; change if the test requires a different voice/language
- **Tools**: At minimum `TOOL_END_CALL`; add `TOOL_DTMF` for IVR flows, `TOOL_END_CALL_ON_TRANSFER` for transfer scenarios
- **Metrics**: Attach Expected Outcome, Infrastructure Issues, Tool Call Success, and Latency to every evaluator
- **Folder**: Place in an organized folder (create one first if needed)

## Complete Worked Examples

### Example 1: Linear Verification Flow

```json
{
  "role": "You are an established patient calling to check your appointment status",
  "conditions": [
    {
      "id": 0,
      "condition": "FIRST_MESSAGE",
      "action": "Hi, I'd like to check on my upcoming appointment",
      "type": "standard",
      "fixed_message": true
    },
    {
      "id": 1,
      "condition": "The agent asks for your name",
      "action": "My name is Sarah Johnson",
      "type": "standard",
      "fixed_message": true
    },
    {
      "id": 2,
      "condition": "The agent asks for your date of birth",
      "action": "January first, nineteen ninety",
      "type": "standard",
      "fixed_message": true
    },
    {
      "id": 3,
      "condition": "The agent confirms your identity and provides appointment details",
      "action": "Thank you, that's all I needed <endcall />",
      "type": "standard",
      "fixed_message": true
    }
  ]
}
```

### Example 2: IVR Navigation

```json
{
  "role": "You are a caller trying to reach the billing department through an IVR",
  "conditions": [
    {
      "id": 0,
      "condition": "FIRST_MESSAGE",
      "action": "<ivr text='Thank you for calling Acme Corp. Press 1 for appointments, press 2 for billing, press 3 for technical support.' />",
      "type": "standard",
      "fixed_message": true
    },
    {
      "id": 1,
      "condition": "The IVR menu finishes playing",
      "action": "<dtmf digits='2' /> I pressed 2 for billing",
      "type": "standard",
      "fixed_message": true
    },
    {
      "id": 2,
      "condition": "The agent greets you and asks how they can help",
      "action": "I have a question about a charge on my last bill",
      "type": "standard",
      "fixed_message": true
    },
    {
      "id": 3,
      "condition": "The agent resolves your billing question",
      "action": "Thanks, that clears it up <endcall />",
      "type": "standard",
      "fixed_message": true
    }
  ]
}
```

### Example 3: Multi-Part Response with action_followup

```json
{
  "role": "You are a customer calling to update your contact information",
  "conditions": [
    {
      "id": 0,
      "condition": "FIRST_MESSAGE",
      "action": "I need to update my email address on file",
      "type": "standard",
      "fixed_message": true
    },
    {
      "id": 1,
      "condition": "The agent asks for your account information to verify your identity",
      "action": "Provide your name and account number for verification",
      "type": "standard",
      "fixed_message": false
    },
    {
      "id": 2,
      "condition": "The agent asks for your new email address",
      "action": "My new email is john.smith@example.com",
      "type": "standard",
      "fixed_message": true
    },
    {
      "id": 3,
      "condition": 2,
      "action": "And please make sure that's lowercase, all one word",
      "type": "action_followup",
      "fixed_message": true
    },
    {
      "id": 4,
      "condition": "The agent confirms the email update",
      "action": "Perfect, thanks for your help <endcall />",
      "type": "standard",
      "fixed_message": true
    }
  ]
}
```

### Example 4: Cancellation with Mid-Flow Pivot

```json
{
  "role": "You are a patient who calls to cancel but changes their mind and reschedules",
  "conditions": [
    {
      "id": 0,
      "condition": "FIRST_MESSAGE",
      "action": "I need to cancel my appointment for next Tuesday",
      "type": "standard",
      "fixed_message": true
    },
    {
      "id": 1,
      "condition": "The agent asks for verification",
      "action": "Provide your name and date of birth for verification",
      "type": "standard",
      "fixed_message": false
    },
    {
      "id": 2,
      "condition": "The agent confirms the appointment you want to cancel",
      "action": "Actually, could I reschedule instead of cancelling?",
      "type": "standard",
      "fixed_message": true
    },
    {
      "id": 3,
      "condition": "The agent offers available reschedule slots",
      "action": "Select the earliest available morning slot",
      "type": "standard",
      "fixed_message": false
    },
    {
      "id": 4,
      "condition": "The agent confirms the new appointment",
      "action": "That works perfectly, thank you <endcall />",
      "type": "standard",
      "fixed_message": true
    }
  ]
}
```

### Example 5: Degraded Connection Simulation

```json
{
  "role": "You are a caller testing the agent's ability to handle poor audio quality",
  "conditions": [
    {
      "id": 0,
      "condition": "FIRST_MESSAGE",
      "action": "<network_simulation packet_loss='10' /> Hello, I'm having trouble hearing you",
      "type": "standard",
      "fixed_message": true
    },
    {
      "id": 1,
      "condition": "The agent asks how they can help",
      "action": "I need to reschedule an appointment <silence time='2s' /> Sorry, bad connection",
      "type": "standard",
      "fixed_message": true
    },
    {
      "id": 2,
      "condition": "The agent processes your reschedule request successfully",
      "action": "Great, thanks <endcall />",
      "type": "standard",
      "fixed_message": true
    }
  ]
}
```

## Common Anti-Patterns

### Don't encode multiple branches in one evaluator
**Wrong:** "If the agent can't find the appointment, say X, otherwise say Y"
**Right:** Two separate evaluators — one for the success path, one for the not-found path.

### Don't use XML tags with fixed_message: false
XML tags are interpreted literally as syntax only when `fixed_message: true`. With `false`, the testing agent sees the angle brackets as instructions to follow, not as special markup.

### Don't write vague conditions
**Wrong:** `"condition": "verification"` — too ambiguous, may not trigger correctly
**Right:** `"condition": "The agent asks for your name and date of birth to verify your identity"`

### Don't skip the final endcall
Without an explicit `<endcall />` or natural conversation close, the call runs until timeout. Always end your last condition with a clear termination.

### Don't hardcode identity data in actions when using test profiles
If you have a test profile, instruct the testing agent to provide the data rather than hardcoding it:
**Wrong:** `"action": "My date of birth is March 15, 1985"`
**Right:** `"action": "Provide your date of birth for verification"` (agent reads from test profile)

### Don't omit `type` on any condition
`type` is required on every condition. The backend no longer defaults it — omitting it returns a validation error.
**Wrong:** `{ "id": 1, "condition": "The agent asks for your name", "action": "John Smith", "fixed_message": true }`
**Right:** add `"type": "standard"` (or `"action_followup"`)

### Don't combine `<ivr>` or `<voicemail>` with other text or tags
Both tags must be the entire action. Adding surrounding text or other tags causes a validation error.
**Wrong:** `"<ivr text='Press 1 for support' /> Please choose an option"`
**Right:** `"<ivr text='Press 1 for support' />"` — and if the caller needs to respond, use a separate follow-up condition.

### Don't put text before `<interruption>`
`<interruption>` must be the very first thing in the action string.
**Wrong:** `"Actually, wait — <interruption time='2s' /> let me ask something"`
**Right:** `"<interruption time='2s' /> Actually, let me ask something first"`

### Don't use `<interruption>` as a standard condition
`<interruption>` only works as `type: "action_followup"`. Using it on a `type: "standard"` condition has no effect — the timing mechanism requires a preceding action to anchor the interrupt to.

### Don't use unsupported `<network_simulation>` attributes
Only `packet_loss` is supported. `jitter` and `latency` are not valid and will be silently ignored.
**Wrong:** `<network_simulation packet_loss="10" jitter="50" latency="200" />`
**Right:** `<network_simulation packet_loss="10" />`

### Don't create overly long condition arrays
If your conditions array exceeds ~15 entries, split into multiple evaluators by logical phase (e.g., verification, scheduling, confirmation). Long arrays are harder to debug and may drift from the intended flow.

## API Access — Cekura MCP Server

**Key MCP tools for this skill:**

| Operation | MCP Tool |
|-----------|----------|
| Create evaluator | `mcp__cekura__scenarios_create` |
| Update evaluator | `mcp__cekura__scenarios_partial_update` |
| Get evaluator | `mcp__cekura__scenarios_retrieve` |
| List evaluators | `mcp__cekura__scenarios_list` |
| Create folder | `mcp__cekura__scenarios_folder_create` |
| List folders | `mcp__cekura__scenarios_folders_list` |
| List test profiles | `mcp__cekura__test_profiles_list` |
| Create test profile | `mcp__cekura__test_profiles_create` |
| List personalities | `mcp__cekura__personalities_list` |
| Run scenario (voice) | `mcp__cekura__scenarios_run_voice` |
| Run scenario (text) | `mcp__cekura__scenarios_run_text` |

**The `conditions` array goes in the `instructions` field** of the scenario create/update payload, as a JSON object:

```json
{
  "name": "CA-01: Appointment verification — success path",
  "agent": <agent_id>,
  "personality": 693,
  "scenario_language": "en",
  "instructions": {
    "role": "You are a patient calling to check appointment status",
    "conditions": [...]
  },
  "expected_outcome": "Agent verifies caller identity and provides appointment details",
  "tools": ["TOOL_END_CALL"],
  "test_profile": <profile_id>
}
```

**Docs lookup:** Use `mcp__cekura__search_cekura` or fetch `https://docs.cekura.ai/llms.txt` for API field details.

**Troubleshooting:** If MCP tools are unavailable, verify `CEKURA_API_KEY` is set and the MCP server is running on port 8001. Run `/setup-mcp` to reconfigure.

## Quick Reference Card

```
Condition fields (ALL five required on every condition):
  id           integer       Unique, start at 0
  condition    str|int       "FIRST_MESSAGE" for id:0 (always required); trigger string for standard;
                             prior ID int for action_followup
  action       string        Exact text (fixed_message:true) or instructions (fixed_message:false)
  type         string        "standard" | "action_followup"  — required, no default
  fixed_message boolean      true = verbatim; false = instructions

XML tags (fixed_message:true only):
  <ivr text="..." />                Uninterruptible IVR — must be entire action, no surrounding text
  <voicemail text="..." />          Uninterruptible + beep at end — must be entire action; use
                                    action_followup for the message left after beep
  <dtmf digits="..." />             Touch-tone input
  <endcall />                       Terminate call
  <silence time="Xs" />             Pause on caller's turn — interruptible; bg noise continues
  <hold time="Xs" />                Dead air — NOT interruptible; bg noise stops
  <spell>TEXT</spell>               Spell text letter-by-letter
  <interruption time="Xs" />        Cut in Xs after agent starts speaking — MUST be action_followup
                                    AND must be at the very start of the action string
  <speed ratio="N" />               Speech rate 0.8–1.2; must start the action
  <volume ratio="N" />              Volume 0–2; must start the action; Cartesia only
  <network_simulation packet_loss="N" />   Only packet_loss supported (% value); jitter/latency ignored
  <background_noise sound="NAME" volume="0.x">spoken text</background_noise>
  <noise sound="NAME" volume="N" />        One-shot sound: office | beep | cough1 | cough2

Background noise sounds (background_noise tag):
  office-ambience, coffee-shop, kitchen-noise, home-chatter, restaurant, shopping-mall,
  train-station, rain-thunder, windy-day, air-conditioner, inside-car, inside-train,
  busy-street, airport-boarding, dog-barking, baby-crying, coughing, two-people-talking,
  keyboard-typing, background-printer, static-radio, fan-buzz, ship-humming,
  quiet-room, stadium-crowd, standard-hiss, public-park, holding-on-song

Action types:
  standard        Fires when conversation context matches condition string
  action_followup Fires immediately after condition ID (int) — multi-part responses

Test profile variables (fixed_message:true only):
  {{test_profile.field_name}}         Simple field
  {{test_profile['key']}}             Bracket notation (keys with spaces/special chars)
  {{test_profile.address.city}}       Nested field
  <spell>{{test_profile.account_number}}</spell>   Combined with XML tag
```
