# Phase 3 — Inventory What to Test

Read `/tmp/infra-workflow-descriptions.md` (written by Phase 2) before doing anything else. That file is the authoritative source — every test item in this phase must be grounded in what Phase 2 actually documented. Do not add test items for behaviors that Phase 2 did not find.

---

## Goal

Produce an exhaustive list of everything the test suite must cover. This list can be 10 items or 1 000 items — there is no target count. The bar is completeness: every behavior, boundary condition, failure path, and cross-component interaction described in Phase 2 must appear as at least one test item.

Write the list to `/tmp/infra-test-list.md`. Phase 4 reads this file and creates one Cekura scenario per item (or groups closely related items into one scenario where it makes engineering sense).

---

## How to enumerate

For every stack component documented in Phase 2, work through these categories in order. Generate a separate test item for each distinct behavior you can identify.

**1. Happy path / normal operation**
The component behaves correctly under ideal conditions. This is always the first item for every component.

**2. Boundary conditions**
At the exact threshold value, just below it, and just above it. Any numeric parameter (timeout, word count, silence duration, retry count, max turns) has at least one boundary test. Use the actual values from Phase 2 — do not guess.

**3. Error and failure paths**
What happens when the component fails, times out, returns an empty result, or returns an invalid result. Every fallback path documented in Phase 2 needs a test.

**4. Recovery behavior**
After a failure, does the pipeline recover cleanly? Can a second call succeed after the first failed? Does the component leave residual state that affects the next operation?

**5. Cross-component interactions**
Where two components touch — e.g. VAD firing while TTS is playing, an LLM timeout during an interruption, a final transcript arriving during idle escalation — there is usually at least one interaction test. List every pair of adjacent components and decide whether an interaction test is warranted.

**6. Configuration-specific behavior**
If Phase 2 found multiple configured values (two STT models, two voices, a primary and fallback provider), each configuration variant may need its own test.

---

## Stack components to enumerate

Work through each component that Phase 2 documented. Skip any component Phase 2 found nothing for.

### Call Connection
- Normal inbound call establishes and bot reaches ready state
- Normal outbound call connects to correct destination
- Static vs. dynamic destination: destination injected correctly at call start
- Session metadata propagated correctly into bot context
- Connection failure: wrong credentials, unreachable endpoint, transport mismatch
- Mid-call transport drop: reconnect, hang-up, or silent drop per documented behavior
- Connection timeout: fires at correct threshold
- Required env var missing at startup: documented failure mode triggers

### Speech-to-Text (STT)
- Normal transcription of clear speech produces accurate text
- Streaming: interim transcripts arrive before final; bot acts on them per documented logic
- All configured non-default STT parameters applied (one test per meaningful parameter — confidence cutoff, endpointing timeout, language/locale, keyword boosting list)
- Post-processing applied correctly (one test per post-processing step — number normalization, disfluency removal, PII redaction, etc.)
- Transcript enrichment attached correctly (confidence score, speaker label, word timestamps — if configured)
- Empty transcript: bot takes the documented action (discard, push empty turn, start no-transcript timer)
- Below-confidence transcript: bot applies the documented threshold and acts accordingly
- STT provider timeout: fallback fires at correct deadline
- Fallback to secondary STT provider: triggers on the documented condition, secondary model used
- Retry cap reached: bot takes the documented terminal action
- STT muted during bot speech: no self-transcription; mute window opens and closes at correct points relative to TTS start/end
- STT provider built-in endpointing (if configured): fires at correct silence value; does not double-trigger with VAD layer
- Each additional non-default parameter found in Phase 2 that has a testable behavioral effect

