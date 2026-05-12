# Phase 3 — Create Evaluators on Cekura

Create a folder, then create each confirmed scenario with a conditional_actions payload and the right metrics. Follow the authoring rules below — they prevent the most common failures.

---

## 3a. Create a folder

Always group infra scenarios in a dedicated folder. Never dump them in the root.

```
POST /test_framework/v1/scenarios/folder/
{
  "name": "Infrastructure Test Suite",
  "project_id": <project_id>
}
```

Use the returned `folder_path` on every scenario in this suite.

---

## 3b. Required fields on every scenario

Every scenario must include:

```json
{
  "scenario_type": "conditional_actions",
  "folder_path": "Infrastructure Test Suite"
}
```

**`personality`** — choose based on what the scenario needs to test: accent, language, background noise level, interruption tendency. Use `GET /test_framework/v1/personalities/` to list available options. Do not default to a fixed ID.

---

## 3c. Authoring rules — read before writing any conditions

### Rule: Condition 0 depends on who speaks first (Q8 answer)

**If the bot speaks first** (Q8: yes) — the testing agent must wait silently. Set `action: ""` so the testing agent stays quiet until the bot's greeting is complete. If both sides fire a first message simultaneously, the STT picks up both speakers and enters a confused state.

```json
{ "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false }
```

**If the caller speaks first** (Q8: no) — the testing agent initiates. Give condition 0 a non-empty action with the caller's opening line.

```json
{ "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "Hi, I need help with [domain-relevant request].", "fixed_message": false }
```

**Override for start-of-call interruption tests** — if the scenario is specifically testing whether the bot handles being interrupted immediately as it begins speaking, the testing agent should fire into the bot's first message intentionally, regardless of Q8. Use `<interruption>` in condition 0's action to cut in as soon as the bot starts.

### Rule: Use `<hold>` for idle timer tests, not `<silence>`

Per the Cekura conditional actions docs:

| | `<silence>` | `<hold>` |
|---|---|---|
| Interruptible by main agent | Yes | No |
| Background noise during pause | Continues | Stops (dead air) |

`<hold>` produces dead air — no background noise — which gives the bot's VAD the cleanest silence signal and is the safest choice for triggering idle timers. `<silence>` keeps background noise running, which depending on the bot's VAD sensitivity may register as caller activity and prevent the idle timer from firing.

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
    { "id": 2, "type": "standard", "condition": "The agent asks a follow-up question", "action": "<hold time=\"{THRESHOLD+2}s\" />", "fixed_message": true },
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
    { "id": 1, "type": "standard", "condition": "The agent greets the caller", "action": "<hold time=\"{TOTAL}s\" />", "fixed_message": true }
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

### Inbound SMS Handling

Use when the bot is expected to react to an SMS sent by the caller. The `<send_sms>` tag makes the testing agent send an SMS mid-call.

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "standard", "condition": "The agent greets the caller", "action": "I'll send you the details over text.", "fixed_message": false },
    { "id": 2, "type": "standard", "condition": "The agent responds or waits", "action": "<send_sms text=\"[the SMS content the caller sends]\" />", "fixed_message": true },
    { "id": 3, "type": "standard", "condition": "The agent acknowledges the SMS or acts on it", "action": "Great, thanks.", "fixed_message": false }
  ]
}
```

Expected outcome: "The bot received the inbound SMS and responded or acted on its contents correctly."

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

Two activation steps are required — missing either means the metric never fires:
1. **Toggle on at the project level** — `POST /test_framework/v1/predefined-metrics/<id>/toggle/`
2. **Add to individual evaluators** — `PATCH /test_framework/v1/scenarios/<id>/` with `metrics: [id, ...]`

Or bulk-add after creating all scenarios: `POST /test_framework/v1/scenarios/actions/modify-scenarios/`

### Baseline — attach to every scenario (all free)

| Metric | What it catches |
|--------|----------------|
| **Expected Outcome** | Did the transcript show the expected infra behavior? Set `expected_outcome_prompt` per scenario. |
| **Infrastructure Issues** | Main agent goes silent for > N seconds (default 10s, configurable). Catches dropped audio and agent non-response invisible in pass/fail. |
| **Latency** | Average response time + P25/P50/P75/P90/P95/P99. Under 2000ms is healthy. |
| **Tool Call Success** | Any tool call returned an error. Free; requires provider integration for tool call data to appear in transcript. |

### Scenario-specific additions

| Scenario | Add these metrics | Why |
|---|---|---|
| Full Pipeline E2E | **Detect Silence in Conversation** | Catches both-speaker silence gaps invisible in the transcript |
| Mid-Speech Interruption | **Stop Time after User Interruption**, **Interruption Score** | Measure how quickly the bot stopped and how cleanly it recovered |
| Repeated Barge-ins | **Stop Time after User Interruption**, **Interruption Score**, **AI Interrupting User** | Same as above; AI Interrupting User flags if the bot is fighting back |
| Mid-Call Idle | **Detect Silence in Conversation** (configure threshold to match idle timer) | Confirms the silence period actually registered |
| Full Idle Escalation | **Appropriate Call Termination by Main Agent** | Verifies the bot ended the call correctly after escalation, not prematurely |
| DTMF Input | **Mock Tool Call Accuracy** | If DTMF triggers a mock tool, checks correct inputs were passed |
| Voicemail Handling | **Voicemail Detection** | Built-in classifier — detects if the call reached a voicemail system |
| Network Degradation | **Voice Tone + Clarity** | Audio quality score; detects jitter and clarity loss from packet loss |

### Expected Outcome prompt rules

The Expected Outcome metric evaluates the transcript text only — it has no access to audio, silences, interruptions, or internal pipeline state. Write prompts that describe only what is visible in the conversation:

**Wrong:** "The LLMRetryProcessor recovered from the timeout and the agent continued"

**Right:** "After a pause, the agent responded coherently and continued the conversation"

---

## Phase 3 Gate

All scenarios are created on Cekura with:
- ✓ `conditional_actions` payload
- ✓ All four metrics attached
- ✓ Placed in the `CI_CD` folder

Move to [Phase 4](phase4-orchestrate.md).
