# Phase 6 (observability) — Review Results & What's Next

> **Start:** Announce "Starting Phase 6 — Review Results".

## 6a. Show results

Retrieve the call log (`call_logs_retrieve`) and walk the user through: the transcript, each metric's score + reasoning, any flagged segments.

## 6b. What's next

| Need | Next step |
|------|-----------|
| Improve metric quality from disagreements | **cekura-metric-improvement** skill |
| Custom metrics | **cekura-metric-design** skill |
| Continuous ingestion (if still on one-shot) | Webhook setup from Phase 3O — for LiveKit/Pipecat this is where the **Cekura SDK** becomes required (`../cekura-create-agent/phase6-sdk-integration.md`) |
| Pre-deploy tests | Re-run onboarding on the **testing** path |
| Scheduled re-evaluation | Cron jobs |

Close with a summary: what was set up, the scored call log link, and any flagged open items from Phase 2.