### Turn Detection (VAD + Transcript Signals)
- Turn opens correctly on speech (standalone VAD if present)
- Turn opens correctly on STT provider speech_started event (if used)
- Turn-start gate: turn does not open until confirmation condition is met (e.g. ≥N words on interim transcript — use actual N from Phase 2)
- Turn-start gate: audio arriving before gate is satisfied is buffered or discarded per documented behavior
- Force-open timeout: turn opens even if gate was never satisfied (fires at correct deadline)
- Background noise below threshold: turn does not open falsely
- Turn ends correctly on standalone VAD silence (at exact configured threshold)
- Turn ends correctly on STT provider utterance_end or endpointing event (if used)
- Turn ends correctly on final transcript + VAD already silent (if that is the documented rule)
- Speech timeout: fires at correct value after VAD goes silent; resets correctly on new interim transcript
- VAD silent but no final transcript: no-transcript timer fires at correct duration; documented terminal action taken
- Final transcript arrives while VAD still active: held or immediately commits per documented rule
- Hard maximum turn duration: force-closes turn at correct value regardless of VAD state
- Signal arbitration: when two end signals are present, the first-to-fire wins (or documented arbitration applies)
- Interim transcript arriving after end timer is counting: timer resets per documented behavior
- DTMF tones: do not false-trigger VAD (if documented as safe)
- Bot audio: does not false-trigger VAD (echo cancellation or mute covers both standalone and STT built-in VAD)
- Rapid back-to-back turns: pipeline handles multiple consecutive end-of-turn events without queuing or state corruption

### Language Model (LLM)
- LLM fires at correct trigger event (turn-end signal, final transcript receipt, or other documented trigger)
- LLM does not fire on empty transcript (minimum-length gate, if present)
- LLM does not fire on below-threshold transcript (if a gate is configured)
- Mid-turn LLM trigger: fires on interim transcript threshold (if configured)
- Proactive/timeout-triggered LLM call: fires at correct deadline with correct context (if feature exists)
- All models and configurations: each configured model produces a valid response (one test per model if multiple are configured)
- System prompt template: all injected variables populated correctly at call start
- Conversation history: sliding window drops oldest turns at correct size; summarisation fires at correct N (per documented strategy)
- Tool call: correct tool invoked for a known trigger phrase; result fed back into conversation via documented mechanism
- Each tool defined in Phase 2 gets at least one test for its trigger condition
- LLM returns empty response: retry fires; fallback phrase used if retry cap reached
- LLM returns malformed response (if validation is documented): discard/retry/fallback per documented rule
- LLM timeout: fires at correct deadline; bot takes documented action (fallback phrase, hang-up, silent drop)
- Retry: correct count and delay observed; audible holding phrase plays (or bot stays silent) per documented behavior
- Retry cap reached: circuit-breaker or terminal action fires per documented rule
- Fallback provider/model: activates on correct trigger; uses same or stripped-down context per documented behavior
- Concurrent turns: second LLM request does not send a stale first response to TTS (cancellation or serialization per documented behavior)
- Streaming response: TTS synthesis begins at first chunk (if streaming is the documented mode)

### Text-to-Speech (TTS)
- Normal synthesis produces intelligible audio
- Each configured voice/model produces audio (one test per voice if multiple are configured)
- All non-default voice parameters applied (speed, stability, pitch, etc. — one test per meaningful parameter)
- Streaming synthesis: audio playback starts at first chunk at correct latency relative to LLM output
- Batch synthesis: audio starts only after full response is ready
- Synthesis error mid-utterance: bot stops speaking / plays silence / retries from failed chunk per documented behavior
- Fallback voice/provider: activates on documented trigger; produces audio
- Multi-voice selection: correct voice selected for each documented context (persona, escalation state, etc.)
- Pre-recorded audio: plays at correct trigger point; interleaved with synthesized speech if that is documented

### Interruption Handling
- Single interruption: bot audio stops, pipeline resets, bot processes caller speech cleanly
- Cancellation scope: in-progress audio chunk cancelled; all queued audio cancelled; pending synthesis requests cancelled — per documented scope
- In-flight LLM request: cancelled or allowed to complete per documented behavior
- Minimum interrupt duration: interrupts shorter than threshold are ignored; threshold-length interrupts are accepted (use actual value from Phase 2)
- Pipeline state after cancellation: LLM context contains truncated / full / no bot utterance per documented rule; new user turn opens immediately or after VAD end-of-turn per documented rule
- Partial utterance: appears in transcript or is suppressed per documented behavior
- Back-to-back interruptions: second interruption fires while bot is responding to first; pipeline does not degrade (no audio artifacts, no duplicate context)
- Interruption suppressed on specific utterances: bot continues speaking through an interrupt attempt on designated utterances (if feature exists)

