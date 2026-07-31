---
name: cekura-onboarding
description: State-aware Cekura onboarding that resumes at the right setup phase and delegates to the cekura-onboarding skill. Supports two variants — `testing` (default) and `observability`.
argument-hint: "[testing|observability] [agent|metrics|evals|run|ingest|evaluate|review] [project-id]"
allowed-tools:
  [
    "AskUserQuestion",
    "Read",
    "Skill",
    "mcp__cekura__list_available_tools",
    "mcp__cekura__test_simple_tool",
    "mcp__cekura__projects_list",
    "mcp__cekura__projects_create",
    "mcp__cekura__projects_retrieve",
    "mcp__cekura__aiagents_list",
    "mcp__cekura__aiagents_retrieve",
    "mcp__cekura__aiagents_create",
    "mcp__cekura__aiagents_partial_update",
    "mcp__cekura__personalities_list",
    "mcp__cekura__predefined_metrics_list",
    "mcp__cekura__metrics_list",
    "mcp__cekura__metrics_create",
    "mcp__cekura__metrics_bulk_create",
    "mcp__cekura__scenarios_list",
    "mcp__cekura__scenarios_folders_list",
    "mcp__cekura__scenarios_folder_create",
    "mcp__cekura__scenarios_generate_bg",
    "mcp__cekura__scenarios_generate_progress",
    "mcp__cekura__scenarios_partial_update",
    "mcp__cekura__scenarios_run_voice",
    "mcp__cekura__scenarios_run_text",
    "mcp__cekura__scenarios_run_websocket",
    "mcp__cekura__scenarios_run_chirp",
    "mcp__cekura__aiagents_auto_fetch_progress_retrieve",
    "mcp__cekura__runs_bulk_retrieve",
    "mcp__cekura__predefined_metrics_copy_create",
    "mcp__cekura__scenarios_run_pipecat_v1",
    "mcp__cekura__scenarios_run_pipecat_v2",
    "mcp__cekura__scenarios_run_retell_webrtc",
    "mcp__cekura__scenarios_run_vapi_webrtc",
    "mcp__cekura__scenarios_run_livekit_v2",
    "mcp__cekura__scenarios_run_elevenlabs",
    "mcp__cekura__scenarios_run_sip",
    "mcp__cekura__results_list",
    "mcp__cekura__results_retrieve",
    "mcp__cekura__observe_create",
    "mcp__cekura__call_logs_list",
    "mcp__cekura__call_logs_retrieve",
    "mcp__cekura__call_logs_evaluate_metrics_create",
    "mcp__cekura__call_logs_rerun_evaluation_create",
    "mcp__cekura__call_logs_mark_metric_vote_create",
    "mcp__cekura__cekura_skill_started",
    "mcp__cekura__cekura_report_issue",
  ]
