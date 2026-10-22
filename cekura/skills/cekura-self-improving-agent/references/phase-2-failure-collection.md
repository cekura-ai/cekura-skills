# Collect — Failure Collection Reference

Full failure-summary template, metric-improvement hand-off wording, edge cases, and the thin-evidence rule.

## COLLECT.5 — Full summary template

Group by **scenario** (runs) or **metric** (call logs) — repeated failures on the same scenario/metric are stronger signals than scattered one-offs.

```
Failure Summary
  Agent: <name> (<id>) — provider <vapi | retell | elevenlabs | bland | self_hosted>
  Source: <input type> — <N items inspected>
  Verdict filter:
    - kept: <K> (failure: <F>, reviewed_failure: <R>)
    - dropped: <D> (success: <S>, reviewed_success: <RS>)
  Failures on kept items: <total> — <voice-related discarded> voice-related discarded — <prompt-following kept>

  Expected-Outcome Failures (<failed> of <total> runs):
    - Scenario: <name>
      Expected: <expected_outcome text>
      Verdict: fail — <explanation>
      Run: <run_id>
      Transcript excerpt: "<quote>"

  Metric Failures (K total across J unique metrics):
    - Metric: <name> (id <metric_id>) — <count> failures
      Sample explanations:
        - <run/call id>: <explanation excerpt>

  Provider Call State Observations (from COLLECT.4):
    - <pattern grouping>
      assistantOverrides.variableValues: <relevant fields>
      artifact.variableValues: <relevant fields — especially absent / null / empty>
      Rendered system message: <literal {{...}} placeholders found, or "all substituted">
      Tool-call arguments: <literal placeholders / empty arrays / hallucinations, or "clean">
    - <or "no provider state available — text-mode runs">
```

Collect surfaces failures; fix shape belongs in Fix.

## Routing to metric improvement

The Fix → Apply user gate (FIX.6) is the standard checkpoint. **One exception:** if failures are dominated by one or two metrics with thin, subjective signal, stop and suggest hand-off to `cekura-metric-improvement` before entering Fix — the loop will keep "fixing" the prompt to satisfy a flawed judge.

Additional signal to route: if the verdict pre-filter dropped multiple `reviewed_success` items where the same metric flagged FAIL, surface those metric ids with their FAIL-on-reviewed-success counts and recommend `cekura-metric-improvement` for those metrics specifically. Do not act on it from this skill.

**Do not** route `reviewed_failure` items to metric improvement just because they cluster on one metric — those carry explicit human confirmation and belong in Fix as the strongest available signal.

## Thin evidence

When the input is small (a single run, one call), say so in one plain line of the summary — e.g. "1 failing run; the diagnosis rests on this one transcript" — weight the diagnosis accordingly and prefer minimal scoped edits. One line is enough; don't repeat the hedge elsewhere.

## Edge cases

- **No failures found**: report and stop. Suggest expanding the input set (more scenarios, more calls).
- **All runs errored** (vs failed): an errored run produced no transcript — usually a provider/connection issue, not a prompt issue. Exclude from the failure summary; surface separately so the user can fix infrastructure first.
- **Mixed input types**: not supported in a single invocation. If the user provides both `scenario_ids` and `call_ids`, ask them to pick one source per iteration.
- **Text-mode runs / chat call logs without provider artifacts**: skip COLLECT.4 inspection for those items; note the gap in COLLECT.5 so Fix knows it's diagnosing on partial data.

## What "kept" means downstream

The kept failure summary (with provider-call-state observations) is Fix's input. Report verdict-drop counts (`success` + `reviewed_success`) and voice-discard count on separate lines so the full pipeline (items → verdict-dropped → voice-discarded → kept) is visible. Within the kept set, `reviewed_failure` items flow into Fix the same as `failure` items — the count is surfaced because users want to know how many kept failures carry explicit human confirmation.
