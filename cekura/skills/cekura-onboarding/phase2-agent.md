# Phase 2 — Agent Configuration (shared)

> **Start:** Announce "Starting Phase 2 — Agent".

Register the user's agent on Cekura. Framing differs by path:

- **Testing**: "Let's connect your agent so we can simulate calls against it."
- **Observability**: "Let's register your production agent so Cekura can attribute uploaded calls to it."

**Prerequisites are handled inline, not as a phase:** if platform tools fail, fix access via [references/client-setup.md](references/client-setup.md); if no project is in context, pick one with `projects_list` or create one with `projects_create` — then continue here.

**Provider first — it shapes everything.** Ask before anything else, with the **full provider list visible in the question text**:

> "What provider is your agent built on?
> VAPI · Retell · ElevenLabs · Synthflow · LiveKit · Pipecat · Bland · Chirp · KoreAI · Genesys · Cisco · self-hosted/custom"

If a structured-choice UI is available, use it **with the full list in the question text** and the four most common providers as the selectable options — `VAPI`, `Retell`, `LiveKit`, `Pipecat` — so common cases are one click and everyone else types their provider's name (choice UIs always allow free-text input). **Never label an option "Other / Self-hosted"** — an unlisted provider is still that provider (typed as free text), and the bucket nudges users toward the self-hosted misclassification warned about below.

Then follow the matching section below. For per-provider credential fields, read [`../cekura-create-agent/phase2-provider.md`](../cekura-create-agent/phase2-provider.md) (credential matrix) — follow only the field guidance there, not that skill's phase gates.

