---
name: add-to-labs
description: Add a Cekura metric to the labs improvement pipeline
argument-hint: "[metric ID]"
allowed-tools: ["Bash", "AskUserQuestion"]
---

# Add Metric to Labs Pipeline

Prepare a metric for the labs improvement cycle by checking feedback status and guiding the user through the process.

## Process

1. **Identify the metric**: Get the metric ID.
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
get_metric "METRIC_ID"
```

2. **Check feedback status**: Review how much feedback has been collected for this metric. Labs needs at least 6 disagree votes with explanations to have enough signal.

3. **If insufficient feedback**: Guide the user to collect more:
   - Offer to run the interactive feedback flow (see leave-feedback command)
   - Suggest specific calls to review based on result distribution
   - Track progress toward the 6-feedback threshold

4. **If sufficient feedback (6+)**: Offer to proceed:
   - Summarize the feedback patterns (what types of errors were found)
   - Ask: "Ready to run auto-improve on this metric?"

5. **Present next steps**: After labs review, the typical flow is:
   1. Run auto-improve → review suggested changes
   2. Re-evaluate on feedback calls → verify improvement
   3. Optionally convert to Pythonic custom_code for production

## Tips

- Quality of feedback matters more than quantity — 6 detailed disagreements are better than 20 vague ones
- Look for patterns in the feedback — if all disagreements are about the same issue, labs can target that specifically
- After auto-improve, always validate on the original feedback calls before deploying
