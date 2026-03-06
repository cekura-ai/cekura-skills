---
name: Cekura Labs Workflow
description: >
  This skill should be used when the user asks to "improve a metric", "run labs",
  "leave feedback on a metric", "add to labs", "fix metric accuracy",
  "review metric results", "find misaligned metrics", "iterate on metric quality",
  or discusses the metric improvement cycle, feedback workflow, or labs pipeline
  in the Cekura platform.
version: 0.1.0
---

# Cekura Labs Workflow

## Purpose

Guide the metric improvement cycle: identify misaligned metric results, leave structured feedback, run the labs improvement pipeline, and validate changes. This workflow transforms metric quality from initial draft to production-ready through systematic iteration.

## The Labs Improvement Cycle

The full cycle for improving a metric:

1. **Identify misalignment** — Find calls where metric results seem wrong
2. **Leave feedback** — Vote agree/disagree with explanation on specific results
3. **Accumulate feedback** — Collect 6+ feedback instances for statistical significance
4. **Run auto-improve** — Labs uses feedback to suggest metric prompt changes
5. **Validate changes** — Re-run the improved metric on the same calls to verify
6. **Deploy** — Once satisfied, optionally convert to Pythonic custom_code for production

## Step 1: Identify Misaligned Results

### Manual Approach

Review recent call evaluations to find suspicious results:

```bash
# List recent calls for an agent
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
list_calls "agent=AGENT_ID&limit=50"

# Get evaluation results for a specific call
get_call_evaluation "CALL_ID"
```

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

Use the `mark_metric_vote` endpoint to leave structured feedback:

```bash
# Vote on a metric result for a specific call
mark_metric_vote "CALL_ID" '{"metric_id": METRIC_ID, "vote": "disagree", "feedback": "The metric failed this call because the agent asked two questions in one turn, but they were related follow-ups about the same topic (address confirmation). This should be a PASS per the spirit-vs-letter principle."}'
```

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

```bash
# Trigger auto-improvement for a metric
auto_improve_metric "METRIC_ID"
```

Labs analyzes the feedback and suggests changes to the metric prompt. Review the suggested changes carefully:
- Do the changes address the feedback patterns?
- Are the changes too broad (might break other cases)?
- Do the safeguarding examples align with the feedback?

## Step 5: Validate Changes

Re-run the improved metric on the same calls that had misaligned results:

```bash
# Re-evaluate specific calls with the updated metric
rerun_evaluation '{"call_ids": [123, 456, 789], "metric_ids": [METRIC_ID]}'
```

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
| `GET /observability/v1/call-logs-external/{id}/evaluation/` | Get metric results for a call |
| `POST /observability/v1/call-logs-external/{id}/mark_metric_vote/` | Leave feedback |
| `POST /test_framework/v1/metrics/{id}/auto-improve/` | Run labs auto-improve |
| `POST /observability/v1/call-logs-external/rerun_evaluation/` | Re-run metrics on calls |
| `POST /observability/v1/call-logs-external/evaluate_metrics/` | Evaluate specific metrics on calls |

## Additional Resources

### Reference Files

- **`references/feedback-examples.md`** — Examples of good feedback for different metric types
