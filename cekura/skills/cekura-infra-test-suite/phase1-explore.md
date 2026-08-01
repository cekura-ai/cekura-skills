# Phase 1 — Explore the Stack

> **ANNOUNCE FIRST:** Before reading any file or taking any action, output this exact line to the user:
> `**Phase 1 — Explore the Stack: starting**`

Read the codebase and answer the questions below. Do not ask the user anything yet — find what you can from the code first, then surface only the gaps you couldn't resolve.

The questions are technology-neutral. The answers will be different for every stack (LiveKit, Pipecat, VAPI, Retell, Cisco, Exotel, a custom WebSocket server — anything). That's expected. Record what's actually there, not what you expected to find.

---

## Pre-step: Identify the deployment target

Before answering Q1–Q9, determine which bot or entry point is the one being deployed and tested. Many codebases contain multiple bot variants (e.g. one per transport type, one per use case, a legacy variant alongside a current one).

- List every entry point you find (e.g. distinct `bot.py` files, server entry points, or agent classes).
- Check Dockerfiles, deployment configs (`pcc-deploy.toml`, `fly.toml`, CI workflows), README, and `CLAUDE.md` or `memory.md` to identify which one is deployed to production.
- If you cannot determine the target from code alone, add it to GAPS and ask the user before answering Q1–Q9.

Answer Q1–Q9 only for the identified deployment target. If a feature exists in one variant but not another, note which variant has it and whether the deployment target is that variant.

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
- Is there a voice activity detection (VAD) layer? If so, what triggers it — and is VAD the only thing that decides when a user turn starts and stops, or is there a custom turn-taking strategy layered on top? Look for classes like `UserTurnStrategy`, `TurnStartStrategy`, `TurnStopStrategy`, or similar. If found: what gates a turn start (e.g. a minimum word count on an interim transcript)? What ends a turn (e.g. a speech timeout after VAD stops, or immediate stop on a finalized transcript)? Record the actual threshold values.
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

**Important:** Check the full pipeline of the deployment target, not just the most prominent entry point. A feature (e.g. DTMF aggregation, SMS handling) may be present in one pipeline configuration but absent in another variant in the same repo. If a feature is found in a different variant than the deployment target, note that explicitly and mark it as absent for the target rather than absent from the codebase entirely.

**Touch-tone input (DTMF received):** Can the caller send keypad digits to the bot? Are they accumulated into a buffer or handled one at a time? Is there a terminator key? Check whether a DTMF aggregation processor (or equivalent) is wired into the deployment target's pipeline — not just whether such a class exists in the codebase.

**DTMF output (DTMF sent):** Can the bot send keypad digits to an external system — e.g. to navigate an IVR it dialed into?

**SMS received:** Can the caller (or another party) send an SMS that the bot processes during or around a call?

**SMS sent:** Can the bot send an SMS to the caller — e.g. a confirmation, a link, or a follow-up after the call?

**Voicemail detection:** When the bot dials out, can it detect that it reached a voicemail system rather than a live caller? What does it do in that case — leave a message, hang up, retry?

**Voicemail playback / pre-recorded audio:** Can the bot play a pre-recorded audio clip rather than synthesizing speech for certain responses?

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

## Q9. What languages does the bot support?

Find every language the bot is configured to handle. This drives which language personalities to use in the test suite and whether multilingual scenarios are needed.

Answer:
- What is the bot's primary/default language?
- Does it support multiple languages? If so, list all configured languages (e.g. `en`, `es`, `fr`, `hi`, `de`).
- How is the language determined per call: fixed at deployment, set by caller locale, detected from caller speech, or switched mid-call by the caller?
- If multilingual: does the bot switch language mid-call (e.g. caller speaks Spanish after starting in English), and if so, what triggers the switch?
- Are there any languages listed in config or env vars that appear to be partial or non-production (e.g. a language code present but no corresponding TTS voice or STT model configured)?

---

## Q10. How do you run the bot locally?

Find everything needed to start the bot in a local dev or test environment.

