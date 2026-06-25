# Regression Phase — Confirm the Fix Didn't Break Anything Else

This phase runs **once**, after Eval declares the validation set 100% green (Eval Step EVAL.4 case 3) and before the PR phase. The reproduction dataset proves the original bug is fixed; this phase proves the fix didn't break a previously-working flow. A fix that resolves the bug but regresses a happy path is not shippable.

> ## ⚠️ ALL REGRESSION RUNS ARE E2E SIMULATIONS ON CEKURA — SAME TRANSPORT
>
> Every regression case is a full end-to-end simulation over the same connection medium as the production call — same agent, same transport. Text mode is never a substitute; do not switch transports. Passing regression over a different medium than production is a false pass.

---

## Step REGRESS.1 — Identify the affected flows

The in-loop sweep (Eval Step EVAL.4 case 2) already re-ran the reproduction dataset / original input batch. This phase widens coverage to flows that touch the **same surface the fix changed** but weren't in the dataset:

- Standard happy-path flows through the same prompt section / squad member / code path the edit touched.
- Edge cases the fix might have broken — error paths, timeouts, retries, fallback branches near the edited region.
- Voice-specific stress on the affected flow: silence gaps, interruptions, background noise, DTMF input.
- Other caller intents that reach the same code path / decision point.

Produce a named list. **Confirm it with the user before creating evaluators** *(in `auto_mode: true`, render the list and proceed unless it's empty or clearly under-scoped — then ask).* The goal is enough coverage to trust the fix, not an exhaustive suite — scale the count to how invasive the edit was (a one-clause prompt tweak needs fewer cases than an orchestration-code change to history management).

---

## Step REGRESS.2 — Create and run the regression cases

Build one evaluator per case. Reuse the harness machinery from the Reproduce phase — the agent already has the mock tools and dynamic variables set, so regression cases inherit a faithful environment.

Evaluator construction follows the same rule as REPRO.4: **prefer `expected_outcome` bullets; fall back to a predefined metric only when the case is out of scope for behavioral bullets** (e.g. silence / non-response → Infrastructure Issues; slow replies → Latency; tool behavior → Tool Call Success). To *generate* voice-specific stress, use XML tags in `fixed_message` (`<silence>`, `<interruption>`, `<background_noise>`, `<dtmf>`).

```bash
create_scenario '{
  "agent": METADATA_AGENT_ID,
  "personality": PERSONALITY_ID,
  "name": "Regression: <case name>",
  "instructions": "...",
  "expected_outcome": "<behavioral bullets>",
  "conditional_actions": { "role": "caller", "conditions": [...] }
}'
```

Run each case over the agent's transport, work through them one at a time (restore any modified conditions between cases), and poll all results. Apply the same **must-pass stochastic policy** as Eval Step EVAL.2: LLM-based cases must pass in ≥ M of N runs; infra cases need a single clean pass.

Build a summary:

| Case | Class | Runs | Pass/Fail | Result URL |
|---|---|---|---|---|
| Happy path | LLM | 8/8 | PASS | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID |
| Silence gap | infra | 1/1 | PASS | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID |

---

## Regression Gate

**Every regression case must pass before the PR phase.**

If a case fails, the fix has collateral damage — do NOT ship it. **Hand back to Optimization · Collect** with the regressed case(s) as the new failure set (exactly like Eval Step EVAL.4 case 4), so Diagnose can scope the fix more narrowly (e.g. a conditional clause for the specific failing scenario type rather than a blanket prompt-wide change). This re-enters the loop and counts toward the iteration cap. Keep the regressed cases in the validation set thereafter so the loop catches re-regressions.

Only when every regression case passes, hand off to [`pr.md`](pr.md) with the full result-URL set (reproduction fail-runs + verification pass-runs + regression pass-runs).
