# Phase 2 — Describe Each Workflow

Take the Q1–Q9 answers from Phase 1 and write a precise, test-focused description of every discovered capability. The goal is not to summarize what the code does — it is to document what a test can actually control, trigger, and observe for each workflow, and what is off-limits.

Write the output to a temp file at `/tmp/infra-workflow-descriptions.md`. Phase 3 reads from this file before designing any scenarios.

---

## How to write each description

For every capability found in Phase 1, answer these four questions:

**What exactly happens?**
Describe the behavior concretely. Not "handles idle" — instead: "After 8 seconds of caller silence mid-call, the bot asks 'Are you still there?' Up to 3 times. On the fourth timeout it hangs up."

**Under what conditions is it triggered?**
State the exact conditions. What must be true before this behavior fires? What prevents it from firing? If a capability only activates in a specific call state (e.g. only mid-call, not at call start), say so explicitly.

**What can the test control?**
List what the test can inject: silence duration, digit sequences, background noise, interruption timing. Be specific. "The test can hold silence for any duration using `<hold>`" is more useful than "the test can simulate silence."

**What is observable in the transcript?**
List only what actually appears in the call transcript — bot speech, caller speech, DTMF acknowledgements. Name anything that is NOT observable (internal retries, provider switches, flag states) and mark it excluded from test verification.

---

## Workflows to describe

Work through each Q answer in order. Skip a section entirely if Phase 1 found nothing for that capability.

### Q1 — Call Connection

Describe:
- The full connection sequence from the moment a call starts to when the bot is ready to speak
- Who initiates (bot or caller) and what the call destination looks like (phone number, SIP URI, WebSocket URL, room token)
- Whether the destination is static or dynamic — if dynamic, how it's injected and when the bot reads it
- Conditions that would cause the connection to fail (wrong credentials, unreachable endpoint, transport mismatch)
- What is observable: typically nothing in the transcript; connection setup happens before audio begins

### Q2 — Speech-to-Text (STT)

Describe:
- What the bot hears vs. what it transcribes — latency, minimum utterance length, confidence thresholds if found
- What triggers a new transcription segment (VAD: end-of-speech detection, or turn-taking logic)
- Under what conditions a transcription might be empty, garbled, or delayed
- What the test can control: speaking rate (via personality), accent (via personality), noise level (via `<background_noise>`)
- What is observable: the transcribed text that appears as caller turns in the transcript; NOT the raw audio or VAD events

### Q3 — Language Model (LLM)

Describe:
- The request/response cycle: what goes in (system prompt, history, tools) and what comes out (response text, tool calls)
- Retry behavior if found: how many retries, what delay, what triggers a retry (timeout? error code? empty response?)
- Timeout enforcement if found: the exact deadline, and what the bot does when it's exceeded (fallback phrase, hang-up, silent failure)
- Validation if found: what makes a response invalid, and what happens — is the bad response discarded? Replaced with a fallback?
- What the test can control: the conversation content that reaches the LLM (via bot speech and caller responses); NOT the model's internals
- What is observable: the bot's spoken response in the transcript; NOT retry attempts, error codes, or internal state

### Q4 — Text-to-Speech (TTS) and Interruption

Describe:
- The synthesis and playback pipeline: when audio starts playing relative to when the LLM finishes
- Interruption behavior if supported: the exact trigger (VAD detects caller speaking over bot), what gets cancelled (audio stream, pending synthesis, or both), and what the pipeline state looks like after the interrupt
- Whether partial bot utterances appear in the transcript (truncated mid-sentence) or are suppressed entirely
- Whether two back-to-back interruptions leave the pipeline in a valid state or produce degraded behavior
- What the test can control: when to interrupt (via `<interruption time="Xs" />`) and whether to interrupt multiple times
- What is observable: bot utterances that were completed, truncated utterances if the platform surfaces them, the bot's response after recovering from interruption; NOT audio stream internals

### Q5 — Caller Silence / Idle Timer

Describe:
- The exact trigger: how long of caller silence (in seconds) fires the idle timer; whether it fires from call start, mid-call, or both
- The escalation sequence if present: prompt 1 at T seconds, prompt 2 at 2T seconds, hang-up at 3T seconds — use the actual values found
- What the bot says at each escalation step (the exact phrases if findable, or the pattern if not)
- Whether background noise can falsely reset the timer (VAD artifact risk — this determines whether `<hold>` or `<silence>` must be used)
- Conditions that prevent the timer from firing: does any bot speech reset it? Does caller speech cancel all pending escalations?
- What the test can control: caller silence duration using `<hold>` (not `<silence>` — see Rule in Phase 4)
- What is observable: the bot's idle prompts in the transcript; the hang-up event; NOT the timer's internal tick

### Q6 — Side Channels

For each side channel found, write a separate sub-description:

