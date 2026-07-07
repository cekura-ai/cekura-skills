---
name: cekura-onboarding
description: State-aware Cekura onboarding that resumes at the right setup phase and delegates to the cekura-onboarding skill. Supports two variants — `testing` (default) and `observability`.
argument-hint: "[testing|observability] [account|agent|metrics|evals|run|ingest|evaluate|review] [project-id]"
allowed-tools:
  [
    "AskUserQuestion",
    "Read",
    "Bash",
    "Skill",
    "mcp__cekura__list_available_tools",
    "mcp__cekura__test_simple_tool",
    "mcp__cekura__user_organizations_list",
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
    "mcp__cekura__call_logs_mark_metric_vote_create"
  , "mcp__cekura__cekura_skill_started", "mcp__cekura__cekura_report_issue"]
---
<!-- cekura-tracking-beacon -->

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="cekura-onboarding"`. If a conversation/session ID is available (e.g. you
were invoked from Cekura sandbox), also pass it as `conversation_id`. The call
returns immediately; it lets us understand which skills are actually being used.

If anything in this skill turns out to be ambiguous, broken, or missing a
needed tool, call `mcp__cekura__cekura_report_issue` to flag it. Use this
LIBERALLY — even `severity="low"` reports are valuable feedback.

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
| Alphabetic phase token | Phase override (testing-flow: `account` \| `agent` \| `metrics` \| `evals` \| `run`; observability-flow: `account` \| `agent` \| `ingest` \| `evaluate` \| `review`). Detection still runs to populate handoff context. |
| Anything else | Ask one short clarifying question with `AskUserQuestion`. |

The variant determines which set of phase tokens is valid:
- `testing` → `account`, `agent`, `metrics`, `evals`, `run`
- `observability` → `account`, `agent`, `ingest`, `evaluate`, `review`

If the user passes a phase token that doesn't match the resolved variant, ask one clarifying question (don't silently re-route).

---

## Step 0 - Preflight

Run silently unless broken.

1. Call `mcp__cekura__list_available_tools`.
   - On error: print `MCP not connected. Run /setup-mcp first.` and stop.
2. Call `mcp__cekura__user_organizations_list`.
   - On 401/403: print `API key invalid or missing. Set CEKURA_API_KEY, restart Claude Code, then run /setup-mcp.` and stop.
   - On success: capture available organization IDs/names and user identity. If there is more than one org, mention the selected org in the confirmation prompt.

If both pass, print nothing yet. Continue to state detection.

---

## Step 1 - State Detection

Detect the current state without asking the user.

### Project

If the user passed a numeric project ID, use it directly and verify with:

```text
mcp__cekura__projects_retrieve(id=<project_id>)
```

Otherwise call `mcp__cekura__projects_list`.

| Result | Behavior |
|---|---|
| 0 projects | Resume at Phase 1. |
| 1 project | Auto-pick it. |
| 2+ projects | Defer selection to the single confirmation prompt. Do not ask a separate question here. |

### Inventory — shared (both variants)

With a chosen `project_id`, gather:

1. `mcp__cekura__aiagents_list(project_id=<project_id>, page_size=20)` for agent summaries. List results use `agent_name`, not `name`, and may not include `description`.
2. `mcp__cekura__aiagents_retrieve(id=<agent_id>)` for each candidate onboarding agent. Capture `id`, `agent_name`, `description`, `assistant_provider`, `inbound`, `contact_number`, and `language`.
3. `mcp__cekura__metrics_list(project_id=<project_id>, page_size=100)` for enabled/copied project metrics. Count likely predefined metrics using fields such as `vocera_defined_metric_code`, `predefined_metric`, `function_name`, or `user_defined=false`. If the response shape is ambiguous, keep the raw count and let the skill verify before creating anything.
4. `mcp__cekura__predefined_metrics_list()` for catalog size only. This endpoint lists available predefined metric templates; it does not prove a project has enabled them.

### Inventory — variant-specific

**Testing variant** also gathers:

5. `mcp__cekura__scenarios_list(project_id=<project_id>, page_size=5)` for evaluator count and folder/folder path names.
6. `mcp__cekura__results_list(project_id=<project_id>, page_size=1)` for latest result `id`, `status`, and any `error_message`.

**Observability variant** also gathers:

5. `mcp__cekura__call_logs_list(project_id=<project_id>, page_size=5)` for ingested call count and latest call_log id.

Hold this inventory for the handoff context.

### Entry Phase — testing variant

| Detected state | Resume at |
|---|---|
| No project | Phase 1 - Account & Project Setup |
| Project, 0 agents | Phase 2 - Agent Configuration |
| Agent exists, but `description` is empty | Phase 2 - Agent Configuration (description step, `phase2-agent.md` §2c) |
| Agent OK, 0 enabled/copied metrics detected | Phase 3 - Metrics Setup |
| Agent + metrics OK, 0 evaluators | Phase 4 - First Evaluators |
| Evaluators exist, 0 results | Phase 5 - First Test Run |
| Latest result has `error_message` or failed/errored infrastructure status | Phase 5 - First Test Run |
| Successful/completed results exist | Phase 6 - What's Next |

### Entry Phase — observability variant

| Detected state | Resume at |
|---|---|
| No project | Phase 1 - Account & Project Setup |
| Project, 0 agents | Phase 2 - Agent Configuration |
| Agent exists, but `description` is empty | Phase 2 - Agent Configuration (description step, `phase2-agent.md` §2c) |
| Agent OK, 0 ingested call logs | Phase 3 - Ingest Call Logs |
| Call logs exist, 0 enabled/copied metrics | Phase 4 - Configure Metrics |
| Calls + metrics OK, no evaluation kicked off | Phase 5 - Run Metric Evaluation |
| Evaluation done | Phase 6 - Review Results |



If the user provided an explicit phase argument, override the detected phase but keep the inventory.

---

## Step 2 - Single Confirmation Prompt

Use `AskUserQuestion` exactly once before the skill takes over.

Prompt format (testing variant):

> Detected project **<name>** (`<id>`): <N> agent(s), <E>/<T> predefined metrics detected, <M> evaluator(s), <K> result(s).
> Variant: **Testing**. Resume at **Phase <P>: <phase title>**.
> Continue?

Prompt format (observability variant):

> Detected project **<name>** (`<id>`): <N> agent(s), <C> ingested call(s), <E>/<T> predefined metrics detected.
> Variant: **Observability**. Resume at **Phase <P>: <phase title>**.
> Continue?

Options:

1. `Yes, resume at Phase <P>` - proceed to Step 3.
2. `Start fresh from Phase 1` - override to Phase 1, keep variant.
3. `Pick a different phase` - follow up with a phase picker (scoped to the resolved variant).
4. `Switch variant` - flip testing ↔ observability and redo state detection.
5. `Pick a different project` - show only if 2+ projects exist.

If more than one organization was detected, mention which org's projects are listed. If the user needs a different org and MCP does not expose org switching, tell them to use an API key scoped to the desired org/project.

---

## Step 3 - Delegate To The Skill

Invoke the `cekura-onboarding` skill with a structured context block. Pass everything known — including the resolved variant — so the skill does not re-ask account, project, agent, or variant facts unless an MCP response contradicts the inventory.

```text
Context already established:
- Variant: <testing|observability>
- Org: <org_id> / <org_name>
- User: <email or "OAuth-authenticated">
- API key: valid
- Project: <project_id> (<project_name>) - <existing|just created>
- Agents in project:
  - <agent_id> (<agent_name>) - description: <yes|no>, provider: <assistant_provider>, inbound: <true|false>, language: <language>
  - ...
