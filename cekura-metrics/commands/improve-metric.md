---
name: improve-metric
description: Run Cekura's auto-improve on a metric using accumulated feedback from labs
argument-hint: "[metric ID]"
allowed-tools: ["Bash", "AskUserQuestion"]
---

# Auto-Improve a Cekura Metric

Trigger the labs auto-improvement pipeline for a metric that has accumulated sufficient feedback (6+ instances).

## Process

1. **Identify the metric**: Get the metric ID.
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
get_metric "METRIC_ID"
```

2. **Verify readiness**: Check that enough feedback has been collected. Warn if fewer than 6 instances.

3. **Run auto-improve**:
```bash
auto_improve_metric "METRIC_ID"
```

4. **Review changes**: Fetch the updated metric and compare the prompt changes:
```bash
get_metric "METRIC_ID"
```
   - Show the diff between old and new prompt
   - Highlight what labs changed and why (based on feedback patterns)
   - Assess whether the changes address the feedback issues

5. **Validate**: Offer to re-run the improved metric on the calls that had feedback:
```bash
rerun_evaluation '{"call_ids": [CALL_IDS_FROM_FEEDBACK], "metric_ids": [METRIC_ID]}'
```

6. **Check regression**: After re-evaluation, verify:
   - Previously misaligned calls now produce correct results
   - Previously correct calls didn't regress
   - Explanations are clearer

7. **Optional Pythonic conversion**: If the user is satisfied, offer to convert to custom_code with section extraction for production performance. See the metric-design skill for the Pythonic pattern.

## Post-Improvement Checklist

- [ ] Auto-improve ran successfully
- [ ] Prompt changes reviewed and make sense
- [ ] Re-evaluated on feedback calls — misalignments fixed
- [ ] Spot-checked other calls — no regression
- [ ] Considered Pythonic conversion for production