**DTMF received (caller → bot)**
- How digits are captured: one at a time or buffered into a sequence
- The terminator character if any (e.g. `#`), or the timeout after which an incomplete sequence is flushed
- What the bot does with the digits once received: routes the call, passes to LLM, triggers a tool, logs the input
- Under what conditions DTMF is accepted vs. ignored: during bot speech? During hold? Only at specific IVR menu points?
- What the test can control: digit sequences via `<dtmf digits="XXXXX#" />` combined with spoken text (pure `<dtmf>` without speech does not advance the condition chain)
- What is observable: bot acknowledgement of the DTMF input in the transcript; NOT the raw digit buffer contents

**DTMF sent (bot → external system)**
- What triggers the bot to send digits outbound: a user request, a tool call, reaching a specific call state
- What digit sequence is sent and to what destination
- What the test can control: driving the conversation to the trigger point via spoken conditions
- What is observable: bot's verbal confirmation that it sent digits, or a tool call result if the platform surfaces it in the transcript

**SMS received**
- What triggers inbound SMS handling: a specific message content, any SMS during the call, or only at certain call stages
- What the bot does in response: reads it aloud, acknowledges it, passes content to LLM context
- What the test can control: sending an SMS mid-call via `<send_sms text="..." />`
- What is observable: bot's verbal response to the SMS content

**SMS sent**
- What triggers the bot to send an SMS: caller request, task completion, specific phrase
- What the test can control: driving the conversation to the send trigger
- What is observable: bot verbally confirming the SMS was sent

**Voicemail detection**
- What signal indicates the call reached voicemail (silence pattern, beep detection, vendor webhook)
- What the bot does: leaves a message, hangs up immediately, retries the call
- What the test can control: `<voicemail />` tag simulates a voicemail greeting
- What is observable: whether the bot responded to the voicemail or hung up

**Any other side channels found** — follow the same pattern: trigger, bot action, test control, observable outcome.

### Q7 — Other Behaviors

For each additional behavior found:

**Call transfer**
- What triggers a transfer: caller request, task completion, escalation threshold
- What the transfer looks like in the call flow (warm handoff vs. blind transfer)
- What the test can control: driving the conversation to the transfer trigger
- What is observable: bot's verbal announcement of the transfer; the call ending (TOOL_END_CALL_ON_TRANSFER)

**Bot-initiated hang-up**
- What conditions cause the bot to end the call on its own (task complete, idle timeout exceeded, error state)
- Whether this is explicit in the transcript (bot says goodbye) or silent
- What the test can control: driving to the hang-up trigger condition
- What is observable: bot's closing phrase and the call end event

**Network degradation (if simulation supported)**
- What parameters can be set: latency (ms), packet loss (%), jitter
- How this affects STT, LLM latency, and TTS delivery
- What the test can control: `<network_simulation latency="Xms" packet_loss="Y%" />`
- What is observable: degraded transcript quality, increased response delays; NOT raw network metrics

**Any other behaviors found** — same pattern.

### Q8 — Bot Speaks First

Describe:
- The exact opening message content (copy from code if possible)
- Whether it is synthesized fresh each call or pre-recorded
- Whether the caller is expected to be silent during the greeting or may speak over it
- The implication for test design: if the bot speaks first, condition 0 must use `action: ""` — otherwise both sides fire simultaneously and STT enters a confused state

### Q9 — Local Run

Describe:
- The full startup sequence: command, required env vars, config file locations
- How the bot signals readiness (log line, health endpoint, timeout)
- How the call destination is injected: env var name, config key, CLI arg — whichever applies
- Whether a previous CI script exists and what it covers vs. what's missing
- Known fragile steps: anything that has broken before, requires a specific order, or depends on external services being up

---

## Phase 2 Output

Write all descriptions to `/tmp/infra-workflow-descriptions.md` using this structure:

```markdown
# Infrastructure Workflow Descriptions

Generated by Phase 2 of cekura-infra-test-suite.
Read by Phase 3 before designing test scenarios.

---

## [Workflow Name] (Q[N])

**What exactly happens:**
[concrete description]

**Trigger conditions:**
[what must be true; what prevents it]

**What the test can control:**
[specific tags, values, or conversation inputs]

**Observable in transcript:**
[what appears; what does NOT appear and must not be used in verification]

---
```

Repeat the block for every workflow found. Omit any workflow where Phase 1 found nothing.

At the end of the file, add:

```markdown
## Explicitly Excluded

The following were found but cannot be reliably tested via Cekura:
- [e.g. LLM retry count — internal state, not transcript-visible]
- [e.g. provider fallback activation — requires forcing a provider failure, not reproducible]
```

---

## Phase 2 Gate

`/tmp/infra-workflow-descriptions.md` exists and covers every capability Phase 1 found.

Move to [Phase 3](phase3-map.md).
