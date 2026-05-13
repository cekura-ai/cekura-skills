# Phase 2 — Analyze Each Layer

Take the Q1–Q11 answers from Phase 1 and write a precise, technical description of every discovered capability. The goal is to document what the stack actually does — how each layer works, what configuration it runs under, and what conditions govern its behavior. Test design comes later (Phase 3). Here, just describe the stack.

Write the output to a temp file at `/tmp/infra-workflow-descriptions.md`. Phase 3 reads from this file before designing any scenarios.

---

## Standard of depth required

**Surface answers are not acceptable.** For every sub-question, go back to the source code and extract the actual answer. The bar is:

- **Exact values, not existence.** Do not write "a timeout is configured." Write "the LLM call timeout is 8 000 ms, set via `LLM_TIMEOUT_MS` in `config.py:34`, defaulting to 5 000 ms if the env var is unset." If you cannot find the value from code, write "value not found in code — must be checked at runtime" and note where you looked.
- **Class and function names, not categories.** Do not write "a custom turn strategy is used." Write "turn-start is gated by `MinimumWordsTranscriptionStrategy` in `bot/strategies.py:112`, which requires ≥3 words on an interim transcript before opening a turn."
- **Code paths, not feature flags.** Trace what actually executes at runtime. If a feature is conditionally compiled or gated by an env var, record the condition and both branches.
- **Every configured item in a list, not 'several'.** If there are four tools defined, list all four by name and purpose. If there are two STT providers, document both.
- **Gaps are named, not glossed over.** If a sub-question cannot be answered from the code (e.g. the value is only known at runtime, or it depends on a vendor default you cannot inspect), write exactly that: what you could not determine, what you looked for, and what would need to happen to find the answer.

Before writing the description for each Q section, re-read the relevant source files — do not rely solely on Phase 1 notes, which may have been high-level. The description must be grounded in what the code actually does, not what you inferred from file names or comments.

---

## How to write each description

For every capability found in Phase 1, answer these two questions:

**What exactly happens?**
Describe the behavior concretely, with actual values and code references. Not "handles idle" — instead: "After 8 s of caller silence mid-call (`IDLE_TIMEOUT=8` in `config.py:61`), `IdleTimerProcessor.on_silence` fires and the bot synthesises the phrase defined in `IDLE_PROMPT_1` ('Are you still there?'). This repeats up to 3 times (`MAX_IDLE_PROMPTS=3`). On the fourth timeout `IdleTimerProcessor._handle_max_retries` calls `end_call()`."

**Under what conditions is it triggered?**
State the exact conditions with code references. What must be true before this behavior fires? What prevents it from firing? If a capability only activates in a specific call state (e.g. only mid-call, not at call start), say so explicitly and cite where that guard lives in the code.

---

## Workflows to describe

Work through each Q answer in order. Skip a section entirely if Phase 1 found nothing for that capability.

### Q1 — Call Connection

**1. Transport and protocol**
- What transport layer handles the voice session (SIP, WebRTC, raw WebSocket, vendor SDK such as VAPI, Retell, LiveKit, Pipecat, Twilio, etc.)
- Whether the bot uses a managed platform that abstracts the transport, or connects directly at the protocol level
- The audio codec(s) negotiated or configured (PCMU, PCMA, Opus, etc.) and sample rate

**2. Session establishment sequence**
- Step-by-step: what happens from the moment a call arrives (inbound) or the bot dials (outbound) to the moment the bot is ready to process audio — list each handshake step, webhook, or SDK callback in order
- Whether inbound and outbound follow different initialization paths
- What "ready" means: is there an explicit signal (event, log line, callback) or does the bot assume readiness after connection?

**3. Authentication and credentials**
- What credentials the bot uses to authenticate with the telephony platform or transport layer (API key, SIP digest auth, JWT, OAuth token)
- Where those credentials are loaded from (env vars, config file, secrets manager) — list the exact env var or config key names
- Whether credentials are per-call or session-scoped

**4. Destination configuration**
- What the call destination looks like (E.164 phone number, SIP URI, WebSocket URL, LiveKit room token, etc.)
- Whether the destination is static (hardcoded in config) or dynamic (injected per-call via webhook payload, env var, or CLI arg)
- If dynamic: exactly where the destination is read from and when in the startup sequence it is consumed