Answer:
- What command starts it?
- Are there env vars, flags, or config values that switch it into local/test mode?
- How is the call destination overridden for testing — can you change it without touching source code?
- Is there an existing test script, CI config, or runbook for local testing?

Also check `CLAUDE.md` and `memory.md` if they exist — they may already have this.

---

## Phase 1 Gate

**Write out your answers IN THE CHAT in this format — do not write to any /tmp/ file during Phase 1.** The gate output must appear in the conversation and be confirmed by the user before Phase 2 begins. Do not skip or abbreviate any Q answer.

```
Q1 — Call connection:    [protocol/platform; inbound/outbound/both; how destination is set]
Q2 — STT:               [what transcribes; VAD: yes/no + trigger; custom turn strategy: yes/no
                          + turn-start gate (e.g. min N words on interim) + turn-stop rule
                          (e.g. Xs speech timeout after VAD stops); fallback: yes/no]
Q3 — LLM:               [what generates response; retry: yes/no; validation: yes/no;
                          timeout: yes/no; fallback: yes/no]
Q4 — TTS:               [what synthesizes audio; interruption: yes/no + mechanism; fallback: yes/no]
Q5 — Caller silence:    [idle detection: yes/no; threshold: Xs; escalation: N prompts then hang-up]
Q6 — Side channels:     [DTMF received: yes/no; DTMF sent: yes/no; SMS in/out: yes/no;
                          voicemail detection: yes/no; other: ...]
Q7 — Other behaviors:   [list each found + what triggers it]
Q8 — Bot speaks first:  [yes/no; opening message if yes]
Q9 — Languages:         [primary language; all supported languages; how determined per call;
                          mid-call switching: yes/no; any partial/non-production language configs]
Q10 — Local run:        [start command; how to override call destination; existing CI script: yes/no]
GAPS:                   [questions you couldn't answer from code alone]
```

Surface gaps as open questions in the Phase 2 checkpoint — do not guess.

---

## Phase 1 User Questions

After presenting the gate summary above, ask the user these two questions before proceeding to Phase 2. Record their answers — they shape Phase 2's analysis and are carried forward to Phase 5.

**Question 1 — Which connection types should the test suite run over?**

Based on Q1, list every connection type the bot supports and ask:

> "The codebase supports the following connection types: [list from Q1 — e.g. WebSocket, SIP, VAPI WebRTC].
> Which of these should the infra test suite run over? You can choose one, several, or all.
> The run script will execute every scenario once per selected connection type."

Record the answer as: `Selected connection types: [list]`

**Question 2 — What are the deployment steps for local testing?**

If Q10 already captured the start command, readiness signal, and stop mechanism, present what was found and ask for confirmation:

> "For local testing I found: start command `[X]`, readiness signal `[Y]`, stop command `[Z]`. Is this correct, or do I need to update anything?"

If Q10 was incomplete, ask:

> "To run the test suite I need to start and stop the bot automatically. Please provide:
> 1. The exact command to start the bot, plus **the names of the env vars it needs** — don't paste the key values, just the variable names (e.g. `OPENAI_API_KEY`, `TWILIO_AUTH_TOKEN`)
> 2. How to know when the bot is ready to accept calls (log line, health endpoint, port, or fixed wait)
> 3. The command to stop the bot after a run"

Record variable **names** only. The generated run script references them as `"${VAR:?}"` and reads values from the user's existing environment — no credential value should ever enter a file this skill writes. If the user pastes a value anyway, don't record it; confirm the variable name and move on.

Record the confirmed deployment steps verbatim.

**Question 3 — What is the Cekura agent ID for this bot?**

Ask:

> "What is the ID of the Cekura agent configured to connect with this bot? I need it to attach all scenarios and dynamic variables to the right agent.
>
> If you're not sure, share the agent name or description and I'll find it via `mcp__cekura__aiagents_list`."

Record the confirmed agent ID as: `Agent ID: [id]`

Write all three answers into the Phase 1 gate output before moving on.

Move to [Phase 2 — Analyze Each Layer](phase2-analyze.md).
