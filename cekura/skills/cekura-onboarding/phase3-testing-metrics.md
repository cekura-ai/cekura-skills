# Phase 3 (testing) — Metrics Setup

> **Start:** Announce "Starting Phase 3 — Metrics".

## 3a. Enable pre-defined metrics

List the catalog with `predefined_metrics_list` and copy metrics into the project with `predefined_metrics_copy_create`. For the **testing (simulation) path**, enable the standard set:

| Enable for testing | Metrics |
|---|---|
| Both paths' baseline | AI interrupting user, Average Pitch, Infrastructure Issues, Interruption Score, Latency, Stop Time after User Interruption, Talk Ratio, Tool Call Success, Unnecessary Repetition Score |
| Testing-only additions | **Expected Outcome**, **Transcription Accuracy**, **Mock tool call accuracy** |
| Leave off unless asked | Letterwise Pronunciation Detection |

Each metric has separate `simulation_enabled` / `observability_enabled` toggles — for this path make sure **simulation** is on.

**Two-step activation:** metrics must be (1) enabled at the project level AND (2) attached to individual evaluators (Phase 4T handles attachment).

## 3b. Custom metrics — defer

Skip custom metrics during onboarding. Once the user has test results, hand off to the **cekura-metric-design** skill for targeted custom metrics.

---

## Phase 3 Gate

**Do not proceed until the project's metric list (`metrics_list`) shows at least Expected Outcome enabled.**

Announce: "Phase 3 complete." Then begin [Phase 4 — First Evaluators](phase4-testing-evaluators.md).
