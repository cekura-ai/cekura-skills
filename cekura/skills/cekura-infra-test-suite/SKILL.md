---
name: cekura-infra-test-suite
description: >
  Use when the user asks to "create CI/CD tests for my voice bot", "test my voice AI infrastructure",
  "write infra tests using conditional actions", "E2E test my pipecat bot", "test STT LLM TTS pipeline",
  "test interruption handling", "test idle timer", "test DTMF processing", "set up a local bot CI test suite",
  "run cekura scenarios against my local bot", "build a CI gate for my voice agent", or
  "generate regression tests for my voice pipeline". Covers end-to-end infrastructure test suite design
  for voice AI agents using Cekura conditional actions — STT→LLM→TTS, interruption, idle timers, DTMF,
  and local bot orchestration via run script.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

# Cekura Voice AI Infrastructure Test Suite

## Purpose

Generate a compact, CI/CD-ready set of Cekura evaluators that test every observable layer of a voice AI pipeline — STT, LLM, TTS, interruption handling, idle timers, and DTMF — using conditional actions for deterministic, repeatable results. These tests run against a local or staging bot and act as a PR gate.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

---

## What This Suite Tests (and What It Doesn't)

### What can be tested via Cekura evaluators

| Infra Layer | Observable Signal | How to Trigger |
|---|---|---|
| STT → LLM → TTS | Bot responds coherently across multiple turns | Multi-turn conversation in conditional actions |
| TTS cancellation | Bot stops mid-sentence when interrupted | `<interruption time="Xs" />` tag |
| Pipeline state reset | Bot recovers correctly after interruption | Two back-to-back interruption cycles |
| Idle timer (single prompt) | Bot says "are you still there?" after silence | `<hold time="Xs" />` — longer than idle threshold |
| Full idle escalation | Bot repeats prompt N times then hangs up | Extended `<hold>` — longer than total idle budget |
| DTMF aggregation | Bot correctly processes multi-digit touch-tone input | `<dtmf digits="12345#" />` + spoken confirmation |
| Clean call termination | Bot ends call cleanly after task completion | `end_call` function call in conversation |

### What CANNOT be reliably tested from a transcript

- Internal processor state (`LLMRetryProcessor`, `LLMErrorDetectionProcessor`, `LLMTimeoutProcessor`) — these are invisible to evaluators
- STT word-level timing or confidence scores
- Whether a specific code path was taken inside the bot
- Call-start silence timeout — `<hold>` and `<silence>` both produce audio artifacts that interfere with initial silence detection; exclude this from CI suites

---

## The Compact 6-Scenario Suite

One scenario per infra layer. All use `conditional_actions` mode for deterministic, repeatable behavior.

| ID | Scenario | Infra Layer | Timeout |
|----|----------|-------------|---------|
| S1 | Full Pipeline E2E | STT→LLM→TTS, multi-turn context, clean hang-up | 400s |
| S2 | Mid-Speech Interruption | TTS cancellation + pipeline reset | 400s |
| S3 | Repeated Mid-Speech Barge-ins | Two back-to-back interrupt cycles, state recovery | 400s |
| S4 | Mid-Call Idle + Phantom VAD | Idle timer fires despite background noise | 180s |
| S5 | Full Idle Escalation to Hang-up | 3×idle prompts then `IDLE_TIMEOUT` call end | 450s |
| S7 | DTMF Multi-digit Processing | DTMFAggregator accumulates digits, `#` flushes buffer | 120s |

> **S6 is intentionally excluded.** Call-start silence timeout cannot be triggered reliably with Cekura tags — `<hold>` and `<silence>` both produce audio artifacts at their boundaries that reset the bot's voice-activity detection.

---

## Step-by-Step: Creating the Suite

### 1. Gather bot configuration

Before authoring scenarios, collect:
- **Agent ID** in Cekura (the agent being tested)
- **Idle timer threshold** (how many seconds before the bot prompts "are you still there?")
- **Idle escalation count** (how many prompts before hang-up)
- **Whether bot speaks first** (set `firstMessage` in bot config) — this determines whether `FIRST_MESSAGE` should have an empty action or a greeting

### 2. Create a folder

```
POST /test_framework/v1/scenarios/folder/
{
  "name": "CI_CD",
  "project_id": <project_id>
}
```

All CI scenarios go into this folder. Pass `folder_path` on each scenario creation.

### 3. Author each scenario as `conditional_actions`

Create each scenario via:

```
POST /test_framework/v1/scenarios/
{
  "agent": <agent_id>,
  "name": "S1 - Full Pipeline E2E",
  "scenario_type": "conditional_actions",
  "personality": 693,
  "tool_ids": ["TOOL_END_CALL"],
  "folder_path": "CI_CD",
  "conditional_actions": { ... }
}
```

