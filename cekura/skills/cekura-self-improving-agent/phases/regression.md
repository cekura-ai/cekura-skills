# Regression Phase — Confirm the Fix Didn't Break Anything Else

Runs **once**, after Eval declares the validation set 100% green (EVAL.4 case 3) and before final handoff. The reproduction dataset proves the original bug is fixed; this phase proves the fix didn't break a previously-working flow. A fix that resolves the bug but regresses a happy path is not shippable.

**The sweep is always Cekura scenarios:** run happy-path + edge-case scenarios with Setup's saved simulation runner. A different runner or a code/unit test is not a substitute.

## Step REGRESS.1 — Identify the affected flows

The in-loop sweep (EVAL.4 case 2) already re-ran the reproduction dataset. This phase widens coverage to flows touching the **same surface the fix changed** but absent from the dataset:

- Happy-path flows through the same prompt section / squad member / code path the edit touched.
- Edge cases the fix might have broken — error paths, timeouts, retries, fallback branches near the edited region.
- (Cekura-scenario) voice stress on the affected flow: silence gaps, interruptions, background noise, DTMF.
- Other caller intents reaching the same code path / decision point.

Produce a named list. **Confirm with the user before creating evaluators** *(in `auto_mode: true`, render and proceed unless empty or clearly under-scoped — then ask)*. Goal is enough coverage to trust the fix, not exhaustiveness — scale the count to how invasive the edit was (a one-clause prompt tweak needs fewer cases than an orchestration-code change).

## Step REGRESS.2 — Create and run the regression cases

**Cekura-scenario targets:** build one evaluator per case, reusing the Reproduce harness machinery (the agent already has mock tools + dynamic variables, so cases inherit a faithful environment). Follow REPRO.4: **prefer `expected_outcome` bullets; fall back to a predefined metric only when the case is out of scope for behavioral bullets** (silence/non-response → Infrastructure Issues; slow replies → Latency; tool behavior → Tool Call Success). To *generate* voice stress, use XML tags in `fixed_message` (`<silence>`, `<interruption>`, `<background_noise>`, `<dtmf>`).

```bash
create_scenario '{
  "agent": AGENT_ID,
  "personality": PERSONALITY_ID,
  "name": "Regression: <case name>",
  "instructions": "...",
  "expected_outcome": "<behavioral bullets>",
  "conditional_actions": { "role": "caller", "conditions": [...] }
}'
```

Run each case with the saved runner one at a time (restore modified conditions between cases), then poll all results.

Apply the same **must-pass stochastic policy** as EVAL.2: every case — LLM and infra alike — must pass in ≥ M of N runs (a single clean pass is never enough), re-run under the ≥ M of N logic when a trigger is intermittent.

| Case | Class | Runs | Pass/Fail | Result URL |
|---|---|---|---|---|
| Happy path | LLM | 8/8 | PASS | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID |
| Silence gap | infra | 8/8 | PASS | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID |

## Regression Gate

**Every regression case must pass before final handoff.**

Any failure = collateral damage — do NOT ship. **Hand back to Optimization · Collect** with the regressed case(s) as the new failure set (exactly like EVAL.4 case 4), so Fix can scope the fix more narrowly (a conditional clause for the specific type rather than a blanket prompt-wide change). This re-enters the loop and counts toward the iteration cap. Keep regressed cases in the validation set thereafter so re-regressions are caught.

When every case passes, report the validated diff and full result-URL set to the
apply-diff workflow. Never promote or repoint production resources.
