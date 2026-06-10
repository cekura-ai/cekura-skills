# Phase 3 — Inventory What to Test

> **ANNOUNCE FIRST:** Before reading any file or taking any action, output this exact line to the user:
> `**Phase 3 — Inventory What to Test: starting**`

Read `/tmp/infra-workflow-descriptions.md` (written by Phase 2) before doing anything else. That file is the authoritative source — every test item in this phase must be grounded in what Phase 2 actually documented. Do not add test items for behaviors that Phase 2 did not find.

---

## Goal

Produce an exhaustive list of every testable case. For a non-trivial voice agent this list should be at least 200 items — often 500–1000+. If your total is below 200, you have collapsed categories into single items and must go back and expand. Phase 4 then compresses this list into a compact set of evaluators.

Write the list to `/tmp/infra-test-list.md`. Phase 4 reads this file and groups items into evaluators using arc patterns.

---

## How to enumerate — mandatory rules

These rules apply before you write a single TEST-NNN item. Breaking any of them produces an under-counted list.

### Rule 1 — One item per instance, not one item per category

"Test all STT parameters" is a category, not a test item. For every list Phase 2 documented — STT parameters, LLM tools, TTS voices, idle escalation steps, DTMF call states, supported languages, configured error codes, fallback paths — generate **one TEST-NNN item per list entry**.

Example: Phase 2 documents 8 non-default STT parameters (`endpointing_ms`, `confidence_cutoff`, `diarization`, `smart_formatting`, `profanity_filter`, `keywords`, `utterance_end_ms`, `encoding`) → 8 separate TEST-NNN items, one per parameter.

### Rule 2 — Three items per numeric threshold

Every numeric value Phase 2 documented (silence timeout, word count gate, retry count, idle threshold, speech timeout, buffer flush timeout, confidence cutoff, minimum speech duration, maximum turn duration, etc.) generates **exactly three TEST-NNN items**:
- `[Component]-[Param]-BelowThreshold` — value is just below threshold; expected behavior X
- `[Component]-[Param]-AtThreshold` — value is exactly at threshold; expected behavior Y
- `[Component]-[Param]-AboveThreshold` — value is just above threshold; expected behavior Z

Example: Phase 2 documents `IDLE_TIMEOUT=8s` → TEST-NNN: idle fires at exactly 8s; TEST-NNN: caller speaks at 7.9s (no idle); TEST-NNN: caller speaks at 8.1s (idle fires).

### Rule 3 — Estimate before you write

Before writing any TEST-NNN items, open `/tmp/infra-workflow-descriptions.md` and count:
- Number of non-default parameters across all components: P
- Number of numeric thresholds × 3: T
- Number of configured tools: L
- Number of supported languages: G
- Number of escalation/state stages: S
- Number of adjacent component pairs: I

Expected minimum item count = P + T + L + G×2 + S + I + happy paths + error paths

Write this estimate at the top of the output file. If your final count is less than 80% of the estimate, you collapsed something — go back and expand.

### Rule 4 — Iterate through Phase 2 after drafting

After writing items for every component section, re-read `/tmp/infra-workflow-descriptions.md` from start to finish. For every documented value, parameter, behavior, or code path that does not yet have a corresponding TEST-NNN item, add one. Do not stop until no uncovered items remain.

### Rule 5 — Exhaustive cross-component pairs, not 6 examples

For every pair of adjacent components in the pipeline (STT→VAD, VAD→LLM, LLM→TTS, TTS→Interruption, Interruption→VAD, Idle→LLM, DTMF→VAD, SMS→LLM, Voicemail→TTS, STT-fallback→turn-detection, etc.), generate at least one interaction test item. Do not sample — cover all pairs.

---

## What "not testable" means — narrow definition

Before generating any items, read this definition. It is the only valid reason to exclude a test item.

**A test item is NOT testable if and only if: the call transcript is byte-for-byte identical regardless of whether the behavior fired correctly or incorrectly.** The bot's audio and speech output are exactly the same either way.

**Genuinely not testable (narrow list):**
- An internal retry counter incremented (no speech or behavior change)
- A memory flag was set to `true` (no observable side effect)
- A log line was written (log does not appear in the transcript)
- A metric was emitted internally (no call-visible effect)

