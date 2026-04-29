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

# Cekura Metric Improvement (Labs Workflow)

## Purpose

Guide the metric improvement cycle: identify misaligned metric results, leave structured feedback, run the labs improvement pipeline, and validate changes. This workflow transforms metric quality from initial draft to production-ready through systematic iteration.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

## Manual Fix First, Then Labs

**When metrics have systemic issues (high false-fail rates), do NOT jump straight to labs feedback.** Instead:

1. **Read failure explanations** and categorize root causes (e.g., cross-pollination from other flows, extra_questions flagged, end-of-call protocol violations, should-be-N/A cases)
2. **Write manual prompt fixes** targeting the dominant failure categories — add SCOPE & FOCUS, DO NOT FLAG, narrow FAILURE CONDITIONS
3. **PATCH the updated descriptions** via API
4. **Re-evaluate a sample** of 20-30 calls per metric to validate the fixes
5. **THEN use labs feedback** for remaining edge cases that manual fixes didn't catch

This avoids wasting labs iterations on issues that are clearly fixable by prompt editing. Labs is for nuanced edge cases, not systemic prompt design flaws.

## The Labs Improvement Cycle

For edge case refinement after manual fixes are validated:

1. **Identify misalignment** — Find calls where metric results seem wrong
2. **Leave feedback** — Vote agree/disagree with explanation on specific results
3. **Accumulate feedback** — Collect 6+ feedback instances for statistical significance
4. **Run auto-improve** — Labs uses feedback to suggest metric prompt changes
5. **Validate changes** — Re-run the improved metric on the same calls to verify
6. **Deploy** — Once satisfied, optionally convert to Pythonic custom_code for production

## Step 1: Identify Misaligned Results

### Manual Approach

Review recent call evaluations to find suspicious results:

List recent calls (with agent filters) and retrieve specific calls to get evaluation results — see "API Endpoints Reference" below.

Look for:
- FALSE results that seem like they should be TRUE (false negatives)
- TRUE results that seem wrong (false positives)
- Unexpected N/A results
- Inconsistent results across similar calls

### Guided Approach (Simulate Labs)

To systematically find misalignment:

1. Pull metric results for recent calls via `evaluate_calls` or `list_calls`
2. Focus on metrics with high variance or unexpected result distributions
3. Read the transcript alongside the metric explanation
4. Ask the user: "This call was marked [TRUE/FALSE]. The explanation says [X]. Does this seem correct?"
5. If the user disagrees, proceed to leave feedback

## Step 2: Leave Feedback

Use the `mark_metric_vote` endpoint to leave structured feedback. First retrieve the call to find the metric result, then POST the feedback (see "API Endpoints Reference" below).

### Good Feedback Patterns

- Reference specific transcript moments: "At 02:15, the agent said X which should be [PASS/FAIL] because..."
- Explain the reasoning: "The metric is being too literal about the one-question rule"
- Suggest the correct outcome: "This should be TRUE because the agent was confirming related details"
- Point out missing context: "The metric didn't account for the tool failure at 01:30"

### Bad Feedback Patterns

- Vague: "This is wrong" (no explanation)
- No reference: "Should be TRUE" (no transcript evidence)
- Contradictory: Disagreeing without explaining what the correct behavior should be

## Step 3: Accumulate Feedback

Collect at least 6 feedback instances before running auto-improve. This gives labs enough signal to identify patterns in the feedback and make meaningful prompt adjustments.

Track feedback progress:
- How many agree/disagree votes have been left
- What patterns emerge (e.g., "metric is consistently too strict about X")
- Whether feedback is balanced across different call types

## Step 4: Run Auto-Improve

Once 6+ feedback instances are accumulated:

Trigger auto-improvement via `POST /test_framework/metric-reviews/process_feedbacks/` with the metric ID.

Labs analyzes the feedback and suggests changes to the metric prompt. Review the suggested changes carefully:
- Do the changes address the feedback patterns?
- Are the changes too broad (might break other cases)?
- Do the safeguarding examples align with the feedback?

