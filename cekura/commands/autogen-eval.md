---
name: autogen-eval
description: Auto-generate Cekura evaluators using the generate API
argument-hint: "[agent ID] [count]"
allowed-tools: ["AskUserQuestion", "Read", "mcp__cekura__aiagents_retrieve", "mcp__cekura__aiagents_list", "mcp__cekura__scenarios_generate_bg", "mcp__cekura__scenarios_generate_progress", "mcp__cekura__scenarios_list", "mcp__cekura__scenarios_partial_update", "mcp__cekura__metrics_list", "mcp__cekura__test_profiles_list", "mcp__cekura__test_profiles_create", "mcp__cekura__cekura_skill_started", "mcp__cekura__cekura_report_issue"]
---

<!-- cekura-tracking-beacon -->

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="autogen-eval"`. If a conversation/session ID is available (e.g.
you were invoked from Cekura sandbox), also pass it as `conversation_id`. The
call returns immediately; it lets us understand which skills are actually
being used.

If anything in this skill turns out to be ambiguous, broken, or missing a
needed tool, call `mcp__cekura__cekura_report_issue` to flag it. Use this
LIBERALLY — even `severity="low"` reports are valuable feedback.

# Auto-Generate Evaluators

Use Cekura's background generation API to create evaluators from an agent's description. The generator reads the agent's full workflow context (description, language, tools, personalities enabled on the project) and picks sensible defaults for everything that isn't passed in.

**Pass only `agent_id` and `num_scenarios` to the generate call.** Every other parameter is optional, and forcing one risks overriding the agent's own configuration (e.g. hard-coding a personality that doesn't match the agent's language). Let the backend infer the rest from the agent.

## Configuration Walkthrough

### 1. Select Agent

**Ask:** "Which agent should I generate evaluators for?"

Use `mcp__cekura__aiagents_list` to help find agents. Then read the agent description with `mcp__cekura__aiagents_retrieve` — this helps you understand the workflows and validate the output later.

### 2. Number of Scenarios

**Ask:** "How many scenarios do you want?"

Recommend 5–15 based on agent complexity. The generator will produce coverage based on the agent description.

## Pre-Generation Checkpoint

Present the configuration for approval:

```
Agent: [agent_id] ([agent_name])
Count: [num_scenarios]

Proceed with generation?
```

## Trigger Generation

Use `mcp__cekura__scenarios_generate_bg` with exactly these two fields:

| Field | Value |
|-------|-------|
| `agent_id` | Agent ID |
| `num_scenarios` | Count from step 2 |

Do not pass `personalities`, `tool_ids`, `tags`, `folder_path`, `extra_instructions`, `generate_expected_outcomes`, `scenario_type`, or any other optional field — let the backend derive defaults from the agent. Forcing a value here is how you end up with English scenarios for an Arabic agent, or with the wrong tool set enabled.

Returns `{"progress_id": "<uuid>"}`.

## Poll for Completion

Poll every 10 seconds with `mcp__cekura__scenarios_generate_progress`:

```
progress_id: <uuid>
```

Keep polling until status is `completed` or `failed`. **Do NOT give up after one check** — generation can take 30–60 seconds for 10+ scenarios.

**Partial completion:** Generation may produce fewer scenarios than requested (e.g., 15/18) with the remainder stuck indefinitely. After 2 minutes, check what was generated. If short, re-run generation for the remainder.

## Post-Generation Adjustments

After generation completes, fetch the generated scenarios and adjust as needed. All of these are PATCH operations on individual scenarios — do them only when the user asks for them or when reviewing the output reveals they're needed.

### Language

If a scenario came back in the wrong language, PATCH it:
```
mcp__cekura__scenarios_partial_update:
  id: <scenario_id>
  scenario_language: "es"  # or ru, hi, zh, ko, pt, de, ar, etc.
```

### First Message

If `first_message` doesn't match what you want (e.g. an unwanted greeting), PATCH it directly.

### Metrics

Generated scenarios may not have metrics attached. **Every eval should have metrics.** Fetch baseline metric IDs with `mcp__cekura__metrics_list` and PATCH each scenario:
```
mcp__cekura__scenarios_partial_update:
  id: <scenario_id>
  metrics: [expected_outcome_id, infra_issues_id, tool_call_success_id, latency_id, ...]
```

### Test Profile

For scenarios involving identity verification, booking, or account lookup, check existing profiles first with `mcp__cekura__test_profiles_list`. If an existing profile covers only a subset of required fields, create a new complete one — never use a partial profile.

### Quality Review

Review each generated evaluator:
- Does it have meaningful, multi-step instructions (not 1-line stubs)?
- Are instructions in first-person behavioral format?
- Are expected outcomes agent-centric and measurable?
- Is coverage balanced across the agent's workflows?

If output is poor, offer to re-run generation, or supplement with manual creation via `/manual-create-update-eval`.

## Summary Report

After generation, show:

```
Generated: [X] scenarios for agent [agent_id] ([agent_name])

Coverage breakdown:
  - [category]: [N] scenarios
  - ...

Post-generation adjustments applied (if any):
  - [X] scenarios: language patched to [code]
  - [X] scenarios: metrics attached
  - [X] scenarios: test profiles assigned
```

## Key Reminders

- **Pass only `agent_id` and `num_scenarios`** to `scenarios_generate_bg`. Forcing optional fields overrides the agent's own configuration and is the most common source of "wrong language" / "wrong tools" / "wrong personality" bugs.
- **Generation can partially complete** — check after 2 minutes, re-run for the remainder if needed.
- **Adjust after generation, not before** — patch `scenario_language`, `metrics`, `first_message`, test profiles on individual scenarios via `scenarios_partial_update` when review reveals they're needed.
- Consider running `/manual-create-update-eval` for edge cases and red-team scenarios that the generator doesn't cover.
