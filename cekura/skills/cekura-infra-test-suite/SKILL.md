---
name: cekura-infra-test-suite
description: >
  Use when the user asks to "create CI/CD tests for my voice bot", "test my voice AI infrastructure",
  "write infra tests", "E2E test my voice pipeline", "build a CI gate for my voice agent",
  "generate regression tests for my voice pipeline", "set up automated testing for my bot",
  "what infra tests should I create", "test my STT LLM TTS pipeline", or "run automated tests
  against my local bot". Auto-discovers the codebase's transport, STT, LLM, TTS, and processor
  components, maps each to the Cekura test pattern that exercises it, presents a confirmation
  checkpoint, then creates a compact CI/CD test suite using conditional actions.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

# Cekura Voice AI Infrastructure Test Suite

## Purpose

Automatically discover what voice AI infrastructure components exist in the user's codebase, map each to a Cekura-testable behavior, and generate a compact CI/CD test suite using conditional actions — without requiring the user to explain their stack first.

This skill applies to any voice AI framework (Pipecat, VAPI, Retell, LiveKit Agents, custom WebSocket servers, etc.) and any provider combination.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

---

## The 5-Phase Workflow

```
Phase 1       Phase 2          Phase 3         Phase 4       Phase 5
Discover  →  Map to Tests  →  Checkpoint  →   Create    →   Orchestrate
Read code     Component →      User confirms   Cekura        Run script +
to find       Cekura pattern   proposed suite  evaluators    CI override
components    table            before build    + metrics     pattern
```

---

## Phase 1 — Infrastructure Discovery

Read the codebase before asking the user anything. Collect answers to every question below. Do not proceed to Phase 2 until you have checked the code.

### What to look for

**1. Transport / call setup**
- SIP: look for `sip:`, `twilio`, `vonage`, `telnyx`, `dial_out`, `sip_uri`, `SIPTransport`
- WebRTC: look for `Daily`, `LiveKit`, `Agora`, `DailyTransport`, `LiveKitTransport`
- WebSocket: look for `WebSocketTransport`, `ws://`, `wss://`
- PSTN / telephony: look for `PhoneTransport`, `phone_number`, `from_number`

**2. STT (Speech-to-Text)**
- Provider: Deepgram, Google, Azure, AssemblyAI, Whisper, Groq, Rev
- Look for: import names, class instantiations (e.g., `DeepgramSTTService`), config keys (`stt_provider`, `transcriber`)
- VAD (voice activity detection): look for `VAD`, `silero`, `WebRTCVAD`, `vad_enabled`

**3. LLM**
- Provider: OpenAI, Anthropic, Google Gemini, Groq, Azure OpenAI, Cohere, Mistral
- Look for: client instantiations, model names, structured output configs
- Resilience: look for retry logic (`LLMRetryProcessor`, `retry_on_error`, `max_retries`), error detection (`LLMErrorDetectionProcessor`), timeout handling (`LLMTimeoutProcessor`)

**4. TTS (Text-to-Speech)**
- Provider: Cartesia, ElevenLabs, PlayHT, Azure, Google, Deepgram, Polly
- Look for: class names, voice IDs, `tts_provider`, `voice`
- Interruption config: look for `interruptionLevel`, `BotInterruptionProcessor`, `stop_on_interrupt`, `InterruptionHandler`

**5. Processors / pipeline components**
Scan for these by name or behavior:

| Signal in code | Infra behavior |
|---|---|
| `UserIdleHandler`, `idle_timeout`, `idleTimeoutSeconds`, `silence_timeout` | Idle timer: bot prompts "are you still there?" |
| `messagePlan.idleMessages`, `idle_messages`, `idleMessageMaxSpokenCount` | Idle escalation: N prompts then hang-up |
| `DTMFAggregator`, `dtmf`, `send_dtmf`, `sendDtmfEnabled` | DTMF digit processing |
| `NetworkImpairmentProcessor`, `network_simulation`, `packet_loss`, `jitter` | Network degradation simulation |
| `TransferHandler`, `transfer_call`, `callHoldFunctionEnabled`, `transfer_to` | Call transfer |
| `endCallFunctionEnabled`, `EndCallTriggerProcessor`, `end_call` | Bot-initiated call end |
| `BackgroundNoiseProcessor`, `backgroundDenoisingEnabled` | Background noise handling |
| `CallRecording`, `use_provider_recording`, `recording_file_name` | Call recording |

