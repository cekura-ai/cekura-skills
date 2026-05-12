# Phase 1 — Discover the Infrastructure

Read the codebase and answer the questions below. Do not ask the user anything yet — find what you can from the code first, then surface only the gaps you couldn't resolve.

The questions are technology-neutral. The answers will be different for every stack (LiveKit, Pipecat, VAPI, Retell, Cisco, Exotel, a custom WebSocket server — anything). That's expected. Record what's actually there, not what you expected to find.

---

## Q1. How does the bot connect to a call?

Find the entry point where a voice session is established — the code that runs when a call starts or when the bot dials out.

Answer:
- What protocol or platform handles the voice connection? (e.g. SIP, WebRTC, raw WebSocket, a vendor SDK)
- Does the bot initiate calls (outbound) or receive them (inbound), or both?
- Where is the call destination (number, URI, room, endpoint) set, and can it be changed without modifying source code?

---

## Q2. How does the bot understand what the caller said?

Find where audio from the caller is converted to text.

Answer:
- What service or component does the transcription?
- Is there logic that detects when the caller starts or stops speaking (voice activity detection)? If so, what triggers it?
- What happens when transcription fails or returns nothing? Is there a fallback?

---

## Q3. How does the bot decide what to say?

Find where the transcript is sent to a language model and a response is generated.

Answer:
- What model or service generates the response?
- What happens when the model call fails? Is there retry logic, and if so, how many attempts and with what delay?
- Is the model's output checked for validity before it's used (e.g. empty response, error string, failed parse)? What happens if the check fails?
- Is there a deadline enforced on the model call? What happens when it's exceeded?
- Is there a secondary model or provider that takes over if the primary is unavailable?

---

## Q4. How does the bot speak to the caller?

Find where the bot's text response is converted to audio and sent to the caller.

Answer:
- What service or component does the audio synthesis?
- Can the caller interrupt the bot while it is speaking? If so, what stops the audio and resets the conversation?
- What happens when audio synthesis fails? Is there a fallback voice or provider?

---

## Q5. What happens when the caller goes silent?

Find whether the bot detects prolonged caller silence and reacts to it.

Answer:
- Is there a timer or mechanism that fires when the caller stops speaking for too long?
- What does the bot do when it fires — play a prompt, ask if the caller is still there, or hang up?
- How long is the silence threshold (in seconds)?
- Does this escalate — does the bot prompt multiple times before ending the call? If so, how many times?

---

## Q6. What side-channel interactions does the bot support?

Beyond the main voice conversation, find every other communication channel or telephony event the bot can send or receive. For each one found, answer: what triggers it, what does the bot do with it, and in which direction does it flow (bot → caller, caller → bot, or bot → external system)?

**Touch-tone input (DTMF received):** Can the caller send keypad digits to the bot? Are they accumulated into a buffer or handled one at a time? Is there a terminator key?

**DTMF output (DTMF sent):** Can the bot send keypad digits to an external system — e.g. to navigate an IVR it dialed into?

**SMS received:** Can the caller (or another party) send an SMS that the bot processes during or around a call?

**SMS sent:** Can the bot send an SMS to the caller — e.g. a confirmation, a link, or a follow-up after the call?

**Voicemail detection:** When the bot dials out, can it detect that it reached a voicemail system rather than a live caller? What does it do in that case — leave a message, hang up, retry?

**Voicemail playback / pre-recorded audio:** Can the bot play a pre-recorded audio clip rather than synthesizing speech for certain responses?

**Call recording:** Is the call being recorded? Is recording triggered by the bot, or always-on?

**Any other events or channels** specific to this platform or vendor (e.g. call status webhooks the bot reacts to, mid-call metadata, real-time transcription callbacks used for something other than STT)?

---

## Q7. Does the bot support any other testable behaviors?

Look broadly at what else the pipeline can do that could affect a call. Common ones:

- **Network degradation simulation** — can the bot artificially introduce latency, jitter, or packet loss for testing purposes?
- **Call transfer** — can the bot hand the call off to another destination (human agent, queue, IVR)?
- **Bot-initiated hang-up** — can the bot end the call on its own (e.g. after task completion, or as an action the LLM can invoke)?
- **Background noise handling** — is there any filtering or simulation of ambient sound?

For each: does it exist, and what triggers it?

---

## Q8. Does the bot speak first?

Find whether the bot sends audio or text to the caller before waiting for the caller to speak.

Answer:
- Yes or no?
- If yes, what is the opening message?

---

## Q9. How do you run the bot locally?

Find everything needed to start the bot in a local dev or test environment.

Answer:
- What command starts it?
- Are there env vars, flags, or config values that switch it into local/test mode?
- How is the call destination overridden for testing — can you change it without touching source code?
- Is there an existing test script, CI config, or runbook for local testing?

Also check `CLAUDE.md` and `memory.md` if they exist — they may already have this.

---

## Phase 1 Gate

Write out your answers in this format before moving on:

```
Q1 — Call connection:    [protocol/platform; inbound/outbound/both; how destination is set]
Q2 — STT:               [what transcribes; VAD: yes/no + trigger; fallback: yes/no]
Q3 — LLM:               [what generates response; retry: yes/no; validation: yes/no;
                          timeout: yes/no; fallback: yes/no]
Q4 — TTS:               [what synthesizes audio; interruption: yes/no + mechanism; fallback: yes/no]
Q5 — Caller silence:    [idle detection: yes/no; threshold: Xs; escalation: N prompts then hang-up]
Q6 — Side channels:     [DTMF received: yes/no; DTMF sent: yes/no; SMS in/out: yes/no;
                          voicemail detection: yes/no; recording: yes/no; other: ...]
Q7 — Other behaviors:   [list each found + what triggers it]
Q8 — Bot speaks first:  [yes/no; opening message if yes]
Q9 — Local run:         [start command; how to override call destination; existing CI script: yes/no]
GAPS:                   [questions you couldn't answer from code alone]
```

Surface gaps as open questions in the Phase 2 checkpoint — do not guess.

Move to [Phase 2](phase2-map.md).
