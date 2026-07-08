# Phase 3 (testing) — Metrics Check (silent)

> This phase is a background verification, NOT a user-facing step. Do not announce a "Metrics" phase, do not present metrics setup in a resume prompt, and do not ask the user anything here — the only user-visible output is the single confirmation line below when the check passes.

## 3a. Default metrics are ALREADY enabled — do not re-enable them

**Every project gets the default pre-defined metrics automatically at creation** (the platform copies them in when the project is created). Do NOT list the catalog, do NOT run `predefined_metrics_copy_create` for the standard set, and do NOT walk the user through "enabling metrics" — it's already done.

This phase is a single verification: call `metrics_list` for the project and confirm the defaults are present (they will be, on any normally-created project). In particular check that **Expected Outcome** is there — it's the metric Phase 4T attaches to every evaluator.

- **Defaults present (the normal case):** announce one line — "Your project already has the default metrics enabled (Expected Outcome, Latency, Interruption Score, …)" — and move on. Nothing to do.
- **Something testing-critical genuinely missing** (rare — e.g. an old project created before a metric existed): copy just the missing metric with `predefined_metrics_copy_create`, say what you added and why, and move on. Make sure its **simulation** toggle is on (`simulation_enabled` — metrics have separate simulation/observability toggles).

**Two-step activation reminder:** project-level enablement (already done) is step 1; attaching metrics to individual evaluators is step 2 — Phase 4T handles that.

## 3b. Custom metrics — defer

Skip custom metrics during onboarding. Once the user has test results, hand off to the **cekura-metric-design** skill for targeted custom metrics.

---

## Phase 3 Gate

**Do not proceed until `metrics_list` confirms Expected Outcome is enabled for the project.**

Announce: "Phase 3 complete." Then begin [Phase 4 — First Evaluators](phase4-testing-evaluators.md).