**6. Bot configuration**
- Does the bot say something first (`firstMessage`, greeting in system prompt)?
- What is the idle timeout value (seconds)?
- How many idle prompts before hang-up (`idleMessageMaxSpokenCount`)?
- Is DTMF enabled? What is the terminator digit?
- Are there fallback providers (STT fallback, LLM fallback, TTS fallback)?

**7. Local run mode**
- Is there a `LOCAL_RUN`, `DEV_MODE`, or similar env var?
- How is the bot started locally (command, script, Docker)?
- How is config overridden for testing (env file, JSON override file, CLI args, test fixture)?
- Is there an existing run script or CI config?

---

## Phase 2 — Component → Test Mapping

Once you have the discovery results, map each found component to the most appropriate Cekura test. Every test is a `conditional_actions` scenario.

**Mapping table — apply only components that were actually found:**

| Discovered Component | Test Scenario | Cekura Trigger | What it proves |
|---|---|---|---|
| STT + LLM + TTS (always present) | **S: Full Pipeline E2E** | Multi-turn conditional_actions conversation | All three pipeline layers work end-to-end |
| Interruption handler (`BotInterruptionProcessor`, `interruptionLevel`, etc.) | **S: Mid-Speech Interruption** | `<interruption time="1s" />` at start of action | TTS stops on interrupt; pipeline resets |
| Interruption handler (same as above) | **S: Repeated Barge-ins** | Two back-to-back `<interruption>` cycles | State resets cleanly after each interrupt |
| Idle timer (`UserIdleHandler`, `idleTimeoutSeconds`, etc.) | **S: Mid-Call Idle** | `<hold time="{threshold+2}s" />` | Idle timer fires; bot prompts caller |
| Idle escalation (`idleMessageMaxSpokenCount` > 1) | **S: Full Idle Escalation** | `<hold time="{threshold × count + buffer}s" />` | Full escalation sequence ends in hang-up |
| DTMF (`DTMFAggregator`, `sendDtmfEnabled`) | **S: DTMF Multi-digit** | `<dtmf digits="XXXXX#" /> spoken text` | Aggregator accumulates + flushes on terminator |
| Network simulation (`NetworkImpairmentProcessor`) | **S: Network Degradation** | `<network_simulation latency="300ms" packet_loss="15%" />` | Bot handles degraded audio without crashing |
| Call transfer (`TransferHandler`) | **S: Transfer to Human** | Trigger transfer phrase; `TOOL_END_CALL_ON_TRANSFER` | Transfer completes cleanly |
| Fallback providers (STT/LLM/TTS) | **S: Fallback Recovery** | Behavioral scenario; ask primary to fail | Bot falls back and continues |

**Compactness rule:** If the codebase does NOT have a component, do not create a test for it. A 4-scenario suite that covers the actual infra is better than an 8-scenario suite with 4 dead tests.

**Always include Full Pipeline E2E.** It's the baseline that every other scenario assumes is passing.

---

## Phase 3 — Pre-Creation Checkpoint

Before creating anything on Cekura, present a checkpoint to the user:

```
INFRA DISCOVERED:
  Transport:    [what you found]
  STT:          [provider + VAD]
  LLM:          [provider + retry/error handling]
  TTS:          [provider + interruption config]
  Idle timer:   [Xs timeout, N prompts before hang-up] OR [not found]
  DTMF:         [found / not found, terminator digit]
  Network sim:  [found / not found]
  Transfer:     [found / not found]
  Bot speaks first: [yes / no]

PROPOSED TEST SUITE (N scenarios):
  S1 — Full Pipeline E2E (always)
  S2 — [next scenario based on found components]
  ...

OPEN QUESTIONS:
  - [Any ambiguity you couldn't resolve from code alone]

Proceed with this suite, or should I adjust the scope?
```

Do not create evaluators until the user confirms. If the user asks to adjust, revise the mapping and re-present.

---

## Phase 4 — Scenario Authoring

Create each scenario via `POST /test_framework/v1/scenarios/` with `scenario_type: "conditional_actions"`.

### Universal field defaults

```json
{
  "personality": 693,
  "tool_ids": ["TOOL_END_CALL"],
  "scenario_type": "conditional_actions"
}
```

Add `"TOOL_END_CALL_ON_TRANSFER"` to `tool_ids` for any transfer scenario.

### Always start with FIRST_MESSAGE action: ""

Every scenario's first condition must be:

```json
{ "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false }
```