---
<!-- cekura-tracking-beacon -->

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="cekura-onboarding"`. If a conversation/session ID is available (e.g. you
were invoked from Cekura sandbox), also pass it as `conversation_id`. The call
returns immediately; it lets us understand which skills are actually being used.

If anything in this skill turns out to be ambiguous, broken, or missing a
needed tool, flag it with `mcp__cekura__cekura_report_issue` — even
`severity="low"` reports are valuable feedback. **Show the user the report text
and get their OK before sending it.** The description is free text and can quote
their workflow, so it needs the same review as anything else leaving the machine.

# `/cekura-onboarding`

Guided end-to-end setup of a Cekura agent, from MCP preflight to a first successful test run. The full walkthrough lives in the `cekura-onboarding` skill; this command is only the state-aware entrypoint.

Goal: the user types `/cekura-onboarding` once, the command resolves the **variant** (testing or observability), detects the current project state, asks for one confirmation, then hands the right context to the skill. Keep output crisp: do not narrate successful detection calls.

---

## Argument Parsing

Up to three optional positional args, in any order — the parser classifies by shape:

| Token shape | Meaning |
|---|---|
| `testing` \| `observability` | Variant override. If absent, default to `testing`. |
| Numeric, e.g. `5242` | Project ID. Skip project picker. |
| Alphabetic phase token | Phase override (testing-flow: `agent` \| `metrics` \| `evals` \| `run`; observability-flow: `agent` \| `ingest` \| `evaluate` \| `review`). Detection still runs to populate handoff context. |
| Anything else | Ask one short clarifying question with `AskUserQuestion`. |

The variant determines which set of phase tokens is valid:
- `testing` → `agent`, `metrics`, `evals`, `run`
- `observability` → `agent`, `ingest`, `evaluate`, `review`

If the user passes a phase token that doesn't match the resolved variant, ask one clarifying question (don't silently re-route).

---

## Step 0 - Preflight

Run silently unless broken.

1. Call `mcp__cekura__list_available_tools`.
   - On error: print `MCP not connected. Run /setup-mcp first.` and stop.

That is the whole preflight — auth is proven by the first real call in state detection (a 401/403 there → print `API key invalid or missing. Set CEKURA_API_KEY, restart Claude Code, then run /setup-mcp.` and stop). Print nothing yet.

---

## Step 1 - State Detection

Detect the current state without asking the user.

### Project

**If the invoking context already fixes a project (the platform UI always does), use it and SKIP this section entirely — do not call `projects_list` or `projects_retrieve`.**

If the user passed a numeric project ID, use it directly and verify with:

```text
mcp__cekura__projects_retrieve(id=<project_id>)
```

Otherwise call `mcp__cekura__projects_list`.

| Result | Behavior |
|---|---|
| 0 projects | Create one now with `projects_create` (confirm the name with the user in the single confirmation prompt), then continue. There is no account/project phase. |
| 1 project | Auto-pick it. |
| 2+ projects | Defer selection to the single confirmation prompt. Do not ask a separate question here. |

### Agent check — the ONLY mandatory inventory call

**The first objective of onboarding is connecting the agent. Do not survey metrics, the predefined-metric catalog, scenarios, or results up front** — each phase checks its own state when it runs, and a fresh account has nothing to count.

With a chosen `project_id`, make exactly one call:

1. `mcp__cekura__aiagents_list(project_id=<project_id>, page_size=20)` — agent summaries (v2 shape: `id`, `name`; `description` may be omitted in list responses).

**If 0 agents (the common case): stop detecting. Entry phase is Phase 2 — Connect your agent.** Skip everything below and go to Step 2.

### Deeper inventory — ONLY when agents already exist (resume case)

2. `mcp__cekura__aiagents_retrieve(id=<agent_id>)` for each candidate onboarding agent. The v2 response nests provider and telephony — capture `id`, `name`, `description`, `language`, `provider.type`, `provider.agent_id`, `telephony.inbound`, and `telephony.phone_number`. (There are no flat `agent_name`/`assistant_provider`/`inbound`/`contact_number` fields.)

**Testing variant** also gathers:

3. `mcp__cekura__scenarios_list(project_id=<project_id>, page_size=5)` for evaluator count and folder/folder path names.
4. `mcp__cekura__results_list(project_id=<project_id>, page_size=1)` for latest result `id`, `status`, and any `error_message`.

**Observability variant** also gathers:

3. `mcp__cekura__call_logs_list(project_id=<project_id>, page_size=5)` for ingested call count and latest call_log id.

Hold this inventory for the handoff context.

### Entry Phase — testing variant

| Detected state | Resume at |
|---|---|
| Project, 0 agents | Phase 2 - Agent Configuration |
| Agent exists, but `description` is empty | Phase 2 - Agent Configuration (description step, `phase2-agent.md` §2c) |
| Agent OK, 0 evaluators | Phase 4 - First Evaluators (metrics are already enabled at project creation; Phase 3's silent verify runs on the way — never present a "Metrics" step to the user) |
| Evaluators exist, 0 results | Phase 5 - First Test Run |
| Latest result has `error_message` or failed/errored infrastructure status | Phase 5 - First Test Run |
| Successful/completed results exist | Phase 6 - What's Next |

### Entry Phase — observability variant

| Detected state | Resume at |
|---|---|
| Project, 0 agents | Phase 2 - Agent Configuration |
| Agent exists, but `description` is empty | Phase 2 - Agent Configuration (description step, `phase2-agent.md` §2c) |
| Agent OK, 0 ingested call logs | Phase 3 - Ingest Call Logs |
| Call logs exist, no evaluation kicked off | Phase 4 - Configure Metrics (it verifies its own state, then flows into Phase 5) |
| Evaluation done | Phase 6 - Review Results |



If the user provided an explicit phase argument, override the detected phase but keep the inventory.

---

## Step 2 - Confirmation Prompt (resume/ambiguity ONLY — skip on a clean slate)

**Clean slate (0 agents, one project or a just-created one): do NOT ask anything.** There is nothing to resume and no decision for the user to make — announce one line ("Project **<name>** — let's connect your agent.") and delegate to the skill immediately at Phase 2. A confirmation prompt here is pure friction.

Ask (`AskUserQuestion`, exactly once) ONLY when there is a real choice:
- agents already exist (resume case), or
- 2+ projects and no explicit project argument, or
- the user's message conflicts with the resolved variant.

Prompt format — resume (agents exist, testing variant):

> Detected project **<name>** (`<id>`): <N> agent(s), <M> evaluator(s), <K> result(s).
> Variant: **Testing**. Next step: **<plain action — e.g. "generate evaluators" / "run the first test">**.
> Continue?

(Never name a phase number in the prompt — describe the next action in plain words.)

Prompt format — resume (agents exist, observability variant):

> Detected project **<name>** (`<id>`): <N> agent(s), <C> ingested call(s).
> Variant: **Observability**. Next step: **<plain action>**.
> Continue?

Options:

1. `Yes, continue` - proceed to Step 3.
2. `Start fresh (new agent)` - override to Phase 2, keep variant.
3. `Pick a different phase` - follow up with a phase picker (scoped to the resolved variant).
4. `Switch variant` - flip testing ↔ observability and redo state detection.
5. `Pick a different project` - show only if 2+ projects exist.

If the user needs a different organization than the one their credentials resolve to, tell them to use an API key scoped to the desired org/project.

---

## Step 3 - Delegate To The Skill

Invoke the `cekura-onboarding` skill with a structured context block. Pass everything known — including the resolved variant — so the skill does not re-ask account, project, agent, or variant facts unless an MCP response contradicts the inventory.

```text
Context already established:
- Variant: <testing|observability>
- API key: valid (proven by successful project/agent calls)
- Project: <project_id> (<project_name>) - <existing|just created>
- Agents in project:
  - <agent_id> (<name>) - description: <yes|no>, provider: <provider.type>, inbound: <telephony.inbound>, language: <language>
  - ...
