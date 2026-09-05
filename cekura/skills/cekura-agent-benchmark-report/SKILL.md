---
name: cekura-agent-benchmark-report
description: "Build a complete, benchmarked Cekura voice-agent evaluation: discover agent workflows, create and validate 5–10 metric-attached evaluators, run a weighted 100-call batch, and produce an evidence-linked HTML report. Use when a user wants an end-to-end benchmark report, not merely analysis of an existing result."
license: MIT
metadata:
  author: cekura
  version: "1.5.0"
---

# Cekura Agent Benchmark Report

Create a defensible benchmark report from a fresh evaluation suite. The workflow is:

1. select and inspect the agent;
2. derive the core workflows from its configuration;
3. create 5–10 focused evaluators and diverse test profiles;
4. attach the report metric set;
5. run each evaluator once and fix only evaluator-related defects;
6. run a weighted 100-call batch;
7. generate a self-contained HTML report from the measured results.

This is a single end-to-end operation. Once the user has authorized the evaluation, continue from batch completion through report assembly, validation, visual inspection, and delivery without asking whether to generate the report or stopping at an intermediate status. A status request during that work is informational: answer it concisely, then resume the workflow. Do not call the work complete, or hand off a report path, until the artifact exists and passes every required check.

Use this skill when the user asks to evaluate an agent and produce a benchmark report. If the user already has a completed result and wants only a report refresh, skip directly to **Report the batch**.

## Locked report template

Every report produced by this skill uses the immutable sample template at [assets/benchmark-report-template.html](assets/benchmark-report-template.html). It is the visual and structural source of truth, not merely an inspiration. Read [references/template-contract.md](references/template-contract.md) before generating or refreshing a report.

Copy that template as the starting document and populate it with the selected agent's measured values, run date, scenario labels, evidence URLs, and the freshly retrieved Bench values. This is a hard requirement, not a styling preference. Do not redesign it or borrow markup from another prior report. Preserve its CSS, document hierarchy, section order, header, navigation, card layout, horizontal-bar treatment, selected-agent emphasis, urgent-issue band, evidence ledger, print behavior, and latency-chart interaction exactly. When a report fails the template contract, regenerate it from the canonical template; never repair the deviation with overrides or a parallel layout.

The only allowed changes are data substitutions inside the existing components: agent/suite names, numerical values, narrative grounded in the selected run, result and call links, dynamic bar/table rows, unavailable labels, SVG data coordinates/labels, and the existing chart data payloads. The selected agent's name and measured values are not a reason to add, remove, restyle, reorder, or substitute UI components. If a required metric cannot be populated, retain its existing component and render the value as **Unavailable**. If the requested content cannot fit the locked component, report the limitation rather than creating a new layout.

## Select and inspect

If the user has not identified an agent, list the available agents and ask them to choose. Retrieve the selected agent and inspect its prompt, description, language, tools, dynamic variables, knowledge-base context, and connection mode.

Derive the workflow inventory from the agent's actual instructions. Identify the high-volume, high-risk, or business-critical paths; required data collection; handoffs; allowed and forbidden claims; correction/recovery behavior; and completion criteria. Do not invent policies, products, tools, or business facts. Do not modify the agent configuration as part of this workflow.

Before creating scenarios, metrics, profiles, or runs, provide one concise checkpoint containing the selected agent, proposed evaluator count, representative workflows, attached metrics, expected paid metrics, the planned 100-call allocation, and a cost estimate. The estimate must state the projected number of pilot calls, the 100 batch calls, any reasonable evaluator-repair reruns, the applicable per-call and paid-metric charges (or the dashboard-provided total when available), and a conservative estimated-total range. Wait for explicit approval of that cost before starting any paid pilot or batch call, even when the user has generally authorized evaluation. If pricing cannot be retrieved, state the run count and that the cost is unavailable, then wait for approval rather than guessing.

## Build the evaluation set

Read and follow cekura-eval-design before authoring scenarios. Create 5–10 evaluators, with the count driven by the number of distinct core workflows rather than a fixed taxonomy. Each evaluator must have a specific expected outcome that can establish whether the main agent completed the intended workflow.

Ensure the set covers the agent's core functionality, not just edge cases. Include normal completion paths first, then meaningful branches such as:

- required information collection and confirmation;
- a correction, clarification, or recovery path;
- a handoff, escalation, or natural ending where applicable;
- interruption handling when the agent supports a spoken voice flow;
- a relevant negative or boundary case when it is grounded in the agent prompt.

Create diverse test profiles that vary caller name, speech style, difficulty, and relevant scenario variables without changing the target facts or success criteria. Use profiles to avoid overfitting to one caller persona; do not introduce unsupported demographic assumptions or conflicting data.

Read and follow cekura-predefined-metrics before activating or attaching metrics. Enable project-scoped versions and attach the same required report metrics to every evaluator:

| Metric | Report purpose |
| --- | --- |
| Expected Outcome | Task completion |
| Infrastructure Issues | Clean-call reliability |
| Latency | Overall, scenario, and per-turn latency |
| Interruption Score | Interruption handling |
| Stop Time after User Interruption | Interruption timing, where exercised |
| Voice Tone + Clarity | Voice naturalness |
| Humanness | Voice context |
| Gibberish Detection | Voice-quality guardrail, when audio supports it |
| Unnecessary Repetition Count | Repetition evidence |

Attach Response Consistency, Relevancy, call-termination, or transcription metrics only when they improve a stated report question and their constraints are supported. Reuse an existing project metric only when its semantics exactly match; never create duplicates.

## Pilot before the batch

Run every evaluator once, using its intended voice-capable mode. Do not infer pilot validity from aggregate pass rate or Expected Outcome alone. Retrieve the completed pilot result and inspect every failed or anomalous call, including its transcript/metric explanations, expected outcome, scenario instructions, profile values, tool calls, and call-ending behavior.

