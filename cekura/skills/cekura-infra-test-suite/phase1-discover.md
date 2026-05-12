# Phase 1 — Discover the Infrastructure

Read the codebase before asking the user anything. The goal is a complete inventory of every voice pipeline component that could be tested.

---

## 1a. Transport layer

Look for how the bot receives and places calls.

| Signal in code | Transport type |
|---|---|
| `sip:`, `sip_uri`, `SIPTransport`, `twilio`, `vonage`, `telnyx`, `dial_out` | SIP / telephony |
| `DailyTransport`, `daily.co`, `room_url` | WebRTC via Daily |
| `LiveKitTransport`, `livekit` | WebRTC via LiveKit |
| `WebSocketTransport`, `ws://`, `wss://` | WebSocket |
| `phone_number`, `from_number`, `to_number` | PSTN |

Record: **transport type** and **how the bot dials out or receives calls**.

---

## 1b. STT (Speech-to-Text)

Look for the transcription provider and any voice activity detection.

| Signal | What it means |
|---|---|
| `DeepgramSTTService`, `deepgram` | Deepgram STT |
| `GoogleSTTService`, `google.cloud.speech` | Google STT |
| `AzureSTTService`, `azure.cognitiveservices.speech` | Azure STT |
| `AssemblyAISTTService`, `assemblyai` | AssemblyAI STT |
| `WhisperSTTService`, `openai.Audio` | Whisper STT |
| `GroqSTTService`, `groq` (with audio) | Groq Whisper STT |
| `VAD`, `silero`, `WebRTCVAD`, `vad_enabled`, `vad_analyzer` | Voice activity detection |
| Fallback transcriber config (`fallbackPlan.transcribers`) | STT fallback configured |

Record: **STT provider**, **whether VAD is present**, **whether a fallback transcriber is configured**.

---

## 1c. LLM

Look for the language model provider and any resilience logic around it.

| Signal | What it means |
|---|---|
| `OpenAILLMService`, `openai.ChatCompletion` | OpenAI |
| `AnthropicLLMService`, `anthropic.messages` | Anthropic |
| `GoogleLLMService`, `google.generativeai`, `gemini` | Google Gemini |
| `GroqLLMService` | Groq |
| `AzureOpenAILLMService` | Azure OpenAI |
| `LLMRetryProcessor`, `retry_on_error`, `max_retries` | Retry logic on LLM failure |
| `LLMErrorDetectionProcessor`, `error_detection` | Error detection in LLM output |
| `LLMTimeoutProcessor`, `timeout`, `llm_timeout` | Timeout handling |
| Fallback model config (`modelFallbackPlan`) | LLM fallback configured |

Record: **LLM provider**, **retry/error/timeout processors present (yes/no)**, **whether a fallback model is configured**.

---

## 1d. TTS (Text-to-Speech)

Look for the synthesis provider and interruption configuration.

| Signal | What it means |
|---|---|
| `CartesiaTTSService`, `cartesia` | Cartesia TTS |
| `ElevenLabsTTSService`, `elevenlabs` | ElevenLabs TTS |
| `PlayHTTTSService`, `playht` | PlayHT TTS |
| `AzureTTSService`, `azure` (speech synthesis) | Azure TTS |
| `GoogleTTSService` | Google TTS |
| `DeepgramTTSService` | Deepgram TTS |
| `BotInterruptionProcessor`, `interruptionLevel`, `stop_on_interrupt`, `InterruptionHandler` | Mid-speech interruption handling |
| TTS fallback config (`fallbackPlan.voices`) | TTS fallback configured |

Record: **TTS provider**, **whether interruption handling is present**.

---

## 1e. Pipeline processors

Scan for these by class name, import, config key, or behavioral description:

| Signal in code | What it tests |
|---|---|
| `UserIdleHandler`, `idle_timeout`, `idleTimeoutSeconds`, `silence_timeout`, `silenceTimeoutSeconds` | Idle timer — bot prompts "are you still there?" |
| `messagePlan.idleMessages`, `idle_messages`, `idleMessageMaxSpokenCount` | Idle escalation — N prompts then hang-up |
| `DTMFAggregator`, `dtmf`, `sendDtmfEnabled`, `send_dtmf` | DTMF digit accumulation |
| `NetworkImpairmentProcessor`, `network_simulation`, `packet_loss`, `jitter` | Network degradation simulation |
| `TransferHandler`, `transfer_call`, `callHoldFunctionEnabled`, `transfer_to` | Call transfer to human or IVR |
| `endCallFunctionEnabled`, `EndCallTriggerProcessor`, `end_call`, `end_call_on_idle` | Bot-initiated call termination |
| `BackgroundNoiseProcessor`, `backgroundDenoisingEnabled`, `backgroundSound` | Background noise / denoising |

For each found processor, also note **configured values** (e.g. idle threshold in seconds, escalation count, DTMF terminator digit).

---

## 1f. Bot configuration

Read the main bot config file (often `bot.py`, `main.py`, `config.py`, a JSON/YAML config, or the local runner):

- Does the bot say something first? Look for `firstMessage`, a greeting string in the system prompt, or a `send_greeting` call.
- What is the idle timeout value (seconds)?
- How many idle prompts before hang-up (`idleMessageMaxSpokenCount`, `maxCount`, etc.)?
- Is DTMF enabled? What is the terminator digit (usually `#`)?

---

## 1g. Local run mode

Understand how to start the bot locally for CI testing:

- Is there a `LOCAL_RUN`, `DEV_MODE`, `LOCAL`, or similar env var that switches to local mode?
- What command starts the bot locally?
- Where is the outbound SIP URI or call destination configured? (env var, config file, hardcoded dict)
- Is there an existing CI script, test runner, or `CLAUDE.md` / `memory.md` that documents local setup?

Read `CLAUDE.md` and `memory.md` if they exist — they may already document the local run procedure.

---

## Phase 1 Gate

Before moving to Phase 2, write out a complete inventory:

```
TRANSPORT:    [type, how bot dials/receives]
STT:          [provider, VAD present, fallback]
LLM:          [provider, retry/error/timeout processors, fallback]
TTS:          [provider, interruption handling, fallback]
PROCESSORS:   [list each found processor + configured values]
BOT CONFIG:   [speaks first: yes/no, idle threshold, idle count, DTMF terminator]
LOCAL RUN:    [start command, config override mechanism]
GAPS:         [anything you couldn't determine from code alone]
```

If there are gaps you couldn't resolve, note them — you will ask the user in Phase 2 during the checkpoint.

Move to [Phase 2](phase2-map.md).
