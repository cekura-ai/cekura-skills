# Phase 4 (observability) — Configure Metrics

> **Start:** Announce the step in plain words (e.g. "Let's connect your agent", "Generating your first evaluators") — never a phase number or the word "Phase"; the numbering below is internal navigation only.

## 4a. Survey existing metrics

`metrics_list` — if the project already has metrics from a prior testing onboarding, reuse them; they apply to call logs too.

## 4b. Enable the observability set

List the catalog with `predefined_metrics_list`; copy/create with `predefined_metrics_copy_create` / `metrics_bulk_create` (pass `project_id`). Each metric has separate `simulation_enabled` / `observability_enabled` toggles — for this path make sure **observability** is on.

| Observability default | Metrics |
|---|---|
| Enable | AI interrupting user, Average Pitch, Infrastructure Issues, Interruption Score, Latency, Stop Time after User Interruption, Talk Ratio, Tool Call Success, Unnecessary Repetition Score |
| Do NOT enable by default (testing-only) | Expected Outcome, Transcription Accuracy, Mock tool call accuracy |
| Leave off unless asked | Letterwise Pronunciation Detection |

Only add the testing-only ones to production calls if the user explicitly asks.

## 4c. LLM-generated metrics (optional)

If the user wants metrics auto-tailored to their agent, use `metrics_generate` (generates from the agent description). Defer careful custom-metric design to the **cekura-metric-design** skill.

---

## Phase 4 Gate

**Do not proceed until the starter metrics exist in `metrics_list`.**

Confirm the step is done in plain words (no phase numbers). Then begin [Phase 5 — Run Evaluation](phase5-observability-evaluate.md).
