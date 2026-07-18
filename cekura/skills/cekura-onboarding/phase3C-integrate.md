# Phase 3C — Integrate your codebase (integrate path)

> **Start:** Announce the step in plain words (e.g. "Let's wire your codebase into Cekura") — never a phase number or the word "Phase"; the numbering below is internal navigation only.

This is the integrate path's one onboarding phase. Shared Phase 2 already gave you a **connected Cekura agent** (a real agent id, plus the connection details Cekura uses to reach it). This phase hands that agent to the integration engine and does not stop until real call data is flowing.

## Why this phase is a handoff, not an inline flow

Wiring a whole codebase into Cekura (config sync, transcript ingestion, per-call metadata, tracing, CI/CD) is a multi-step engineering task with real dependencies between the steps. That work lives in the **`custom-integrate`** skill and the phase skills it coordinates. Onboarding's job here is narrow: confirm the setup, carry the connected agent id in, make sure the one platform-side toggle that the eval sink needs is flipped, and verify the loop lights up. So unlike every other onboarding phase, **this phase deliberately opens a sibling skill** — that is the path, not a detour.

## 3C.a — Gate: this path is for your own code only

The integrate path exists to wire a **codebase** into Cekura. A managed-platform agent has no codebase to wire, so this path does not apply to it. Confirm before going further.

Ask once (skip if Phase 2's provider answer already settled it):

> Is this agent **your own code** we can instrument (custom / self-hosted in any language, LiveKit Agents, or Pipecat), or a **managed platform** agent (VAPI / Retell / ElevenLabs / Synthflow / Bland / ...)?

- **Own code** → continue to 3C.b. Which of the three (custom/self-hosted, LiveKit, Pipecat) becomes part of the profile the engine reads. Every integration phase applies and is done by editing the repo.
- **Managed platform → STOP. The integrate path does not apply; redirect, do not run the engine.** There is nothing to wire: config-sync is redundant (the prompt auto-imports from the provider at Phase 2), metadata and tracing have no publish path or code to instrument, and CI/CD has no deploy of yours. The one phase that fits, evaluators, is exactly what the **testing** path does, and production call logs are the **observability** path, both with native provider ingest. Route the user out:
>   - Wants to simulate calls and grade them → switch to the **testing** path ([phase3-testing-metrics.md](phase3-testing-metrics.md)).
>   - Wants to ingest and score production calls → switch to the **observability** path ([phase3-observability-ingest.md](phase3-observability-ingest.md)).
>
>   Explain briefly why (their provider is already natively supported there) and do not proceed with the integrate phases.

Only own-code setups pass this gate.

## 3C.b — Hand off to the integration engine

Invoke the **`custom-integrate`** skill and hand it the context you already have:

- the connected Cekura agent id (and project id) from Phase 2,
- the own-code setup type from 3C.a (custom/self-hosted, LiveKit, or Pipecat),
- the agent's connection details (how Cekura dials in for simulated runs).

`custom-integrate` runs its own Phase 0 repo profiling and then walks its phase sequence (config-sync → ingestion → metadata → tracing → CI/CD), checkpointing between each. Let it drive that sequence; do not re-implement it here. If the user only wants part of the pipeline, the engine handles partial integrations too.

**Ingestion (Phase 2) is check-and-add by default, not a silent skip.** On start the engine verifies whether transcripts already reach Cekura: it queries the call logs / observe log for recent ingested calls and looks for an existing publisher in the repo. If that check passes, ingestion is a no-op. If it does not, the engine adds a sink and continues, since metadata, tracing, and evals all attach to the published transcript. The user can still explicitly opt out of any phase, including this one; if they decline ingestion, respect it but tell them those later phases won't function until transcripts flow.

**Least-intrusive is non-negotiable.** Everything the engine adds must be strictly additive, off by default (no-ops without the `CEKURA_*` env vars), and never in the call's hot path. This is the customer's production agent.

## 3C.c — Turn on the eval transcript toggle automatically

Whenever the integration wires the **eval webhook sink** (`custom-transcript-provider`, used to replay calls against scenarios and score them), the Cekura agent must have `transcript_provider = "custom"` or simulated runs silently ignore the published transcript. This field is **not settable via the v2 agent API or MCP** (v2 derives it from the provider block and maps custom to empty), so set it with a direct PATCH.

Do this **automatically, without a confirmation prompt** — the user already opted into integration, and it is Cekura-side config that never touches the running bot:

```bash
curl -sS -X PATCH "https://api.cekura.ai/test_framework/v1/aiagents-external/<AGENT_ID>/" \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"transcript_provider":"custom"}'
```

Then **read the agent back and confirm it stuck** (a GET on the same `aiagents-external/<AGENT_ID>/` endpoint returns `transcript_provider: "custom"`). If it did not stick, retry once and, if it still fails, surface the blocker rather than proceeding as if the eval sink will work.

Skip this only when the eval webhook sink is not being wired (e.g. the user wants production observability only). The observe sink does **not** need this flag.

## Phase 3C Gate — end at a verified loop, never at "code written"

Onboarding is not done when files are added or records exist. It is done when **one real (or simulated) call flows all the way through** on the connected agent. Confirm on that one call log:

- the **transcript** ingested (visible in the dashboard),
- the **metadata** is present and PII-free, with `system_prompt` populated,
- the **trace** is linked by `trace_id` and renders the expected span tree,
- if the eval sink was wired, a **simulated run** trust-matched to its `run_id` (proves `transcript_provider = "custom"` is working).

If the inbound simulation connection exists, also kick off the starter **Observability Suite** (the ~10-15 scenario set the engine generates from the synced prompt) so the user sees green/red the same day.

Note what you verified programmatically vs. what still needs a human eyeball (the rendered span tree and audio playback are not checkable via the API). Then confirm the step is done in plain words (no phase numbers) and close with a short summary: what was wired, the verified call/run link, and any flagged open items.
