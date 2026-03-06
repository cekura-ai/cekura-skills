---
name: generate-trigger
description: Auto-generate an evaluation trigger for a Cekura metric
argument-hint: "[metric description or ID]"
allowed-tools: ["Bash", "AskUserQuestion"]
---

# Generate Evaluation Trigger

Use Cekura's auto-generation to create an evaluation trigger prompt from a metric description.

## Process

1. **Get metric description**: Either from the user's input or by fetching an existing metric.

2. **Generate trigger**:
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
generate_trigger '{"description": "METRIC_DESCRIPTION"}'
```

3. **Review the generated trigger**: Present the auto-generated trigger prompt to the user. Assess:
   - Is it specific enough? (avoids false positives)
   - Is it inclusive enough? (doesn't miss relevant calls)
   - Does it match the intended use case?

4. **Refine if needed**: If the generated trigger isn't ideal, suggest modifications.

5. **Apply to metric**: If updating an existing metric, offer to apply the trigger:
```bash
update_metric "METRIC_ID" '{"evaluation_trigger": "custom", "trigger_type": "llm_judge", "evaluation_trigger_prompt": "TRIGGER_PROMPT"}'
```

## Trigger Types

| Trigger | When to Use |
|---------|-------------|
| `always` | Metric applies to every call (soft skills, business context) |
| `custom` + `llm_judge` | Conditional metrics (fires only when a scenario is detected) |
| `custom` + `custom_code` | Complex trigger logic requiring Python |
| `automatic` | Let Cekura auto-determine (less control) |
