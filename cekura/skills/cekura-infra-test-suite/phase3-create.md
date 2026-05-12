# Phase 3 — Create Evaluators on Cekura

Create a folder, then create each confirmed scenario with a conditional_actions payload and the right metrics. Follow the authoring rules below — they prevent the most common failures.

---

## 3a. Create a folder

Always group CI scenarios in a dedicated folder. Never dump them in the root.

```
POST /test_framework/v1/scenarios/folder/
{
  "name": "CI_CD",
  "project_id": <project_id>
}
```

Use the returned `folder_path` on every scenario in this suite.

---

## 3b. Universal field defaults

Use these on every scenario:

```json
{
  "personality": 693,
  "tool_ids": ["TOOL_END_CALL"],
  "scenario_type": "conditional_actions",
  "folder_path": "CI_CD"
}
```

Add `"TOOL_END_CALL_ON_TRANSFER"` to `tool_ids` for transfer scenarios.

---

## 3c. Authoring rules — read before writing any conditions

### Rule: Always start with FIRST_MESSAGE action: ""

The first condition of every scenario must be:

```json
{ "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false }
```

**Why:** If the bot has `firstMessage` configured, both sides fire a first message simultaneously. The STT picks up both speakers and enters a confused state. Setting `action: ""` makes the testing agent stay silent until the bot finishes its greeting.

**Exception:** If the bot does NOT speak first (no `firstMessage`, no greeting), the testing agent should initiate — give condition 0 a non-empty action in that case.

### Rule: Conditions are natural language, not keyword filters

Conditions are matched semantically by Cekura's testing agent. They must describe what the bot said in plain English.

**Wrong:** `"condition": "contains 'help' OR contains 'assist'"`

**Right:** `"condition": "The agent greets the caller and asks how it can help"`

Write conditions the way a human would describe the bot's turn to a colleague.

### Rule: Never use action_followup on condition 0

When a bot's greeting is long, the STT engine may split it across two transcribed utterances. An `action_followup` attached to condition 0 (FIRST_MESSAGE) fires once per STT chunk — which means twice. Use a `standard` condition to match the full greeting before starting any followup chain.

### Rule: Use `<silence>` for idle timer tests, not `<hold>`

`<silence>` sends no audio from the testing agent's side — true silence that the bot's idle timer will fire on.

`<hold>` plays hold music — actual audio content that the bot's VAD may interpret as caller activity, preventing the idle timer from firing. Only use `<hold>` when you want to simulate a caller who put the bot on hold, not when you want the bot to detect silence.

### Rule: Combine `<dtmf>` with spoken text

A pure `<dtmf>` action with no spoken text does not register as a completed testing-agent turn. The condition chain freezes. Always add spoken text after the tag:

```
"action": "<dtmf digits=\"98765#\" /> I've entered my account number."
```

### Rule: `<interruption>` must be at the start of the action

The `<interruption>` tag must be the first thing in the action string, and `fixed_message: true` is required on that action.

```json
{ "action": "<interruption time=\"1s\" /> Wait, I have a question.", "fixed_message": true }
```

---

## 3d. Scenario templates

Substitute actual values from Phase 1 (idle threshold, domain-appropriate dialogue, DTMF digits, etc.).

### Full Pipeline E2E

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "standard", "condition": "The agent greets the caller and asks how it can help", "action": "[first request relevant to this agent's domain]", "fixed_message": false },
    { "id": 2, "type": "standard", "condition": "The agent responds and asks a follow-up question", "action": "[answer the follow-up]", "fixed_message": false },
    { "id": 3, "type": "standard", "condition": "The agent provides information or asks for more details", "action": "[complete the interaction]", "fixed_message": false },
    { "id": 4, "type": "standard", "condition": "The agent confirms and asks if there is anything else", "action": "No, that's all. Thank you.", "fixed_message": false }
  ]
}
```

Expected outcome: "The bot greeted the caller, handled a multi-turn conversation in its domain, and ended the call cleanly."

---

### Mid-Speech Interruption

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "standard", "condition": "The agent greets the caller and asks how it can help", "action": "<interruption time=\"1s\" /> Wait, I have a quick question.", "fixed_message": true },
    { "id": 2, "type": "action_followup", "condition": 1, "action": "[a follow-up question in the agent's domain]", "fixed_message": false },
    { "id": 3, "type": "standard", "condition": "The agent answers the question", "action": "Thank you, goodbye.", "fixed_message": false }
  ]
}
```

Expected outcome: "The bot was interrupted mid-greeting, stopped speaking, and responded coherently to the follow-up question."

---

### Repeated Barge-ins

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "standard", "condition": "The agent greets the caller and asks how it can help", "action": "<interruption time=\"1s\" /> Sorry, can you repeat that?", "fixed_message": true },
    { "id": 2, "type": "action_followup", "condition": 1, "action": "[a question in the agent's domain]", "fixed_message": false },
    { "id": 3, "type": "standard", "condition": "The agent begins responding", "action": "<interruption time=\"1s\" /> Actually, one more thing —", "fixed_message": true },
    { "id": 4, "type": "action_followup", "condition": 3, "action": "[second follow-up question]", "fixed_message": false },
    { "id": 5, "type": "standard", "condition": "The agent answers the second question", "action": "Great, thank you. Goodbye.", "fixed_message": false }
  ]
}
```

Expected outcome: "The bot recovered from two back-to-back interruptions and provided coherent responses after each one."

---

### Call-Start Silence Timeout

Tests that the bot hangs up when the caller never speaks. No tags needed — the testing agent simply has no further conditions after `FIRST_MESSAGE`, so it stays silent for the entire call. The bot's silence timer fires naturally.

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false }
  ]
}
```