**5. Session metadata**
- What metadata is available at call start and injected into the bot's context: caller ID, call ID, custom SIP headers, webhook payload fields, platform metadata
- Whether any of this metadata reaches the system prompt or LLM context directly

**6. Failure handling**
- What happens if the transport connection fails mid-call (reconnect attempt, hang-up, silent drop)
- Whether there is a connection timeout and what value it is set to
- What happens if required credentials are missing or invalid at startup

---

### Q2 — Speech-to-Text (STT)

**1. Models and configurations**
- What provider(s) and model(s) are configured (e.g. Deepgram `nova-2`, Google STT `latest_long`, AssemblyAI `best`, Whisper via OpenAI) — list every one found in config, not just the default in use
- For each model: list all non-default parameters set — language/locale, encoding, sample rate, endpointing timeout, keyword/keyterm boosting list, confidence cutoff, punctuation, smart formatting, profanity filter, diarization, word timestamps, multichannel. Omit params left at defaults.
- Whether transcription is streaming (interim + final results) or batch (final only), and whether the bot acts on interim transcripts before a final arrives

**2. Custom logic layered on top of transcription**
- Any post-processing applied to the raw transcript before it reaches the LLM: regex normalization, number-to-word conversion, disfluency removal ("um"/"uh"), PII redaction, punctuation injection
- Any pre-screening done at the STT layer (keyword match, wake-word detection, intent classification) before the LLM sees the text
- Any transcript enrichment attached to the turn message: speaker labels, confidence scores, word-level timestamps, utterance metadata

**3. Fallback logic**
- Whether a secondary STT provider or model activates on primary failure — exact trigger (error code? timeout? empty result?) and what the secondary model is
- What happens on an empty or below-confidence transcript: retry the STT call, push an empty turn to the LLM anyway, or start a no-transcript timer — record the timer duration if present
- Whether a retry cap or maximum wait deadline bounds the fallback sequence

**4. Start/stop transcription**
- When the bot starts transcribing: at call connect (always on), on first VAD event, or another explicit trigger
- When the bot stops transcribing: at call end only, or muted during bot speech to prevent echo/self-transcription — if muted, exactly when the mute window opens and closes relative to TTS start/end events
- Whether the STT provider has a built-in endpointing parameter (e.g. Deepgram `endpointing`, AssemblyAI `utterance_end_ms`) and what value it is set to — note if this overlaps with what the VAD layer does

---

### Q3 — Turn Detection (VAD + Transcript Signals)

Turn start and turn end are decisions, not single events. Multiple signal sources can feed into each decision — a standalone VAD processor, the STT provider's own built-in VAD/endpointing, interim transcript arrival, and final transcript arrival. Document every signal source the codebase actually uses, then describe exactly how they combine.

**1. Signal sources present in this stack**

For each source found, record what it emits and at what layer:

- **Standalone VAD processor** (e.g. WebRTC VAD, Silero VAD, a named pipeline class): what it emits (`speech_started` / `speech_stopped` events, probability scores, binary flags), its configured parameters (speech probability threshold, min speech duration ms, min silence duration ms), and where in the pipeline it runs
- **STT provider built-in VAD / endpointing** (e.g. Deepgram `vad_events: true` emits `speech_started` + `utterance_end`; Deepgram `endpointing: Nms` forces a final transcript after Nms silence; AssemblyAI `utterance_end_ms`; Google STT `single_utterance`): list every VAD-related parameter enabled on the STT connection and what event or transcript shape each one produces
- **Interim transcripts**: whether the STT provider streams partial results before the utterance is finalized, and whether the bot subscribes to them
- **Final transcripts**: the event or callback that delivers a finalized, non-revisable transcript, and what metadata accompanies it (confidence, duration, word timestamps)

If a signal source is not present (e.g. no standalone VAD, STT-only endpointing), say so explicitly.

**2. Turn-start logic**

Walk through the exact sequence of events that opens a user turn — from first audio arriving to the moment the pipeline commits to processing this as a caller turn:

- What is the first signal that can open a turn: standalone VAD `speech_started`, STT provider `speech_started` event, first interim transcript word, or raw audio above an amplitude threshold?
- Is a single signal sufficient, or must multiple conditions be satisfied before the turn is confirmed? (e.g. "VAD fires AND an interim transcript of ≥N words arrives" — record N and where it is configured)
- If there is a confirmation gate: what happens to audio and interim transcripts that arrive before the gate is satisfied — are they buffered and replayed, or discarded?
- Is there a maximum wait after the first signal before the turn is force-opened regardless of the gate condition — record the timeout value
- What state does the pipeline enter while waiting for turn-start confirmation (listening, buffering, ignoring)?