## Cost Guard — Never Evaluate >100 Calls Without Confirmation

Each evaluation costs the client real money. Before triggering any bulk evaluation:
1. Query the call count first (use `page_size=1` and read the response count)
2. Report the number to the user
3. If count > 100, **stop and ask for explicit approval** before proceeding

Use `page_size` parameter (up to 200) instead of paginating through multiple pages. Use server-side filters (`agent_id`, `project`, `timestamp__gte`/`timestamp__lte`) to scope calls before evaluating.

## Step 5: Validate Changes

Re-run the improved metric on the same calls that had misaligned results:

Use `POST /observability/v1/call-logs/rerun_evaluation/` with the call IDs and metric ID.

Check:
- Do the previously misaligned calls now produce correct results?
- Do previously correct calls still produce correct results (no regression)?
- Are the explanations clearer and more accurate?

If validation fails, leave additional feedback and iterate.

## Step 6: Deploy (Optional Pythonic Conversion)

Once the metric prompt is validated through labs, consider converting to a Pythonic custom_code metric for production:

1. Take the final validated prompt from the llm_judge `description` field
2. Wrap it in custom_code with section extraction (see metric-design skill)
3. Set both `description` (the prompt) and `custom_code` (the Python wrapper)
4. Toggle to custom_code as the active type

This gives the benefit of the labs-refined prompt with the performance advantage of targeted context extraction.

## Interactive Labs Simulation

When the user wants to simulate the labs workflow interactively:

1. Fetch recent calls and metric results
2. Present potentially misaligned results to the user one at a time
3. Ask: "Call [ID] was scored [result]. Here's the explanation: [explanation]. The transcript shows: [relevant excerpt]. Do you agree with this result?"
4. If user disagrees, generate the feedback payload and submit via mark_metric_vote
5. Track feedback count and notify when 6+ is reached
6. Offer to trigger auto-improve

## API Endpoints Reference

| Endpoint | Purpose |
|----------|---------|
| `GET /observability/v1/call-logs-external/?agent=ID` | List calls |
| `GET /observability/v1/call-logs-external/{id}/` | Get call details + evaluation results |
| `POST /observability/v1/call-logs-external/{id}/mark_metric_vote/` | Leave feedback |
| `POST /test_framework/metric-reviews/process_feedbacks/` | Run labs auto-improve (see below) |
| `GET /test_framework/metric-reviews/process_feedbacks_progress/` | Poll improvement progress |
| `POST /observability/v1/call-logs/evaluate_metrics/` | Evaluate specific metrics on calls |
| `POST /observability/v1/call-logs/rerun_evaluation/` | Re-run evaluation on calls |
| `POST /test_framework/test-sets/create_from_call_log/` | Create test set from call log |

### Labs Auto-Improve (process_feedbacks)

```json
POST /test_framework/metric-reviews/process_feedbacks/
{
  "metric_id": 123,
  "test_set_ids": [456, 789]
}
```

Optional fields: `metric_type` (default "llm_judge"), `skip_evaluation` (bool), `simplified_prompt` (string).

Returns `{"progress_id": "<uuid>"}`. Poll at `GET /test_framework/metric-reviews/process_feedbacks_progress/?progress_id=<uuid>`.

The response includes improved `description` and `evaluation_trigger` when complete — **you must PATCH the metric to apply changes** (they are not auto-applied).

### Create Test Set from Call Log

```json
POST /test_framework/test-sets/create_from_call_log/
{
  "call_log_id": 3358270,
  "metrics": [{"metric": 123, "feedback": "The metric incorrectly failed this call because..."}]
}
```

**Note:** `metrics` must be an array of objects `[{"metric": <id>, "feedback": "<text>"}]`, NOT bare metric IDs. Passing bare IDs returns 500.

## Additional Resources

### Reference Files

- **`references/feedback-examples.md`** — Examples of good feedback for different metric types
