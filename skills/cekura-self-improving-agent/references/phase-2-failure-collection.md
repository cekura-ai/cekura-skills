# Phase 2 — Failure Collection Reference

Full failure-summary template, the metric-improvement hand-off wording, edge cases, and the no-overfitting-caveats rule.

## Step 2.5 — Full summary template

Group failures by **scenario** (for runs) or by **metric** (for call logs), since repeated failures on the same scenario or the same metric are stronger signals than scattered one-offs.

```
Failure Summary
  Agent: <name> (<id>) — provider vapi
  Source: <input type> — <N items inspected>
  Reviewed-success skipped: <S items> (human-reviewed pass — metric/outcome verdicts on these items ignored)
  Failures: <total collected on remaining items> — <voice-related discarded> voice-related discarded — <kept> prompt-following kept

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
        - <run/call id>: <explanation excerpt>

  Provider Call State Observations (from Step 2.4):
    - <observation grouping — e.g., "all 3 failed runs share the following pattern:">
      assistantOverrides.variableValues: <relevant fields>
      artifact.variableValues: <relevant fields, especially absent / null / empty>
      Rendered system message: <literal {{...}} placeholders found, or "all substituted">
      Tool-call arguments: <literal placeholders / empty arrays / hallucinations, or "clean">
    - <or "no provider state available for these items — text-mode runs">
```

Phase 2's job is to surface failures, not to commit to a fix shape — that belongs to Phase 3.

## Routing to metric improvement (the one Phase 2 exception)

The user-facing gate is at every Phase 3 → Phase 4 transition (after they see proposed edits), not at Phase 2. **The one exception**: if the failures are dominated by one or two metrics with thin signal (i.e. most kept failures come from the same metric and the explanations look subjective), stop and suggest hand-off to `cekura-metric-improvement`. Those are metric-quality issues, not agent-quality issues, and Phase 3 won't fix them — the loop will keep "fixing" the prompt to satisfy a flawed judge.

If the `reviewed_success` pre-filter dropped multiple items where the same metric flagged FAIL, that's another flavor of the same signal — surface the metric ids with their FAIL-on-reviewed-success counts and recommend `cekura-metric-improvement` for those metrics specifically. But do not act on it from this skill.

## No small-sample / overfitting caveats (user-facing)

Even when the input is a single run, do **not** include lines like:

- "with N runs any fix risks overfitting"
- "5–10+ items would be a healthier signal"
- "consider expanding the input set first"

…in the user-facing summary. Internal calibration of confidence is fine — weight the diagnosis with less confidence and prefer minimal, narrowly-scoped edits — but **user-facing hedging reads as a stall** and the user has already chosen to act on the input they have. The summary should report the failure shape and move on.

## Edge cases

- **No failures found**: report this and stop. There's nothing to improve from this input. Suggest expanding the input set (more scenarios, more calls).
- **All runs errored** (vs failed): an errored run never produced a transcript — usually a provider/connection issue, not an agent prompt issue. Don't include errored runs in the failure summary; surface them separately so the user can fix infrastructure before iterating on the prompt.
- **Mixed input types**: not supported in a single invocation. If the user gives both `scenario_ids` and `call_ids`, ask them to pick one source per iteration — mixing test runs and production calls muddles the signal.
- **Text-mode runs without provider artifacts** and some chat call logs don't expose `provider_call_details`. Skip Step 2.4 inspection for those items and surface the gap in Step 2.5 — Phase 3 should know it's diagnosing on partial data.

## What "kept" means downstream

The kept failure summary (with provider-call-state observations) is the input to Phase 3. The reviewed-success skip count and voice-discard count are tracked separately because they're distinct reasons for ignoring an item — the summary should report them on different lines so the user can see the full pipeline (items → skipped → discarded → kept) at a glance.