**3. Turn-end logic**

Walk through the exact sequence of events that closes a user turn — from last caller audio to the moment the pipeline commits the transcript to the LLM:

- What is the primary signal that can end a turn: standalone VAD `speech_stopped` after Xms silence, STT provider `utterance_end` event, STT provider endpointing firing a final transcript, a speech timeout timer that the bot manages itself, or receipt of a final transcript?
- Record the exact timeout or threshold value for every signal that involves a delay (e.g. "standalone VAD fires after 300ms silence", "Deepgram endpointing set to 500ms", "bot-side speech timeout of 1200ms")
- If multiple signals are present: does the first one to fire win, or must they all agree? Describe the arbitration logic exactly — e.g. "turn ends on whichever comes first: standalone VAD silence for 300ms OR Deepgram `utterance_end` event, but if a new interim transcript arrives the bot-side timer resets"
- What happens if VAD goes silent but no final transcript arrives — does the bot wait indefinitely, fire a no-transcript timer (record duration), or push an empty turn to the LLM?
- What happens if a final transcript arrives but VAD is still active (caller still speaking) — is the transcript held until VAD goes silent, or does it immediately close the turn?
- Is there a hard maximum turn duration that force-closes the turn regardless of VAD or transcript state — record the value

**4. Interaction between signal sources**

- If both a standalone VAD and the STT provider's built-in endpointing are active, can they conflict? (e.g. standalone VAD says silence but STT endpointing hasn't fired yet — which one wins?)
- Whether the bot disables or ignores the STT provider's built-in endpointing in favour of its own logic, or relies on it entirely
- Whether interim transcripts can reset a turn-end timer that is already counting down (i.e. new words arriving extend the turn)

**5. VAD artifact risks**
- Whether background noise, DTMF tones, hold music, or bot echo can false-trigger or false-suppress any of the signal sources above
- Whether bot audio is excluded from VAD processing via acoustic echo cancellation or a hard mute applied during TTS playback — and whether this mute covers both the standalone VAD and the STT provider's built-in VAD

---

### Q4 — Language Model (LLM)

**1. LLM generation trigger**
- What event causes the bot to fire an LLM request — is it turn-end (VAD silence + final transcript committed), receipt of a final transcript regardless of VAD state, an explicit turn-end event emitted by the turn-detection layer, or something else?
- Whether the LLM is called once per user turn or can be called mid-turn (e.g. triggered by an interim transcript reaching a word-count threshold, or by a specific keyword detected in an interim result)
- Whether the bot can generate an LLM response proactively without any caller input (e.g. a timeout-triggered response, a scheduled follow-up, or a re-prompt after silence) — if so, what triggers it and what context is sent
- If the turn produced an empty or very short transcript (e.g. "um", background noise bleed): does the LLM still get called, does the bot discard the turn silently, or does a minimum-length gate prevent the call?
- Whether multiple rapid turns can queue up concurrent LLM requests, and how the pipeline handles the responses arriving out of order (cancel stale requests, queue and serialize, or last-write-wins)

**2. Models and configurations**
- What provider(s) and model(s) are configured (e.g. OpenAI `gpt-4o`, Anthropic `claude-3-5-sonnet`, Groq `llama-3.1-70b`, Azure OpenAI) — list every one found in config
- For each model: list all non-default parameters — temperature, max_tokens, top_p, frequency_penalty, presence_penalty, stop sequences, seed, response_format. Omit defaults.
- Whether responses are streamed token-by-token or returned as a complete batch, and how streaming affects when TTS synthesis begins

**2. Request structure**
- The anatomy of the system prompt: is it a static string, a template with runtime-injected variables, or dynamically assembled per call? List what variables are injected and where they come from.
- How conversation history is managed: full history passed every turn, sliding window (record window size), or summarized after N turns — record the exact strategy and any size limits
- What tool/function definitions are included in every request — list each tool name, its purpose, and whether it is always present or conditionally included

**3. Response handling**
- Whether the LLM output is parsed or validated before being passed to TTS: schema check, JSON parse, minimum length, profanity filter
- What happens to a response that fails validation: discard and retry, substitute a fallback phrase, or pass through as-is
- Whether tool calls and text responses are handled in the same pipeline pass or separately
- How tool call results are fed back into the conversation: as a tool result message, injected into the next system prompt, or another mechanism

