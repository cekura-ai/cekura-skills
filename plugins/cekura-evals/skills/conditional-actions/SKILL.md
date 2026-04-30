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

Build one condition per conversation turn. Follow this structure for each:

```json
{
  "id": <integer>,
  "condition": "<trigger description or FIRST_MESSAGE>",
  "action": "<what to say or do>",
  "type": "standard",
  "fixed_message": <true|false>
}
```

**Start with the opening message (id: 0):**
- `condition` must be the string `"FIRST_MESSAGE"` exactly
- `fixed_message` must be `true` — the opener is always spoken verbatim
- If the main agent speaks first, `action` can be an empty string `""`

**For all subsequent conditions:**
- Write the trigger as a natural description of what the main agent will say/do
- Write the action as either exact text (`fixed_message: true`) or behavioral instructions (`fixed_message: false`)
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

XML tags only work with `fixed_message: true`. Use them for:

| Scenario | Tag | Example |
|----------|-----|---------|
| IVR message plays | `<ivr>` | `<ivr text="Press 1 for appointments" />` |
| Caller navigates IVR | `<dtmf>` | `<dtmf digits="1" /> I pressed 1` |
| Voicemail detected | `<voicemail>` | `<voicemail text="Please leave a message." />` |
| Caller pauses | `<silence>` | `<silence time="3s" /> Sorry, I was distracted` |
| Call goes on hold | `<hold>` | `<hold time="10s" />` |
| Caller spells name | `<spell>` | `My name is <spell>SZCZEPANSKI</spell>` |
| End call naturally | `<endcall>` | `Thanks, that's all I needed <endcall />` |
| Simulate bad connection | `<network_simulation>` | `<network_simulation packet_loss="10" jitter="50" latency="200" />` |
| Background noise | `<background_noise>` | `<background_noise sound="office" volume="0.05">I'm at work</background_noise>` |
| Interrupt the agent | `<interruption>` | `<interruption time="2s" /> Wait, I have a question` |

### Step 6: Validate Before Submitting

Run through this checklist:

- [ ] `id: 0` has `"FIRST_MESSAGE"` as condition (exactly this string)
- [ ] `id: 0` has `fixed_message: true`
- [ ] All IDs are unique integers
- [ ] Every condition has `id`, `condition`, `action`, `type`, `fixed_message`
- [ ] `action_followup` conditions have an integer (not string) in `condition`
- [ ] No XML tags used with `fixed_message: false`
- [ ] The last condition ends the conversation (via `<endcall />` or a natural close)
- [ ] `scenario_language` is set correctly (not left as default `"en"` for non-English tests)
- [ ] A personality is set (API returns 400 without it)

### Step 7: Pair with a Test Profile

**Every conditional action evaluator should use a test profile** for any identity data (name, DOB, account number, phone number). Do not hardcode these in the `action` field directly — the testing agent should read from the test profile.

Reference profile data in condition actions by describing what to provide:
```
"action": "Provide your full name and date of birth for verification"
```

Not:
```
"action": "My name is John Smith and my DOB is January 1st 1990"
```

The exception: when the exact value is required for compliance testing or when you intentionally want to test a specific fixed input.

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
      "action": "<network_simulation packet_loss='10' jitter='80' latency='200' /> Hello, I'm having trouble hearing you",
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
Condition fields (all required):
  id           integer       Unique, start at 0
  condition    str|int       "FIRST_MESSAGE" for id:0; trigger string; or prior ID int for followup
  action       string        Exact text (fixed_message:true) or instructions (fixed_message:false)
  type         string        "standard" | "action_followup"
  fixed_message boolean      true = verbatim; false = instructions

XML tags (fixed_message:true only):
  <ivr text="..." />                IVR system message
  <dtmf digits="..." />             Touch-tone input
  <voicemail text="..." />          Voicemail greeting
  <endcall />                       Terminate call
  <silence time="Xs" />             Pause before speaking
  <hold time="Xs" />                Wait (hold music simulation)
  <spell>TEXT</spell>               Spell text letter-by-letter
  <interruption time="Xs" />        Interrupt agent after timeout
  <network_simulation ... />        Simulate packet loss/jitter/latency
  <background_noise sound="..." volume="0.x">...</background_noise>

Action types:
  standard        Fires when conversation context matches condition string
  action_followup Fires immediately after condition ID (int) — multi-part responses
```
