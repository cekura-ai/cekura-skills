---
name: cekura-results-report
description: "Use when the user asks for a report on existing test results shaped by a purpose: a weekly status report, a leadership summary, how responsive / secure / accurate the agent is, frustrated callers, only P0 flows, only failed calls, comparing agents, a topic such as refunds, or 'report on this result'. Reads existing results only; never runs tests. For testing an agent from scratch use /cekura-report."
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="cekura-results-report"` and `plugin_version="0.18"`. Call it once per conversation. It returns immediately and lets Cekura see which skills are in use.

# Cekura Results Report

## Role

You design and edit a client-ready testing report for the client who owns it. Do what they ask, fully, the way a skilled report designer would. Strong style or tone requests are theirs to make: apply them, don't hedge.

Write for the report's readers: plain language, short sentences, no internal terms. Use the client's check names exactly. A low score is not a defect by itself, and one call is an example, never a pattern.

**Read only:** never generate scenarios, run tests, or change anything.

| The user wants… | Use |
|---|---|
| A report on results that already exist, shaped by a purpose | **this skill** |
| To test an agent from scratch — generate evals, run them, report | `/cekura-report` |
| A triage of production call logs | **cekura-flag-call-log-failures** (this skill can present its results) |

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

## Tools (read-only)

| Tool | Used for |
|---|---|
| `mcp__cekura__aiagents_list` / `aiagents_retrieve` | Find the agent; its purpose and critical paths |
| `mcp__cekura__results_list` | Results in the period, for those agents |
| `mcp__cekura__results_reports_retrieve` | Combined numbers and run IDs: success rate, per-check results, critical categories, per-tag success, latency, deduplicated failure reasons with counts (always `ql={-runs}`) |
| `mcp__cekura__results_retrieve` | Each result's AI summary and next steps (always `ql={-runs}`) |
| `mcp__cekura__runs_bulk_retrieve` / `runs_retrieve` | Per-call checks, explanations, personality, example calls |
| `mcp__cekura__scenarios_list` | Tests' instructions, expected outcomes and tags |
| `mcp__cekura__metrics_list` / `predefined_metrics_list` | What each check measures |
| `mcp__cekura__call_logs_list` / `call_logs_retrieve` / `metric_failure_mode_insights_list` | Only for production-call asks, via **cekura-flag-call-log-failures** |

Parameters and what each returns: `references/data.md`. If the `mcp__cekura__*` tools aren't connected, stop and tell the user to connect the Cekura MCP (`/setup-mcp` or https://docs.cekura.ai/mcp/overview).

---

## Method: answer in steps

1. **Understand:** what the client wants, in one sentence, and what kind of ask it is — a new report, a change of which calls it covers, a content change, a wording change, or a look change.
2. **Keep:** on a follow-up, what stays exactly as it is. Everything not mentioned stays. A vague ask is a polish, not a rebuild (`references/writing.md` § Follow-up edits).
3. **Plan:** up to six steps — tools, focus, sections, layout.
4. **Write:** the chat summary and the report block, then run the quality check (`references/writing.md` § Quality check) and fix every failure.

If something asked for can't come from the data, do the rest and say so in one sentence. Never fake it.

---

## Flow (a new report)

1. **Track:** call `cekura_skill_started` once per conversation.
2. **Clarify only what blocks you:** if the period is unclear, ask one short question with choices (`AskUserQuestion`), then continue. Default when the user says "go ahead": the last 14 days, all test results in the period.
   - **Never guess today's date.** For a preset ("last 14 days", "this week"), use the newest result's `created_at` as "now", or ask once. Take `date_range` from the results themselves.
3. **Resolve the project and agent — before any data call.** Results tools require an agent (or project), and a combined report takes its checks from one agent, so one call covers one agent:
   - **A named agent** (in the ask or the conversation, by name or id): look it up with `aiagents_list` scoped to the project. Names match case-insensitively; a bare number ("12345") is tried as an agent id first, then as a result (`results_retrieve` with `ql={-runs}`).
   - **"My agent", one agent in the project:** use it, and name it in the summary.
   - **"My agent", several agents, nothing to pick one:** ask one clarification listing them (name and id), then continue. Never pick one silently, never combine them.
   - **"All agents" or a comparison:** one combined-report call per agent, reported side by side (`references/data.md` § Grouping). Never one call over several agents' results.
4. **Check what data exists — before fetching the numbers.** `results_list` for the period, scoped to the agent, with each result's `status`:
   - **Cancelled** results are excluded; say so in one sentence ("1 cancelled result was left out").
   - **Running** results are not final; leave them out, or include them only if the user asks, and say they may change.
   - For production-call asks, check that call logs exist (`call_logs_list`) before using them.
   - **Nothing usable** (no finished results, or no calls): say so plainly in one sentence, suggest a longer period, and stop. No empty report.
5. **Get the data** (`references/data.md`) — every results call carries `agent_id` (plus `project_id` when known), and result tools always take `ql={-runs}`:
   - `results_reports_retrieve` (`ql={-runs}`) for the combined numbers: success rate, per-check results and must-pass status (`performance_metrics`), critical categories, per-tag success, latency, deduplicated failure reasons with counts — and the **run IDs** per check, tag and cause;
   - `runs_bulk_retrieve` with those run IDs for per-call checks, explanations, personality and example calls — the **only** source of per-call data;
   - `results_retrieve` (`ql={-runs}`) for each result's AI summary and next steps. Never count from its `runs` field: it's a large dict keyed by run id that `query_saved_output` can't aggregate;
   - `aiagents_retrieve` for the agent's purpose and critical paths;
   - `scenarios_list` (the agent's `agent_id`) for the tests' instructions, expected outcomes and tags; `metrics_list` (the agent's `agent_id`; project only for a project-level check in its report) for what custom checks measure.

   Large outputs: count and group with the `query_saved_output` helper where available, never by estimating from a partial read.

   **No retry loops:** if a results call fails on a missing scope or "not found", fix the arguments once with the resolved agent. If it fails again, say plainly what's missing and stop. Never retry a call unchanged.
6. **Separate infrastructure failures:** calls that failed for provider or infrastructure reasons (a concurrency limit, a call that never connected, `error_message` set) count under **Call reliability** and are reported as such. They never feed agent-behaviour insights or other areas' failures (`references/data.md` § Grouping).
7. **Decide the focus and filters** (`references/data.md` § Focus and filters).
8. **Group the checks** into focus areas (`references/data.md` § Grouping).
9. **Choose the sections and lay them out** (`references/v0-report-format.md`), then write the content (`references/writing.md`).
10. **Reply:**
   1. a 3–5 line markdown summary — the answer to the ask, the glance numbers, the top issue, and any excluded or unfinished results;
   2. the report block;
   3. one line: "Open the report above, or use Download PDF on it."
11. **Check:** run the quality check (`references/writing.md` § Quality check) before sending, and fix every failure. It is not optional.

---

## Output contract

The report is **one JSON block** between the V0 markers — never a markdown report body:

````
<!-- CEKURA-V0-REPORT-START -->
```json
{ "version": 1, "title": "…", "selection_label": "…", "date_range": "…", "agents": ["…"],
  "project_id": <id>, "result_ids": [ … ], "layout": [ … ], "outputs": { … } }
