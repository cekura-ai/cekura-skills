---
name: delete-metric
description: Delete a Cekura metric
argument-hint: "[metric ID]"
allowed-tools: ["Bash", "AskUserQuestion"]
---

# Delete a Cekura Metric

Remove a metric from the Cekura platform. This is irreversible.

## Process

1. **Identify the metric**: Get the metric ID.

2. **Fetch current state** to confirm with the user:
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
get_metric "METRIC_ID"
```

3. **Confirm deletion**: Show the metric name and details. Ask: "Are you sure you want to delete metric [NAME] (ID: [ID])? This cannot be undone."

4. **Delete**:
```bash
delete_metric "METRIC_ID"
```

5. **Verify**: A successful delete returns HTTP 204. Confirm with the user.

## Warning

Deleting a metric removes it permanently. If other metrics gate on this metric's results (via `data.get("Metric Name")`), those downstream metrics will break. Check for dependencies before deleting.
