---
name: update-metric
description: Update an existing Cekura metric's configuration or prompt
argument-hint: "[metric ID and what to change]"
allowed-tools: ["Bash", "Read", "Write", "Edit", "AskUserQuestion"]
---

# Update a Cekura Metric

Modify an existing metric on the Cekura platform.

## Process

1. **Identify the metric**: Get the metric ID. If not provided, use list-metrics to find it.

2. **Fetch current state**:
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
get_metric "METRIC_ID"
```

3. **Show current configuration**: Display the current metric fields so the user can see what they're changing.

4. **Determine changes**: Understand what the user wants to modify:
   - Prompt/description text
   - Eval type
   - Trigger configuration
   - Custom code
   - Name

5. **Apply changes**: Confirm with user before updating.
```bash
update_metric "METRIC_ID" '{"description": "NEW_PROMPT"}'
```

6. **Verify**: Fetch the metric again to confirm changes were applied.

## Key Reminders

- PATCH only sends the fields being changed, not the full payload
- If updating the prompt, follow metric design best practices (spirit vs letter, safeguarding, etc.)
- After prompt changes, consider re-running the metric on recent calls to validate