**4. Retry and timeout logic**
- Exact retry count and retry delay (fixed or exponential backoff) — record the values
- What triggers a retry: HTTP error code, timeout, empty content, malformed JSON, specific error strings
- The LLM call timeout deadline (ms or seconds) and what the bot does when it expires: play a fallback phrase, hang up, silently drop the turn
- Whether retries are transparent to the caller (bot stays silent) or trigger an audible holding phrase

**5. Fallback and provider switching**
- Whether a secondary LLM provider or model activates if the primary fails — what triggers the switch and what the fallback model is
- Whether the fallback uses the same system prompt and context or a stripped-down version
- Whether there is a circuit-breaker that stops retrying after repeated failures within a time window

---

### Q5 — Text-to-Speech (TTS)

**1. Provider and voice configuration**
- What provider(s) and voice model(s) are configured (e.g. ElevenLabs `eleven_turbo_v2`, Deepgram Aura, Google TTS WaveNet, PlayHT, Azure Neural) — list every one found in config
- For each voice: list all non-default parameters — voice ID, stability, similarity boost, style, speed, pitch, output audio format, sample rate. Omit defaults.
- Whether multiple voices are used in the same call (e.g. different voices for different bot personas or escalation states)

**2. Synthesis pipeline**
- Whether synthesis is streaming (audio chunks begin arriving before the full text is ready) or batch (full audio returned at once)
- If streaming: what chunking strategy is used — sentence boundaries, punctuation splits, token count, or the provider's own chunking — and whether the first chunk is played before the rest is synthesized
- The latency model: when does audio playback start relative to when the LLM response text (or first chunk of it) is available

**3. Audio playback**
- How synthesized audio is buffered and sent to the caller: pushed immediately, queued, or rate-limited
- Whether there is a pre-buffer or jitter buffer that introduces intentional delay before playback starts
- How the bot handles a TTS synthesis error mid-utterance: stops speaking, plays silence, or retries from the failed chunk

**4. Fallback**
- Whether a secondary TTS provider or voice activates if the primary fails — what triggers the switch and what the fallback voice is

---

### Q6 — Interruption Handling

**1. Interruption trigger**
- Whether caller-over-bot interruption is supported and what triggers it: VAD detects caller speech above threshold during bot playback, a specific interrupt event from the transport layer, or both
- Whether there is a minimum interrupt duration (caller must speak for at least Nms before the interrupt is accepted) — record the value if set
- Whether interruption can be disabled or suppressed for specific bot utterances (e.g. legal disclaimers, opening greetings)

**2. Cancellation scope**
- Exactly what is cancelled when an interruption fires: the in-progress audio chunk only, all queued audio, any pending synthesis requests, or all three
- Whether in-flight LLM requests are also cancelled when an interruption fires, or allowed to complete in the background

**3. Pipeline state after cancellation**
- What the LLM context contains after an interruption: the truncated bot utterance text, the full planned utterance, or nothing
- Whether the pipeline immediately opens a new user turn to receive the caller's interrupting speech, or waits for a VAD end-of-turn signal first

**4. Partial utterance handling**
- Whether partial bot utterances (mid-sentence cuts) appear in the conversation transcript or are suppressed entirely
- If they appear: what form they take (truncated text, a marker, or the full intended text)

**5. Back-to-back interruption behavior**
- What happens if the caller interrupts, the bot begins a new response, and the caller interrupts again before the new response completes
- Whether the pipeline handles this cleanly or degrades (queued synthesis requests pile up, audio artifacts, LLM receives duplicate context)

---

### Q7 — Caller Silence / Idle Timer

**1. Timer configuration**
- The exact silence threshold (in seconds) that fires the idle timer
- Whether the timer starts from call connect (before any exchange) or only after the first bot utterance or first caller turn
- Whether a separate threshold applies at call start vs. mid-call — record both values if different

**2. Escalation sequence**
- Whether the bot escalates (multiple prompts before hang-up) or fires a single action
- The exact escalation sequence: what happens at T=N₁s, T=N₂s, T=N₃s — record the actual values and the exact phrase (or phrase template) spoken at each step
- What happens at the final escalation: hang-up, transfer, leave voicemail, or something else