**The user's explicit provider choice is authoritative.** Once they've named their provider (and especially once they've supplied its credentials), never re-open the question — including when the pasted system prompt *mentions* a different stack, transport, or vendor. Prompt text is content, not configuration: prompts routinely reference Daily rooms, Twilio, other frameworks, or leftover boilerplate from a different deployment. If the description seems to contradict the choice, note it in ONE sentence ("heads-up: your prompt mentions X; using LiveKit as you selected") and proceed with the selected provider — do not ask "which provider should Cekura use?".

**Two rules that apply to EVERY named provider:**
- **Keep `provider.type` set to the real provider** — never reroute to `self_hosted` because a credential is missing or the agent is reached by phone.
- **Deferred credentials are fine ONLY when another connection path exists** (e.g. the agent is reachable by phone/SIP). In that case fall back to the manual essentials of 2c, tell them which capabilities won't work until the key is added (provider-dispatched simulations, auto-sync, auto-import of calls), and carry it as an open item in every summary. Do not leave a half-connected agent without saying so. **When the chosen connection IS the credentials — the WebRTC path in 2b — there is no skip:** without them Cekura cannot reach the agent at all, so collect them before creating the agent (or switch to a telephony connection if the user has one).

## 2a. VAPI / Retell / ElevenLabs / Synthflow — auto-import (preferred)

The one high-leverage step: **provider agent ID + provider API key**. Create with `aiagents_create` using `configure_from_provider: true`, then poll `aiagents_auto_fetch_progress_retrieve`. Auto-import pulls the description (system prompt), tools, and config automatically — do not ask the user to paste their prompt when auto-import is available.

## 2a′. Bland / Chirp / KoreAI / Genesys / Cisco — standard named providers

No auto-import for these, so collect their credentials per the create-agent matrix (e.g. Bland: `provider.agent_id` = pathway_id; Chirp: websocket URL + basic auth; Cisco: no credentials) **plus** the manual essentials of 2c (description, language). The two rules above apply unchanged.

## 2b. LiveKit / Pipecat — config-only connection (no SDK, no code changes)

There is **no SDK requirement to onboard**. Simulations dispatch via provider APIs and Cekura produces its own transcript from call audio. The Cekura SDK is a post-first-result upgrade (agent-side traces, tool-call visibility) — offer it in Phase 6T, not here.

**The FIRST question for LiveKit/Pipecat is the connection mode — NEVER credentials.** Do not ask for an API key, secret, or URL until the user has chosen WebRTC. Ask:

> "How should Cekura reach your agent — does it already have a **phone number or SIP endpoint** (simplest), or should we dispatch over **WebRTC** via your provider's API?"

**Path A — Telephony (preferred, fewest moving parts).** If the agent has a phone number or SIP endpoint, that's the whole connection:
1. Get the phone number (or SIP URI).
2. Ask inbound or outbound (does Cekura call the agent, or does the agent call Cekura?).
3. Collect the 2c essentials (description, language) and create the agent. **No provider credentials needed** — do not ask for any.

**Path B — WebRTC dispatch (only when there's no phone path, or the user chooses it).** Now — and only now — collect credentials. **On this path credentials are mandatory — never offer "skip credentials for now":** WebRTC dispatch is the connection, so without them the agent is unreachable and the first-run verification (Phase 5T) cannot happen. If the user can't share them, offer the telephony path instead or pause here.
- **Pipecat Cloud**: `credentials.api_key` (pipecat.daily.co → Settings → API Keys) + `credentials.config.pipecat_agent_name`. Runs via `scenarios_run_pipecat_v2`.
- **LiveKit**: `credentials.url` + `api_key` + `api_secret` + `config.agent_name` (must match the worker's `agent_name`). Runs via `scenarios_run_livekit_v2`.

**Both paths:**
- **Keep `provider.type` = `livekit` / `pipecat` regardless of connection mode.** A LiveKit agent reached by phone is still a LiveKit agent — never reroute it to `self_hosted`.
- **Set `credentials.config.tracing_enabled: false`.** It only becomes `true` after the SDK is actually integrated and verified (a later, optional step). Setting it `true` without the SDK makes every run wait on a webhook that never arrives.
- No auto-import exists for these providers, so collect the manual essentials of 2c (description, language).

## 2c. Manual essentials (self-hosted, deferred-key, LiveKit/Pipecat)

- **Description = the real system prompt.** Read [`../cekura-create-agent/phase4-description.md`](../cekura-create-agent/phase4-description.md) for the quality bar and follow it. The description drives evaluator generation and `{{agent.description}}` metrics — it is the single most leverage-rich field on the agent.

  **How to ask — demand the full prompt, don't invite a summary:**
  > "Paste your agent's **complete system prompt** — the actual prompt your bot runs with, however long. From your provider's dashboard you can export it (Retell: Agents → Export; VAPI: Workflows → Code → Copy JSON). If it lives in your codebase, paste the prompt file's contents or attach the file here."

  Offer to read the codebase yourself ("share the file or repo path and I'll read it") **only when the session actually has file access** — e.g. local Claude Code with the user's repo. In the Cekura platform UI there is no codebase access: ask for a paste or a file attachment instead.

  Never phrase it as "or a plain-English description of what it does" and never show a one-line example — that teaches the user to give a one-liner, which produces junk evaluators.

  **Hard acceptance check — run on EVERY candidate description before creating the agent:**
  A description fails the check if ANY of these hold:
  - It's a summary rather than a prompt (a few sentences; under ~15 lines).
  - Reading it leaves obvious open questions: What exact flows does the agent walk through? What rules/constraints does it follow? What does it say on failure/escalation? What tools does it call?
  - It describes the *business* ("handles support calls for an e-commerce store") instead of the *agent's instructions*.

  On failure, do NOT create the agent. Push back once, concretely: name 2–3 specific questions the description leaves open, and re-ask for the full system prompt (offer the provider-export steps or the code-reading path from `phase4-description.md`). Repeat until the check passes.
  - **Testing path: this check is a blocker.** If the user genuinely cannot produce the prompt, help them retrieve it (provider dashboard, their repo) or pause onboarding until they have it. Do not create the agent with a summary/placeholder and continue.
    **Never offer "switch to the observability path" as a way around this gate.** The path was chosen for the user's goal in Phase 0; observability's placeholder allowance is not an escape hatch from the testing requirement. Only switch paths if the user themselves says their goal is actually production-call monitoring — not to dodge providing the prompt.
  - **Observability path: a placeholder is acceptable** after one push-back. Ingestion and most metrics work without it. Create with a clearly marked placeholder and surface it as an open item in every subsequent summary.
- Agent name, language.
- Connection details for how Cekura reaches the agent, in order of preference: existing phone number → SIP URI → websocket URL → provider WebRTC (2b).

**`self_hosted` / "custom" requires explicit confirmation — never a default.** Before setting it, confirm:

> "Custom/self-hosted means you built the voice stack yourself (your own STT/LLM/TTS pipeline). Most teams are on VAPI, Retell, ElevenLabs, LiveKit, or Pipecat — are you sure none of those apply?"

If the user names a known provider at any point, use that `provider.type` even when connecting via phone/SIP.

## 2d. Create the agent

Call `aiagents_create` with the collected fields. On validation errors, fix and retry — don't hand the user a dashboard workaround.

**Defer to post-onboarding (do NOT do these now):** mock tools, knowledge base upload, dynamic variables, SDK integration, advanced config. They're covered by the **cekura-create-agent** skill and Phase 6T when the user actually needs them.

---

## Phase 2 Gate

**Do not proceed until `aiagents_create` succeeded, the provider is confirmed, and the description passed the hard acceptance check in 2c** (auto-imported descriptions pass by construction). On the **testing** path a summary/placeholder blocks this gate; on the **observability** path a clearly flagged placeholder is acceptable.

Announce: "Phase 2 complete." Then begin the path's Phase 3: [testing](phase3-testing-metrics.md) or [observability](phase3-observability-ingest.md).
