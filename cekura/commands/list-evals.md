---
name: list-evals
description: List Cekura evaluators filtered by agent, project, or tags
argument-hint: "[agent ID, project ID, or tags]"
allowed-tools: ["AskUserQuestion", "mcp__cekura__scenarios_list"]
---

# List Cekura Evaluators

Fetch and display evaluators from the Cekura platform.

## Process

1. **Determine filter**: Ask for agent ID, project ID, or tags if not provided.

2. **Fetch evaluators**: Use `mcp__cekura__scenarios_list` with appropriate filters (e.g., `agent`, `project`, `tags`).

3. **Present results**: Display evaluators in a clear table:
   - ID, Name, Tags, Has Instructions, Has Expected Outcome
   - Group by category tag if available
   - Show counts by category and priority