**3. Reset and cancellation conditions**
- What resets the timer: any caller audio above VAD threshold, any finalized transcript, only a finalized non-empty transcript, or something else
- Whether bot speech resets the timer (bot speaking mid-escalation could restart the silence window)
- Whether an in-progress escalation is fully cancelled when the caller speaks, or only paused until the next silence window

**4. Timer interactions**
- Whether the idle timer runs concurrently with other timers (e.g. a call-level max-duration timer) and what happens if both fire
- Whether DTMF input from the caller counts as "activity" that resets the idle timer

---

### Q8 — Side Channels

For each side channel found, write a separate sub-description. Skip sub-sections for channels not present.

**DTMF received (caller → bot)**
- How digits arrive at the bot: as individual events from the transport layer or pre-aggregated into sequences
- Whether the bot runs a DTMF aggregation processor — if so: what terminator character ends a sequence (e.g. `#`), and what timeout (ms) flushes an incomplete sequence
- The complete processing pipeline once digits are received: routed to an IVR handler, injected into the LLM context as a user message, passed to a tool call, or logged only
- Under what call states DTMF is accepted vs. silently ignored: during bot speech, during hold, only at specific menu prompts, or always

**DTMF sent (bot → external system)**
- What triggers the bot to send digits outbound: a specific user phrase, an LLM tool call, or reaching a defined call state
- The exact digit sequence sent and the destination (the SIP peer, the phone number dialed)
- Whether the sequence is hardcoded or dynamic (generated by the LLM or a tool)

**SMS received**
- What triggers inbound SMS handling: any SMS arriving during the call, a message matching specific content, or only at certain call stages
- How the SMS content enters the bot's processing: read aloud to the caller, appended to LLM context as a system event, both, or neither
- Whether SMS received mid-conversation can interrupt the current bot turn

**SMS sent**
- What triggers the bot to send an SMS: a caller request, completion of a specific task, a named tool call, or a specific LLM output pattern
- Whether the message content is fixed, templated, or LLM-generated
- What confirmation the bot receives that the SMS was delivered (webhook, API response, or fire-and-forget)

**Voicemail detection**
- What signal indicates the call reached voicemail: an AMD (Answering Machine Detection) result from the platform, a silence-then-beep pattern, a vendor webhook event, or a combination
- Exactly what the bot does upon detection: starts playing a pre-recorded or synthesized message, hangs up immediately, waits for a beep before speaking, or retries the call
- The maximum message length if leaving a voicemail, and whether the bot detects when recording has ended

**Pre-recorded audio / audio injection**
- Whether the bot can play a pre-recorded audio file instead of synthesizing speech for certain responses
- What triggers playback (a named intent, a tool call, a specific call state) and how the file is referenced (URL, file path, asset ID)
- Whether pre-recorded audio and synthesized speech can be interleaved in the same response

**Any other side channels found** — describe trigger, processing pipeline, and direction (bot↔caller, bot↔external).

---

### Q9 — Other Behaviors

For each behavior found, write a sub-description. Skip sub-sections for behaviors not present.

**Call transfer**
- What triggers a transfer: a specific caller phrase, an LLM tool call, an escalation threshold, a business-hours check, or another condition
- Transfer type: blind (bot drops immediately after initiating) or warm (bot stays on the line until the destination answers)
- The transfer destination: a hardcoded number or queue, a dynamically determined target, or one chosen by the LLM
- Whether the bot announces the transfer to the caller before initiating, and if so, the exact phrase or template
- What happens if the transfer target is unreachable: retry, fall back to a different destination, or return to the bot conversation

**Bot-initiated hang-up**
- What conditions cause the bot to end the call autonomously: task completion signal from the LLM, max idle escalation exceeded, max call duration reached, unrecoverable error, or another trigger
- Whether the bot speaks a closing phrase before hanging up and what that phrase is (or its template)
- Whether there is a grace period between the closing phrase and the actual disconnect

**Call recording**
- Whether the platform or bot records the call audio, and at which layer (transport, pipeline, vendor-side)
- What triggers recording start and stop: always-on, triggered by a specific event, or consent-gated
- Where recordings are stored and what format they use

**Network degradation simulation**
- Whether the bot or its test harness can artificially introduce latency, packet loss, or jitter
- What parameters are configurable and their ranges
- Which pipeline layers are affected by each parameter (STT input quality, LLM round-trip, TTS delivery)