See "Scenario Templates" below for the exact `conditional_actions` payloads.

### 4. Attach metrics to all scenarios

Every infra scenario needs at minimum:

| Metric | Why |
|--------|-----|
| Expected Outcome | Verifies the transcript shows the expected infra behavior |
| Infrastructure Issues | Catches silent periods, dropped connections, agent non-response |
| Tool Call Success | Flags tool call failures even in conversational agents |
| Latency | Measures response time per turn |

Use `PATCH /test_framework/v1/scenarios/<id>/` to add metrics after creation, or `POST /test_framework/v1/scenarios/actions/modify-scenarios/` to bulk-add.

**Critical:** Expected Outcome prompts must reference only transcript-observable behavior. Never mention internal processor names or code paths.

### 5. Wire up the run orchestration script

See "Orchestration Script" section below.

---

## Scenario Templates

### S1 — Full Pipeline E2E

Tests STT→LLM→TTS across 4 turns, multi-turn context retention, and clean `end_call`.

```json
{
  "role": "caller",
  "conditions": [
    {
      "id": 0,
      "type": "standard",
      "condition": "FIRST_MESSAGE",
      "action": "",
      "fixed_message": false
    },
    {
      "id": 1,
      "type": "standard",
      "condition": "The agent greets the caller and asks how it can help",
      "action": "I'd like to schedule a primary care appointment",
      "fixed_message": false
    },
    {
      "id": 2,
      "type": "standard",
      "condition": "The agent asks whether I am a new or returning patient",
      "action": "I'm a returning patient",
      "fixed_message": false
    },
    {
      "id": 3,
      "type": "standard",
      "condition": "The agent asks for my name or date of birth",
      "action": "My name is Alex Chen, date of birth June 5, 1988",
      "fixed_message": false
    },
    {
      "id": 4,
      "type": "standard",
      "condition": "The agent offers appointment times or asks about availability",
      "action": "The first available slot works for me",
      "fixed_message": false
    },
    {
      "id": 5,
      "type": "standard",
      "condition": "The agent confirms the appointment and asks if there is anything else",
      "action": "No, that's all. Thank you.",
      "fixed_message": false
    }
  ]
}
```

**Expected Outcome prompt:** "The bot greeted the caller, collected patient type and name/DOB, offered and confirmed an appointment slot, and ended the call cleanly."

---

### S2 — Mid-Speech Interruption

Tests that `<interruption>` stops the bot mid-sentence and the pipeline resets.

```json
{
  "role": "caller",
  "conditions": [
    {
      "id": 0,
      "type": "standard",
      "condition": "FIRST_MESSAGE",
      "action": "",
      "fixed_message": false
    },
    {
      "id": 1,
      "type": "standard",
      "condition": "The agent greets the caller and asks how it can help",
      "action": "<interruption time=\"1s\" /> Wait, actually I have a quick question first.",
      "fixed_message": true
    },
    {
      "id": 2,
      "type": "action_followup",
      "condition": 1,
      "action": "Can you tell me your clinic hours?",
      "fixed_message": false
    },
    {
      "id": 3,
      "type": "standard",
      "condition": "The agent describes clinic hours or office availability",
      "action": "Great, thank you. Goodbye.",
      "fixed_message": false
    }
  ]
}
```

**Expected Outcome prompt:** "The bot was interrupted during its greeting and stopped speaking. After the interruption, the bot responded to the question about clinic hours."

> **Important:** `<interruption>` must be at the **start** of the action string, and `fixed_message: true` is required for the action containing it.

---

### S3 — Repeated Mid-Speech Barge-ins

Two back-to-back interruption cycles to verify pipeline state resets cleanly each time.

```json
{
  "role": "caller",
  "conditions": [
    {
      "id": 0,
      "type": "standard",
      "condition": "FIRST_MESSAGE",
      "action": "",
      "fixed_message": false
    },
    {
      "id": 1,
      "type": "standard",
      "condition": "The agent greets the caller and asks how it can help",
      "action": "<interruption time=\"1s\" /> Sorry, can you start again?",
      "fixed_message": true
    },
    {
      "id": 2,
      "type": "action_followup",
      "condition": 1,
      "action": "Actually, sorry again — what are your hours?",
      "fixed_message": false
    },
    {
      "id": 3,
      "type": "standard",
      "condition": "The agent begins explaining hours or services",
      "action": "<interruption time=\"1s\" /> One more thing — do you take walk-ins?",
      "fixed_message": true
    },
    {
      "id": 4,
      "type": "action_followup",
      "condition": 3,
      "action": "Great, thank you. That's all I needed.",
      "fixed_message": false
    }
  ]
}
```

**Expected Outcome prompt:** "The bot was interrupted twice and recovered each time, providing a coherent response after each interruption."

