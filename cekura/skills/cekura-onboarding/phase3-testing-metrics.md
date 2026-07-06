# Phase 3 (testing) — Metrics Setup

> **Start:** Announce "Starting Phase 3 — Metrics".

## 3a. Enable pre-defined metrics

**Recommend selecting ALL pre-defined metrics** for a comprehensive baseline. List the catalog with `predefined_metrics_list` and copy the chosen ones into the project with `predefined_metrics_copy_create`.

| Category | Examples |
|----------|---------|
| Accuracy | Expected Outcome, Hallucination, Relevancy, Tool Call Success, Transcription Accuracy |
| Quality | Interruptions, Response latency, Silence, Call termination appropriateness |
| Customer Experience | CSAT, Sentiment, Dropoff nodes, Topic categorization |
| Speech Quality | Pitch, Speaking rate, Gibberish detection, Pronunciation |

**Two-step activation:** metrics must be (1) enabled at the project level AND (2) attached to individual evaluators (Phase 4T handles attachment).

## 3b. Custom metrics — defer

Skip custom metrics during onboarding. Once the user has test results, hand off to the **cekura-metric-design** skill for targeted custom metrics.

---

## Phase 3 Gate

**Do not proceed until the project's metric list (`metrics_list`) shows at least Expected Outcome enabled.**

Announce: "Phase 3 complete." Then begin [Phase 4 — First Evaluators](phase4-testing-evaluators.md).