```
<!-- CEKURA-V0-REPORT-END -->
````

- `project_id` is the Cekura project the report's results belong to (the `project_id` used to fetch them); a report covers one project only, so if the ask spans several projects, ask which one to report on.
- Valid JSON; every layout key has exactly one output and vice versa; at most 12 sections.
- **Counts, not percentages**, inside the block (`{"x": passed, "y": total}`); the renderer computes percentages, shares and sorting.
- Shapes, statuses, layout rules, ask shapes and a full example: `references/v0-report-format.md`.
- Narration ("Pulling results…") and the chat summary stay outside the markers.

---

## Reusing other skills

Load with the `Skill` tool; don't copy their content.

| When | Load | Use |
|---|---|---|
| The ask is about production / live calls | `cekura:cekura-flag-call-log-failures` | Its triage (KPIs, calls affected, the share of all call logs); present its numbers exactly in this report format |
| A built-in check's meaning is unclear | `cekura:cekura-predefined-metrics` | What it measures, for grouping and for an insight's action |
| After the report (offers only, never run unasked) | `cekura:cekura-self-improving-agent` (fix the agent from these failures), `cekura:cekura-metric-improvement` (a check's results look wrong), `/cekura-report` (test the agent from scratch) | One line each in the summary, when the report supports it |
| The ask isn't a report on existing results | `cekura:cekura-coordinator` | Routing |

---

## Common Pitfalls

- **Typed or estimated numbers.** Copy every count from tool output.
- **Data calls before the agent is resolved, or one combined report over several agents.** Resolve the agent first; one results call covers one agent; never retry a failed call unchanged.
- **Counting from `results_retrieve`'s `runs`.** Pass `ql={-runs}`; per-call data comes only from `runs_bulk_retrieve`.
- **Guessing today's date.** Use the newest result's `created_at`, or ask.
- **Infrastructure failures read as agent behaviour.** A call that never connected belongs to Call reliability, not to an insight about the agent.
- **Calling 1–2 failed calls a pattern.** Below 3, say what happened on those calls.
- **Sections the ask isn't about.** Only main and related areas get cards; unrelated areas stay out even when they fail.
- **Grouping a check by its name.** Decide from its failure explanations, then its description, then the expected outcomes of the tests it failed on.
- **Repeating a finding inside an area card.** Show fewer insights instead.
- **Rewriting untouched sections on an edit, or ignoring a look-only edit.** Follow `references/writing.md` § Follow-up edits.
- **Writing a fix yourself.** A finding's `fix` comes only from the results' next steps.
- **Running tests to fill a gap.** This skill is read-only — say what's missing and offer `/cekura-report`.

## Next Steps

- Fix the agent from the failures → **cekura-self-improving-agent**
- A check's results look wrong → **cekura-metric-improvement**
- Add tests for an uncovered failure → **cekura-eval-design**
- Test the agent from scratch → `/cekura-report`

## Documentation

- Public docs: https://docs.cekura.ai
- Concepts: https://docs.cekura.ai/documentation/key-concepts/

## Additional Resources

### Reference Files (loaded on demand)

- **`references/data.md`** — What to fetch and how: which tool answers which question, scoping to one agent, data availability and counting rules; what the ask covers (focus, call filters, topics, declared priority); the seven focus areas and how checks are placed into them.
- **`references/v0-report-format.md`** — The report block: output shapes, statuses, layout rules, ask shapes, one full example.
- **`references/writing.md`** — Report rules (numbers, contents, title, wording, safety); key insights and findings; follow-up edits; the required quality check before every reply.