**Why:** If the bot has `firstMessage` configured and the testing agent also fires a first message, both sides speak simultaneously. The STT picks up both speakers and enters a confused state. Setting `action: ""` makes the testing agent wait silently until the bot's greeting is complete.

**Exception:** If the bot does NOT speak first (no `firstMessage`, no greeting), the testing agent should initiate. In this case, condition 0 can have a non-empty action.

### Writing conditions — natural language only

Conditions are matched semantically by Cekura's testing agent. They must describe what the bot said, not filter by keywords.

**Wrong:** `"condition": "contains 'help' OR contains 'assist'"`

**Right:** `"condition": "The agent greets the caller and asks how it can help"`

Write conditions that a human would use to describe the bot's turn in plain English.

### Scenario templates by type

**Full Pipeline E2E — 4+ conversational turns:**

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "standard", "condition": "The agent greets the caller and asks how it can help", "action": "[first user request, relevant to this agent's domain]", "fixed_message": false },
    { "id": 2, "type": "standard", "condition": "The agent responds and asks a follow-up question", "action": "[answer the follow-up]", "fixed_message": false },
    { "id": 3, "type": "standard", "condition": "The agent provides information or asks for more details", "action": "[complete the interaction]", "fixed_message": false },
    { "id": 4, "type": "standard", "condition": "The agent summarizes or confirms and asks if there is anything else", "action": "No, that's all. Thank you.", "fixed_message": false }
  ]
}
```

Tailor the action strings to the bot's actual domain (scheduling, customer support, IVR, etc.).

**Mid-Speech Interruption:**

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

> `<interruption>` must be at the **start** of the action string, and `fixed_message: true` is required on that action. Do not use `action_followup` on condition 0 (FIRST_MESSAGE) — if the bot's greeting splits across two STT chunks, the followup fires twice.

**Mid-Call Idle — use `{threshold + 2}s` hold:**

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "standard", "condition": "The agent greets the caller", "action": "Hello, I need help with something.", "fixed_message": false },
    { "id": 2, "type": "standard", "condition": "The agent asks a follow-up question", "action": "<hold time=\"12s\" />", "fixed_message": true },
    { "id": 3, "type": "standard", "condition": "The agent asks if the caller is still there", "action": "Yes, sorry, I'm here.", "fixed_message": false }
  ]
}
```

> **Use `<hold>`, not `<silence>`.** `<silence>` produces a brief audio artifact at its end boundary that triggers STT voice-activity detection and resets the idle timer. `<hold>` plays audio (hold music) that doesn't trigger VAD.

