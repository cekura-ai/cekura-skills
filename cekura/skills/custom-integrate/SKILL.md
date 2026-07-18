---
name: custom-integrate
description: >-
  One-shot orchestrator that wires an ENTIRE voice-AI agent codebase into Cekura
  (eval + observability) end to end — works for ANY repo, ANY language, ANY
  business domain. Use this when someone says "integrate my agent with Cekura",
  "set up Cekura from scratch", "wire up observability and evals", "onboard this
  bot to Cekura", "do the whole Cekura integration", or names several of the
  pieces at once (config sync + metadata + tracing + evals + CI/CD). It first
  PROFILES the repo (language, telephony/recording provider, where the prompt is
  assembled, where calls terminate, deploy mechanism, domain) and then walks the
  phase skills in dependency order with a checkpoint between each so you can
  verify before moving on, plus optional prerequisite sink skills
  (observability and/or custom-transcript-provider, each standalone) for
  repos that don't already ship transcripts to Cekura.
  Dual-channel / speaker-separated recording is surfaced as an option rather than a
  turnkey step — if the user wants it, dive deeper since it's telephony-provider
  dependent. The reference example throughout is a
  speech-to-speech voice agent (e.g. Python/FastAPI/Telnyx/Gemini Live), but
  nothing here assumes that stack. If the user only wants one phase, invoke that
  phase's skill directly instead of this orchestrator.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