### Caller Silence / Idle Timer
- Call-start silence: timer fires at correct call-start threshold (if separate from mid-call)
- Mid-call silence: timer fires at correct mid-call threshold
- First escalation prompt: fires at correct T₁ with correct phrase
- Each subsequent escalation: fires at correct Tₙ with correct phrase (one test per escalation step)
- Final escalation: hang-up / transfer / voicemail per documented terminal action at correct threshold
- Timer resets on caller speech: any finalized transcript (or the documented reset condition) cancels escalation and restarts
- Timer does not reset on background noise below VAD threshold
- Bot speech: does or does not reset timer per documented behavior
- DTMF input: resets or does not reset timer per documented behavior
- Concurrent timer: idle timer and call-duration timer both active; documented behavior when both fire
- Escalation cancelled mid-sequence: caller speaks between prompt 1 and prompt 2; subsequent prompts do not fire

### Side Channels

**DTMF received**
- Single digit captured and processed
- Sequence buffered correctly until terminator character (use actual terminator from Phase 2)
- Incomplete sequence flushed after timeout (use actual timeout value from Phase 2)
- Sequence routed to correct handler (IVR, LLM, tool call — per documented pipeline)
- DTMF accepted during bot speech (or correctly ignored — per documented state gate)
- DTMF accepted during hold (or correctly ignored — per documented state gate)
- DTMF only accepted at specific IVR menu points (if that is the documented behavior)

**DTMF sent**
- Correct digit sequence sent to correct destination on documented trigger
- Hardcoded vs. dynamic sequence: dynamic sequence generated correctly (if documented)

**SMS received** (if present)
- SMS content read aloud / appended to LLM context / both — per documented behavior
- SMS received mid-conversation: processed without disrupting current bot turn (or interrupting it per documented behavior)
- SMS matching specific content triggers correct action (if content-gated)

**SMS sent** (if present)
- SMS send triggered by documented condition
- Message content is fixed / templated / LLM-generated per documented behavior
- Bot receives delivery confirmation (or fire-and-forget per documented behavior)

**Voicemail detection** (if present)
- Detection signal fires correctly (AMD result, silence-then-beep, vendor webhook)
- Bot leaves message / hangs up / retries per documented action
- Message plays until documented end condition

**Pre-recorded audio** (if present)
- Plays at correct trigger; correct file loaded
- Interleaved correctly with synthesized speech if documented

**Any other side channels from Phase 2** — enumerate all testable behaviors using the same pattern.

### Other Behaviors

**Call transfer** (if present)
- Transfer triggered by correct condition (phrase, tool call, escalation)
- Blind transfer: bot drops immediately after initiating
- Warm transfer: bot stays on until destination answers
- Transfer destination selected correctly (static / dynamic)
- Bot announcement plays correct phrase before transferring
- Transfer target unreachable: fallback to documented alternative

**Bot-initiated hang-up** (if present)
- Hang-up fires on correct condition (task complete, error, max idle)
- Closing phrase spoken before disconnect (if documented)
- Grace period observed between closing phrase and actual disconnect (use actual value from Phase 2)

**Call recording** (if present)
- Recording starts at correct event
- Recording stops at correct event
- Consent gate applied if documented

**Network degradation simulation** (if present)
- Each configurable parameter (latency, packet loss, jitter) applied at documented range
- Effect on STT, LLM, TTS delivery matches documented expectation

**Background noise suppression** (if present)
- Suppression applied on documented noise profiles
- Always-on or conditional trigger correct per documented behavior

### Bot Speaks First
- Opening message content matches exactly what Phase 2 documented (template variables populated correctly)
- Opening message synthesized live vs. played from file per documented method
- Timing: delay from call connect to first audio matches documented value
- Interruptible opening: caller speech during greeting is processed or discarded per documented behavior
- Non-interruptible opening: caller speech during greeting is correctly suppressed

