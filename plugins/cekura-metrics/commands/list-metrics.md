---
name: list-metrics
description: List Cekura metrics filtered by agent or project
argument-hint: "[agent ID or project ID]"
allowed-tools: ["Bash", "AskUserQuestion"]
---

# List Cekura Metrics

Fetch and display metrics from the Cekura platform.

## Process

1. **Determine filter**: Ask for agent ID or project ID if not provided in the arguments.

2. **Fetch metrics**:
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
list_metrics "agent=AGENT_ID"
# or
list_metrics "project=PROJECT_ID"
```

3. **Present results**: Display metrics in a clear table format:
   - ID, Name, Type, Eval Type, Trigger
   - Highlight any deprecated types or potential issues

## Environment

- API key: `CEKURA_API_KEY` env var or `.claude/cekura-metrics.local.md`
- Endpoint: `GET /test_framework/v1/metrics/`
