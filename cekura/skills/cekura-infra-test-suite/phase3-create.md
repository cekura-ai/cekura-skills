# Phase 3 — Create Evaluators on Cekura

**All infra test scenarios must use `scenario_type: "conditional_actions"`** — always, without exception. Behavioral instructions are not deterministic enough to reliably trigger specific infra behaviors like idle timers, interruptions, or DTMF. Never use behavioral mode for this suite.

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

### Rule: After condition 0, always use action_followup with fixed_message: true

Infra tests exercise specific technical behaviors — not the content of what the bot says. Every condition after condition 0 must be `type: "action_followup"` with `fixed_message: true`. This delivers a scripted sequence regardless of the bot's exact phrasing, making tests deterministic and independent of wording changes in the bot's responses.

```
Condition 0 → FIRST_MESSAGE (standard — always the entry point)
Condition 1 → action_followup of 0, fixed_message: true
Condition 2 → action_followup of 1, fixed_message: true
...
```

Never use `standard` conditions after condition 0. Standard conditions match on bot speech content — infra tests have no business depending on what the bot says, only on triggering and observing a specific pipeline behavior.

### Rule: Use `<hold>` for idle timer tests, not `<silence>`

Per the Cekura conditional actions docs, `<hold>` produces dead air (background noise stops) while `<silence>` keeps background noise running — which may register as caller activity on sensitive VAD configurations and prevent the idle timer from firing.

For all other tag constraints (`<interruption>` placement, `<voicemail>` usage, `<dtmf>` syntax, etc.) refer to the **cekura-eval-design** conditional actions reference.

---

## 3d. Scenario templates

Substitute actual values from Phase 1 (idle threshold, domain-appropriate dialogue, DTMF digits, etc.).

### Full Pipeline E2E

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "action_followup", "condition": 0, "action": "[first request relevant to this agent's domain]", "fixed_message": true },
    { "id": 2, "type": "action_followup", "condition": 1, "action": "[answer to the bot's follow-up]", "fixed_message": true },
    { "id": 3, "type": "action_followup", "condition": 2, "action": "[complete the interaction]", "fixed_message": true },
    { "id": 4, "type": "action_followup", "condition": 3, "action": "No, that's all. Thank you.", "fixed_message": true }
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
    { "id": 1, "type": "action_followup", "condition": 0, "action": "<interruption time=\"1s\" /> Wait, I have a quick question.", "fixed_message": true },
    { "id": 2, "type": "action_followup", "condition": 1, "action": "[a follow-up question in the agent's domain]", "fixed_message": true },
    { "id": 3, "type": "action_followup", "condition": 2, "action": "Thank you, goodbye.", "fixed_message": true }
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
    { "id": 1, "type": "action_followup", "condition": 0, "action": "<interruption time=\"1s\" /> Sorry, can you repeat that?", "fixed_message": true },
    { "id": 2, "type": "action_followup", "condition": 1, "action": "[a question in the agent's domain]", "fixed_message": true },
    { "id": 3, "type": "action_followup", "condition": 2, "action": "<interruption time=\"1s\" /> Actually, one more thing —", "fixed_message": true },
    { "id": 4, "type": "action_followup", "condition": 3, "action": "[second follow-up question]", "fixed_message": true },
    { "id": 5, "type": "action_followup", "condition": 4, "action": "Great, thank you. Goodbye.", "fixed_message": true }
  ]
}
```

Expected outcome: "The bot recovered from two back-to-back interruptions and provided coherent responses after each one."

---

### Call-Start Silence Timeout

No conditions after condition 0 — the testing agent stays silent for the entire call. The bot's silence timer fires naturally.

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false }
  ]
}
```

Expected outcome: "The bot greeted the caller, received no response, and ended the call after the silence timeout expired."

---

### Mid-Call Idle

Replace `{THRESHOLD}` with the bot's idle timeout in seconds + 2.

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "action_followup", "condition": 0, "action": "Hello, I need help with something.", "fixed_message": true },
    { "id": 2, "type": "action_followup", "condition": 1, "action": "<hold time=\"{THRESHOLD+2}s\" />", "fixed_message": true },
    { "id": 3, "type": "action_followup", "condition": 2, "action": "Yes, sorry. I'm here.", "fixed_message": true }
  ]
}
```

Expected outcome: "After a period of silence mid-call, the bot asked if the caller was still there, and the caller confirmed presence."

---

### Full Idle Escalation to Hang-up

Replace `{TOTAL}` with `{THRESHOLD} × {ESCALATION_COUNT} + 5`.

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "action_followup", "condition": 0, "action": "<hold time=\"{TOTAL}s\" />", "fixed_message": true }
  ]
}
```

Expected outcome: "The bot prompted the caller multiple times asking if they were still there, then ended the call due to prolonged silence."

---

### DTMF Multi-digit Processing

Replace `{DIGITS}` and `{TERMINATOR}` with the configured values from Phase 1.

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "action_followup", "condition": 0, "action": "<dtmf digits=\"{DIGITS}{TERMINATOR}\" />", "fixed_message": true },
    { "id": 2, "type": "action_followup", "condition": 1, "action": "That's all, goodbye.", "fixed_message": true }
  ]
}
```

Expected outcome: "The bot received and processed the DTMF digit sequence."

---

### Inbound SMS Handling

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "action_followup", "condition": 0, "action": "I'll send you the details over text.", "fixed_message": true },
    { "id": 2, "type": "action_followup", "condition": 1, "action": "<send_sms text=\"[the SMS content the caller sends]\" />", "fixed_message": true },
    { "id": 3, "type": "action_followup", "condition": 2, "action": "Great, thanks.", "fixed_message": true }
  ]
}
```

Expected outcome: "The bot received the inbound SMS and responded or acted on its contents correctly."

---

### DTMF Output to IVR

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "action_followup", "condition": 0, "action": "[request that triggers the bot to dial an IVR or external system]", "fixed_message": true },
    { "id": 2, "type": "action_followup", "condition": 1, "action": "Great, thank you.", "fixed_message": true }
  ]
}
```

Expected outcome: "The bot initiated a connection to the external system and navigated it using the correct digits."

---

### Outbound SMS

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "action_followup", "condition": 0, "action": "[request that should result in the bot sending an SMS]", "fixed_message": true },
    { "id": 2, "type": "action_followup", "condition": 1, "action": "[provide number if asked, or confirm receipt]", "fixed_message": true }
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
