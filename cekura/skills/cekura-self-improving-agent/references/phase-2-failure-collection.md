# Phase 2 — Failure Collection Reference

Full failure-summary template, metric-improvement hand-off wording, edge cases, and the no-overfitting-caveats rule.

## Step 2.5 — Full summary template

Group by **scenario** (runs) or **metric** (call logs) — repeated failures on the same scenario/metric are stronger signals than scattered one-offs.

```
Failure Summary
  Agent: <name> (<id>) — provider <vapi | retell | elevenlabs | bland | self_hosted>
  Source: <input type> — <N items inspected>
  Verdict filter:
    - kept: <K> (failure: <F>, reviewed_failure: <R>)
    - dropped: <D> (success: <S>, reviewed_success: <RS>)
  Failures on kept items: <total> — <voice-related discarded> voice-related discarded — <prompt-following kept>

  Expected-Outcome Failures (M of N runs):
    - Scenario: <name>
      Expected: <expected_outcome text>
      Verdict: fail — <explanation>
      Run: <run_id>
      Transcript excerpt: "<quote>"

  Metric Failures (K total across J unique metrics):
    - Metric: <name> (id <metric_id>) — <count> failures
      Sample explanations:
        - <run/call id>: <explanation excerpt>

  Provider Call State Observations (from Step 2.4):
    - <pattern grouping>
      assistantOverrides.variableValues: <relevant fields>
      artifact.variableValues: <relevant fields — especially absent / null / empty>
      Rendered system message: <literal {{...}} placeholders found, or "all substituted">
      Tool-call arguments: <literal placeholders / empty arrays / hallucinations, or "clean">
    - <or "no provider state available — text-mode runs">
```

Phase 2 surfaces failures; fix shape belongs in Phase 3.

## Routing to metric improvement

The Phase 3 → Phase 4 user gate is the standard checkpoint. **One exception:** if failures are dominated by one or two metrics with thin, subjective signal, stop and suggest hand-off to `cekura-metric-improvement` before entering Phase 3 — the loop will keep "fixing" the prompt to satisfy a flawed judge.

Additional signal to route: if the verdict pre-filter dropped multiple `reviewed_success` items where the same metric flagged FAIL, surface those metric ids with their FAIL-on-reviewed-success counts and recommend `cekura-metric-improvement` for those metrics specifically. Do not act on it from this skill.

**Do not** route `reviewed_failure` items to metric improvement just because they cluster on one metric — those carry explicit human confirmation and belong in Phase 3 as the strongest available signal.

## No small-sample / overfitting caveats (user-facing)

Even on a single run, do **not** include lines like "with N runs any fix risks overfitting", "5–10+ items would be a healthier signal", or "consider expanding the input set first" in the user-facing summary. Internal calibration is fine — weight the diagnosis with less confidence and prefer minimal scoped edits — but user-facing hedging reads as a stall. Report the failure shape and move on.

## Edge cases

- **No failures found**: report and stop. Suggest expanding the input set (more scenarios, more calls).
- **All runs errored** (vs failed): an errored run produced no transcript — usually a provider/connection issue, not a prompt issue. Exclude from the failure summary; surface separately so the user can fix infrastructure first.
- **Mixed input types**: not supported in a single invocation. If the user provides both `scenario_ids` and `call_ids`, ask them to pick one source per iteration.
- **Text-mode runs / chat call logs without provider artifacts**: skip Step 2.4 inspection for those items; note the gap in Step 2.5 so Phase 3 knows it's diagnosing on partial data.

## What "kept" means downstream

The kept failure summary (with provider-call-state observations) is Phase 3's input. Report verdict-drop counts (`success` + `reviewed_success`) and voice-discard count on separate lines so the full pipeline (items → verdict-dropped → voice-discarded → kept) is visible. Within the kept set, `reviewed_failure` items flow into Phase 3 the same as `failure` items — the count is surfaced because users want to know how many kept failures carry explicit human confirmation.