Expected outcome: "The bot greeted the caller, received no response, and ended the call after the silence timeout expired."

> This is the only scenario with `FIRST_MESSAGE action: ""` and **no further conditions**. Every other scenario uses that pattern to wait for the bot's greeting before the first response. Here, never responding is the test itself.

---

### Mid-Call Idle

Replace `{THRESHOLD}` with the bot's idle timeout in seconds (from Phase 1). Set silence to `{THRESHOLD} + 2s` so the timer fires before the silence ends.

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "standard", "condition": "The agent greets the caller", "action": "Hello, I need help with something.", "fixed_message": false },
    { "id": 2, "type": "standard", "condition": "The agent asks a follow-up question", "action": "<silence time=\"{THRESHOLD+2}s\" />", "fixed_message": true },
    { "id": 3, "type": "standard", "condition": "The agent asks if the caller is still there", "action": "Yes, sorry. I'm here.", "fixed_message": false }
  ]
}
```

Expected outcome: "After a period of silence mid-call, the bot asked if the caller was still there, and the caller confirmed presence."

---

### Full Idle Escalation to Hang-up

Replace `{TOTAL}` with `{THRESHOLD} × {ESCALATION_COUNT} + 5` (5s buffer past the full escalation budget).

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "standard", "condition": "The agent greets the caller", "action": "<silence time=\"{TOTAL}s\" />", "fixed_message": true }
  ]
}
```

Expected outcome: "The bot prompted the caller multiple times asking if they were still there, then ended the call due to prolonged silence."

---

### DTMF Multi-digit Processing

Replace `{DIGITS}` with a representative digit sequence and `{TERMINATOR}` with the configured terminator (usually `#`).

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "standard", "condition": "The agent greets the caller or asks for input", "action": "<dtmf digits=\"{DIGITS}{TERMINATOR}\" /> I've entered the number.", "fixed_message": true },
    { "id": 2, "type": "standard", "condition": "The agent acknowledges the input or continues", "action": "That's all, goodbye.", "fixed_message": false }
  ]
}
```

Expected outcome: "The bot received and processed the DTMF digit sequence."

---

### DTMF Output to IVR

Use when the bot dials into an external IVR and must send digits to navigate it. Drive the conversation to the point where the bot is expected to send DTMF, then verify it did so in the transcript or bot response.

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "standard", "condition": "The agent greets the caller", "action": "[request that triggers the bot to dial an IVR or external system]", "fixed_message": false },
    { "id": 2, "type": "standard", "condition": "The agent confirms it is connecting or navigating the system", "action": "Great, thank you.", "fixed_message": false }
  ]
}
```

Expected outcome: "The bot initiated a connection to the external system and navigated it using the correct digits."

---

### Outbound SMS

Use when the bot can send an SMS to the caller. Drive the conversation to the trigger point and verify the bot confirms the SMS was sent.

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "standard", "condition": "The agent greets the caller and asks how it can help", "action": "[request that should result in the bot sending an SMS — e.g. 'Send me a confirmation text']", "fixed_message": false },
    { "id": 2, "type": "standard", "condition": "The agent confirms the SMS was sent or asks for the number", "action": "[provide number if asked, or confirm receipt]", "fixed_message": false }
  ]
}
```

Expected outcome: "The bot confirmed that an SMS was sent to the caller."

---

### Voicemail Detection

Use when the bot dials out and may reach a voicemail system instead of a live caller. Cekura's `<voicemail>` tag plays a voicemail greeting to simulate this condition.

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "<voicemail />", "fixed_message": true }
  ]
}
```

Expected outcome: "The bot detected a voicemail system and either left a message or ended the call cleanly without treating the voicemail as a live conversation."

> `<voicemail>` must be the entire action on the condition that uses it — it cannot be combined with other tags or text in the same action.

---

### Network Degradation

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "standard", "condition": "The agent greets the caller", "action": "<network_simulation latency=\"300ms\" packet_loss=\"15%\" /> I'm calling about my account.", "fixed_message": true },
    { "id": 2, "type": "standard", "condition": "The agent responds or asks a follow-up", "action": "Thanks, that's all I needed.", "fixed_message": false }
  ]
}
```

Expected outcome: "The bot handled a degraded network connection and produced a coherent response despite packet loss."

---

## 3e. Attach metrics to every scenario

After creating each scenario, attach these four metrics:

| Metric | Purpose |
|--------|---------|
| Expected Outcome | Was the target infra behavior visible in the transcript? |
| Infrastructure Issues | Silent periods, dropped audio, agent non-response |
| Tool Call Success | Tool invocations completed without error |
| Latency | Per-turn response time |

Use `PATCH /test_framework/v1/scenarios/<id>/` to add metrics, or `POST /test_framework/v1/scenarios/actions/modify-scenarios/` to bulk-add after creating all scenarios.

**Critical:** Expected Outcome prompts must describe only what is observable in the transcript. Never reference internal processor names (`UserIdleHandler`, `LLMRetryProcessor`) — evaluators cannot observe code internals.

---

## Phase 3 Gate

All scenarios are created on Cekura with:
- ✓ `conditional_actions` payload
- ✓ All four metrics attached
- ✓ Placed in the `CI_CD` folder

Move to [Phase 4](phase4-orchestrate.md).
