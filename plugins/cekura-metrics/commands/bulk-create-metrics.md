---
name: bulk-create-metrics
description: Create multiple Cekura metrics from a specification file or structured input
argument-hint: "[path to spec file or description of metrics to create]"
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "AskUserQuestion"]
---

# Bulk Create Cekura Metrics

Create multiple metrics at once from a structured specification.

## Process

1. **Identify the source**: Determine where the metric definitions come from:
   - A specification file (JSON, CSV, or markdown)
   - Existing metric files in a directory (like the Elyos Metrics pattern)
   - User description that needs to be converted to metrics

2. **Parse the specifications**: Read and validate each metric definition. Required fields per metric:
   - `name` — descriptive metric name
   - `description` — evaluation prompt (for llm_judge) or description text
   - `type` — `llm_judge` or `custom_code`
   - `eval_type` — binary_qualitative, binary_workflow_adherence, enum, numeric, etc.
   - `agent` or `project` — target agent/project ID

3. **Review all metrics**: Present a summary table of all metrics to be created:
   - Name, Type, Eval Type, Trigger
   - Highlight any issues (missing fields, deprecated types, etc.)

4. **Get user confirmation**: "I'm about to create [N] metrics. Proceed?"

5. **Create sequentially**: Create each metric via API, collecting results:
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
for each metric:
  create_metric '{"name": "...", "description": "...", ...}'
```

6. **Report results**: Show which metrics were created successfully and any failures.

## Specification Formats

### JSON Array
```json
[
  {"name": "Metric 1", "description": "...", "type": "llm_judge", "eval_type": "binary_qualitative"},
  {"name": "Metric 2", "description": "...", "type": "custom_code", "eval_type": "binary_workflow_adherence"}
]
```

### Directory of Metric Files
Follow the Elyos pattern — `.md` files for llm_judge prompts, `.py` files for custom_code:
```
metrics/
├── 1-soft-skills.md      # llm_judge prompt
├── 2-classification.md   # llm_judge prompt
├── 3-flow-adherence.py   # custom_code
```

### CSV
```csv
name,type,eval_type,trigger,prompt_file
"Soft Skills",llm_judge,binary_qualitative,always,prompts/soft-skills.md
"Flow Adherence",custom_code,binary_workflow_adherence,always,code/flow.py
```

## Pre-Creation Checklist

Before creating custom metrics, verify baseline predefined metrics are enabled:
- **Expected Outcome**, **Infrastructure Issues**, **Tool Call Success**, **Latency**
- These require two-step activation: project-level toggle + per-evaluator attachment

## Tips

- Consider metric ordering if any metrics gate on others (create upstream metrics first)
- Verify agent ID exists before bulk creation
- Keep metric names consistent (numbered prefix helps: "1 - Name", "2 - Name")
- Use `llm_judge` by default — only use `custom_code` for gating on upstream metrics or section extraction
- Do NOT use deprecated types `basic` or `custom_prompt` — they return 400
