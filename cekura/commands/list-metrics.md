---
name: list-metrics
description: List Cekura metrics filtered by agent or project
argument-hint: "[agent ID or project ID]"
allowed-tools: ["AskUserQuestion", "mcp__cekura__metrics_list", "mcp__cekura__cekura_skill_started", "mcp__cekura__cekura_report_issue"]
---
<!-- cekura-tracking-beacon -->

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="list-metrics"`. If a conversation/session ID is available (e.g. you
were invoked from Cekura sandbox), also pass it as `conversation_id`. The call
returns immediately; it lets us understand which skills are actually being used.

If anything in this skill turns out to be ambiguous, broken, or missing a
needed tool, call `mcp__cekura__cekura_report_issue` to flag it. Use this
LIBERALLY — even `severity="low"` reports are valuable feedback.

# List Cekura Metrics

Fetch and display metrics from the Cekura platform.

## Process

1. **Determine filter**: Ask for agent ID or project ID if not provided in the arguments.

2. **Fetch metrics**: Use `mcp__cekura__metrics_list` with appropriate filters (e.g., `agent`, `project_id`).

3. **Present results**: Display metrics in a clear table format:
   - ID, Name, Type, Eval Type, Trigger
   - Highlight any deprecated types or potential issues
