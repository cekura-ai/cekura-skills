# Phase 6 (testing) — What's Next

> **Start:** Announce the step in plain words (e.g. "Let's connect your agent", "Generating your first evaluators") — never a phase number or the word "Phase"; the numbering below is internal navigation only.

Onboarding is done (Phase 5 gate passed). Offer the depth that was deliberately deferred — each item is an upsell triggered by a real need, not a required step.

## 6a. LiveKit / Pipecat — offer the SDK once, proactively

**This one is not need-triggered: for `provider.type` `livekit` or `pipecat`, offer it after you have shown the results.** Every other row below waits for the user to describe a problem, which they can only do if they already know the data exists. The SDK is the data — without it a run carries only what the provider exposes, so the user never sees what they're missing and never asks. Skip this section entirely for every other provider.

**Order matters: results first, then the offer.** Walk through the run and its failures as usual, then:

> "One upgrade worth knowing about: the Cekura SDK plugs into your agent code and adds what a provider-side run can't see — per-turn STT / LLM / TTS latency, tool-call attribution, session logs, OTel traces, and dual-channel audio. Want me to look at wiring it in?"

**If the repo scan already ran in Phase 2**, say what you'd be editing — the entrypoint is already known, so this is one sentence, not a survey.

**Ask the scope with the offer** (don't inherit it from the Phase 0 path — that answer was about a different question):

> Testing only · Observability only · Both

- **Testing** — `track_*`. Cekura's simulation runs get agent-side data.
- **Observability** — `observe_*`. Real production calls that don't originate from Cekura.
- **Both** — wired to one entrypoint and gated on `CEKURA_MODE`, unless the repo shows separate prod/UAT entrypoints. State which you're doing in the plan and let them correct it.

**Declined → do nothing.** Confirm the results stand on their own, leave `credentials.config.tracing_enabled` at `false`, and don't re-offer.

**Accepted → hand off to `../cekura-create-agent/phase6-sdk-integration.md`** and follow it. This is the sanctioned Phase-6 cross-skill read; the "onboarding is self-contained" rule covers Phases 0–5.

**The SDK pays off on the NEXT run, not the one just shown.** It needs a merged PR, two environment variables and a redeploy before any data flows. Say so in the offer — a user who expects the completed run to gain traces will think it failed.

## 6b. Everything else — need-triggered

| Need the user expresses | Next step |
|------|-----------|
| "Why was this response slow?" / "Show me the agent's tool calls" (LiveKit/Pipecat) | **Cekura SDK integration** — see 6a above; it is offered proactively rather than waiting for this question. |
| Agent calls external APIs and tests need realistic data | **Mock tools** — hand off to **cekura-create-agent** (mock tools phase) / **cekura-eval-design** for mock data design. |
| Agent answers from documents | **Knowledge base upload** — cekura-create-agent KB phase. |
| Per-call data (names, account IDs) | **Dynamic variables** — cekura-create-agent dynamic-variables phase. |
| Better metrics | **cekura-metric-design** skill. |
| More/targeted evaluators (red-team, edge cases) | **cekura-eval-design** skill. |
| Improve metric quality from disagreements | **cekura-metric-improvement** skill. |
| Monitor production | Re-run onboarding on the **observability** path. |
| CI/CD or scheduled tests | GitHub Actions / cron jobs (`cron_jobs_create`). |

Close with a short summary: what was set up, the verified run link, and any flagged open items from Phase 2 (deferred API key, placeholder description).
