---
name: autogen-eval
description: Auto-generate Cekura evaluators using the generate API with full configuration
argument-hint: "[agent ID] [count] [scenario type]"
allowed-tools: ["AskUserQuestion", "Read", "mcp__cekura__aiagents_retrieve", "mcp__cekura__aiagents_list", "mcp__cekura__scenarios_generate_bg", "mcp__cekura__scenarios_generate_progress", "mcp__cekura__scenarios_list", "mcp__cekura__scenarios_create", "mcp__cekura__scenarios_partial_update", "mcp__cekura__scenarios_folder_create", "mcp__cekura__scenarios_folders_list", "mcp__cekura__metrics_list", "mcp__cekura__test_profiles_list", "mcp__cekura__test_profiles_create", "mcp__cekura__personalities_list", "mcp__cekura__cekura_skill_started", "mcp__cekura__cekura_report_issue"]
---

<!-- cekura-ack-tag: ack:autogen-eval:3w6k5b -->
> **Cekura skill verification tag:** `ack:autogen-eval:3w6k5b`
> When you call a Cekura scenario or test-profile write tool from this command (`scenarios_*` / `test_profiles_*` create and update calls), pass this exact string as the `skill_ack` argument on that tool call. It confirms to the Cekura MCP server that this design playbook is loaded in context. Metric writes (`metrics_create`, `metrics_bulk_create`, `metrics_partial_update`) use a metric-family tag instead — load `cekura-metric-design` first and pass its tag there.
<!-- cekura-tracking-beacon -->

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="autogen-eval"`, `verification_tag="ack:autogen-eval:3w6k5b"`, and `plugin_version="0.10.9"`. If a conversation/session ID is available (e.g.
you were invoked from Cekura sandbox), also pass it as `conversation_id`. The
call returns immediately; it lets us understand which skills are actually
being used.

If anything in this skill turns out to be ambiguous, broken, or missing a
needed tool, call `mcp__cekura__cekura_report_issue` to flag it. Use this
LIBERALLY — even `severity="low"` reports are valuable feedback.

# Auto-Generate Evaluators

Use Cekura's background generation API to create evaluators from an agent's description. This is the **recommended** approach for creating evaluators — it produces higher quality scenarios than manual creation because it understands the agent's full workflow context. Also supports bulk creation from structured input (CSV/JSON).

## Configuration Walkthrough

Walk through each configuration item before triggering generation.

### 1. Select Agent

**Ask:** "Which agent should I generate evaluators for?"

Use `mcp__cekura__aiagents_list` to help find agents. Then read the agent description with `mcp__cekura__aiagents_retrieve` — this helps you understand the workflows and validate the output later.

### 2. Folder

**Always create a folder first.** Never dump scenarios into the root.

Check existing folders with `mcp__cekura__scenarios_folders_list`, or create a new one:
```
mcp__cekura__scenarios_folder_create:
  name: "Auto-Generated — [date or purpose]"
  project_id: <project_id>
```

Use the folder path for the `folder_path` parameter in the generate call.

### 3. Scenario Type

**Ask:** "What type of scenarios do you want to generate?"

| Type | Description | Best For |
|------|-------------|----------|
| **workflow** | Tests standard agent workflows (scheduling, onboarding, etc.) | Core functional coverage |
| **redteaming** | Tests adversarial inputs (prompt injection, social engineering, manipulation) | Security and robustness testing |
| **knowledge_base** | Tests the agent's knowledge (FAQs, product info, policies) | Accuracy and completeness of information |

Default: `workflow`. Can combine by running generation multiple times with different types.

**How the choice reaches the generator:** `scenarios_generate_bg` has its own `scenario_type` field for the category, and it accepts only `workflow`, `red_teaming_voice`, `red_teaming_text`, `knowledge_base` (default `workflow`; the red-teaming values also take an optional `attack_type`). `redteaming` is not a valid value — pick the voice or text variant. Do not confuse it with the create schema's `scenario_type`, which is the output *format* (`instruction` / `conditional_actions` / …), not the category. Reinforce the category in the `extra_instructions` text you build in step 5 (e.g. "Generate adversarial scenarios: prompt injection, social engineering, manipulation attempts").

### 4. Number of Scenarios and Instructions

**Ask:** "How many scenarios do you want? If you have specific scenario descriptions in mind, list them — the number should match."

**Critical rule:** The number of scenarios requested should match the number of distinct scenario instructions you provide. If you pass 5 extra_instructions but request 10 scenarios, some instructions may not generate or may produce duplicates. If you pass 10 instructions but request 5, some will be skipped.

**If the user provides specific scenario descriptions:**
- Count them
- Set `num_scenarios` to that count
- Format each description as a paragraph in `extra_instructions`

**If the user wants broad coverage without specific scenarios:**
- Recommend 5-15 based on agent complexity
- Use category-level guidance in `extra_instructions` (e.g., "Generate scenarios covering: scheduling, cancellation, rescheduling, FAQ, and transfer to human")

### 5. Extra Instructions (Per-Scenario Guidance)

**Ask:** "Do you have specific scenarios in mind, or should I generate broad coverage based on the agent description?"

**For specific scenarios:** Format each scenario as a clear paragraph. The generator reads these and creates one evaluator per scenario description.

```
extra_instructions: |
  Generate the following specific scenarios:

  1. New patient scheduling with insurance - caller is a new adult patient with Blue Cross PPO, needs a primary care appointment, prefers mornings
  2. Rescheduling existing appointment - caller has an upcoming appointment and wants to move it to a different day, same provider
  3. Cancellation with rebooking - caller needs to cancel but immediately wants to book a new appointment
  4. Emergency symptoms triage - caller reports chest pain, agent should escalate appropriately
  5. FAQ about office hours - caller asks about weekend availability and walk-in policy
