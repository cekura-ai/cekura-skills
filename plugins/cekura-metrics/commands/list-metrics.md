---
name: list-metrics
description: List Cekura metrics filtered by agent or project
argument-hint: "[agent ID or project ID]"
allowed-tools: ["AskUserQuestion", "mcp__cekura__metrics_list"]
---

# List Cekura Metrics

Fetch and display metrics from the Cekura platform.

## Process

1. **Determine filter**: Ask for agent ID or project ID if not provided in the arguments.

2. **Fetch metrics**: Use `mcp__cekura__metrics_list` with appropriate filters (e.g., `agent`, `project_id`).

3. **Present results**: Display metrics in a clear table format:
   - ID, Name, Type, Eval Type, Trigger
   - Highlight any deprecated types or potential issues
