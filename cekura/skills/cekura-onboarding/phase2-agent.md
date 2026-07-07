# Phase 2 — Agent Configuration (shared)

> **Start:** Announce "Starting Phase 2 — Agent".

Register the user's agent on Cekura. Framing differs by path:

- **Testing**: "Let's connect your agent so we can simulate calls against it."
- **Observability**: "Let's register your production agent so Cekura can attribute uploaded calls to it."

**Provider first — it shapes everything.** Ask before anything else:

> "What provider is your agent built on — VAPI, Retell, ElevenLabs, Synthflow, LiveKit, Pipecat, Bland, Chirp, KoreAI, Genesys, Cisco, or something self-hosted/custom?"

Then follow the matching section below. For per-provider credential fields, read [`../cekura-create-agent/phase2-provider.md`](../cekura-create-agent/phase2-provider.md) (credential matrix) — follow only the field guidance there, not that skill's phase gates.

**Two rules that apply to EVERY named provider:**
- **Keep `provider.type` set to the real provider** — never reroute to `self_hosted` because a credential is missing or the agent is reached by phone.
- **Deferred credentials are fine, but never silent.** If the user won't share an API key yet, fall back to the manual essentials of 2c, tell them which capabilities won't work until the key is added (provider-dispatched simulations, auto-sync, auto-import of calls), and carry it as an open item in every summary. Do not leave a half-connected agent without saying so.

## 2a. VAPI / Retell / ElevenLabs / Synthflow — auto-import (preferred)

The one high-leverage step: **provider agent ID + provider API key**. Create with `aiagents_create` using `configure_from_provider: true`, then poll `aiagents_auto_fetch_progress_retrieve`. Auto-import pulls the description (system prompt), tools, and config automatically — do not ask the user to paste their prompt when auto-import is available.

## 2a′. Bland / Chirp / KoreAI / Genesys / Cisco — standard named providers

No auto-import for these, so collect their credentials per the create-agent matrix (e.g. Bland: `provider.agent_id` = pathway_id; Chirp: websocket URL + basic auth; Cisco: no credentials) **plus** the manual essentials of 2c (description, language). The two rules above apply unchanged.

## 2b. LiveKit / Pipecat — config-only connection (no SDK, no code changes)

There is **no SDK requirement to onboard**. Simulations dispatch via provider APIs and Cekura produces its own transcript from call audio. The Cekura SDK is a post-first-result upgrade (agent-side traces, tool-call visibility) — offer it in Phase 6T, not here.

1. **Connection mode — prefer telephony when it exists.** Ask: "Does your agent already have a phone number or SIP endpoint?" If yes, connect via phone/SIP (validated in 2d) — it's the fewest moving parts. Use WebRTC dispatch only when there's no phone path:
   - **Pipecat Cloud**: `credentials.api_key` (pipecat.daily.co → Settings → API Keys) + `credentials.config.pipecat_agent_name`. Runs via `scenarios_run_pipecat_v2`.
   - **LiveKit**: `credentials.url` + `api_key` + `api_secret` + `config.agent_name` (must match the worker's `agent_name`). Runs via `scenarios_run_livekit_v2`.
2. **Keep `provider.type` = `livekit` / `pipecat` regardless of connection mode.** A LiveKit agent reached by phone is still a LiveKit agent — never reroute it to `self_hosted`.
3. **Set `credentials.config.tracing_enabled: false`.** It only becomes `true` after the SDK is actually integrated and verified (a later, optional step). Setting it `true` without the SDK makes every run wait on a webhook that never arrives.
4. No auto-import exists for these providers, so collect the manual essentials of 2c (description, language).

## 2c. Manual essentials (self-hosted, deferred-key, LiveKit/Pipecat)

- **Description = the real system prompt.** Read [`../cekura-create-agent/phase4-description.md`](../cekura-create-agent/phase4-description.md) for the quality bar and follow it. Do not accept a one-line summary: the description drives evaluator generation and `{{agent.description}}` metrics — it is the single most leverage-rich field on the agent. If the user genuinely can't provide it now, create with a clearly marked placeholder AND surface it as an open item in every subsequent summary; do not silently proceed to evaluator generation on a placeholder.
- Agent name, language.
- Connection details for how Cekura reaches the agent, in order of preference: existing phone number → SIP URI → websocket URL → provider WebRTC (2b).

**`self_hosted` / "custom" requires explicit confirmation — never a default.** Before setting it, confirm:

> "Custom/self-hosted means you built the voice stack yourself (your own STT/LLM/TTS pipeline). Most teams are on VAPI, Retell, ElevenLabs, LiveKit, or Pipecat — are you sure none of those apply?"

If the user names a known provider at any point, use that `provider.type` even when connecting via phone/SIP.

## 2d. Validate expensive-to-be-wrong inputs (before `aiagents_create`)

- **Phone numbers:** before attaching an outbound number, check the country is supported for Cekura outbound calling. If it isn't (e.g. many non-US/EU country codes), say so now and steer to SIP/WebRTC/websocket instead. Never accept a number Cekura cannot dial.
- **SIP:** capture the full URI and any auth; flag that it will be verified with a real call in Phase 5T before onboarding is declared done.
- **Description:** placeholder → flagged open item (2c).

## 2e. Create the agent

Call `aiagents_create` with the collected fields. On validation errors, fix and retry — don't hand the user a dashboard workaround.

**Defer to post-onboarding (do NOT do these now):** mock tools, knowledge base upload, dynamic variables, SDK integration, advanced config. They're covered by the **cekura-create-agent** skill and Phase 6T when the user actually needs them.

---

## Phase 2 Gate

**Do not proceed until `aiagents_create` succeeded AND the connection details are plausible** (provider confirmed, no unsupported phone number, description real or explicitly flagged as placeholder).

Announce: "Phase 2 complete." Then begin the path's Phase 3: [testing](phase3-testing-metrics.md) or [observability](phase3-observability-ingest.md).