### Supported Languages

Generate test items only for languages Phase 2 confirmed are fully configured (STT model + TTS voice + system prompt all present). Skip partial/non-production language configs.

- Full pipeline E2E in each supported non-primary language (one test per language): caller speaks in that language end-to-end, bot responds in the same language
- STT accuracy in each supported language: clear speech in that language transcribed correctly
- Language determination: correct language selected per the documented mechanism (locale metadata, speech detection, DTMF selection, fixed config)
- Mid-call language switch (if supported): caller switches language mid-call; bot detects and switches STT model, LLM prompt, and TTS voice per documented behavior
- Mid-call switch to unsupported language (if switching is supported): bot falls back per documented behavior
- Language-specific system prompt: correct prompt/template used for each language variant (if prompts differ per language)
- Language-specific TTS voice: correct voice model used for each language (one test per language where voice differs)
- Language-specific STT model: correct model used for each language (one test per language where model differs)

### Full Pipeline End-to-End
- A complete call from connect → bot greeting → caller turn → LLM response → TTS playback → caller turn → task completion → hang-up runs without errors
- This is always the first scenario built; all other scenarios assume this baseline is passing

---

## Cross-component interaction tests

After enumerating per-component tests, go back and identify interactions between adjacent components that could produce failure modes not covered above. Common pairs to check:

- **VAD fires while TTS is playing**: does the interrupt path activate? Does the turn-start gate suppress it?
- **LLM timeout during interruption recovery**: what does the bot do when the LLM is still running when a second interrupt arrives?
- **Idle timer fires while LLM is generating**: does the LLM response cancel the escalation, or does the escalation cancel the LLM response?
- **STT fallback fires during mid-turn**: does the transcript produced by the secondary provider still close the turn correctly?
- **No-transcript timer and idle timer both running**: which fires first; what does each one do to the other?
- **Back-to-back tool calls**: LLM returns tool call, result comes back, LLM returns another tool call — does the pipeline serialize these correctly?

For each interaction pair found in Phase 2 descriptions, decide whether the interaction creates a distinct failure mode that justifies its own test item.

---

## Phase 3 Output

Write the complete test list to `/tmp/infra-test-list.md` using this structure:

```markdown
# Infra Test List

Generated by Phase 3 of cekura-infra-test-suite.
Source: /tmp/infra-workflow-descriptions.md
Read by Phase 4 before creating any scenarios.

---

## [Stack Component]

### [TEST-001] Short descriptive name

**What is being tested:** The specific behavior, condition, boundary, or failure path.
**Grounded in:** The Phase 2 finding that justifies this test (quote or cite the relevant value/rule).
**Priority:** Critical / High / Medium / Low
  - Critical: if this breaks, the call is completely non-functional
  - High: significant caller-facing degradation
  - Medium: edge case with real-world probability
  - Low: boundary or recovery scenario unlikely to be triggered in normal use

---

### [TEST-002] ...
```

Number tests sequentially across all components (TEST-001, TEST-002, ...). The total count at the end of the file is the authoritative number of things to test.

After all test items, add:

```markdown
## Summary

Total test items: N
By component:
  - Call Connection: N
  - STT: N
  - Turn Detection: N
  - LLM: N
  - TTS: N
  - Interruption: N
  - Idle Timer: N
  - Side Channels: N
  - Other Behaviors: N
  - Full Pipeline E2E: N
  - Cross-component interactions: N

Not testable (from Phase 2 "Explicitly Excluded"):
  - [item — reason]
```

---

## Phase 3 Gate

`/tmp/infra-test-list.md` exists, every capability Phase 2 documented has at least one test item, and every boundary condition with a numeric value from Phase 2 has a test at that value.

Confirm the list with the user before moving to Phase 4. Present the summary block and ask whether any items should be added, removed, or re-prioritized.

Move to [Phase 4 — Design the Test Plan](phase4-plan.md).