<!-- cekura-ack-tag: ack:custom-integrate:9b2t6r -->
> **Cekura skill verification tag:** `ack:custom-integrate:9b2t6r`
> Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="custom-integrate"`, `verification_tag="ack:custom-integrate:9b2t6r"`, and `plugin_version="0.9.0"`. It returns immediately and lets Cekura see which skills are in use. This skill mostly edits the target codebase and calls plain HTTP endpoints; any Cekura metric/scenario writes go through the design skills (`cekura-eval-design` / `cekura-metric-design`) and use their tags.

# Wire a voice agent into Cekura — end to end

## What this skill does

This is the **conductor**. It does not contain integration logic of its own — it
profiles the target repo, then invokes the phase skills below **in order**,
pausing at a checkpoint between each phase so the work can be verified before the
next phase builds on it. Run it when you want the full integration; reach for an
individual phase skill when you only need one piece.

Each phase skill is two-layered: a **durable Cekura contract** (true for any
repo/language/domain) + an **adapt-to-your-stack checklist** + a labeled
**reference implementation** drawn from a typical S2S voice agent. This orchestrator's job is
to feed each phase the repo profile so its adaptation layer has what it needs.

## Why an orchestrator (and why this order)

The phases have real dependencies. Evals/metrics grade against the prompt that
config-sync ships to the agent `description` AND the per-call prompt that metadata
ships; the CI gate assumes evals exist and data is already flowing; everything
needs the Cekura env vars wired (the CD half of `ci-cd`). Doing them out of
order produces half-working integrations that are hard to debug. Follow the order
below unless the repo already has some phases in place (skip those, keep the
sequence).

Do **not** try to do all phases in a single pass without checkpoints. Each phase
should be verifiable on its own before the next phase assumes it works.

## Least-intrusive by default (the overriding constraint)

This is the customer's production agent. Every change must be **strictly
additive** and must never degrade or alter the running bot. This constraint
outranks convenience — when a phase's "easy" implementation would touch the call
path or core logic, find the additive way instead.

- **Off by default.** All Cekura wiring no-ops unless the `CEKURA_*` env vars are
  set; the bot must run byte-for-byte identically without them.
- **Observe, don't restructure.** Wrap/hook existing calls; never reorder the
  call flow or change prompts, tools, or behavior. Don't edit unrelated code.
  When a core-file edit is unavoidable, preserve exact existing behavior (e.g.
  refactor a prompt builder so its output is unchanged).
- **Never in the hot path, never blocking.** Publishing, metadata, and tracing
  are fire-and-forget with swallowed errors — a Cekura failure is a WARNING, not
  a surfaced error, and never touches call teardown.
- **Decoupled from the app's own config.** Don't import the app's fail-fast
  config into the Cekura code (it can hard-exit on missing keys and kill CI /
  imports — see `ci-cd`). Read `CEKURA_*` from their own small config.
- **Prefer new files + guarded hooks** over edits to core files. Cekura-side
  config (agent settings, `transcript_provider`) is safe to change — it never
  touches the running bot — but still change only what's needed.
- **Group the files you add; don't scatter them.** Put new integration modules in
  a dedicated, clearly-named folder (e.g. `src/cekura/` — publishing, tracing,
  recording, config) rather than loose among the customer's source root, so the
  integration is one obvious, reviewable, removable unit. Put test files in the
  repo's existing test location (a `tests/` dir, `__tests__`, or its colocated
  `*.test` convention — match what's there); create a `tests/` folder if the repo
  has none. Reuse existing folders when one fits (deploy config sync → its own
  `scripts/…` dir, workflows → `.github/workflows/`) instead of inventing parallel
  ones. Update imports / test globs / build config after moving.

## Phase 0 — Profile the repo (do this first, always)

Before invoking any phase skill, establish the profile. Read the repo (or, for a
managed platform, the agent's dashboard/config) and answer:

0. **Which setup is this? (branch first)** — the rest of the orchestration adapts
   to one of:
   - **Custom / self-hosted code (any language)** — you own the agent process and
     can edit code in Python, Node, Go, Java, etc. Every phase applies and is
     done by editing code.
   - **LiveKit Agents** — agent runs in the LiveKit Agents framework; phases are
     done in that framework's hooks/handlers.
   - **Pipecat** — agent runs as a Pipecat pipeline; phases attach to pipeline
     processors and lifecycle events.
   - **Managed platform (Vapi / Retell / ElevenLabs)** — no agent process you
     control. There is often **no codebase to edit**; config-sync, transcript
     publishing, tracing, and recording may be handled by the platform itself or
     by Cekura's provider integration. Route those sub-steps to the managed path
     (configure on the platform / verify Cekura's native ingest) rather than
     assuming code exists to change.

   Self-select here and read every later step through this lens: where a step says
   "edit/instrument code," a managed platform usually means "configure on the
   platform or rely on Cekura's provider integration."
1. **Language & framework / platform** — what is the agent built on? (Python/
   FastAPI, Node, Go, etc.; or LiveKit Agents, Pipecat; or a managed platform.)
   Decides which reference snippets translate directly vs. need porting — and
   whether a phase is a code change at all vs. a platform/dashboard setting.
   **If Python:** the official `cekura` SDK/CLI (`pip install cekura`) already wraps
   the transport for several phases — observe publish (`client.calls.send` /
   `cekura calls send`, see `observability`), config-sync (`agents` resource /
   `cekura agents`, `cekura config`, see `config-sync`), and running the eval suite
   in CI (`cekura run …`, see `ci-cd`). Prefer it over hand-rolled HTTP. **LiveKit /
   Pipecat** additionally get turnkey tracers (`cekura.livekit.tracer` /
   `cekura.pipecat.tracer`) — use those instead of hand-instrumenting (see
   `tracing`). Everything the SDK doesn't wrap (generic OTel tracing, the generic
   eval webhook, metadata assembly) still follows the manual contract.
2. **Architecture: pipeline vs speech-to-speech** — discrete STT → LLM → TTS
   calls, or a single speech-to-speech model (Gemini Live, etc.)? Changes which
   OTel spans to emit (`tracing`).
3. **Telephony / recording provider** — Telnyx, Twilio, Vonage, LiveKit,
   in-house? Decides where calls start/end and whether dual-channel recording
   applies. **ASK whether they want call audio recorded and sent to Cekura**
   (the `voice_recording_url` on the observe payload) — it unlocks audio playback
   in the dashboard plus audio-based metrics (interruptions, latency, talk-over)
   that a transcript alone can't score. It's opt-in, not automatic. Most
   telephony providers make basic recording trivial — e.g. Twilio's
   `record="record-from-answer"` / a recording status callback, or Telnyx call
   recording — so basic mono recording is usually a small, low-risk add. If they specifically
   need reliable caller-vs-agent speaker separation (dual-channel recording),
   **flag it as an option** — there is no turnkey path for it here. How to capture
   separate caller/agent channels depends heavily on the telephony provider, so
   dive deeper into that provider's recording capabilities to work out how before
   committing to it. **Audio is a privacy/compliance opt-in —
   some users specifically do NOT want call audio recorded or sent to a third
   party.** Keep it **off by default**, gated behind its own flag (e.g.
   `RECORD_CALLS`), and only enable it when the user explicitly asks. If they
   don't want recordings, leave `voice_recording_url` unset (it's
   omitted-when-empty) and move on.
   - **Explicit question to ask (default = NO for any PHI/health/regulated
     domain):** "Should call **audio** (the `voice_recording_url`) be sent to
     Cekura **observability**?" Treat this as its OWN decision, separate from
     sending the transcript/metadata — the transcript can flow while audio does
     not. The recording URL is itself PHI leaving the box, so for healthcare and
     other regulated domains **default to NOT sending it even when the telephony
     provider already has a recording available**, and only send after the user
     explicitly confirms it's acceptable (e.g. BAA-covered). Ask this per sink
     (observe vs eval) since a customer may allow it for one and not the other.
     Don't assume "recording exists" implies "send the recording."
4. **Where a call terminates** — what hook fires at hangup? That's where
   transcript publishing is triggered (if you need to wire a sink skill —
   `observability` and/or `custom-transcript-provider`).
5. **Are transcripts already flowing to Cekura? VERIFY, don't assume.** This is a
   real check, not a yes/no you guess. Confirm with two signals: (a) query the
   Cekura call logs / observe log for this agent or project and see whether recent
   calls have actually ingested, and (b) look in the repo for an existing publisher
   (a POST to the observe API or the custom-provider webhook, or a Cekura-native
   provider integration). If the check is positive, ingestion is satisfied and
   Phase 2 is a no-op. If it is negative, the default is to **add it and continue**
   (metadata, tracing, and evals all need transcripts flowing); the user can still
   explicitly decline it, in which case skip but warn those later phases won't
   function. Which sink(s): `observability` for prod call logs,
   `custom-transcript-provider` for the eval pipeline, or both. Each is standalone.
6. **Where the system prompt is assembled** — one template? Many partials?
   Config branches? Drives `config-sync` (sync the assembled prompt to the
   agent `description`) and `metadata` (snapshot the rendered per-call prompt).
7. **Where tools/functions are defined and called** — for tool spans
   (`tracing`), the deploy-time mock-tool sync (`config-sync`), and the CI
   gate's invariant checks (`ci-cd`).
8. **Deploy mechanism** — GitHub Actions? Cloud Run? Something else? How are env
   vars injected? Decides `config-sync` (the post-deploy sync step) and
   `ci-cd`'s CD half (env-var wiring + per-env gating).
9. **Domain & PII** — what is the business domain, what dimensions are worth
   slicing evals by, and what fields count as PII (must NOT ship to Cekura)?
   Drives `metadata`.
10. **What already exists** — is any OTel/tracing, recording, or Cekura wiring
    already present? Add to it; never rip out and replace.
11. **How will Cekura place a *simulated* call INTO this agent?** Everything else
    in this skill is about publishing and grading the agent's **real** calls.
    The starter eval suite and the CI gate (Phase 5) additionally need Cekura to *drive*
    simulated calls into the agent — and the phases below **assume that inbound
    connection already exists without setting it up.** Establish it here:
    - **Telephony agent (Twilio / Telnyx / Vonage / SIP) — the common case:**
      Cekura dials the agent. Two supported mechanisms (docs:
      `key-concepts/phone-numbers/twilio`, `integrations/sip-integration`):
      - **Imported phone number.** In the Cekura dashboard, Settings → Phone
        Numbers → import your Twilio number (Account SID, Auth Token, E.164), then
        set it as the agent's **Contact Number**. Cekura routes test calls
        through that number to the agent — exercising the real telephony → media
        path with **zero transport changes** (the recommended path for an agent
        that already answers a Twilio number).
      - **SIP endpoint.** Configure the agent's SIP URI (`sip:…`, optional
        digest auth). Cekura sends a **SIP INVITE** and injects `X-Run-Id`,
        `X-Scenario-Id`, `X-Result-Id` headers you can read to correlate the run.
    - **No telephony leg** (web-widget / raw-websocket bot): use a websocket or
      other Cekura connection type, which usually means exposing a
      **Cekura-protocol** endpoint or a framing adapter — your telephony
      provider's own websocket framing (e.g. Twilio Media Streams) is **not**
      directly dialable by Cekura's websocket runner.

    This connection is configured with the **`cekura-create-agent`** skill
    (connection type), **NOT** by any integration phase — treat it as a **prerequisite for
    the starter eval suite and the Phase 5 CI eval-gate**. It is independent of
    transcript publishing: real-call observability (Phases 1–4) works even when no
    simulation connection exists.

Capture this profile and carry it into every phase invocation. If the repo
closely matches the reference stack, the reference sections already match; otherwise
translate.

## Optional extras (recording — company-dependent)

Audio recording is not a phase, it is a pure opt-in that many integrations skip.
Wire it only if the user asks. Ingestion itself is now **Phase 2** of the sequence
below.

> **Managed platforms (Vapi / Retell / ElevenLabs):** transcript publishing and
> recording are typically handled by the platform and Cekura's provider
> integration, not by code you write. Verify Cekura is already ingesting calls
> from that provider; if so, **Phase 2 (ingestion) is a no-op** and you skip the
> code-publisher path entirely.

| Extra | When you need it | Verify |
|---|---|---|
| Basic audio recording | The user **wants call audio in Cekura** (playback + audio-based metrics) and it isn't already flowing. Not a separate skill: enable the provider's recording (Twilio `record` / recording status callback, Telnyx call recording, …), then pass the resulting URL as `voice_recording_url` in the publish (`observability` owns that field + the recording-wait). **Ask the user — it's opt-in.** | The call log has a playable recording |
| Dual-channel recording *(deeper dive — no turnkey skill)* | The user needs reliable **speaker attribution** (caller vs agent on separate audio channels) and basic mono recording isn't enough. Flag it as an option; if they want it, investigate how their telephony provider exposes separate caller/agent channels before implementing. | Recording attributes speakers correctly |

## The phase sequence

Invoke each skill below in order. **The user can opt out of any phase** — if they
explicitly don't want one, skip it and note what it costs. But the default is not a
silent skip: **for Phase 2 (ingestion) you always check on start and, if it isn't
already set up, add it and continue** (it's the foundation the later phases attach
to). The Phase 5 CI eval-gate is an opt-in (it needs a generated eval suite and the
inbound sim connection), and on a managed platform several phases are no-ops. So: do
the phases that apply, honor explicit opt-outs, and never skip Phase 2 by
assumption — check, and add it if missing. After each, run its own spot-check, then checkpoint with
the user before continuing. The "Produces" column describes the outcome to achieve,
not the mechanism: on custom code / LiveKit / Pipecat you achieve it by
instrumenting the agent; on a managed platform you achieve the same outcome through
platform config or Cekura's provider integration.

| Phase | Skill to invoke | Produces | Verify before continuing |
|---|---|---|---|
| 1 | `config-sync` | Dynamic vars + mock tools + assembled prompt PATCHed to the Cekura agent at deploy | A deploy runs the sync; the agent `description`/vars/tools match code |
| 2 *(auto-check on start; add if missing)* | `observability` and/or `custom-transcript-provider` (`sinks-publisher` = chooser) | End-of-call transcripts reaching Cekura: the observe sink (prod call logs) and/or the eval webhook (scenario replay/scoring). This is the foundation metadata + tracing attach to. **Always run the check (Phase 0, item 5) first**: if calls already ingest, it's a no-op; if not, add it and continue. The user may still explicitly decline it. Each sink is standalone; the "both" setup splits observe on prod, eval webhook on sandbox, by `CEKURA_ENVIRONMENT`. | Either the check found existing ingestion, or a finished call now appears in the observe log and/or the eval webhook (or the user explicitly opted out). |
| 3 | `metadata` | System prompt + domain flags + non-PII signals stamped on the call sinks | Metadata fields show on the call; no PII leaked; `system_prompt` populated |
| 4 | `tracing` | One OTel trace per call, exported to Cekura, linked by `trace_id` | A trace appears and links to its call log; spans match the architecture (pipeline vs s2s) |
| 5 | `ci-cd` | CI gate (eval suite + language-side invariant checks the sim can't see) **and** CD deploy env wiring (CEKURA_* vars + per-env gating) | Gate runs and reports pass/fail; tool-ordering invariants checked from local logs; each environment hits the right sink with its own agent id |

> **Phase 2 (`ingestion`) is the foundation, so the default is check-and-add, not
> skip.** Metadata (Phase 3) threads into whichever sink you publish, and
> tracing-linkage (Phase 4) rides on the published transcript, so the later phases
> only work once transcripts reach Cekura. So **on start, always run the check
> first** (Phase 0, item 5): query the Cekura call logs / observe log for recent
> ingested calls AND look for an existing publisher in the repo (or a Cekura-native
> provider integration). If that check passes, ingestion is already satisfied and
> Phase 2 is a no-op. If it does not pass, **add it and continue** — do not silently
> move on. The user can still explicitly opt out of this (or any) phase; if they
> decline ingestion, respect it, but tell them metadata, tracing, and evals won't
> function until transcripts flow.

> **Evaluators are generated via the kickstart, not a dedicated phase here.** This
> engine no longer has an eval-authoring phase; the **kickstart** below generates a
> starter suite with the Cekura eval skills (`cekura-eval-design` /
> `cekura-metric-design`), pointed at the synced prompt. Running that suite, and the
> CI eval-gate in Phase 5, needs the inbound simulation connection (Phase 0, item
> 11) and is a separate opt-in: skip it when the user only wants observability,
> hasn't set up the inbound dial-in, or maintains evals elsewhere. If there is no
> eval suite, Phase 5's **CI eval-gate** half has nothing to run — keep the rest of
> Phase 5 (CD env wiring + language-side invariant checks).

> **`ci-cd`'s CD half is plumbing the earlier phases depend on.** The Cekura
> env vars (`CEKURA_API_KEY`, `CEKURA_AGENT_ID`, `CEKURA_PROJECT_ID`,
> `CEKURA_ENVIRONMENT`, `CEKURA_ROUTE_TO`, `CEKURA_OTEL_ENDPOINT`) must exist for
> Phases 1–4 to function. So in practice you wire each env var the moment a phase
> first needs it (using `ci-cd`'s "CD half" as the catalog), and only
> *finalize* the gating + the CI eval gate at Phase 5 — the eval-gate genuinely
> comes last because it needs a generated eval suite to exist (skip the eval-gate
> if there is none; the CD wiring + invariant checks still apply). On a managed platform
> with no deploy pipeline of your own, these env vars live wherever you run the
> eval suite / sync job from (CI, a script, or the platform's own settings) rather
> than in an app you deploy.

> **The simulated-call phases need the inbound connection (Phase 0, item 11).**
> The starter eval suite and Phase 5's CI eval-gate run *simulated* calls, so Cekura must be
> able to dial the agent. For a telephony agent that means the agent's phone number
> / SIP is registered on Cekura (via `cekura-create-agent`) and Cekura calls it.
> Confirm this connection works — place one test call from Cekura — before
> running the suite or wiring the eval-gate. Phases 1–4 (config-sync, ingestion, metadata, tracing) and Phase 5's CD env wiring + language-side invariant checks do
> NOT need it, so they proceed even when the eval-gate is skipped.

> **Why config-sync is Phase 1.** Evaluators read section
> headings off the agent `description`, which `config-sync` populates. Syncing the
> prompt early means the section catalog is in place before you author
> prompt-anchored evals (with `cekura-eval-design`). Metadata (Phase 3) then ships
> the *per-call rendered* version of that same prompt, which the evals inject via
> `{{metadata.system_prompt}}`.

## How to run a phase

For each phase: (1) state the phase and what it depends on; (2) invoke the phase
skill, handing it the Phase-0 profile (including the setup branch); (3) realize the
change in the target's own style — edit code in the repo's idioms for custom /
LiveKit / Pipecat setups, or apply platform config / confirm Cekura's provider
integration for a managed platform (do not restructure unrelated code, and never
fabricate a codebase that isn't there); (4) run that skill's spot-check; (5)
**checkpoint** — summarize what landed and confirm before the next phase. If a
phase is already present (in the repo or handled by the platform), verify it meets
the contract and move on.

**Commit once before you start — not at every phase.** Before beginning the phase
sequence, make sure the repo is in a clean, committed state so the entire
integration lands as a clearly separable, revertible set of changes on top of a
known baseline. You do NOT need a commit per phase — that's needless churn; the
checkpoints are for verification, not commits. Respect the user's git rules:
commit only with explicit approval, work on a branch rather than the default
branch, and never push or open/modify a PR without being asked.

## Final acceptance (after the last phase)

Per-phase checkpoints verify each piece in isolation; finish with ONE check that
the whole thing lights up together. Drive a single call — a real one, or a
simulated one if the inbound connection exists — and confirm on that one call
log: the **transcript** ingested, the **metadata** (incl. `system_prompt`) is
present and PII-free, the **trace** is linked by `trace_id` and renders the
expected span tree, and the **recording** plays if recording was opted in. Each
phase can pass alone yet still not compose (e.g. `trace_id` set but never
exported, metadata shipped but empty) — this closing pass catches that. Note what
you verified programmatically vs. what still needs a human eyeball (the rendered
span tree and audio playback aren't checkable via the API).

## Kickstart: generate a starter eval suite (so they can test immediately)

Wiring is only half the value — finish by handing the customer a ready-to-run
test suite so they can start testing the **same day** instead of authoring
scenarios from scratch. Do NOT build eval logic here or hand-write scenarios:
**delegate to the existing Cekura eval skills**, pointed at the agent's own
prompt (this is also the house rule — route all evaluator/metric creation through
the dedicated Cekura skills, never ad-hoc).

- **Source of truth = the agent's synced prompt.** After Phase 1 the flattened
  prompt lives on the Cekura agent `description`; feed that + the mock tools +
  the Phase-0 domain to the generator so the scenarios match what the agent
  actually does.
- **Invoke the Cekura eval-generation skill** — e.g. `cekura-eval-design` (or the
  `eval-suite-planner` agent / `autogen-eval`); resolve it by base name since the
  MCP/plugin prefix varies. Ask it for a **starter suite of ~10–15 scenarios**:
  the core happy-path flows, a few realistic edge cases, and 1–2 red-team /
  adversarial cases. Enough to exercise the agent right away, not exhaustive.
- **Group them in a scenarios folder named `Observability Suite`.** Create the
  folder (`scenarios_folder_create`, or reuse it if it exists) and put the
  generated scenarios in it, so this starter set is discoverable and clearly
  separated from the customer's own scenarios rather than dumped loose at the
  project root.
- **Generating ≠ running.** The suite is generated from the prompt with no live
  call, but **running** it needs the inbound simulation connection (Phase 0,
  item 11) — confirm the dial-in works, then kick off the first run so they see
  green/red immediately.

This quick-start is the engine's eval story: it hands over a runnable suite fast,
generated from the synced prompt with the Cekura eval skills. For deeper,
prompt-section-anchored authoring plus quality metrics, use `cekura-eval-design` and
`cekura-metric-design` directly — that is not a phase in this engine.

## Partial integrations

If the user only wants part of the pipeline, skip the orchestrator and invoke the
specific phase skill(s) directly — they each stand alone. Use this orchestrator
only for the full end-to-end wiring or when the user explicitly wants "the whole
thing."

## Common mistakes to avoid

- **Skipping Phase 0.** Without the profile, every phase guesses at the
  stack and the reference snippets get copied verbatim instead of adapted.
- **Not branching by setup.** Treating a managed platform (Vapi / Retell /
  ElevenLabs) like a codebase — hunting for files to edit when transcript
  publishing, tracing, or recording are already handled by the platform or
  Cekura's provider integration. Route those sub-steps to the managed path.
- **Running phases out of dependency order.** Evals before config-sync/metadata
  (no section catalog, no `system_prompt` to inject), gate before evals,
  tracing-linkage before tracing — all produce broken half-states.
- **Forgetting the optional prerequisites.** If transcripts aren't already
  reaching Cekura, metadata and trace-linkage have nothing to attach to — wire the
  sink skill(s) first (`observability` and/or `custom-transcript-provider`).
- **No checkpoints.** Verify each phase against its own spot-check before the
  next one builds on it.
- **Not committing a baseline before starting.** Beginning the integration on top
  of a dirty tree makes the whole set of changes hard to separate and revert.
  Commit (or have the user commit) once before starting — but don't force a
  commit at every phase; that's needless churn.
- **Copying the reference code verbatim** into a different stack.
  The durable contract is what carries over; the Python/Telnyx/Gemini specifics
  are examples.
- **Intrusive changes that risk the running agent.** Editing the call flow,
  changing prompts/tools/behavior, importing the app's fail-fast config into
  Cekura code, or doing publish/trace work in the hot path. Keep it additive and
  off-by-default (see "Least-intrusive by default").
- **Replacing existing wiring.** If the repo already has OTel, recording, or a
  Cekura sink, extend it — don't tear it out.
- **Shipping PII.** `metadata`'s PII boundary is non-negotiable regardless of
  domain.
