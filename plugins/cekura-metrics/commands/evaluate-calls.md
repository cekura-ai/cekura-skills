---
name: evaluate-calls
description: Run specific Cekura metrics against selected calls for evaluation or re-evaluation
argument-hint: "[call IDs and/or metric IDs]"
allowed-tools: ["Bash", "AskUserQuestion"]
---

# Evaluate Calls with Metrics

Run specific metrics against selected calls, or re-evaluate calls that have already been scored.

## Process

1. **Identify targets**: Determine which calls and which metrics to evaluate.
   - If the user provides call IDs and metric IDs, use them directly
   - If the user wants to evaluate recent calls, fetch them first:
   ```bash
   source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
   list_calls "agent=AGENT_ID&limit=20"
   ```
   - If the user wants specific metrics, list them:
   ```bash
   list_metrics "agent=AGENT_ID"
   ```

2. **Confirm scope**: Show the user what will be evaluated:
   - Number of calls x number of metrics = total evaluations
   - Warn if this is a large batch

3. **Run evaluation**:
```bash
# For new evaluations
evaluate_calls '{"call_ids": [123, 456], "metric_ids": [789, 101]}'

# For re-evaluation of previously scored calls
rerun_evaluation '{"call_ids": [123, 456], "metric_ids": [789]}'
```

4. **Check results**: After evaluation completes, offer to fetch results:
```bash
get_call_evaluation "CALL_ID"
```

## Use Cases

- **Testing a new metric**: Run it against a few known calls to validate behavior
- **Re-evaluating after metric changes**: Verify the updated prompt produces better results
- **Spot-checking**: Run metrics on specific calls flagged for review
- **Validating labs improvements**: Re-run on the same calls used for feedback
