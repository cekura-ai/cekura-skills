---
name: list-evals
description: List Cekura evaluators filtered by agent, project, or tags
argument-hint: "[agent ID, project ID, or tags]"
allowed-tools: ["Bash", "AskUserQuestion"]
---

# List Cekura Evaluators

Fetch and display evaluators from the Cekura platform.

## Process

1. **Determine filter**: Ask for agent ID, project ID, or tags if not provided.

2. **Fetch evaluators**:
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
list_scenarios "agent=AGENT_ID"
# or filter by tags
list_scenarios "agent=AGENT_ID&tags=Scheduling"
```

3. **Present results**: Display evaluators in a clear table:
   - ID, Name, Tags, Has Instructions, Has Expected Outcome
   - Group by category tag if available
   - Show counts by category and priority
