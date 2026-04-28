---
name: cekura-metric-improvement
description: >
  Use when the user asks to "improve a metric", "run labs", "leave feedback on a metric",
  "add to labs", "fix metric accuracy", "review metric results", "find misaligned metrics",
  or "iterate on metric quality". Covers the metric improvement cycle, the feedback
  workflow, and the labs pipeline used to refine metric accuracy over time.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.3.0"
---

# Cekura Metric Improvement

## Purpose

Guide the metric improvement cycle: identify misaligned metric results, leave structured feedback, run the labs improvement pipeline, and validate changes. This workflow takes a metric from initial draft to production-ready through systematic iteration.

## Manual Fix First, Then Labs

**When metrics have systemic issues (high false-fail rates), do NOT jump straight to labs feedback.** Labs is best for nuanced edge cases, not systemic prompt design flaws.

Instead:

1. **Read failure explanations** and categorize root causes — cross-pollination from other flows, extra questions flagged, end-of-call protocol violations, should-be-N/A cases, etc.
2. **Write manual prompt fixes** targeting the dominant failure categories — add SCOPE & FOCUS, DO NOT FLAG, narrow FAILURE CONDITIONS
3. **Update the metric** with the revised prompt
4. **Re-evaluate a sample** of 20–30 calls per metric to validate the fixes
5. **Then use labs feedback** for remaining edge cases that manual fixes didn't catch

This avoids wasting labs iterations on issues clearly fixable by prompt editing.

## The Labs Improvement Cycle

For edge case refinement after manual fixes are validated:

1. **Identify misalignment** — Find calls where the metric's verdict seems wrong
2. **Leave feedback** — Vote agree/disagree with an explanation on specific results
3. **Accumulate feedback** — Collect 6+ feedback instances for statistical significance
4. **Run auto-improve** — Labs uses feedback to suggest metric prompt changes
5. **Validate** — Re-run the improved metric on the same calls to verify
6. **Deploy** — Once satisfied, optionally convert to a Pythonic custom_code form for production

## Step 1: Identify Misaligned Results

Review recent call evaluations to find suspicious results:

- **FALSE results that should be TRUE** (false negatives)
- **TRUE results that should be FALSE** (false positives)
- **Unexpected N/A results** — the metric should have applied
- **Inconsistent results across similar calls**

Pull a sample of 20–30 recent calls per metric. Read the transcript and the metric's verdict together. Disagreements with the verdict are candidates for feedback.

## Step 2: Leave Structured Feedback

Each piece of feedback should include:

- **The result you're disagreeing with** — specific call ID, specific metric
- **Your verdict** — what the result *should* have been (TRUE / FALSE / N/A / specific value)
- **Reasoning** — why. Cite the part of the transcript that supports your verdict.
- **Pattern hint** — if this is part of a broader pattern, name the pattern (e.g., "agent's politeness language being misread as evasion")

Vague feedback ("this is wrong") doesn't help labs improve the prompt. Specific reasoning grounded in the transcript does.

## Step 3: Accumulate Feedback

Labs needs **6+ feedback instances** per metric for the auto-improve step to work well. With fewer than 6, the feedback signal isn't strong enough to drive prompt changes.

If you don't have 6 yet, keep reviewing calls and leaving feedback. Don't run labs until the threshold is met.

## Step 4: Run Auto-Improve

Once enough feedback has accumulated, trigger the labs auto-improve flow. It analyzes the feedback against the current metric prompt and proposes revisions.

Review the proposed changes:
- Do they address the patterns in the feedback?
- Do they introduce new edge cases?
- Are they consistent with how the metric is supposed to work?

If the proposal looks reasonable, accept it. If not, revise manually and re-run.

## Step 5: Validate

Re-run the improved metric on the **same calls** that produced the feedback. Verify:

- Calls you flagged as false fails now pass (or are correctly N/A)
- Calls you flagged as false passes now fail
- Other calls weren't accidentally broken (regression check)

If the validation passes, deploy. If not, iterate again.

## Step 6: Optional — Promote to Custom Code

For production-grade metrics, convert the validated `llm_judge` prompt to `custom_code` with targeted section extraction. This:

- Reduces token usage by extracting only the relevant transcript section
- Allows N/A short-circuiting without an LLM call
- Lets the metric gate on upstream metric results

The Cekura platform stores both forms — toggle the active type when ready.

## Best Practices

- **Don't aim for 100% agreement.** Edge cases will always exist. Aim for 90–95% alignment with human judgment on a sample.
- **Track which patterns drove changes.** Note them in the metric's description so future iterations don't undo them.
- **Re-run validation periodically.** As the agent evolves, metrics drift. Schedule a quarterly review.
- **Don't over-iterate.** After 3–4 cycles, diminishing returns set in. Either accept the current accuracy or rethink the metric's framing.

## Documentation

- Public docs: https://docs.cekura.ai
- Concepts: https://docs.cekura.ai/documentation/key-concepts/
