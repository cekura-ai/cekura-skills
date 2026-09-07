# Phase 6 (testing) — What's Next

> **Start:** Announce the step in plain words (e.g. "Let's connect your agent", "Generating your first evaluators") — never a phase number or the word "Phase"; the numbering below is internal navigation only.

Onboarding is done (Phase 5 gate passed). Offer the depth that was deliberately deferred — each item is an upsell triggered by a real need, not a required step.

**LiveKit / Pipecat agents came through `cekura-livekit-pipecat-onboarding`, which already offered the SDK.** When that skill exits here — finished, or the user declined somewhere — write the closing summary below and do **not** re-pitch the SDK; the table row is enough.

| Need the user expresses | Next step |
|------|-----------|
| "Why was this response slow?" / "Show me the agent's tool calls" (LiveKit/Pipecat) | **Cekura SDK integration** — `cekura-livekit-pipecat-onboarding` phase5-sdk-pr.md, post-first-result only. Not cekura-create-agent. |
| Agent calls external APIs and tests need realistic data | **Mock tools** — hand off to **cekura-create-agent** (mock tools phase) / **cekura-eval-design** for mock data design. |
| Agent answers from documents | **Knowledge base upload** — cekura-create-agent KB phase. |
| Per-call data (names, account IDs) | **Dynamic variables** — cekura-create-agent dynamic-variables phase. |
| Better metrics | **cekura-metric-design** skill. |
| More/targeted evaluators (red-team, edge cases) | **cekura-eval-design** skill. |
| Improve metric quality from disagreements | **cekura-metric-improvement** skill. |
| Monitor production | Re-run onboarding on the **observability** path. |
| CI/CD or scheduled tests | GitHub Actions / cron jobs (`cron_jobs_create`). |

Close with a short summary: what was set up, the verified run link, and any flagged open items from Phase 2 (deferred API key, placeholder description).
