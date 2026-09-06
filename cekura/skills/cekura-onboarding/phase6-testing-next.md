# Phase 6 (testing) — What's Next

> **Start:** Announce the step in plain words (e.g. "Let's connect your agent", "Generating your first evaluators") — never a phase number or the word "Phase"; the numbering below is internal navigation only.

Onboarding is done (Phase 5 gate passed). Offer the depth that was deliberately deferred — each item is an upsell triggered by a real need, not a required step.

**LiveKit / Pipecat agents get one proactive offer here and only here: the Cekura SDK.** Show the run results first, then offer it as "here's what more Cekura can capture" — [phase7-sdk-pr.md](phase7-sdk-pr.md) runs that step. It is the one item on this page you raise unprompted, because the user cannot ask for data they have never seen; everything else waits for them to express the need.

| Need the user expresses | Next step |
|------|-----------|
| "Why was this response slow?" / "Show me the agent's tool calls" (LiveKit/Pipecat) | **Cekura SDK integration** — [phase7-sdk-pr.md](phase7-sdk-pr.md). Only now, post-first-result. Do NOT open the cekura-create-agent skill for this; phase7 is self-contained. |
| Agent calls external APIs and tests need realistic data | **Mock tools** — hand off to **cekura-create-agent** (mock tools phase) / **cekura-eval-design** for mock data design. |
| Agent answers from documents | **Knowledge base upload** — cekura-create-agent KB phase. |
| Per-call data (names, account IDs) | **Dynamic variables** — cekura-create-agent dynamic-variables phase. |
| Better metrics | **cekura-metric-design** skill. |
| More/targeted evaluators (red-team, edge cases) | **cekura-eval-design** skill. |
| Improve metric quality from disagreements | **cekura-metric-improvement** skill. |
| Monitor production | Re-run onboarding on the **observability** path. |
| CI/CD or scheduled tests | GitHub Actions / cron jobs (`cron_jobs_create`). |

Close with a short summary: what was set up, the verified run link, and any flagged open items from Phase 2 (deferred API key, placeholder description).
