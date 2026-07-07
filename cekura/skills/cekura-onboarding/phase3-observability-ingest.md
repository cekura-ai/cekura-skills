# Phase 3 (observability) — Ingest Call Logs & Verify

> **Start:** Announce "Starting Phase 3 — Ingest Call Logs".

The observability path does not generate scenarios or run simulations. You ingest the user's real production calls. This phase carries the path's **verification gate**: one call log visible in Cekura.

## 3a. Pick an ingestion mode

**Default for VAPI / Retell / ElevenLabs / Synthflow / Bland (when the provider API key is on the agent): auto-fetch production calls.** Enable it with `aiagents_auto_fetch_create` (poll `aiagents_auto_fetch_progress_retrieve`) — Cekura pulls the calls from the provider directly, no webhook or manual upload needed. Only fall back to the modes below if the API key was deferred in Phase 2 (surface that as the reason and offer to add the key now).

For other providers — or when no key is available — ask: "(a) upload a sample call to see how Cekura processes it, or (b) configure continuous webhook ingestion from your provider?"

### (a) One-shot upload — fastest aha-moment, zero integration

Call `observe_create` with the user's transcript. Identify the agent by `agent` (the Cekura agent ID from Phase 2, preferred) or `assistant_id` (provider-side ID).

Minimum payload:
```json
{
  "call_id": "<unique call id>",
  "agent": <agent_id>,
  "transcript_type": "cekura",
  "transcript_json": [
    {"role": "Testing Agent", "content": "Hi, can I book a room?", "start_time": 0.0, "end_time": 2.1},
    {"role": "Main Agent", "content": "Of course — for what date?", "start_time": 2.3, "end_time": 4.0}
  ],
  "call_ended_reason": "completed"
}
```

For `transcript_type: "cekura"`, the only valid roles are `"Testing Agent"` (caller) and `"Main Agent"`. If the user has a provider-native transcript (VAPI, Retell, ElevenLabs, Bland, LiveKit, Pipecat, KoreAI, Trillet), set `transcript_type` to that provider and pass `transcript_json` exactly as the provider emits it.

**Always try to include the call recording** — `voice_recording_url` (or `voice_recording` as a file upload). Ask the user for it; every provider exposes recordings. It unlocks the audio metrics (pitch, speaking rate, gibberish, latency-from-audio) that show the platform's value on the very first call. Omit it only if the user genuinely has no recording at all.

Other optional fields: `metadata` (freeform filter tags), `dynamic_variables`, `customer_number` (E.164), `metric_ids` (evaluate immediately — skips Phase 5O's separate kickoff).

### (b) Continuous webhook ingestion

Provider-specific webhook endpoints accept the provider's raw post-call shape:

| Provider | Webhook URL |
|---|---|
| VAPI | `POST /observability/v1/vapi/observe/` |
| Retell | `POST /observability/v1/retell/observe/` |
| ElevenLabs | `POST /observability/v1/elevenlabs/observe/` |
| LiveKit | `POST /observability/v1/livekit/observe/` |
| Pipecat | `POST /observability/v1/pipecat/observe/` |
| Other | generic `observe_create` |

The user configures their provider to POST every completed call to the URL with `Authorization: Bearer <Cekura API key>`. Then trigger one real test call so an ingestion lands.

**LiveKit / Pipecat note:** continuous production observability for these providers requires the Cekura SDK in the agent (read `../cekura-create-agent/phase6-sdk-integration.md` when the user is ready) — or the user pushes call data themselves via `observe_create` after each call. Start with the one-shot upload either way.

## 3b. Verification gate

1. List call logs (`call_logs_list`) and confirm the ingested call is visible.
2. Show the user the call log ID; explain evaluation is async (`status: "evaluating"` initially).

**If nothing landed, onboarding is not done** — debug the webhook/auth/payload now, not after the user leaves.

---

## Phase 3 Gate

**Do not proceed until at least one call log is visible via `call_logs_list`.**

Announce: "Phase 3 complete." Then begin [Phase 4 — Configure Metrics](phase4-observability-metrics.md).