---

### S4 — Mid-Call Idle + Phantom VAD Regression

Hold for longer than the idle threshold (e.g., 12s for a 10s timer). The bot should prompt "are you still there?".

```json
{
  "role": "caller",
  "conditions": [
    {
      "id": 0,
      "type": "standard",
      "condition": "FIRST_MESSAGE",
      "action": "",
      "fixed_message": false
    },
    {
      "id": 1,
      "type": "standard",
      "condition": "The agent greets the caller and asks how it can help",
      "action": "I'd like to schedule an appointment.",
      "fixed_message": false
    },
    {
      "id": 2,
      "type": "standard",
      "condition": "The agent asks a follow-up question about the appointment",
      "action": "<hold time=\"12s\" />",
      "fixed_message": true
    },
    {
      "id": 3,
      "type": "standard",
      "condition": "The agent asks if the caller is still there or checks on them",
      "action": "Yes, I'm here. Sorry about that.",
      "fixed_message": false
    }
  ]
}
```

**Expected Outcome prompt:** "After a period of silence mid-call, the bot asked if the caller was still there. The caller confirmed presence and the bot continued the conversation."

> **Use `<hold>`, not `<silence>`.** `<silence>` produces a brief audio artifact at its boundary that can register as a voice-activity event and reset the idle timer. `<hold>` plays real audio (hold music) that doesn't trigger STT VAD.

---

### S5 — Full Idle Escalation to Hang-up

Hold long enough for the full idle escalation sequence: N prompts then hang-up.

```json
{
  "role": "caller",
  "conditions": [
    {
      "id": 0,
      "type": "standard",
      "condition": "FIRST_MESSAGE",
      "action": "",
      "fixed_message": false
    },
    {
      "id": 1,
      "type": "standard",
      "condition": "The agent greets the caller and asks how it can help",
      "action": "<hold time=\"90s\" />",
      "fixed_message": true
    }
  ]
}
```

**Expected Outcome prompt:** "The bot prompted the caller multiple times asking if they were still there, then ended the call due to prolonged silence."

> Set `<hold>` duration to exceed `idle_timeout × escalation_count`. For a 10s timer with 3 prompts, use at least 40s.

---

### S7 — DTMF Multi-digit Processing

Tests that the DTMFAggregator accumulates digits and flushes on `#`.

```json
{
  "role": "caller",
  "conditions": [
    {
      "id": 0,
      "type": "standard",
      "condition": "FIRST_MESSAGE",
      "action": "",
      "fixed_message": false
    },
    {
      "id": 1,
      "type": "standard",
      "condition": "The agent greets the caller or asks for input",
      "action": "Please process the following: <dtmf digits=\"98765#\" /> Thank you, I entered it.",
      "fixed_message": true
    },
    {
      "id": 2,
      "type": "standard",
      "condition": "The agent acknowledges the input or asks what it can help with",
      "action": "That's all I needed, goodbye.",
      "fixed_message": false
    }
  ]
}
```

**Expected Outcome prompt:** "The bot received multi-digit DTMF input and processed or acknowledged it."

> **Always combine `<dtmf>` with spoken text.** A pure `<dtmf>` action with no voice doesn't register as a completed testing-agent turn, and the condition chain never advances to the next step.

---

## Key Conditional Actions Patterns

### FIRST_MESSAGE with empty action — always do this when the bot speaks first

```json
{ "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false }
```

If the bot has `firstMessage` configured and the testing agent also fires a first message, both sides speak simultaneously. This causes STT to pick up both speakers and enter a confused state. Setting `action: ""` makes the testing agent stay silent and wait for the bot's greeting before responding.

### Conditions are natural language descriptions — not keyword filters

**Wrong:** `"condition": "contains 'help' OR contains 'assist'"`

**Right:** `"condition": "The agent greets the caller and asks how it can help"`

Conditions are matched by the Cekura testing agent using semantic understanding of the main agent's speech. Use plain English to describe what the bot said or did.

### action_followup on the FIRST_MESSAGE condition can fire twice

When the bot's greeting is long, the STT engine may split it across two transcribed utterances. An `action_followup` attached to condition 0 fires once for each transcribed chunk — twice total. Fix: use a `standard` condition (not `action_followup`) to match the bot's full greeting before starting any action chain.

---

## Local Bot Orchestration

### The CI Override Pattern

For testing a local bot, the run orchestration script:

1. Triggers a Cekura run to get the testing agent's outbound number
2. Writes a `.ci_test_config.json` file the bot reads at startup
3. Starts the bot with `LOCAL_RUN=1`
4. Polls Cekura for `evaluation_status`
5. Cleans up (kill bot, delete config file)

