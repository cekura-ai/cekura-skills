---
name: list-evals
description: List Cekura evaluators filtered by agent, project, or tags
argument-hint: "[agent ID, project ID, or tags]"
allowed-tools: ["AskUserQuestion", "mcp__cekura__scenarios_list", "mcp__cekura__cekura_skill_started", "mcp__cekura__cekura_report_issue"]
---
<!-- cekura-tracking-beacon -->

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="list-evals"`. If a conversation/session ID is available (e.g. you
were invoked from Cekura sandbox), also pass it as `conversation_id`. The call
returns immediately; it lets us understand which skills are actually being used.

If anything in this skill turns out to be ambiguous, broken, or missing a
needed tool, you may flag it with `mcp__cekura__cekura_report_issue` (even
`severity="low"` is useful), but only with the user's OK. Don't interrupt
the task for it: when the task is done, show the user the exact text of every
field you would send. In Claude Code, then call the tool: Claude Code asks the
user to approve it and remembers a "Yes, and don't ask again". Anywhere else,
ask in chat and call the tool only after they agree. If they decline, drop it.
Exception: when you are the Cekura AI Assistant in the Cekura dashboard (the
Cekura sandbox above), send it without asking, since that conversation
already runs on Cekura.

# List Cekura Evaluators

Fetch and display evaluators from the Cekura platform.

## Process

1. **Determine filter**: Ask for agent ID, project ID, or tags if not provided.

2. **Fetch evaluators**: Use `mcp__cekura__scenarios_list` with appropriate filters (e.g., `agent`, `project`, `tags`).

3. **Present results**: Display evaluators in a clear table:
   - ID, Name, Tags, Has Instructions, Has Expected Outcome
   - Group by category tag if available
   - Show counts by category and priority
