# Phase 1 — Discover the Infrastructure

Read the codebase before asking the user anything. The goal is a complete inventory of every voice pipeline component that could be tested.

For each section below, look for the **behavior** — not just a specific class name. Class names vary across frameworks and teams; the underlying behaviors are consistent. The examples given are illustrative, not exhaustive.

---

## 1a. Transport layer

**What to find:** How the bot establishes calls — both inbound (receiving) and outbound (dialing).

**Behavioral signals:**
- Outbound: code that constructs a destination address (SIP URI, phone number, room URL) and initiates a connection before the conversation starts
- Inbound: a webhook handler, WebSocket server, or listener that accepts incoming calls
- Config: wherever the destination address, caller ID, or server endpoint is set — the name of the key doesn't matter, the value format does (`sip:...`, `wss://...`, `+1...`, `https://...`)

**Provider examples to recognize:** Twilio, Vonage, Telnyx, Plivo (SIP/PSTN) · Daily, LiveKit, Agora (WebRTC) · Raw WebSocket servers

Record: **transport type** and **how the bot dials out or receives calls**.

---

## 1b. STT (Speech-to-Text)

**What to find:** Where audio from the caller gets converted to text, and whether the bot uses voice activity detection.

**Behavioral signals:**
- A service or client that accepts an audio stream and emits text transcription results
- VAD: logic that decides when the caller has started or stopped speaking — look for energy thresholds, silence duration checks, or a dedicated VAD model
- Fallback: a secondary transcriber that activates when the primary fails or returns an error

**Provider examples to recognize:** Deepgram, Google Speech-to-Text, Azure Cognitive Speech, AssemblyAI, OpenAI Whisper, Groq Whisper, Rev AI

Record: **STT provider**, **whether VAD is present**, **whether a fallback transcriber is configured**.

---

## 1c. LLM

**What to find:** Where the transcript gets sent to a language model, and what resilience logic wraps that call.

**Behavioral signals:**

*Provider:* A client or API call that sends a prompt/messages array to a model and receives a text or structured response.

*Retry logic:* Code that re-attempts the LLM call when it fails — look for:
- Loops with a max attempt count
- Exponential backoff or sleep between attempts
- Decorators like `@retry`, `tenacity.retry`, `backoff.on_exception`
- Try/except blocks that call the same LLM endpoint again

*Output validation:* Code that inspects the LLM's response for errors before using it — look for:
- Checks for empty or null responses
- Detection of error strings or refusal phrases in the output
- Structured output parsing with fallback on parse failure
- A post-LLM step that decides whether the response is usable

*Timeout handling:* Code that enforces a deadline on the LLM call — look for:
- `asyncio.wait_for`, `asyncio.timeout`, `concurrent.futures.ThreadPoolExecutor` with a timeout
- A timeout parameter on the API client
- A fallback response or recovery action triggered when the deadline is exceeded

*Fallback model:* A secondary model that activates when the primary is unavailable — look for a secondary provider client or a fallback model name in config.

**Provider examples to recognize:** OpenAI, Anthropic, Google Gemini, Groq, Azure OpenAI, Cohere, Mistral, Ollama

Record: **LLM provider**, **retry logic present (yes/no)**, **output validation present (yes/no)**, **timeout handling present (yes/no)**, **fallback model configured (yes/no)**.

---

## 1d. TTS (Text-to-Speech)

**What to find:** Where the bot's text response gets converted to audio, and whether mid-speech interruption is handled.

**Behavioral signals:**
- A service or client that accepts text and streams or returns audio back to the caller
- **Interruption handling:** Logic that stops audio playback when the caller speaks mid-sentence — look for:
  - An interrupt signal that cancels in-flight TTS audio
  - A boolean flag or mode that controls whether the caller can cut off the bot
  - A handler triggered by caller speech that flushes or cancels queued audio
- Fallback: a secondary voice or TTS provider that activates when the primary fails

**Provider examples to recognize:** ElevenLabs, Cartesia, PlayHT, Azure Neural TTS, Google TTS, Amazon Polly, Deepgram TTS, Rime

Record: **TTS provider**, **whether interruption/barge-in handling is present**, **whether a fallback voice is configured**.

---

## 1e. Pipeline behaviors

Look for these behavioral capabilities — regardless of what they are named in this codebase:

**Idle detection:** Does the bot notice when the caller goes silent for too long and prompt them?
- Look for: a timer or countdown that starts when the caller stops speaking; a silence threshold in seconds after which the bot says something like "Are you still there?"; a configured list of idle prompts; a maximum number of prompts before the call ends

**DTMF processing:** Does the bot handle touch-tone key presses from the caller?
- Look for: code that receives digit events from the telephony layer and accumulates them into a buffer; a configured terminator key that signals the end of input (commonly `#`); a handler that acts on the complete digit sequence

**Network simulation:** Can the bot simulate degraded network conditions for testing?
- Look for: code that introduces artificial latency, jitter, or packet loss into the audio pipeline during a call

**Call transfer:** Can the bot hand the call off to a human agent or another system?
- Look for: a transfer action or function the LLM can invoke; a configured destination (phone number, SIP URI, queue name) the call is forwarded to

**Bot-initiated hang-up:** Can the bot end the call programmatically?
- Look for: an end-call function or tool the LLM can invoke; logic that triggers automatic hang-up after task completion or after idle escalation exhausts its prompts

For each capability found, note the **configured values** — the threshold in seconds, the number of escalation prompts, the DTMF terminator character, etc. These values feed directly into the scenario timings in Phase 3.

---

## 1f. Bot configuration

Read the main bot config (often a Python/JS entry point, a JSON/YAML file, or a dedicated local runner script):

- **Does the bot speak first?** Look for a greeting string or a call to send audio/text before waiting for caller input.
- **Idle timeout value** — how many seconds of silence before the first idle prompt?
- **Idle escalation count** — how many idle prompts before the call is hung up?
- **DTMF terminator** — which digit signals end of input (usually `#`)?

---

## 1g. Local run mode

Understand how to start the bot locally for CI testing:

- Is there a flag, env var, or config value that switches the bot into local/dev mode?
- What command starts the bot locally?
- Where is the outbound call destination set — and can it be overridden without changing source code? (env var, config file, CLI arg)
- Is there an existing CI script, Makefile target, or Docker Compose file for local testing?

Read `CLAUDE.md` and `memory.md` if they exist — they may already document the local run procedure.

---

## Phase 1 Gate

Before moving to Phase 2, record a complete inventory:

```
TRANSPORT:    [type — SIP / WebRTC / WebSocket / PSTN; how bot dials/receives]
STT:          [provider; VAD: yes/no; fallback: yes/no]
LLM:          [provider; retry: yes/no; output validation: yes/no; timeout: yes/no; fallback: yes/no]
TTS:          [provider; interruption handling: yes/no; fallback: yes/no]
BEHAVIORS:    [idle timer: Xs / N prompts; DTMF: yes/no + terminator; transfer: yes/no;
               network sim: yes/no; bot hang-up: yes/no]
BOT CONFIG:   [speaks first: yes/no]
LOCAL RUN:    [start command; config override mechanism]
GAPS:         [anything you couldn't determine from code alone]
```

Note any gaps — you will surface them as open questions during the Phase 2 checkpoint.

Move to [Phase 2](phase2-map.md).