- Metrics detected in project: <enabled_or_copied_count>
- Predefined metric catalog size: <catalog_count>
[testing-only:]
- Evaluators: <count> in folders [<folder1>, <folder2>, ...]
- Latest result: <result_id> (<status>, error: <yes|no>) - or "none"
[observability-only:]
- Ingested call logs: <count>
- Latest call_log: <call_log_id> (<status>) - or "none"

Resume at: Phase <N> - <title>
Skip phases 1..<N-1>. For each remaining phase, use MCP tools where available
(the skill names the primary tool per phase).
Confirm with the user at phase boundaries and before write/run operations.
Do not ask known account/project/agent/variant facts again.

User intent for this session: <short string from arguments, or "default end-to-end onboarding">
```

Do not inline the onboarding phases here. The skill remains the source of truth.

---

## Step 4 - Post-Handoff Verification

After the skill returns, run a short state diff using the same MCP tools as Step 1. Report only what changed.

**Testing variant** — report:
- New project: name + dashboard link.
- New agent: `id`, `agent_name`, dashboard link.
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
- New agent: `id`, `agent_name`, dashboard link.
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

> Paused at Phase 4. Run `/cekura-onboarding testing evals <project_id>` to resume.

or

> Paused at Phase 5. Run `/cekura-onboarding observability evaluate <project_id>` to resume.

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
