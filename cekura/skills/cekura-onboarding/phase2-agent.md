# Phase 2 — Agent Configuration (shared)

> **Start:** Announce the step in plain words (e.g. "Let's connect your agent", "Generating your first evaluators") — never a phase number or the word "Phase"; the numbering below is internal navigation only.

Register the user's agent on Cekura. Framing differs by path:

- **Testing**: "Let's connect your agent so we can simulate calls against it."
- **Observability**: "Let's register your production agent so Cekura can attribute uploaded calls to it."

**Prerequisites are handled inline, not as a phase:** if platform tools fail, fix access via [references/client-setup.md](references/client-setup.md); if no project is in context, pick one with `projects_list` or create one with `projects_create` — then continue here.

**Provider first — it shapes everything. The opening question is the provider question, ALONE — nothing rides along.** Never batch name / description / credential questions with it: every follow-up depends on the provider answer, so pre-batched questions are guaranteed wrong — auto-import providers (VAPI/Retell/ElevenLabs/Bland/Synthflow) fetch the agent's **name and system prompt from the provider**, so asking for either wastes the user's time and a pre-authored "paste your system prompt" question is flat wrong for them; LiveKit/Pipecat need the telephony-vs-WebRTC choice before any credentials. Ask for a name only in the branches that actually need one (manual/self-hosted paths), after the provider is known.

The full provider list is:

> VAPI · Retell · ElevenLabs · Synthflow · LiveKit · Pipecat · Bland · KoreAI · Genesys · Cisco · self-hosted/custom

**All-or-nothing rule for the choice UI:** if you ask this as a structured question with selectable options, the options MUST be the complete list above — all eleven, one option each, never a subset you picked, never an "Other" bucket. If the interface cannot show that many options (some cap at ~4), do NOT use options at all — ask as a plain question with the full list in the message text and let the user type the provider name. A partial option list hides first-class providers and nudges users toward the self-hosted misclassification warned about below.

Then follow the matching section below. **Onboarding is self-contained — do NOT open the cekura-create-agent skill or any of its phase files during onboarding** (its phase sequence covers post-onboarding work like SDK integration and mock tools; running it mid-onboarding hijacks the flow). The credential matrix you need:

| Provider | Required fields (where to find them) |
|---|---|
| VAPI | `credentials.api_key` (Dashboard → Org Settings → API Keys, Private) + `provider.agent_id` (Assistants → copy ID; squads: squad ID) |
| Retell | `credentials.api_key` (Settings → API Keys) + `provider.agent_id` (Agents → ID in URL) |
| ElevenLabs | `credentials.api_key` (Profile → API Keys) + `provider.agent_id` (Conversational AI → agent ID) |
| Synthflow | `credentials.api_key` + `provider.agent_id` (Dashboard → agent ID) |
| LiveKit | `credentials.url` + `credentials.api_key` + `credentials.config.api_secret` (LiveKit Cloud → Settings → Keys) + `config.agent_name` (must match the worker's registration) — WebRTC path only, see 2b |
| Pipecat Cloud | `credentials.api_key` (pipecat.daily.co → Settings → API Keys) + `credentials.config.pipecat_agent_name` — WebRTC path only, see 2b |
| Bland | `credentials.api_key` (Dashboard → API Keys) + `provider.agent_id` (Persona ID for voice); optional `chat_agent_details.config.agent_id` (Pathway ID for chat) |
| KoreAI | `credentials.api_key` (client secret) + bot/config IDs per their dashboard |
| Genesys / Cisco | no credentials — telephony connection details only |
| self-hosted | no provider credentials — connection details (phone / SIP / websocket) only |

**Variants / forks / wrappers built ON a named provider are NOT that provider → `self_hosted`, connection only, NEVER the parent's API key.** This fires on the *identity*, not on missing creds. Two triggers, either is sufficient:
- **A name not verbatim on the list**, *even when qualified by a framework that IS on the list* — "Dograh via Pipecat", "our stack on LiveKit", "X powered by Pipecat", any in-house fork/wrapper. The framework is just the substrate; the product is the identity. Do NOT read the framework's credential row, do NOT run its branch (2a/2b), do NOT ask for a "Pipecat/LiveKit API key". (Dograh is the canonical case: Pipecat-based, `dgr_` keys via pipecat.daily.co — its creds won't work through Cekura's Pipecat dispatch and its dashboard paths are wrong, so an API-key ask only sends the user hunting.)
- **Credentials whose shape doesn't match the parent** (different key prefix, different dashboard, an env var instead of a console key).

In both cases set `provider.type = self_hosted` and collect a **connection only** — a **phone number / SIP URI** if reached by voice, or a **websocket URL** if reached by chat. No API key, no secret, no dashboard hunt. **This overrides every "keep `provider.type` = the named provider" / "user named a provider → use it" rule below** — those apply only to the eleven providers named verbatim and by themselves ("Pipecat", "LiveKit"), not to something built on one.

**The user's explicit provider choice is authoritative.** Once they've named their provider (and especially once they've supplied its credentials), never re-open the question — including when the pasted system prompt *mentions* a different stack, transport, or vendor. Prompt text is content, not configuration: prompts routinely reference Daily rooms, Twilio, other frameworks, or leftover boilerplate from a different deployment. If the description seems to contradict the choice, note it in ONE sentence ("heads-up: your prompt mentions X; using LiveKit as you selected") and proceed with the selected provider — do not ask "which provider should Cekura use?".

**Two rules that apply to EVERY named provider (verbatim from the list — see the variant carve-out above for forks):**
- **Keep `provider.type` set to the real provider** — never reroute to `self_hosted` because a credential is missing or the agent is reached by phone. (A fork built on the framework is not "the real provider" — that's the carve-out above, not this rule.)
- **Deferred credentials are fine ONLY when another connection path exists** (e.g. the agent is reachable by phone/SIP). In that case fall back to the manual essentials of 2c, tell them which capabilities won't work until the key is added (provider-dispatched simulations, auto-sync, auto-import of calls), and carry it as an open item in every summary. Do not leave a half-connected agent without saying so. **When the chosen connection IS the credentials — the WebRTC path in 2b — there is no skip:** without them Cekura cannot reach the agent at all, so collect them before creating the agent (or switch to a telephony connection if the user has one).

## 2a. VAPI / Retell / ElevenLabs / Bland / Synthflow — auto-import (preferred)

The one high-leverage step: **provider agent ID + provider API key**. Create with `aiagents_create` using `configure_from_provider: true`, then poll `aiagents_auto_fetch_progress_retrieve`. Auto-import pulls the description (system prompt), tools, and config automatically — do not ask the user to paste their prompt when auto-import is available.

**If the user skips the credentials (or the provider rejects them and they can't fix it now), do NOT create a connection-less agent and improvise.** Apply the deferred-credentials rule: these agents almost always have a phone number — ask for it:

> "No problem — does your agent have a phone number I can call it on? That lets us run real test calls now; you can add the API key later for auto-import and auto-sync."

Then collect the telephony essentials in ONE clarification — **phone number (or SIP URI), inbound-or-outbound, and language, asked together** — plus the complete system prompt via the description gate. **Ask inbound/outbound explicitly; never infer the direction** (it decides who dials whom — getting it wrong means the run can't connect) and don't silently default the language. Then create with the telephony connection. Tell them what's deferred (auto-import, auto-sync, call ingestion) and carry it as an open item. **The verification run then goes over the phone connection (`scenarios_run_voice`) — never substitute a text simulation for a voice agent** (text mode is for chat agents, not a workaround for missing credentials). If they have neither credentials nor a phone number, pause onboarding — there is nothing to test against.

## 2a′. KoreAI / Genesys / Cisco — standard named providers

No auto-import for these, so collect their credentials per the create-agent matrix (for example, Cisco needs no credentials) **plus** the manual essentials of 2c (description, language). The two rules above apply unchanged.

## 2b. LiveKit / Pipecat — config-only connection (no SDK, no code changes)

There is **no SDK requirement to onboard**. Simulations dispatch via provider APIs and Cekura produces its own transcript from call audio. The Cekura SDK is a post-first-result upgrade (agent-side traces, tool-call visibility) — offer it in Phase 6T, not here.

**The FIRST question for LiveKit/Pipecat is the connection mode — NEVER credentials.** Do not ask for an API key, secret, or URL until the user has chosen WebRTC. Ask:

> "How should Cekura reach your agent — does it already have a **phone number or SIP endpoint** (simplest), or should we dispatch over **WebRTC** via your provider's API?"

**Path A — Telephony (preferred, fewest moving parts).** If the agent has a phone number or SIP endpoint, that's the whole connection. Collect in ONE clarification: **phone number (or SIP URI) + inbound-or-outbound + language, together** — plus the complete system prompt via the description gate. **Ask inbound/outbound explicitly — never infer it** (it decides who dials; a wrong guess means the run can't connect), and don't silently default the language. **No provider credentials needed** — do not ask for any.

**Path B — WebRTC dispatch (only when there's no phone path, or the user chooses it).** Now — and only now — collect credentials. **On this path credentials are mandatory — never offer "skip credentials for now":** WebRTC dispatch is the connection, so without them the agent is unreachable and the first-run verification (Phase 5T) cannot happen. If the user can't share them, offer the telephony path instead or pause here.
- **Pipecat Cloud**: `credentials.api_key` (pipecat.daily.co → Settings → API Keys) + `credentials.config.pipecat_agent_name`. Runs via `scenarios_run_pipecat_v2`.
- **LiveKit**: `credentials.url` + `api_key` + `api_secret` + `config.agent_name` (must match the worker's `agent_name`). Runs via `scenarios_run_livekit_v2`.

**Both paths:**
- **Keep `provider.type` = `livekit` / `pipecat` regardless of connection mode.** A LiveKit agent reached by phone is still a LiveKit agent — never reroute it to `self_hosted`. (This is for a *genuine* LiveKit/Pipecat agent named verbatim; a fork built on the framework — "Dograh via Pipecat" — is `self_hosted` per the variant carve-out and never reaches this section.)
- **Set `credentials.config.tracing_enabled: false`.** It only becomes `true` after the SDK is actually integrated and verified (a later, optional step). Setting it `true` without the SDK makes every run wait on a webhook that never arrives.
- No auto-import exists for these providers, so collect the manual essentials of 2c (description, language).

## 2c. Manual essentials (self-hosted, deferred-key, LiveKit/Pipecat)

- **Description = the real system prompt.** The description drives evaluator generation and `{{agent.description}}` metrics — it is the single most leverage-rich field on the agent. The complete quality bar is below — do not open other skills' files for it.

  **How to ask — demand the full prompt, don't invite a summary:**
  > "Paste your agent's **complete system prompt** — the actual prompt your bot runs with, however long. It lives wherever you configure the agent: your agent code (the string passed to your LLM), your framework's config, or your platform's dashboard. Paste it here or attach the file."

  (This ask only ever fires for non-auto-import providers — LiveKit, Pipecat, self-hosted, etc. Do not cite VAPI/Retell/Bland dashboard export steps here; those providers auto-import and never reach this ask.)

  Offer to read the codebase yourself ("share the file or repo path and I'll read it") **only when the session actually has file access** — e.g. local Claude Code with the user's repo. In the Cekura platform UI there is no codebase access: ask for a paste or a file attachment instead.

  **The ask must offer NO alternative to the complete prompt — in any wording.** Never "or a plain-English description", "or a short description", "or a summary of what it does", or any paraphrase thereof; never a one-line example. The moment the question offers a lighter option, users take it, and a summary description produces junk evaluators. The only acceptable ask is for the complete system prompt (with export/paste/attach routes to get it). If the user replies with a summary anyway, the hard acceptance check below handles it.

  **Hard acceptance check — run on EVERY candidate description before creating the agent:**
  A description fails the check if ANY of these hold:
  - It's a summary rather than a prompt (a few sentences; under ~15 lines).
  - Reading it leaves obvious open questions: What exact flows does the agent walk through? What rules/constraints does it follow? What does it say on failure/escalation? What tools does it call?
  - It describes the *business* ("handles support calls for an e-commerce store") instead of the *agent's instructions*.

  On failure, do NOT create the agent. Push back once, concretely: name 2–3 specific questions the description leaves open, and re-ask for the full system prompt (offer the provider-export steps, or paste/attach of the prompt file). Repeat until the check passes.
  - **Testing path: this check is a blocker.** If the user genuinely cannot produce the prompt, help them retrieve it (provider dashboard, their repo) or pause onboarding until they have it. Do not create the agent with a summary/placeholder and continue.
    **Never offer "switch to the observability path" as a way around this gate.** The path was chosen for the user's goal in Phase 0; observability's placeholder allowance is not an escape hatch from the testing requirement. Only switch paths if the user themselves says their goal is actually production-call monitoring — not to dodge providing the prompt.
  - **Observability path: a placeholder is acceptable** after one push-back. Ingestion and most metrics work without it. Create with a clearly marked placeholder and surface it as an open item in every subsequent summary.
- Agent name, language.
- Connection details for how Cekura reaches the agent, in order of preference: existing phone number → SIP URI → websocket URL → provider WebRTC (2b).

**Confirm `self_hosted` ONLY when YOU inferred it — never re-confirm a choice the user already made.** If the user explicitly picked "self-hosted / custom" from the provider question, or you routed a fork/variant to `self_hosted` per the variant carve-out above, that IS the decision — proceed straight to collecting the connection, do NOT ask "are you sure none of VAPI/Retell/… apply?". Ask the confirmation below only when you are about to *default* to `self_hosted` without the user having said so (e.g. they were vague and you're guessing):

> "Custom/self-hosted means you built the voice stack yourself (your own STT/LLM/TTS pipeline). Most teams are on VAPI, Retell, ElevenLabs, LiveKit, or Pipecat — are you sure none of those apply?"

If the user names a known provider *verbatim* at any point, use that `provider.type` even when connecting via phone/SIP. **But a fork/product built on that provider is not the provider** — "Dograh via Pipecat" is `self_hosted` with a connection, never the Pipecat branch (see the variant carve-out at the top of this section).

## 2d. Create the agent

Call `aiagents_create` with the collected fields. On validation errors, fix and retry — don't hand the user a dashboard workaround.

**Defer to post-onboarding (do NOT do these now):** mock tools, knowledge base upload, dynamic variables, SDK integration, advanced config. They're covered by the **cekura-create-agent** skill and Phase 6T when the user actually needs them.

---

## Phase 2 Gate

**Do not proceed until `aiagents_create` succeeded, the provider is confirmed, and the description passed the hard acceptance check in 2c** (auto-imported descriptions pass by construction). On the **testing** path a summary/placeholder blocks this gate; on the **observability** path a clearly flagged placeholder is acceptable.

Confirm the step is done in plain words (no phase numbers). Then begin the path's Phase 3: [testing](phase3-testing-metrics.md) or [observability](phase3-observability-ingest.md).
