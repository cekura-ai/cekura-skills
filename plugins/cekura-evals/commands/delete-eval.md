---
name: delete-eval
description: Delete a Cekura evaluator
argument-hint: "[evaluator ID]"
allowed-tools: ["Bash", "AskUserQuestion"]
---

# Delete a Cekura Evaluator

Remove an evaluator from the Cekura platform. This is irreversible.

## Process

1. **Identify the evaluator**: Get the evaluator ID.

2. **Fetch current state** to confirm:
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
get_scenario "SCENARIO_ID"
```

3. **Confirm deletion**: Show the eval name and details. Ask: "Are you sure you want to delete evaluator [NAME] (ID: [ID])?"

4. **Delete**:
```bash
delete_scenario "SCENARIO_ID"
```
