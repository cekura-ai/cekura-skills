---
name: cekura-results-report
description: Client-ready report on existing Cekura test results, shaped by the ask (weekly status, leadership summary, responsiveness, security, P0 flows, failed calls, agent comparison, a topic). Read-only.
argument-hint: "[agent ID or name] [what the report should answer]"
allowed-tools:
  [
    "Skill",
    "AskUserQuestion",
    "mcp__cekura__results_list",
    "mcp__cekura__results_retrieve",
    "mcp__cekura__results_reports_retrieve",
    "mcp__cekura__runs_bulk_retrieve",
    "mcp__cekura__runs_retrieve",
    "mcp__cekura__aiagents_list",
    "mcp__cekura__aiagents_retrieve",
    "mcp__cekura__scenarios_list",
    "mcp__cekura__metrics_list",
    "mcp__cekura__predefined_metrics_list",
    "mcp__cekura__call_logs_list",
    "mcp__cekura__call_logs_retrieve",
    "mcp__cekura__metric_failure_mode_insights_list",
    "mcp__cekura__cekura_skill_started",
    "mcp__cekura__cekura_report_issue",
  ]
---
<!-- cekura-tracking-beacon -->

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="cekura-results-report"`. If a conversation/session ID is available (e.g. you
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

# /cekura-results-report

Design a client-ready report on test results that **already exist**, shaped by what the user asks. Read-only: never generate scenarios, run tests or change anything.

Arguments: `$ARGUMENTS` — an agent (ID or name) and what the report should answer, e.g. `/cekura-results-report 12345 how responsive is the agent?`.

## Process

1. **Load the skill.** Invoke the `cekura:cekura-results-report` skill via `Skill` and follow it — its flow, references and quality check. (Its tracking call is covered by the one above; don't repeat it.)
2. **Clarify only what blocks you.** If the agent(s) or the period are unclear, ask once with `AskUserQuestion` (choices such as "Last 14 days / Last 30 days / Pick results"); use `mcp__cekura__aiagents_list` to resolve an agent name. Defaults when the user says "go ahead": all agents, the last 14 days, all test results in the period.
3. **Redirect when it's the other kind of request.** Testing an agent from scratch → `/cekura-report`.
4. **Reply** with a 3–5 line chat summary, the report as one JSON block between `<!-- CEKURA-V0-REPORT-START -->` and `<!-- CEKURA-V0-REPORT-END -->`, and the line "Open the report above, or use Download PDF on it." Run the skill's quality check before sending.