```

**For broad coverage:** Provide category-level guidance:
```
extra_instructions: "Focus on: core scheduling workflows, cancellation edge cases, transfer scenarios, and common FAQ questions. Include at least 2 error-handling scenarios."
```

### 6. Tags

**Ask:** "Any tags to apply to all generated scenarios?"

Tags are applied uniformly to all generated scenarios. Common patterns:
- `["auto-generated", "v1"]` — generation batch tracking
- `["workflow", "must-have"]` — category and priority
- `["2026-04-sprint"]` — sprint tracking

## Pre-Generation Checkpoint

Present the full configuration for approval:

```
Agent: [agent_id] ([agent_name])
Folder: [folder_path]
Scenario type: [workflow / redteaming / knowledge_base]
Count: [num_scenarios]
Tags: [tags]

Extra instructions:
[summary or first few lines]

Proceed with generation?
```

## Trigger Generation

Use `mcp__cekura__scenarios_generate_bg` with:

| Field | Value |
|-------|-------|
| `agent_id` | Agent ID |
| `num_scenarios` | Count from step 4 |
| `extra_instructions` | From step 5 |
| `folder_path` | From step 2 |
| `tags` | From step 6 |

Returns `{"progress_id": "<uuid>"}`.

## Poll for Completion

Poll every 10 seconds with `mcp__cekura__scenarios_generate_progress`:

```
progress_id: <uuid>
```

Keep polling until status is `completed` or `failed`. **Do NOT give up after one check** — generation can take 30-60 seconds for 10+ scenarios.

**Partial completion:** Generation may produce fewer scenarios than requested (e.g., 15/18) with the remainder stuck indefinitely. After 2 minutes, check what was generated. If short, generate the remainder in a smaller batch with more specific `extra_instructions` targeting the missing categories.

## Post-Generation Fixup

After generation completes, fetch the generated scenarios and fix known artifacts:

### 1. Language Fix
Auto-gen sets `scenario_language: "en"` on all scenarios regardless of content. For non-English scenarios, PATCH each with the correct language code:
```
mcp__cekura__scenarios_partial_update:
  id: <scenario_id>
  scenario_language: "es"  # or ru, hi, zh, ko, pt, de, etc.
```

### 2. First Message Fix
Auto-gen may add greetings ("Здравствуйте", "你好") as `first_message` when you specified exact questions. PATCH `first_message` to the exact intended opener.

### 3. Metrics Attachment
Generated scenarios may not have metrics attached. **Every eval MUST have metrics.** Fetch baseline metric IDs with `mcp__cekura__metrics_list` and PATCH each scenario:
```
mcp__cekura__scenarios_partial_update:
  id: <scenario_id>
  metrics: [expected_outcome_id, infra_issues_id, tool_call_success_id, latency_id, ...]