**`.ci_test_config.json` format:**
```json
{
  "sip_uri": "sip:+13682101298@cekura-pipecat-local.sip.twilio.com?X-CallerId=+19789751706",
  "scenario_config": {
    "name": "Riley — Wellness Partners scheduling assistant",
    "instructions": "..."
  }
}
```

The bot's `dial_out_utils.py` must read this file and apply overrides **before** dialing out:

```python
ci_override_path = pathlib.Path(__file__).parent / ".ci_test_config.json"
if ci_override_path.exists():
    with open(ci_override_path) as f:
        ci_overrides = json.load(f)
    if "sip_uri" in ci_overrides:
        body["dialout_settings"]["sip_uri"] = ci_overrides["sip_uri"]
    if "scenario_config" in ci_overrides:
        body["scenario_config"].update(ci_overrides["scenario_config"])
```

> **Do NOT override nested config dicts wholesale.** Python's `dict.update()` replaces entire nested structures. Overriding `configuration` wipes `configuration.model.provider` and the bot defaults to the wrong LLM. Only override top-level fields or do deep merges.

### SIP URI construction

Cekura's run response contains `runs[0].number` — the outbound phone number the testing agent will call from. Use it to construct the SIP URI:

```python
sip_uri = f"sip:{run_number}@cekura-pipecat-local.sip.twilio.com?X-CallerId={agent_number}"
```

### Run orchestration script outline

```python
for scenario in SCENARIOS:
    # 1. Trigger Cekura run
    result = POST /test_framework/v1/scenarios/run_scenarios/ {
        "agent_id": agent_id,
        "scenarios": [scenario["id"]],
        "frequency": 1,
        "agent_number": "+1XXXXXXXXXX",   # your bot's inbound number
        "concurrency_limit": 1
    }
    run_id = result["result_id"]
    run_number = result["runs"][0]["number"]

    # 2. Write CI override
    write_json(".ci_test_config.json", {"sip_uri": f"sip:{run_number}@..."})

    # 3. Start bot (LOCAL_RUN=1)
    proc = subprocess.Popen(["python", "bot.py"], env={**os.environ, "LOCAL_RUN": "1"})
    await asyncio.sleep(20)  # wait for Daily room + SIP dial-out

    # 4. Poll for result
    while time_remaining > 0:
        status = GET /test_framework/v1/runs/{run_id}/
        if status["status"] == "completed":
            break
        await asyncio.sleep(10)

    # 5. Evaluate
    passed = status.get("evaluation_status") == "success"

    # 6. Cleanup
    proc.terminate()
    os.remove(".ci_test_config.json")
```

---

## Common Pitfalls

| Pitfall | What happens | Fix |
|---------|-------------|-----|
| `firstMessage` overlap | Both bot and testing agent speak simultaneously; STT gets confused | Set `FIRST_MESSAGE action: ""` |
| `action_followup` on condition 0 fires twice | Long bot greeting splits across two STT turns; followup fires once per chunk | Use `standard` condition to match full greeting |
| Using `<silence>` for idle timer tests | Audio artifact at tag boundary triggers VAD, resets idle timer | Use `<hold>` instead |
| Keyword-style conditions | `contains "X"` syntax is wrong for Cekura | Write natural-language descriptions of agent behavior |
| Expected outcomes reference internal code | Metrics can't observe processor state | Only describe what appears in the call transcript |
| Pure `<dtmf>` with no voice | Action doesn't register as a testing-agent turn; chain freezes | Add spoken text after the `<dtmf>` tag |
| Overriding nested config dicts | `dict.update()` on `configuration` wipes `model.provider`; bot defaults to wrong LLM | Override only `sip_uri` and `scenario_config`, not `configuration` |
| Testing call-start silence timeout (S6) | `<hold>`/`<silence>` produce audio artifacts that interfere with initial silence detection | Exclude from CI; test manually |

---

## Metrics Quick Reference

Use these on every infra scenario:

| Metric Name | Purpose |
|-------------|---------|
| Expected Outcome | Was the expected infra behavior visible in the transcript? |
| Infrastructure Issues | Silent periods, dropped audio, agent non-response |
| Tool Call Success | Tool invocations completed without error |
| Latency | Per-turn response time within acceptable bounds |

---

## Documentation

- Cekura docs: https://docs.cekura.ai
- Conditional actions reference: https://docs.cekura.ai/documentation/key-concepts/evaluators/conditional-actions
- Pre-defined metrics: https://docs.cekura.ai/documentation/key-concepts/metrics/pre-defined-metrics
- Run scenarios API: https://docs.cekura.ai/api-reference/scenarios/run-scenarios

## Next Steps

- To design additional behavioral (non-infra) test coverage → **cekura-eval-design**
- To add or tune metrics → **cekura-metric-design**
- To debug a failing prod call → **cekura-fixing-prod-issues**
