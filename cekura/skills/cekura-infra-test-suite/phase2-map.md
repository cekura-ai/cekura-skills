# Phase 2 — Map Answers to Tests and Confirm

Take the Q1–Q9 answers from Phase 1 and decide which scenarios to build. Then confirm the plan with the user before creating anything.

---

## 2a. Map each Q answer to a test

Work through the answers in order. For each answer, add the corresponding scenario if the capability was found — skip it if it wasn't.

| Phase 1 answer | → Test scenario | Cekura trigger |
|---|---|---|
| Q2 + Q3 + Q4 all answered (always true) | **Full Pipeline E2E** | Multi-turn conditional_actions conversation |
| Q2: STT accuracy matters (noise, accents, challenging input) | **STT Stress Test** | `<background_noise>` or non-native accent personality; scored via **Transcription Accuracy** metric |
| Q4: interruption supported — caller can cut off bot mid-speech | **Mid-Speech Interruption** | `<interruption time="1s" />` at start of action |
| Q4: same as above (run a second scenario) | **Repeated Barge-ins** | Two back-to-back `<interruption>` cycles |
| Q5: bot detects silence at call start and hangs up if caller never speaks | **Call-Start Silence Timeout** | Testing agent stays silent for entire call — `FIRST_MESSAGE action: ""` with no further conditions |
| Q5: idle detection mid-call — bot prompts on silence | **Mid-Call Idle** | `<hold>` for threshold + 2s mid-conversation |
| Q5: idle escalates — bot prompts N times then hangs up | **Full Idle Escalation to Hang-up** | `<hold>` for (threshold × N) + 5s |
| Q6: DTMF received — caller sends digits to bot | **DTMF Input Processing** | `<dtmf digits="XXXXX#" />` + spoken text |
| Q6: DTMF sent — bot dials digits to external system | **DTMF Output to IVR** | Trigger the IVR navigation flow; verify bot sends correct sequence |
| Q6: SMS sent — bot sends SMS to caller | **Outbound SMS** | Drive conversation to SMS trigger point; verify bot confirms sending |
| Q6: voicemail detection — bot handles reaching voicemail | **Voicemail Handling** | `<voicemail />` — Cekura plays a voicemail greeting |
| Q7: network degradation simulation supported | **Network Degradation** | `<network_simulation latency="300ms" packet_loss="15%" />` |
| Q7: call transfer supported | **Transfer to Human / IVR** | Trigger transfer phrase; use `TOOL_END_CALL_ON_TRANSFER` |

**Full Pipeline E2E is always included** — it is the baseline every other scenario assumes is passing.

**Add a scenario only if Phase 1 confirmed the capability exists.** If Q5 found no idle timer, there is no idle test. If Q6 found no DTMF, there is no DTMF test.

---

## 2b. What cannot be tested — exclude unconditionally

Remove these from the suite regardless of what Phase 1 found:

| Scenario | Why |
|---|---|
| Internal pipeline state | Evaluators see only the call transcript — retry attempts, error flags, validation outcomes, and internal state changes are invisible |
| Provider fallback activation | Forcing a primary provider to fail from the test side is not reliably reproducible via Cekura tags |
| SMS received mid-call | Cekura has no mechanism to inject an inbound SMS into an active call session |

---

## 2c. Confirm with the user

Present the proposed suite before creating anything. Mirror the Phase 1 gate output exactly so the user can verify nothing was lost or misread:

```
DISCOVERY SUMMARY (from Phase 1):
  Q1 — Call connection:   [your answer]
  Q2 — STT:               [your answer]
  Q3 — LLM:               [your answer]
  Q4 — TTS:               [your answer]
  Q5 — Caller silence:    [your answer]
  Q6 — Side channels:     [your answer]
  Q7 — Other behaviors:   [your answer]
  Q8 — Bot speaks first:  [your answer]
  Q9 — Local run:         [your answer]

PROPOSED TEST SUITE ({N} scenarios):
  S1 — Full Pipeline E2E               (always — Q2 + Q3 + Q4 present)
  S2 — Mid-Speech Interruption         (Q4: interruption supported)
  S3 — Repeated Barge-ins              (Q4: interruption supported)
  S4 — Mid-Call Idle                   (Q5: idle threshold = {X}s)
  S5 — Full Idle Escalation            (Q5: {X}s × {N} prompts then hang-up)
  S6 — DTMF Input Processing           (Q6: DTMF received, terminator = {X})
  ... (add/remove based on what Phase 1 actually found)

OPEN QUESTIONS:
  - [Gaps from Phase 1 that need the user's input before proceeding]

Proceed with this suite, or should I adjust?
```

**Do not move to Phase 3 until the user explicitly confirms.** If they adjust scope, revise the mapping and re-present.

---

## Phase 2 Gate

User has confirmed. You now know:
- The exact scenario list
- The timing values needed (idle threshold, escalation count, DTMF terminator)
- Whether the bot speaks first (determines FIRST_MESSAGE handling in Phase 3)

Move to [Phase 3](phase3-create.md).
