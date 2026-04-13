---
name: evaluate-calls
description: Run specific Cekura metrics against selected calls for evaluation or re-evaluation
argument-hint: "[call IDs and/or metric IDs]"
allowed-tools: ["AskUserQuestion", "mcp__cekura__call_logs_list", "mcp__cekura__call_logs_retrieve", "mcp__cekura__call_logs_evaluate_metrics_create", "mcp__cekura__call_logs_rerun_evaluation_create", "mcp__cekura__metrics_list"]
---

# Evaluate Calls with Metrics

Run specific metrics against selected calls, or re-evaluate calls that have already been scored.

## Process

1. **Identify targets**: Determine which calls and which metrics to evaluate.
   - If the user provides call IDs and metric IDs, use them directly
   - If the user wants to evaluate recent calls, fetch them first:
     Use `mcp__cekura__call_logs_list` with agent or project filters.
   - If the user wants specific metrics, list them:
     Use `mcp__cekura__metrics_list` with agent or project filters.

2. **Confirm scope**: Show the user what will be evaluated:
   - Number of calls x number of metrics = total evaluations
   - Warn if this is a large batch

3. **Run evaluation**:
   Use `mcp__cekura__call_logs_evaluate_metrics_create` with call IDs and metric IDs.
   For re-evaluation: Use `mcp__cekura__call_logs_rerun_evaluation_create`.

4. **Check results**: After evaluation completes, offer to fetch results:
   Use `mcp__cekura__call_logs_retrieve` with the call ID.

## Use Cases

- **Testing a new metric**: Run it against a few known calls to validate behavior
- **Re-evaluating after metric changes**: Verify the updated prompt produces better results
- **Spot-checking**: Run metrics on specific calls flagged for review
- **Validating labs improvements**: Re-run on the same calls used for feedback
