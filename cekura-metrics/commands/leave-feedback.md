---
name: leave-feedback
description: Leave feedback (agree/disagree) on a Cekura metric evaluation result
argument-hint: "[call ID and metric ID, or 'guide me']"
allowed-tools: ["Bash", "AskUserQuestion"]
---

# Leave Feedback on Metric Results

Vote agree or disagree on metric evaluation results, with structured explanations. This feedback fuels the labs improvement pipeline.

## Process

1. **Identify the result**: Get the call ID and metric ID for the result to review.
   - If not provided, fetch recent evaluations:
   ```bash
   source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
   list_calls "agent=AGENT_ID&limit=20"
   ```
   Then get evaluation results for a specific call:
   ```bash
   get_call_evaluation "CALL_ID"
   ```

2. **Review the result**: Show the user:
   - Metric name and result (TRUE/FALSE/enum value/score)
   - The metric's explanation
   - Relevant transcript excerpts if available

3. **Ask for feedback**: "Do you agree with this result? If not, what should it be and why?"

4. **Submit feedback**:
```bash
mark_metric_vote "CALL_ID" '{"metric_id": METRIC_ID, "vote": "disagree", "feedback": "STRUCTURED_EXPLANATION"}'
```

5. **Track progress**: Remind the user how many feedback instances they've submitted for this metric. Labs needs 6+ before auto-improve can run effectively.

## Writing Good Feedback

Good feedback references:
- Specific transcript timestamps (MM:SS) where the issue occurred
- The exact agent utterance that was misjudged
- Why the metric result is wrong (what it should be and why)
- Which safeguarding principle was violated (spirit vs letter, etc.)

See the labs-workflow skill for detailed feedback patterns.

## Interactive Mode

If the user says "guide me" or wants help finding misaligned results:
1. Fetch recent calls with metric evaluations
2. Present potentially misaligned results one at a time
3. Ask the user to agree/disagree
4. Submit feedback for disagreements
5. Track running total toward the 6-feedback threshold