[testing-only:]
- Evaluators: <count> in folders [<folder1>, <folder2>, ...]
- Latest result: <result_id> (<status>, error: <yes|no>) - or "none"
[observability-only:]
- Ingested call logs: <count>
- Latest call_log: <call_log_id> (<status>) - or "none"

Resume at: Phase <N> - <title>
Skip phases before <N>. For each remaining phase, use MCP tools where available
(the skill names the primary tool per phase).
Announce phase boundaries and keep moving; confirm with the user before write/run operations (creating the agent, starting a test run) and before anything destructive.
Do not ask known account/project/agent/variant facts again.

User intent for this session: <short string from arguments, or "default end-to-end onboarding">
```

Do not inline the onboarding phases here. The skill remains the source of truth.

---

## Step 4 - Post-Handoff Verification

After the skill returns, run a short state diff using the same MCP tools as Step 1. Report only what changed.

**Testing variant** — report:
- New project: name + dashboard link.
- New agent: `id`, `name`, dashboard link.
- New evaluators: count + folder.
- New result: `id`, `status`, dashboard link.

Format as one tight block:

> Onboarding complete (testing).
> - Agent: **My Voice Agent** (`12345`) - [open](https://dashboard.cekura.ai/<project_id>/agents/12345)
> - 10 evaluators in folder **First Run**
> - Result `r-abc123` - `completed`, 7/10 expected outcomes met - [open](https://dashboard.cekura.ai/<project_id>/results/r-abc123)
>
> Next: refine evaluators (`cekura-eval-design`) or design custom metrics (`cekura-metric-design`).

**Observability variant** — report:
- New project: name + dashboard link.
- New agent: `id`, `name`, dashboard link.
- New ingested call logs: count + latest call_log id.
- New metrics attached: count.

Format as one tight block:

> Onboarding complete (observability).
> - Agent: **Prod Voice Agent** (`12345`) - [open](https://dashboard.cekura.ai/<project_id>/agents/12345)
> - 3 ingested calls; latest `call_log-789` (evaluated)
> - 4 metrics attached
>
> Next: improve metric prompts from review feedback (`cekura-metric-improvement`).

If the skill exited mid-flow, do not call it complete. Use the variant-appropriate resume hint:

> Paused before generating evaluators. Run `/cekura-onboarding testing evals <project_id>` to pick up there.

or

> Paused before running the evaluation. Run `/cekura-onboarding observability evaluate <project_id>` to pick up there.

(Same rule as the confirmation prompt: user-facing pause/resume messages name the next ACTION in plain words, never a phase number — phase numbers are internal navigation only.)

---

## Failure Modes

- **MCP unavailable** - Stop and send the user to `/setup-mcp`.
- **Every MCP tool returns 403** - API key is set but invalid. Ask the user to rotate it in Settings > API Keys.
- **`projects_list` is empty but the user expects projects** - likely org/API-key scope mismatch. Surface the org context.
- **`aiagents_list` lacks descriptions** - expected. Retrieve candidate agents with `aiagents_retrieve`; do not conclude the description is missing from the list response alone.
- **Metric detection is ambiguous** - do not create duplicate predefined metrics silently. Ask the skill to verify project metrics before enabling all templates.
- **Latest results are infrastructure failures** (testing variant) - resume at Phase 5 and rerun rather than handing off to Phase 6.
- **`call_logs_list` returns calls in `evaluating` status** (observability variant) - ingestion succeeded; metric evaluation is async. Treat the call as ingested for resume purposes; the skill verifies before re-evaluating.
- **Skill exits without any MCP write/run tool** - the user likely paused or declined. Report where it stopped; do not say onboarding is complete.
- **Argument parser ambiguity** - shape-based: `testing`/`observability` → variant; numeric → project ID; other alphabetic → phase token; otherwise ask one clarifying question.
- **Phase token doesn't match resolved variant** - e.g. `/cekura-onboarding observability evals` (evals is testing-only). Ask one clarifying question — do not silently substitute.