**NOT a valid reason to exclude:**
- **"Sub-second timing"** — if the difference crosses a threshold boundary, behavior differs (prompt fires vs. doesn't fire). That difference IS in the transcript. Use comfortable margins: BelowThreshold = threshold−2s (behavior clearly should NOT fire), AboveThreshold = threshold+2s (behavior clearly SHOULD fire). You do not need millisecond precision.
- **"Internal state"** — if the internal state change produces ANY observable output (bot speaks, bot pauses, bot hangs up, call ends), it is testable.
- **"Nothing happened"** — absence of behavior IS observable. "No idle prompt appeared" is a transcript fact. "Bot did not hang up" is observable. "Interruption did not fire" is observable (bot speech was not truncated). If you can check the transcript and confirm something was absent, it is testable.
- **"Hard to time precisely"** — boundary tests check whether behavior fires at all, not the exact millisecond. A 6s hold with an 8s threshold reliably produces no idle prompt; a 10s hold reliably does produce one. Both are deterministic.
- **"Not directly visible"** — if the behavior is visible through its downstream effect on the bot's speech or action, it is testable.

**Worked example — absence of behavior is testable:**
- `Idle-BelowThreshold`: hold 6s (threshold=8s) → transcript shows NO idle prompt → verifiable pass/fail
- `Idle-AtThreshold`: hold 9s (threshold=8s) → transcript shows idle prompt → verifiable pass/fail
- Both are transcript-verifiable. Neither requires sub-second precision.

**Worked example — what NOT to exclude:**
- "VAD suppressed during TTS" → observable: no spurious user turn opened during bot speech
- "STT confidence below threshold" → observable: bot processed or discarded the transcript (behavior differs)
- "Retry count reached" → observable: bot speaks a fallback phrase or hangs up after last retry

**The only truly unobservable case:** BOTH the pass case and the fail case produce exactly the same transcript — same words, same call outcome, same sequence. If you can describe how a passing transcript differs from a failing transcript, it is observable.

**When in doubt, include the test item.** Phase 4 will decide whether it can be grouped or is genuinely unreachable. Do not make that decision here.

---

## How to enumerate

**Before generating items for any component:** any behavior that produces a different observable output (different bot speech, different bot action, different call outcome) under different conditions is testable. Do not exclude it.

For every stack component documented in Phase 2, work through these categories in order. Apply the mandatory rules above to each category to generate individual items.

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
- Session metadata propagated correctly into bot context — each field from Phase 2 Q1 that feeds into the system prompt or LLM context gets its own test
- Call context variation: if Phase 2 documents different bot behavior for inbound vs. outbound, or based on time-of-day, caller ID, or campaign — one test per documented variation
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
- Turn-start gate: audio arriving before gate is satisfied is buffered vs. discarded — verify per documented behavior
- Signal arbitration: when standalone VAD and STT provider endpointing both fire simultaneously, the documented winner takes effect (one test per arbitration rule found in Phase 2 Q3)
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
- Each tool defined in Phase 2 gets at least one test for its trigger condition — but see "Agent Workflow Tests" below for the full per-tool test matrix
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

**Multiple mechanisms per side channel — Rule 1 applies.** Phase 2 Q8 may have found multiple independent code paths for the same behavior (e.g., SMS can be sent via a tool call AND via a webhook handler AND via a direct SDK call). Each mechanism is a separate test item. If Phase 2 documented 3 ways to send SMS, generate 3 separate test items — one per mechanism. Do not collapse them into "SMS sent works."

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

**Multiple trigger paths per behavior — Rule 1 applies.** Phase 2 Q9 may have found multiple independent code paths that trigger the same behavior (e.g., hang-up can be triggered by: idle timeout, LLM tool call, max duration timer, unrecoverable error). Each trigger path is a separate test item. If Phase 2 documented 4 hang-up triggers, generate 4 test items. Do not collapse them into "hang-up works."

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

**Every supported non-primary language must be tested as thoroughly as the primary language.** A behavior that works in the primary language but not in a secondary language is a bug. Apply Rule 1: for every test item in every other section, check whether Phase 2 Q11 documents language-specific behavior differences — if so, that test item generates one variant per language.

**Per-language infrastructure tests (one set per fully-configured non-primary language):**
- Full pipeline E2E: caller speaks end-to-end in that language, bot responds correctly
- STT accuracy: clear speech transcribed correctly in that language
- Idle timer: escalation prompts delivered in correct language with correct phrases
- Interruption: pipeline recovers correctly when caller interrupts in that language
- LLM response: bot responds in the correct language when caller speaks in it
- TTS: correct voice/model used for that language
- DTMF (if applicable): accepted and processed correctly during a call in that language
- Tool calls: tools invoked correctly when the trigger phrase is in that language

**Language determination tests:**
- Correct language selected per documented mechanism (locale metadata, speech detection, DTMF selection, fixed config) — one test per mechanism
- Wrong/ambiguous locale metadata: bot falls back per documented behavior

**Mid-call language switching tests (one per trigger type × language pair):**
- Each documented trigger (DTMF, speech detection, explicit caller request) × each language pair the bot supports
- Switch to unsupported language: bot falls back per documented behavior
- Components switch correctly: STT model, LLM prompt, AND TTS voice all switch (not just one)

**Language-specific behavior differences (if Phase 2 documented them):**
- Response style, formality, or behavior differs between language variants — one test per documented difference

### Full Pipeline End-to-End
- A complete call from connect → bot greeting → caller turn → LLM response → TTS playback → caller turn → task completion → hang-up runs without errors
- This is always the first scenario built; all other scenarios assume this baseline is passing

### Agent Workflow Tests

These tests come from the agent's actual business logic — the tools it calls, the conversation flows it implements, and the decisions it makes. They are derived from Phase 2 Q4 (LLM tool definitions, system prompt workflows) and are separate from the pipeline infrastructure tests above.

**For every LLM tool documented in Phase 2 Q4, generate all of the following test items (applying Rule 1 — one item per path):**
- **Happy path**: tool triggered by the documented caller input, returns valid result, bot uses result correctly in its response
- **Tool not triggered**: caller says something adjacent but should NOT trigger the tool; bot does not call it
- **Tool called with missing inputs**: caller provides incomplete information; bot asks for missing fields before calling the tool
- **Tool returns error**: tool call fails or returns an error code; bot responds with documented fallback
- **Tool returns not-found**: tool returns empty or no-match result; bot responds with documented not-found handling
- **Tool call timeout**: tool takes too long to respond; bot takes documented timeout action
- **Consecutive tool calls**: first tool result triggers a second tool call; pipeline serializes correctly and both results are used

**For every documented conversation flow branch in the system prompt:**
- The correct branch activates when the documented trigger condition is met
- Ambiguous caller input at a decision point: bot clarifies or defaults per documented behavior
- Caller goes off-script mid-flow: bot recovers and re-anchors to the flow per documented behavior
- Caller refuses to provide required information: bot handles the refusal per documented behavior

Apply Rule 1 throughout: each tool × each path = one test item. A bot with 5 tools × 7 paths = 35 tool workflow items before any branching or flow tests.

---

## Cross-component interaction tests

Apply **Rule 5**: generate a test item for every adjacent component pair — do not sample. List all pairs systematically, not just the most obvious ones.

For each pair, ask: "If component A is in state X when component B fires, does an unexpected or untested code path activate?" If yes, that is a test item.

Common pairs to check (not an exhaustive list — derive yours from the actual Phase 2 pipeline):

- **VAD fires while TTS is playing** — interrupt path activation vs. turn-start gate suppression
- **LLM timeout during interruption recovery** — second interrupt arrives while LLM still running
- **Idle timer fires while LLM is generating** — which cancels which
- **STT fallback fires during mid-turn** — does secondary provider transcript still close the turn correctly
- **No-transcript timer and idle timer both running** — which fires first; what does each do to the other
- **Back-to-back tool calls** — LLM serialization of consecutive tool results
- **DTMF received during bot speech** — accepted or gated
- **SMS received during idle escalation** — does it reset the timer or is it independent
- **Voicemail detection during TTS playback** — does bot stop speaking and handle voicemail
- **STT endpointing and standalone VAD both active** — which signal wins the turn-end decision

For each pair found in Phase 2, generate a separate TEST-NNN item. Do not merge multiple pairs into one item.

---

## Phase 3 Output

Write the complete test list to `/tmp/infra-test-list.md` using this structure:

```markdown
# Infra Test List

Generated by Phase 3 of cekura-infra-test-suite.
Source: /tmp/infra-workflow-descriptions.md
Read by Phase 4 before creating any scenarios.

Expected item count estimate:
  Parameters (P): N  →  N items
  Thresholds × 3 (T): N × 3 = N items
  Tools (L): N items
  Languages × 2 (G): N items
  Escalation stages (S): N items
  Interaction pairs (I): N items
  Happy paths + error paths: N items
  TOTAL ESTIMATE: N items

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

**If total < 200 for a non-trivial agent: stop, flag as incomplete, and go back to expand.** A count below 200 means categories were collapsed into single items. Apply Rule 1 and Rule 2 again until every parameter and threshold has its own entries.

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

**Before writing this gate, count your actionable test items. The count determines what you write here — there is no user question that can override it.**

Write the following check output before anything else in this section:

```
PHASE 3 COUNT CHECK
Total TEST-NNN items generated: [X]
Not-testable items (excluded): [Y]
Actionable items: [X - Y]
Required minimum: 200
Status: PASS / FAIL
```

**If actionable items < 200 → Status = FAIL. Do NOT write "Move to Phase 4." Do NOT ask the user if you should proceed. Instead write:**

```
PHASE 3 INCOMPLETE — [X] actionable items, need [200 - X] more.

Returning to expand. Applying:
- Rule 1 to every component section (one item per instance, not per category)
- Rule 2 to every numeric threshold (3 items per threshold)
- Agent Workflow Tests section (7 paths per tool × N tools)
- Multi-language section (full test set per language)
- Reviewing all "not testable" classifications against the narrow definition
```

Then actually go back and expand — add the missing items to `/tmp/infra-test-list.md`, recount, and re-run this gate check.

**If actionable items ≥ 200 → Status = PASS. Then:**

1. Present the summary block.
2. Ask the user whether any items should be added, removed, or re-prioritized.
3. Wait for user confirmation before proceeding.

Move to [Phase 4 — Design the Test Plan](phase4-plan.md) **only after Status = PASS and user confirmation.**
