---
name: improve-metric
description: Improve a Cekura metric through feedback collection, labs pipeline, and auto-improvement
argument-hint: "[metric ID] [feedback|improve|full-cycle]"
allowed-tools: ["AskUserQuestion", "mcp__cekura__metrics_retrieve", "mcp__cekura__metrics_partial_update", "mcp__cekura__metrics_run_reviews_create", "mcp__cekura__metrics_run_reviews_progress", "mcp__cekura__call_logs_list", "mcp__cekura__call_logs_retrieve", "mcp__cekura__call_logs_rerun_evaluation_create", "mcp__cekura__test_sets_create_from_call_log", "mcp__cekura__test_sets_create_from_run", "mcp__cekura__metric_reviews_process_feedbacks", "mcp__cekura__metric_reviews_process_feedbacks_progress"]
---

# Improve a Metric

Single entry point for the full metric improvement cycle: collecting feedback, adding to labs, and running auto-improvement. The labs-workflow skill provides detailed guidance on feedback patterns and improvement strategy.

## Determine Phase

Ask what the user needs or infer from context:

| User Says | Phase |
|-----------|-------|
| "leave feedback", "this metric is wrong", "disagree with result" | **Phase 1: Collect Feedback** |
| "add to labs", "ready for improvement", "enough feedback" | **Phase 2: Check Readiness** |
| "improve", "run auto-improve", "fix this metric" | **Phase 3: Auto-Improve** |
| "full cycle", "help me improve this metric" | **Full cycle: all phases** |

## Phase 1: Collect Feedback

Feedback fuels the labs improvement pipeline. Each feedback instance teaches the system what the metric got wrong and why.

### Find Misaligned Results

1. **Get the metric**: Use `mcp__cekura__metrics_retrieve` with the metric ID. Note the metric name and what it evaluates.

2. **Fetch recent evaluations**: Use `mcp__cekura__call_logs_list` filtered by agent/project. For each call, use `mcp__cekura__call_logs_retrieve` to see evaluation results.

3. **Identify potential misalignments**: Look for:
   - Results that seem wrong based on the transcript (false passes or false fails)
   - Results where the explanation doesn't match the transcript evidence
   - N/A results on calls where the metric should have fired (or vice versa)
   - Inconsistent results across similar calls

### Submit Feedback

For each misaligned result:

1. **Show the user**: Present the metric result, explanation, and relevant transcript excerpt
2. **Ask**: "Do you agree with this result? If not, what should it be and why?"
3. **Record feedback**: Add to labs via `mcp__cekura__test_sets_create_from_call_log`:
   ```
   call_log_id: <call_id>
   metrics: [{"metric": <metric_id>, "feedback": "<user's explanation of why result is wrong>"}]
   ```

### Writing Good Feedback

Good feedback includes:
- Specific transcript timestamps (MM:SS) where the issue occurred
- The exact agent utterance that was misjudged
- Why the metric result is wrong (what it should be and why)
- Which principle was violated (spirit vs letter, cross-pollination from other flows, etc.)

**Example:** "FALSE at 2:45 — agent correctly said 'let me transfer you to scheduling' which IS the callback protocol per the description. Metric flagged this because it confused the transfer-to-scheduling flow with the emergency-transfer flow."

### Interactive Feedback Mode

If the user says "guide me" or wants help finding misaligned results:
1. Fetch recent calls with metric evaluations
2. Present potentially misaligned results one at a time
3. Ask the user to agree/disagree
4. Submit feedback for disagreements
5. **Track running total**: "You've submitted [N]/6 feedback instances for this metric."

## Phase 2: Check Readiness

Labs needs at least **6 disagree instances** with explanations to have enough signal for meaningful improvement.

1. **Check feedback count**: Fetch the metric and check its reviews/test sets
2. **If insufficient (< 6)**: Guide the user to collect more — offer interactive feedback mode (Phase 1)
3. **If sufficient (6+)**: Summarize the feedback patterns:
   - What types of errors were found? (false passes, false fails, wrong N/A)
   - Common themes? (cross-pollination, missing DO NOT FLAG items, trigger too broad/narrow)
   - "Ready to run auto-improve? The feedback suggests [summary of issues]."

## Phase 3: Auto-Improve

### Before Auto-Improve: Consider Manual Fix First

**When metrics have systemic issues (high false-fail rates), do NOT jump straight to auto-improve.** Instead:
1. Read failure explanations and categorize root causes
2. If a dominant pattern is clearly fixable by prompt editing (e.g., missing DO NOT FLAG item, wrong scope), apply the manual fix first via `/create-metric` (update mode)
3. Use labs auto-improve for remaining edge cases that manual fixes didn't catch

### Run Auto-Improve

1. **Trigger**: Use `mcp__cekura__metrics_run_reviews_create` with the metric ID.

2. **Poll for completion**: Use `mcp__cekura__metrics_run_reviews_progress` with the progress ID. Poll every 10 seconds.

3. **Review changes**: Fetch the updated metric with `mcp__cekura__metrics_retrieve` and compare:
   - Show the diff between old and new prompt
   - Highlight what labs changed and why (based on feedback patterns)
   - Assess whether the changes address the feedback issues

4. **Validate on feedback calls**: Re-run the improved metric on the calls that had feedback:
   Use `mcp__cekura__call_logs_rerun_evaluation_create` with the call IDs and metric ID.

5. **Check regression**:
   - Previously misaligned calls now produce correct results? (improvement)
   - Previously correct calls didn't regress? (stability)
   - Explanations are clearer? (quality)

6. **If satisfied**: Confirm the improvement is deployed (changes are live immediately after auto-improve).

7. **If not satisfied**: Options:
   - Apply manual prompt fixes on top of the auto-improved version
   - Collect more feedback on remaining issues and run another improvement cycle
   - Consider converting to custom_code with section extraction for hard-isolation (Pythonic pattern)

## Post-Improvement Checklist

- [ ] Feedback collected (6+ instances with explanations)
- [ ] Feedback patterns categorized (dominant issues identified)
- [ ] Manual fixes applied for obvious/systemic issues (if applicable)
- [ ] Auto-improve ran successfully
- [ ] Prompt changes reviewed and make sense
- [ ] Re-evaluated on feedback calls — misalignments fixed
- [ ] Spot-checked other calls — no regression
- [ ] Cross-project copies updated (if metric exists on multiple projects)

## Tips

- Quality of feedback matters more than quantity — 6 detailed disagreements are better than 20 vague ones
- Look for patterns — if all disagreements are about the same issue, labs targets it more effectively
- Plan for 2-3 feedback rounds before a metric stabilizes — each round reveals new edge cases
- The most common feedback categories: extra_questions flagged as failures, end_protocol violations, should-be-N/A calls, cross-pollination from adjacent flows
- After auto-improve, always validate before considering the metric done
