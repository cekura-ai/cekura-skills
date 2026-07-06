# Phase 4 (observability) — Configure Metrics

> **Start:** Announce "Starting Phase 4 — Configure Metrics".

## 4a. Survey existing metrics

`metrics_list` — if the project already has metrics from a prior testing onboarding, reuse them; they apply to call logs too.

## 4b. Recommend a starter set

Three metrics that cover the high-value bases:

| Metric | Why |
|---|---|
| **Hallucination** | Catches invented facts on live calls — highest blast-radius failure. |
| **Expected Outcome adherence** | Did the agent accomplish the call's purpose? |
| **Sentiment** | Surfaces frustration trends — leading churn indicator. |

List the catalog with `predefined_metrics_list`; create chosen ones with `metrics_create` / `metrics_bulk_create` (pass `project_id`).

## 4c. LLM-generated metrics (optional)

If the user wants metrics auto-tailored to their agent, use `metrics_generate` (generates from the agent description). Defer careful custom-metric design to the **cekura-metric-design** skill.

---

## Phase 4 Gate

**Do not proceed until the starter metrics exist in `metrics_list`.**

Announce: "Phase 4 complete." Then begin [Phase 5 — Run Evaluation](phase5-observability-evaluate.md).