**Full Idle Escalation — hold = `threshold × escalation_count + 5s` buffer:**

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "standard", "condition": "The agent greets the caller", "action": "<hold time=\"40s\" />", "fixed_message": true }
  ]
}
```

**DTMF Multi-digit — always combine with spoken text:**

```json
{
  "role": "caller",
  "conditions": [
    { "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false },
    { "id": 1, "type": "standard", "condition": "The agent asks for input or greets the caller", "action": "<dtmf digits=\"12345#\" /> I've entered my account number.", "fixed_message": true },
    { "id": 2, "type": "standard", "condition": "The agent acknowledges the input or proceeds", "action": "That's all, goodbye.", "fixed_message": false }
  ]
}
```

> Pure `<dtmf>` with no spoken text does not register as a completed testing-agent turn. The condition chain never advances. Always add spoken text after the DTMF tag.

### Metrics — attach to every scenario

| Metric | Why required |
|--------|-------------|
| Expected Outcome | Was the infra behavior visible in the transcript? |
| Infrastructure Issues | Silent periods, dropped audio, agent non-response |
| Tool Call Success | Tool invocations completed without error |
| Latency | Per-turn response time |

**Critical:** Expected Outcome prompts must describe only transcript-observable behavior. Never reference internal processor names (`LLMRetryProcessor`, `UserIdleHandler`, etc.) — evaluators cannot observe code internals, only what appears in the call transcript.

---

## Phase 5 — Local Bot Orchestration

### Discover how to start the bot locally

From Phase 1, you should know:
- The start command (e.g., `python bot.py`, `uvicorn main:app`, `node index.js`)
- Any required env vars (`LOCAL_RUN=1`, `DEV_MODE=true`, etc.)
- How to inject the Cekura SIP URI so the bot dials the right number

### The CI Override Pattern

The run script needs to tell the bot which SIP URI to dial (Cekura assigns a different number per run). Two common approaches:

**A) JSON override file** — bot reads a file at startup:
```python
ci_override_path = Path(__file__).parent / ".ci_test_config.json"
if ci_override_path.exists():
    overrides = json.load(open(ci_override_path))
    config["sip_uri"] = overrides.get("sip_uri", config["sip_uri"])
```

**B) Environment variable** — bot reads `SIP_URI` from env:
```bash
SIP_URI="sip:+13682101298@cekura-pipecat-local.sip.twilio.com" python bot.py
```

Choose the approach that fits how the bot already reads config. If there's no override mechanism, add the simplest one.

**Do NOT override nested config dicts wholesale.** Python's `dict.update()` replaces entire nested structures — overriding `configuration` wipes `configuration.model.provider` and the bot defaults to the wrong LLM. Override only specific leaf fields.

### Run script outline

```python
for scenario in SCENARIOS:
    # 1. Trigger Cekura run — get testing agent's outbound number
    result = POST /test_framework/v1/scenarios/run_scenarios/ {
        "agent_id": AGENT_ID,
        "scenarios": [scenario["id"]],
        "frequency": 1,
        "agent_number": BOT_INBOUND_NUMBER,
        "concurrency_limit": 1
    }
    run_id = result["result_id"]
    sip_uri = f"sip:{result['runs'][0]['number']}@{SIP_DOMAIN}?X-CallerId={BOT_NUMBER}"

    # 2. Inject SIP URI (use method A or B from above)
    inject_sip_uri(sip_uri)

    # 3. Start bot locally
    proc = subprocess.Popen(["python", "bot.py"], env={**os.environ, "LOCAL_RUN": "1"})
    await asyncio.sleep(20)  # wait for transport setup + outbound dial

    # 4. Poll until completion or timeout
    deadline = time.time() + scenario["timeout_s"]
    while time.time() < deadline:
        run = GET /test_framework/v1/runs/{run_id}/
        if run["status"] == "completed":
            break
        await asyncio.sleep(10)

    # 5. Record result
    passed = run.get("evaluation_status") == "success"

    # 6. Cleanup
    proc.terminate()
    remove_sip_uri_injection()
```

---

## What Cannot Be Tested

Exclude these from CI suites — they cannot be triggered or observed reliably via Cekura:

| Scenario | Why untestable |
|---|---|
| Call-start silence timeout | `<hold>` and `<silence>` both produce audio artifacts at their boundaries that trigger STT VAD, resetting the timer before it fires |
| Internal processor state | Evaluators see only the call transcript — not whether `LLMRetryProcessor` ran, not error counts, not internal flags |
| STT confidence / word-level timing | Not visible in transcripts |
| Exact LLM token counts or latency internals | Latency metric measures end-to-end turn time, not internal steps |

---

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| `firstMessage` overlap | Both bot and testing agent speak simultaneously; STT gets confused | Set `FIRST_MESSAGE action: ""` to make testing agent wait |
| `action_followup` on condition 0 fires twice | Bot greeting splits across two STT chunks; followup fires once per chunk | Use `standard` condition to match full greeting before starting followup chain |
| Using `<silence>` for idle timer tests | Audio artifact at tag end triggers VAD, resets idle timer | Use `<hold>` instead |
| Keyword-style conditions | Chain fails to advance; testing agent loops on same condition | Write natural-language descriptions of bot behavior |
| Expected outcomes reference internal code | Metric fires "failure" even when infra works correctly | Only describe what appears in the call transcript |
| Pure `<dtmf>` with no voice | Chain freezes at DTMF step | Add spoken text after `<dtmf>` tag |
| Overriding nested config dicts wholesale | Bot defaults to wrong LLM/STT provider | Override only specific fields; avoid `dict.update()` on nested dicts |
| Timeout too short | Scenario times out before Cekura completes evaluation | Add 60–90s buffer beyond the expected call duration |
| Starting bot before Cekura run is ready | Bot dials before testing agent is listening | Wait for `runs[0].number` in the API response before starting bot |

---

## Documentation

- Cekura docs: https://docs.cekura.ai
- Conditional actions: https://docs.cekura.ai/documentation/key-concepts/evaluators/conditional-actions
- Pre-defined metrics: https://docs.cekura.ai/documentation/key-concepts/metrics/pre-defined-metrics
- Run scenarios API: https://docs.cekura.ai/api-reference/scenarios/run-scenarios

## Next Steps

- To design behavioral (non-infra) test coverage → **cekura-eval-design**
- To add or tune evaluation metrics → **cekura-metric-design**
- To debug a failing production call → **cekura-fixing-prod-issues**
