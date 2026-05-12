# Phase 2 — Map Components to Tests and Confirm

Turn the Phase 1 inventory into a proposed test suite, then get user confirmation before building anything.

---

## 2a. Apply the mapping table

For each component found in Phase 1, look up the corresponding test. **Only include tests for components that actually exist in the codebase.**

| Discovered component | Test scenario | Cekura trigger mechanism |
|---|---|---|
| STT + LLM + TTS (always present) | **Full Pipeline E2E** | Multi-turn conditional_actions conversation |
| Interruption handler (`BotInterruptionProcessor`, `interruptionLevel`, etc.) | **Mid-Speech Interruption** | `<interruption time="1s" />` at start of action |
| Interruption handler (same component, second scenario) | **Repeated Barge-ins** | Two back-to-back `<interruption>` cycles |
| Idle timer (`UserIdleHandler`, `idleTimeoutSeconds`, etc.) | **Mid-Call Idle** | `<hold time="{threshold+2}s" />` mid-conversation |
| Idle escalation (`idleMessageMaxSpokenCount` > 1) | **Full Idle Escalation to Hang-up** | `<hold time="{threshold × count + 5}s" />` |
| DTMF received (caller sends digits to bot) | **DTMF Input Processing** | `<dtmf digits="XXXXX#" />` + spoken confirmation |
| DTMF sent (bot sends digits to external IVR) | **DTMF Output to IVR** | Trigger the flow that causes the bot to dial digits; verify the correct sequence was sent |
| SMS sent by bot | **Outbound SMS** | Drive conversation to the point that triggers an SMS; verify the bot confirms sending |
| Voicemail detection | **Voicemail Handling** | `<voicemail />` tag — Cekura plays a voicemail greeting; verify bot leaves a message or hangs up correctly |
| Network simulation (`NetworkImpairmentProcessor`) | **Network Degradation** | `<network_simulation latency="300ms" packet_loss="15%" />` |
| Call transfer (`TransferHandler`, `callHoldFunctionEnabled`) | **Transfer to Human** | Trigger transfer phrase; use `TOOL_END_CALL_ON_TRANSFER` |

**Full Pipeline E2E is always included** — it is the baseline that every other scenario assumes is passing.

**Never add a scenario for a component that isn't in the codebase.** No DTMF processor → no DTMF test. No idle timer → no idle test.

---

## 2b. What cannot be tested — exclude these

Some behaviors cannot be reliably triggered or observed via Cekura evaluators. Remove them from the suite regardless of whether the component exists:

| Scenario | Why excluded |
|---|---|
| Call-start silence timeout | `<hold>` and `<silence>` both produce audio artifacts at their boundaries that trigger STT VAD, resetting the timer before it fires |
| Internal processor / pipeline state | Evaluators see only the transcript — retry counts, error flags, internal state changes are invisible |
| STT confidence scores or word-level timing | Not visible in transcripts |
| Provider fallback activation | Triggering a primary provider failure from the test side is not reliably reproducible via Cekura tags |
| SMS received mid-call | Cekura has no mechanism to inject an inbound SMS into an active call session |
| Call recording state | Whether a recording started or its quality cannot be observed from a call transcript |

---

## 2c. Confirm with the user

Present the checkpoint before creating anything on Cekura. Use this format:

```
INFRA DISCOVERED:
  Transport:          [type]
  STT:                [provider] + VAD: [yes/no] + Fallback: [yes/no]
  LLM:                [provider] + Retry: [yes/no] + Timeout: [yes/no] + Fallback: [yes/no]
  TTS:                [provider] + Interruption: [yes/no] + Fallback: [yes/no]
  Idle timer:         [{N}s timeout, {M} prompts before hang-up] — OR — [not found]
  DTMF:               [found — terminator: {#}] — OR — [not found]
  Network simulation: [found] — OR — [not found]
  Transfer:           [found] — OR — [not found]
  Bot speaks first:   [yes / no]

PROPOSED TEST SUITE ({N} scenarios):
  S1 — Full Pipeline E2E               (always)
  S2 — Mid-Speech Interruption         (interruption handler found)
  S3 — Repeated Barge-ins              (interruption handler found)
  S4 — Mid-Call Idle                   (idle timer: {N}s)
  S5 — Full Idle Escalation            (idle timer: {N}s × {M} prompts)
  S6 — DTMF Multi-digit Processing     (DTMF found, terminator: #)
  ...

OPEN QUESTIONS:
  - [Anything you couldn't determine from the code — ask here]

Proceed with this suite, or should I adjust the scope?
```

**Do not move to Phase 3 until the user explicitly confirms.** If the user adjusts scope, revise the mapping and re-present.

---

## Phase 2 Gate

User has confirmed the scenario list. You now know:
- Exactly which scenarios to create
- The configured values needed (idle timeout seconds, escalation count, DTMF terminator)
- Whether the bot speaks first

Move to [Phase 3](phase3-create.md).