**Background noise handling**
- Whether the pipeline includes any noise suppression or audio enhancement before STT (Krisp, RNNoise, vendor-built)
- What noise profiles the suppression is tuned for (HVAC, office, traffic) if documented
- Whether the suppression is always-on or conditionally applied

**Any other behaviors found** — describe trigger, mechanism, and effect on the call.

---

### Q10 — Bot Speaks First

**1. Opening message**
- The exact content of the opening message — copy from code or config if possible; if it is a template, copy the template and list all injected variables and where they come from
- Whether the opening message varies by call context (inbound vs. outbound, time of day, caller ID, campaign) and if so, what drives the variation

**2. Synthesis method**
- Whether the opening is synthesized live on each call (TTS) or played from a pre-recorded audio file
- If pre-recorded: what format, where it is stored, and how it is loaded at call start

**3. Timing**
- How long after call connect the opening message begins playing — is there a deliberate delay, or does it start as soon as the session is established?
- Whether the delay is configurable and what value it is set to

**4. Interruptibility**
- Whether the caller can speak over the opening message and have the bot register it as a turn
- If interruptible: whether the bot processes whatever the caller said during the greeting or discards it

---

### Q11 — Local Run

**1. Startup command**
- The exact command to start the bot locally (including working directory, interpreter version, and any required flags)
- Whether a Makefile target, shell script, or Docker Compose file wraps the startup — if so, what it does step by step

**2. Environment variables**
- Every env var the bot reads at startup — list name, purpose, whether required or optional, and the default if optional
- Which vars must be set differently for local/test vs. production (e.g. a test phone number, a mock endpoint URL, a reduced timeout)

**3. Config files**
- Every config file the bot loads (YAML, TOML, JSON, `.env`) — list path, what it controls, and whether it must be created manually or is version-controlled

**4. Readiness signal**
- How the bot signals it is ready to accept calls: a specific log line, a health endpoint returning 200, a TCP port becoming available, or a fixed sleep after startup
- The exact string or endpoint to watch for, so a CI script can gate on it

**5. Call destination override**
- The exact mechanism to point the bot at a test endpoint instead of production: which env var to change, which config key to set, or which CLI flag to pass
- Whether the override requires a full restart or can be changed without restarting

**6. Existing CI coverage**
- Whether a CI script, GitHub Actions workflow, or Makefile target already runs the bot in a test mode — what it does, what it does not cover, and where it lives in the repo

**7. Known fragile steps**
- Any step in the local startup that has broken before, depends on a specific ordering, requires an external service to be up, or is underdocumented in the repo
- Any known timing issues: race conditions, ports that take time to open, services that must be started in a specific order

---

## Phase 2 Output

Write all descriptions to `/tmp/infra-workflow-descriptions.md` using this structure:

```markdown
# Infrastructure Workflow Descriptions

Generated by Phase 2 of cekura-infra-test-suite.
Read by Phase 3 before designing test scenarios.

---

## [Workflow Name] (Q[N])

### [Sub-topic — e.g. "LLM generation trigger", "Turn-end logic", "Idle timer escalation"]

[Detailed description with actual values, class/function names, config keys, and file:line
references. Every numeric threshold must be recorded. Every conditional branch must be named.
Example level of detail:

"Turn-end is handled by `SpeechTimeoutStrategy` (`bot/turn_strategy.py:88`). After standalone
VAD reports silence, a 1 200 ms countdown starts (`SPEECH_TIMEOUT_MS=1200`, `config.py:47`).
If a new interim transcript arrives before the countdown expires, the timer resets. When the
countdown fires, the strategy emits a `user_turn_ended` event regardless of whether a final
transcript has arrived. If no final transcript is present at that point, the bot pushes the
last interim transcript to the LLM. If there is no interim transcript either, the turn is
discarded silently and no LLM call is made."]

### [Next sub-topic]

[...]

**Unresolved — could not determine from code:**
- [specific value or behaviour that could not be found, what was searched, what would surface it]

---
```

Repeat the block for every workflow found. Omit any workflow where Phase 1 found nothing.

At the end of the file, add:

```markdown
## Explicitly Excluded

The following were found but cannot be fully described without runtime inspection or vendor
documentation:
- [name the item, what is known, and what is unknown]
```

---

## Phase 2 Gate

`/tmp/infra-workflow-descriptions.md` exists and covers every capability Phase 1 found.

Move to [Phase 3 — Inventory What to Test](phase3-inventory.md).