The approved estimate covers only the stated pilot and batch scope. If evaluator defects require additional paid reruns beyond the approved contingency, stop and obtain approval for the revised cost before running them.

Classify each pilot failure before proceeding:

- **Main-agent failure:** the scenario, profile, metric, and expected outcome are faithful to the agent configuration; retain it as evidence.
- **Evaluator defect:** ambiguous instructions, impossible prerequisites, a conflicting profile, unsupported tool data, an invalid metric expectation, or connection/test setup failure; correct the evaluator or profile, then rerun that evaluator once.

Do not change the agent to make a pilot pass. Do not start the 100-call batch while unresolved evaluator defects could invalidate the result. State clearly when a failure remains ambiguous and needs user direction.

Before starting the batch, record a compact pilot disposition for every evaluator: expected-outcome verdict, any non-workflow metric anomaly, its classification, and whether the evaluator is valid to retain. A call can fully meet Expected Outcome while still revealing a real agent-quality failure (for example, a voice-quality flag or an incomplete transfer); retain that finding as batch evidence rather than treating it as evaluator validation. Conversely, fix and rerun only evaluator-caused issues before batch launch.

## Run the 100-call batch

Allocate exactly 100 runs across the validated evaluators. The distribution may be uneven: assign more runs to critical workflows, high-risk branches, or paths with ambiguous/recent pilot behavior; retain at least one run for every validated evaluator. Record the allocation and rationale in the report evidence ledger.

Use the validated profiles and metrics unchanged for the batch unless a user-approved change is required. Poll the batch to completion, retrieve the full result, and retain individual run IDs for evidence.

## Report the batch

Create or refresh the requested report.html from the locked template as a self-contained artifact: no remote fonts, scripts, or chart libraries. Keep the benchmark comparison first, followed by latency, urgent issues, and the evidence ledger. Do not append CSS overrides, a second layout system, or post-render DOM injections; populate the template's existing markup and interaction hooks directly.

Resolve all result links and use the retrieved result object as the source of truth. A result may retain an in_progress top-level status after individual runs have completed. Treat a primary result and a supplemental/top-up result as separate evidence sets; state their counts and purposes. Pool a metric only when both sets use the same evaluator and the report explicitly presents the pooled total.

For task completion, use fully met Expected Outcome calls divided by expected-outcome evaluated calls; do not substitute generic success_rate. Do not reuse a value from an earlier result. If a metric is absent, show it as unavailable.

Read [references/benchmark-conventions.md](references/benchmark-conventions.md) before designing the comparison charts. For every report, fetch the current public Cekura Bench page or its live data source at report-generation time and record the retrieval date in the evidence ledger. Do not use cached or previously copied provider values. If the live source cannot be retrieved, do not render provider comparisons from stale data; state that limitation and ask the user whether to continue without them.

Use horizontal, descending bars for Task completion, Infrastructure reliability, Interruption handling, and Voice naturalness. Each chart must render every provider currently present in the live Bench cohort, plus the selected agent, rather than a curated subset. If Bench has no published value for a provider on that metric, retain the provider row and label it unavailable; do not silently omit it. Keep the leaderboard as a table. Highlight the selected agent clearly without an overflow-prone suffix. Do not assign a formal Bench rank when the scenario suite differs. When the task-completion suite differs from Bench, place a concise directional-comparison note inside the Task completion chart.

When raw Latency (in ms) graph data exists, include all of the following; a latency summary table does not substitute for either breakdown chart:

- overall P50, mean, P95, and P99;
- a visible scenario chart with response-time mean and P95;
- a separate visible per-turn chart grouping main-agent response timings by ordinal turn.

Show both charts in the page at the same time; do not use tabs, toggles, or any other control that hides one chart behind the other. Show sample counts in tooltips and preserve keyboard focus behavior for SVG points. Omit a chart only when the underlying data is absent.

For each urgent finding, link to a specific representative call with the dashboard result URL plus call_id, not merely the parent result. Choose evidence that isolates the claimed failure when practical. Do not infer an exceeded-max-duration end state unless the result explicitly says so.

## Final checks

- Make counts, percentages, bars, table values, and the evidence ledger agree.
- Before delivery, compare the provider labels in each chart against the live Bench cohort and confirm none were omitted without an explicit unavailable label.
- Include the batch allocation and rationale in the evidence ledger.
- Keep external result links intentional and report styling/scripts self-contained.
- Validate the HTML structure and inspect desktop and narrow layouts for overflow, clipping, and usability before delivery.
- Run `python3 scripts/validate_template_contract.py <report.html>` from this skill directory. It must pass alongside the normal HTML report validator. If it fails, regenerate from the locked template rather than patching visual drift with overrides.
- Render the completed local file at desktop and narrow widths and resolve visible overflow, clipping, or broken links without changing the locked template presentation.
- Confirm the output directory exists and `report.html` is nonempty. Only after this check may the skill return a final response; include a clickable report link and the absolute path.

## Autonomous completion gate

Treat the following as an atomic delivery gate after the 100-call batch completes:

1. Retrieve all batch groups and individual runs; calculate the report values and choose evidence calls.
2. Fetch the live Bench source at that time and populate every comparison row.
3. Copy the immutable template and substitute only permitted data.
4. Run both HTML validators and visually inspect the finished file.
5. Correct report-data or rendering defects and repeat validation until both checks pass.
6. Deliver the actual report file path.

Do not end on any of these incomplete states: "report generation is underway", "data is ready", "template assembly remains", or a path to a report that does not yet exist. If a required source, result, or live Bench page cannot be retrieved after reasonable retries, explain the concrete blocker and the narrowest next decision needed; otherwise, complete the report autonomously.
