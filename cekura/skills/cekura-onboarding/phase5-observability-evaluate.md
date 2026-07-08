# Phase 5 (observability) — Run Metric Evaluation

> **Start:** Announce the step in plain words (e.g. "Let's connect your agent", "Generating your first evaluators") — never a phase number or the word "Phase"; the numbering below is internal navigation only.

If `metric_ids` was passed during ingestion, auto-evaluation already started — skip to the gate check.

## 5a. Kick off evaluation

Call `call_logs_evaluate_metrics_create`:

```json
{
  "call_log_ids": [<id1>],
  "metric_ids": [<metric_id1>, <metric_id2>]
}
```

Evaluation is async — the call log shows `status: "evaluating"` and an empty `metrics` array at first. Re-retrieve shortly after.

## 5b. Rerun (when needed)

If a metric prompt changes later and the user wants existing call logs re-scored: `call_logs_rerun_evaluation_create`.

---

## Phase 5 Gate

**Do not proceed until the call log's metrics array shows real scores** (`call_logs_retrieve`).

Confirm the step is done in plain words (no phase numbers). Then begin [Phase 6 — Review Results](phase6-observability-review.md).
