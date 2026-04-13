---
name: autogen-eval
description: Auto-generate Cekura evaluators using the generate API with full configuration
argument-hint: "[agent ID] [count] [scenario type]"
allowed-tools: ["AskUserQuestion", "Read", "mcp__cekura__aiagents_retrieve", "mcp__cekura__aiagents_list", "mcp__cekura__scenarios_generate_bg_create", "mcp__cekura__scenarios_generate_progress_retrieve", "mcp__cekura__scenarios_list", "mcp__cekura__scenarios_partial_update", "mcp__cekura__scenarios_create_folder_create", "mcp__cekura__scenarios_folders_list", "mcp__cekura__metrics_list", "mcp__cekura__test_profiles_list", "mcp__cekura__test_profiles_create", "mcp__cekura__personalities_list"]
---

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
mcp__cekura__scenarios_create_folder_create:
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

### 7. Personality

Default: 693 (Normal Male, en/American) for English agents.

**Ask about language first:** "What language should the scenarios be in?" Then select an appropriate personality.

If non-English: use 693 + set `scenario_language` on each generated scenario after creation (see post-generation fixup).

### 8. Tools

**Ask:** "Should the testing agent have end-call and transfer tools enabled?"

Default recommendation: `["TOOL_END_CALL"]`. Add `TOOL_END_CALL_ON_TRANSFER` for agents with transfer flows. Add `TOOL_DTMF` for IVR flows.

**VAPI agents use prefixed names:** `VAPI_TOOL_END_CALL`, etc.

## Pre-Generation Checkpoint

Present the full configuration for approval:

```
Agent: [agent_id] ([agent_name])
Folder: [folder_path]
Scenario type: [workflow / redteaming / knowledge_base]
Count: [num_scenarios]
Personality: [personality_id] ([name])
Tools: [tool_ids]
Tags: [tags]

Extra instructions:
[summary or first few lines]

Proceed with generation?
```

## Trigger Generation

Use `mcp__cekura__scenarios_generate_bg_create` with:

| Field | Value |
|-------|-------|
| `agent_id` | Agent ID |
| `num_scenarios` | Count from step 4 |
| `extra_instructions` | From step 5 |
| `personalities` | `[personality_id]` |
| `generate_expected_outcomes` | `true` (always) |
| `folder_path` | From step 2 |
| `tags` | From step 6 |
| `tool_ids` | From step 8 |

Returns `{"progress_id": "<uuid>"}`.

## Poll for Completion

Poll every 10 seconds with `mcp__cekura__scenarios_generate_progress_retrieve`:

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
Check if generated scenarios need test profiles. For scenarios involving identity verification, booking, or account lookup — create/assign profiles. Check existing profiles first with `mcp__cekura__test_profiles_list`.

### 5. Quality Review
Review each generated evaluator:
- Does it have meaningful, multi-step instructions (not 1-line stubs)?
- Are instructions in first-person behavioral format?
- Are expected outcomes agent-centric and measurable?
- Is coverage balanced across the agent's workflows?

If output is poor, offer to:
- Re-run with different `extra_instructions`
- Supplement with manual creation via `/manual-create-update-eval`
- Use generated evals as a starting point and improve individually

## Bulk Creation from Structured Input (CSV/JSON)

If the user has a pre-designed scenario list (CSV file, JSON array, or structured description):

### CSV Format
```csv
ID,Category,Name,Instructions,Expected Outcome,Priority
S-01,Scheduling,New adult patient,Calls as new patient...,Agent books appointment...,must-have
```

### Process
1. Parse the input file
2. Walk through the same configuration (agent, personality, metrics, tools, tags, folder)
3. Present a summary grouped by category
4. Get confirmation: "Ready to create [N] evaluators?"
5. Create sequentially with `mcp__cekura__scenarios_create`, including `metrics` and `tool_ids`
6. Report results: created vs failed with error details

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

Missing coverage (consider manual creation):
  - [workflow not covered]
  - [edge case not covered]
```

## Key Reminders

- **Always create a folder first** — never dump scenarios into root
- **Number of scenarios should match instruction count** — mismatches cause skipped or duplicate scenarios
- **Generation can partially complete** — check after 2 minutes, generate remainder separately
- **`scenario_language` defaults to "en"** — always PATCH non-English scenarios
- **Metrics are required** — PATCH them on after generation
- **Personality is required** — set it in the generate call
- Consider running `/manual-create-update-eval` for edge cases and red-team scenarios that the generator doesn't cover
