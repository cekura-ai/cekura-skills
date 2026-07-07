# Phase 6 (testing) — What's Next

> **Start:** Announce "Starting Phase 6 — What's Next".

Onboarding is done (Phase 5 gate passed). Offer the depth that was deliberately deferred — each item is an upsell triggered by a real need, not a required step:

| Need the user expresses | Next step |
|------|-----------|
| "Why was this response slow?" / "Show me the agent's tool calls" (LiveKit/Pipecat) | **Cekura SDK integration** — read `../cekura-create-agent/phase6-sdk-integration.md`. Only now, post-first-result. After a verified integration, set `credentials.config.tracing_enabled: true`. |
| Agent calls external APIs and tests need realistic data | **Mock tools** — hand off to **cekura-create-agent** (mock tools phase) / **cekura-eval-design** for mock data design. |
| Agent answers from documents | **Knowledge base upload** — cekura-create-agent KB phase. |
| Per-call data (names, account IDs) | **Dynamic variables** — cekura-create-agent dynamic-variables phase. |
| Better metrics | **cekura-metric-design** skill. |
| More/targeted evaluators (red-team, edge cases) | **cekura-eval-design** skill. |
| Improve metric quality from disagreements | **cekura-metric-improvement** skill. |
| Monitor production | Re-run onboarding on the **observability** path. |
| CI/CD or scheduled tests | GitHub Actions / cron jobs (`cron_jobs_create`). |

Close with a short summary: what was set up, the verified run link, and any flagged open items from Phase 2 (deferred API key, placeholder description).