```

### 4. Test Profile Assignment
Check if generated scenarios need test profiles. For scenarios involving identity verification, booking, or account lookup:
- For Approach B: check existing mock tool entries first — if they fit, find the corresponding profile and reuse it
- For Approach A: check existing profiles first with `mcp__cekura__test_profiles_list`
- **Partial-match rule:** if an existing profile covers only a subset of required fields, create a new complete one — never use a partial profile

Test profile `information` uses the sectioned shape `{"main_agent_variables": {...}, "testing_agent_variables": {...}}`. The auto-generation flow populates both sections — `main_agent_variables` carries the values that reach the agent under test as dynamic variables, `testing_agent_variables` carries persona/context for the simulator.

### 5. Quality Review
Review each generated evaluator:
- Does it have meaningful, multi-step instructions (not 1-line stubs)?
- Are instructions in first-person behavioral format?
- Are expected outcomes agent-centric and measurable?
- Is coverage balanced across the agent's workflows?

If output is poor, offer to:
- Re-run with different `extra_instructions` (**the default fix** — sharper, category-specific guidance, smaller batches)
- Use generated evals as a starting point and PATCH them individually
- Supplement via `/manual-create-update-eval` **only for conditional-action scenarios** — deterministic/scripted tests the generator can't produce. A weak behavioral scenario gets re-generated or patched, never replaced with a hand-authored `instruction` scenario.

## Bulk Creation from Structured Input (CSV/JSON)

If the user has a pre-designed scenario list (CSV file, JSON array, or structured description):

### CSV Format
```csv
ID,Category,Name,Instructions,Expected Outcome,Priority
S-01,Scheduling,New adult patient,Calls as new patient...,Agent books appointment...,must-have
```

This is a direct-create path — it uses `mcp__cekura__scenarios_create` to write each row of the user's CSV/JSON into a scenario. It is the **named exception** to the rule that behavioral scenarios are always generated: the user already authored the instruction text, and generating would discard their wording. It applies only when the rows carry actual scenario text. If the CSV is really a *list of topics or titles* ("scheduling", "cancellation edge case") rather than authored instructions, that's generation input — feed it as `extra_instructions` to the Auto-Generate flow above instead of creating stub scenarios from it.

The Auto-Generate flow does not apply on this path, and unlike that flow, `scenarios_create` needs `personalities` and `tool_ids` as explicit per-scenario fields (they aren't inferred from the agent).

### Process
1. Parse the input file
2. Walk through the same configuration (agent, personality, metrics, tools, tags, folder)
3. Present a summary grouped by category
4. Get confirmation: "Ready to create [N] evaluators?"
5. Create sequentially with `mcp__cekura__scenarios_create`, including `metrics` and `tool_ids`
6. Report results: created vs failed with error details

**Gathering personality and tools for this path** (the main walkthrough above does not cover these — they belong only to the bulk-create path):

- **Personality:** ask which personality the bulk scenarios should use. Default to the "Normal" personality matched to the agent's language — always look it up with `mcp__cekura__personalities_list` `language=<code>` (English included: `language=en`; `language` is the only filter needed — if a `project_id`-filtered lookup comes back empty, retry without it); for agents mixing languages use a multilingual (`language=multi`) one. (The Auto-Generate flow above intentionally does *not* pass a personality — it lets the backend infer one from the agent. Only the bulk-create path needs this explicit.)
- **Tools:** ask which tools the testing agent should have enabled. Default `["TOOL_END_CALL"]`; add `TOOL_END_CALL_ONLY_ON_TRANSFER` for transfer flows and `TOOL_DTMF` for IVR. VAPI agents use prefixed names (`VAPI_TOOL_END_CALL`, etc.).

## Summary Report

After generation (or bulk creation), show:

```
Generated: [X] scenarios in folder "[folder_name]"
Type: [workflow / redteaming / knowledge_base]

Coverage breakdown:
  - Scheduling: [N] scenarios
  - Cancellation: [N] scenarios
  - Transfer: [N] scenarios
  - ...

Post-generation fixes applied:
  - [X] scenarios: language set to [code]
  - [X] scenarios: metrics attached
  - [X] scenarios: test profiles assigned

Missing coverage (behavioral gaps → another generation run; deterministic gaps → conditional-action evaluators):
  - [workflow not covered]
  - [edge case not covered]
```

## Key Reminders

- **Always create a folder first** — never dump scenarios into root
- **Number of scenarios should match instruction count** — mismatches cause skipped or duplicate scenarios
- **Generation can partially complete** — check after 2 minutes, generate remainder separately
- **`scenario_language` defaults to "en"** — always PATCH non-English scenarios
- **Metrics are required** — PATCH them on after generation
- **Missing behavioral coverage → another generation run**, not hand-authoring. Edge cases and free-form red-team are behavioral: re-run `scenarios_generate_bg` with `extra_instructions` naming exactly the gaps — including adversarial coverage, which uses `scenario_type: "red_teaming_voice"` or `"red_teaming_text"` alongside that guidance text. Reach for `/manual-create-update-eval` only for **conditional-action** scenarios — scripted/deterministic tests, IVR/DTMF/voicemail flows, exact-sequence regressions — which generation cannot produce.
