---
name: self-improve
description: Improve YOUR AGENT from eval/run results — entrypoint for the cekura-self-improving-agent skill (diagnose failures, fix prompt/tools, re-validate). Not for improving metrics.
argument-hint: "[agent ID | via these evaluators - <scenario IDs> (result ids: <result IDs>)]"
allowed-tools: ["Skill", "AskUserQuestion", "Read", "Bash", "mcp__cekura__cekura_skill_started", "mcp__cekura__cekura_report_issue"]
---
<!-- cekura-tracking-beacon -->

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="self-improve"`. If a conversation/session ID is available (e.g. you
were invoked from Cekura sandbox), also pass it as `conversation_id`. The call
returns immediately; it lets us understand which skills are actually being used.

If anything in this skill turns out to be ambiguous, broken, or missing a
needed tool, call `mcp__cekura__cekura_report_issue` to flag it. Use this
LIBERALLY — even `severity="low"` reports are valuable feedback.

# `/self-improve`

Improve the **user's agent** based on evaluation results: diagnose failing
runs, propose and apply fixes to the agent's prompt / tool config, then
re-run the same evaluators to verify the fix. The full loop lives in the
`cekura-self-improving-agent` skill; this command is only the entrypoint.

**Load the `cekura-self-improving-agent` skill now and follow it.** Do not
improvise the loop from memory — the skill's Setup phase (target resolution,
self-hosted vs provider apply path, must-fail-first reproduction) and its
mandatory post-change re-validation run are the whole point.

## This is NOT metric improvement

`/self-improve` never means the `improve-metric` command. The user wants
their agent fixed, not a metric's grading changed. Only route to
`improve-metric` when the user explicitly disputes a metric's score or
explanation ("this metric is wrong", "disagree with this result").

## Argument Parsing

| Token shape | Meaning |
|---|---|
| Bare numeric ID or "agent <ID>" | The Cekura agent to improve. |
| `via these evaluators - <IDs>` | **Scenario** (evaluator) IDs to diagnose and re-run. Evaluators are scenarios — NEVER treat these IDs as metric IDs or call `metrics_retrieve` on them; use `scenarios_retrieve`. |
| `(result ids: <IDs>)` | Result-set IDs holding the failing runs to diagnose. |
| No args | Ask which agent (and optionally which result set) to improve. |

Hand every parsed ID to the skill's Setup phase and continue there.
