# Phase 6 (observability) — Review Results, Vote, What's Next

> **Start:** Announce "Starting Phase 6 — Review & Vote".

## 6a. Show results

Retrieve the call log (`call_logs_retrieve`) and walk the user through: the transcript, each metric's score + reasoning, any flagged segments.

## 6b. Collect votes

Ask the user to pick at least one metric result they disagree with and why, then record it:

```json
{
  "call_log_id": <id>,
  "metric_id": <id>,
  "vote": "incorrect",
  "reasoning": "<user's reason>"
}
```

via `call_logs_mark_metric_vote_create`. Encourage 3–5 votes for a meaningful signal.

## 6c. What's next

| Need | Next step |
|------|-----------|
| Improve metrics with the votes | **cekura-metric-improvement** skill |
| Custom metrics | **cekura-metric-design** skill |
| Continuous ingestion (if still on one-shot) | Webhook setup from Phase 3O — for LiveKit/Pipecat this is where the **Cekura SDK** becomes required (`../cekura-create-agent/phase6-sdk-integration.md`) |
| Pre-deploy tests | Re-run onboarding on the **testing** path |
| Scheduled re-evaluation | Cron jobs |

Close with a summary: what was set up, the scored call log link, and any flagged open items from Phase 2.
