# Phase 4 (testing) — First Evaluators

> **Start:** Announce the step in plain words (e.g. "Let's connect your agent", "Generating your first evaluators") — never a phase number or the word "Phase"; the numbering below is internal navigation only.

## 4a. Generation-first — this is a hard rule

**Do NOT ask "would you like me to auto-generate evaluators?"** — generation is the mandated path of this phase and the user already opted into onboarding. Announce ("Generating your first evaluators from the agent description…") and start immediately.

**Nothing about the evaluators is a question either.** Do NOT ask which cases to cover, what kinds of tests they want, how many, which personality, or whether the generated set looks right before running. A handful spanning a few cases is the target; one personality or several is immaterial — whatever the call defaults to is correct. The description is the input, the generator does the design, and the run is what proves the setup works. Every question asked here is a turn spent deliberating about tests the user has not seen results from yet.

Generate the first evaluators with the **background generation endpoint**:

1. Call **`scenarios_generate_bg`**:

```json
{
  "agent_id": <agent_id>,
  "num_scenarios": 10,
  "generate_expected_outcomes": true,
  "tool_ids": ["TOOL_END_CALL", "TOOL_END_CALL_ONLY_ON_TRANSFER"]
}
```

`personalities` is optional — pass one from `aiagents_personalities_list` if you already have an id in context, otherwise omit it and let the default apply. **Never spend a call or a question getting one.**

2. Poll **`scenarios_generate_progress`** with the returned `progress_id` until complete.
3. List and review the generated scenarios.

**Do NOT hand-author evaluators with `scenarios_create` during onboarding.** Generation grounds evaluators in the agent description; hand-written ones depend entirely on improvisation. These evaluators are behavioral (`instruction`), and behavioral scenarios are always generated.

- **If `scenarios_generate_bg` fails**, retry once with a smaller `num_scenarios` and sharper `extra_instructions`. If it still fails, **stop and report the failure** — do not hand-write a stopgap set. A hand-written set looks like progress while leaving the user with evaluators nobody grounded in their agent. Offer `/report-bug`.
- **The one exception:** the user supplies the scenario text themselves and wants it verbatim. Create that one directly and say that it bypassed generation.

If the agent description is a flagged placeholder from Phase 2, **stop and resolve the description first** — generation from a placeholder produces junk.

## 4b. Sanity-check the generated set — silently

This is your check, not a review meeting. Do not present the set for approval, do not ask which ones to keep, and do not offer to regenerate. Fix what is clearly wrong, then move on. Check:
- Instructions are specific and behavioral.
- Expected outcomes are concise and achievable.
- The right tools are enabled.
- For non-English agents: PATCH `scenario_language` to the correct code.

Coverage gaps (red-team scenarios, domain edge cases, multi-language, tool failures) belong in the closing summary as things to add later via the **cekura-eval-design** skill — not in a question now, and not as a reason to pause before the run.

## 4c. Attach metrics

Every evaluator needs metrics attached. At minimum: **Expected Outcome** and an infrastructure/connection metric. Use `scenarios_bulk_update` (or the UI's bulk modify) to attach across the generated set.

---

## Phase 4 Gate

**Do not proceed until generated evaluators exist (via `scenarios_generate_bg`) with metrics attached.**

Confirm the step is done in plain words (no phase numbers). Then begin [Phase 5 — First Test Run](phase5-testing-first-run.md).
