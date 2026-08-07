---
name: manual-create-update-eval
description: Manually create, update, or duplicate a Cekura evaluator (a.k.a. scenario, eval)
argument-hint: "[create|update|duplicate] [eval type or scenario ID]"
allowed-tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "AskUserQuestion", "mcp__cekura__personalities_list", "mcp__cekura__aiagents_retrieve", "mcp__cekura__aiagents_list", "mcp__cekura__metrics_list", "mcp__cekura__test_profiles_list", "mcp__cekura__test_profiles_create", "mcp__cekura__scenarios_create", "mcp__cekura__scenarios_duplicate_create", "mcp__cekura__scenarios_retrieve", "mcp__cekura__scenarios_partial_update", "mcp__cekura__scenarios_list", "mcp__cekura__scenarios_run_voice", "mcp__cekura__scenarios_run_text", "mcp__cekura__scenarios_folder_create", "mcp__cekura__scenarios_folders_list", "mcp__cekura__cekura_skill_started", "mcp__cekura__cekura_report_issue"]
---
<!-- cekura-ack-tag: ack:manual-create-update-eval:5m4p7c -->
> **Cekura skill verification tag:** `ack:manual-create-update-eval:5m4p7c`
> When you call a Cekura scenario or test-profile write tool from this command (`scenarios_*` / `test_profiles_*` create and update calls), pass this exact string as the `skill_ack` argument on that tool call. It confirms to the Cekura MCP server that this design playbook is loaded in context. Metric writes (`metrics_create`, `metrics_bulk_create`, `metrics_partial_update`) use a metric-family tag instead — load `cekura-metric-design` first and pass its tag there.
<!-- cekura-tracking-beacon -->

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="manual-create-update-eval"`, `verification_tag="ack:manual-create-update-eval:5m4p7c"`, and `plugin_version="0.10.3"`. If a conversation/session ID is available (e.g. you
were invoked from Cekura sandbox), also pass it as `conversation_id`. The call
returns immediately; it lets us understand which skills are actually being used.

If anything in this skill turns out to be ambiguous, broken, or missing a
needed tool, call `mcp__cekura__cekura_report_issue` to flag it. Use this
LIBERALLY — even `severity="low"` reports are valuable feedback.

# Manually Create or Update an Evaluator

Create a new evaluator (test scenario) or update an existing one on Cekura. This command walks through every field with the user — use it when you need precise control over the scenario configuration. For bulk/auto-generation, use `/autogen-eval` instead.

## Scope Gate

Use this command only to create, update, or duplicate an evaluator. A test profile is an
evaluator configuration input, not an evaluator itself. Do **not** load this
command for a standalone test-profile question or edit request (for example,
"How do I modify a test profile?"). Answer that request directly or use the
test-profile tools without starting this evaluator walkthrough.

## Determine Mode: Create, Update, or Duplicate

- **Create**: User says "create", "new", "add", or provides a scenario description without an ID
- **Update**: User says "update", "edit", "change", or provides a scenario ID
- **Duplicate**: User says "duplicate", "copy", or asks to place copies of existing evaluators in another folder or project

For updates, fetch the existing scenario first with `mcp__cekura__scenarios_retrieve` and show the user the current state before asking what to change.

## Duplicate Existing Evaluators

When the user wants copies of existing evaluators, use
`mcp__cekura__scenarios_duplicate_create` — **never rebuild them with
`scenarios_create`**. Same-project copies retain the evaluator configuration,
metrics, and test profile; cross-project copies use the destination project's
predefined metrics.

- `project`: source project ID
- `copy_to_project`: destination project ID; use the same ID for a folder-only copy
- `scenarios`: source evaluator IDs
- `scenario_agent`: optional destination agent ID, if the copies should be assigned to one
- `folder_path`: destination folder path; it is created if it does not exist

Confirm the source evaluators and destination before duplicating. The copied
evaluators are named `Copy of <original name>`.

## Field Walkthrough — Ask in This Order

Walk through each field conversationally. Don't dump a form — ask about each section, confirm, then move on.

### 1. Agent and Project

Ask for the agent ID or project ID. Use `mcp__cekura__aiagents_list` to help find them if needed.

For updates: show the current agent/project assignment.

### 2. Scenario Type — Instructions vs Conditional Actions

**Ask:** "Do you want an adaptive scenario (behavioral instructions) or a deterministic scenario (conditional actions / structured test)?"

| Type | When to Use | How It Works |
|------|------------|--------------|
| **Adaptive (instructions)** | Most evals — testing natural conversations, edge cases, red-team | Testing agent follows behavioral instructions, adapts to agent responses naturally |
| **Deterministic (conditional actions)** | Unit tests, regression tests, exact flow validation | Testing agent follows predefined condition→action pairs, repeats identically each run |

**For adaptive:** Write instructions in first-person, behavioral, wrapped in `<scenario>` tags. See the eval-design skill for patterns.

**For conditional actions:** Build a conditions array. Each condition has: `id`, `condition` (trigger), `action` (what to say/do), `type` ("say" or "do"), `fixed_message` (true for exact scripted lines, false for general instructions). See the cekura-eval-design skill's `references/conditional-actions.md` for full structure.

### 3. Name

Max 80 characters. Use format: `"[ID] - [Brief description]"` (e.g., `"RS-01: Reschedule with same provider"`).

### 4. Instructions or Conditions

**For adaptive scenarios:** Write step-by-step instructions wrapped in `<scenario>` tags.

Key rules:
- First person: "State your name when asked" NOT "The caller should state their name"
- Behavioral, not scripted: "Report fever and cough" NOT "Say exactly: I have a fever"
- Reference test profile data generically: "Provide your date of birth when asked"
- **NEVER write filler steps** like "Listen to the agent's response", "Wait for agent to speak", "End the call politely". Every step must describe a specific caller action.
- Be explicit about exact phrases when mock/backend behavior depends on them

**For conditional actions:** Build the conditions array. Use `fixed_message: true` for exact scripted lines (name, DOB, specific phrases), `fixed_message: false` for general behavioral instructions. Include `<silence time="3s"/>` in fixed messages for speech pauses if needed.

### 5. Expected Outcome

What the main agent should achieve. Agent-centric, specific, measurable, but **concise** — overly specific prompts (exact dates/times) cause false failures. Focus on behavioral outcomes.

Write each "The main agent should…" statement on its own line (newline-separated). Do not merge multiple statements into a single paragraph.

### 6. Test Profile

**Ask:** "Does this scenario need caller identity data (name, DOB, account info, etc.)?"

If yes:
1. For Approach B: check existing mock tool entries first — if they fit, find the corresponding profile and reuse it
2. For Approach A: check existing profiles with `mcp__cekura__test_profiles_list`
3. **Partial-match rule:** if an existing profile covers only a subset of required fields, create a new complete profile — never use a partial one; the testing agent will improvise missing fields
4. Show the full `information` dict for approval before creating any new profile. Use the sectioned shape: `{"main_agent_variables": {...}, "testing_agent_variables": {...}}`. Put values the agent under test should receive as dynamic variables in `main_agent_variables`; put persona/context for the simulated caller in `testing_agent_variables`. Either section may be omitted when not needed.
5. **Never hardcode identity data in instructions** — always put it in the test profile and reference via `{{test_profile.field_name}}`

### 7. Language

**Ask about language BEFORE personality.** Language determines which personalities are valid.

Supported: `af, ar, bn, bg, zh, cs, da, nl, en, et, fi, fr, de, el, gu, hi, he, hu, id, it, ja, kn, ko, ms, ml, mr, multi, no, pl, pa, pt, ro, ru, sk, es, sv, th, tr, ta, te, uk, vi`

Default: `en`. Set via `scenario_language` field on the scenario.

### 8. Personality (Required)

**After confirming language**, select a personality. The API returns 400 without one.

Use `mcp__cekura__personalities_list` to list available personalities, filtered by the chosen language if possible.

**Recommended defaults:**
- **Purely English scenarios:** 693 (Normal Male, en/American). Use 693 ONLY when the scenario is entirely in English.
- **Spanish:** 362 (Normal Spanish Male)
- **Other non-English languages:** pick a personality matching the scenario's language from `mcp__cekura__personalities_list` (filter with `language=<code>`), and set `scenario_language` to the correct code (platform uses `scenario_language` for TTS).
- **Multiple languages / code-switching in one scenario:** use a multilingual personality (filter with `language=multi`, e.g. 4710 "Normal (Spanish + English)").

**Note:** Language-specific personalities may not be enabled on all projects. Only if the language-matched personality returns a "Personality is not enabled" error, fall back to 693 with `scenario_language` set — never default to 693 for a non-English scenario without trying the language-matched personality first.

### 9. Metrics

**Ask:** "What metrics should this evaluator run? I'll attach the baselines (Expected Outcome, Infrastructure Issues, Tool Call Success, Latency) plus any custom metrics."

Use `mcp__cekura__metrics_list` to find metrics for the agent/project.

**Every eval MUST have metrics attached.** Without them, runs only report call completion, not correctness. Attach at minimum:
- Expected Outcome
- Infrastructure Issues
- Tool Call Success
- Latency

Plus any custom metrics relevant to the scenario's workflow (e.g., booking flow adherence for a scheduling scenario).

### 10. Tools for the Evaluator

**Ask:** "Does this scenario need any special tools for the testing agent?"

| Tool | When to Enable | Why |
|------|---------------|-----|
| `TOOL_END_CALL` | Recommended by default | Testing agent can hang up — without it, calls run until timeout |
| `TOOL_END_CALL_ONLY_ON_TRANSFER` | Transfer scenarios | Ends call after transfer instead of sitting through hold music |
| `TOOL_DTMF` | IVR/phone menu flows | Send touch-tone inputs |
| `TOOL_SEND_DTMF` | Same as above (alternate name) | |
| `TOOL_RECEIVE_DTMF` | Receiving DTMF inputs | |

**VAPI agents use prefixed names:** `VAPI_TOOL_END_CALL`, `VAPI_TOOL_END_CALL_ONLY_ON_TRANSFER`, etc.

Default recommendation: `["TOOL_END_CALL"]` for most scenarios, add `TOOL_END_CALL_ONLY_ON_TRANSFER` for transfer scenarios.

### 11. Max Call Duration

**Ask:** "What's the average length of the longest call you'd expect for this scenario? I'll set the max duration a bit above that."

| Call Type | Typical Duration | Suggested Max |
|-----------|-----------------|---------------|
| Simple FAQ / quick question | 1-2 min | 3 min |
| Standard workflow (scheduling, cancellation) | 2-5 min | 7 min |
| Complex multi-step (onboarding, full intake) | 5-10 min | 12 min |
| Extended conversations (interviews, detailed intake) | 10-15 min | 18 min |

Set via `max_call_duration` field (in seconds). Most scenarios should be under 10 minutes (600 seconds). Longer durations = higher cost per run.

### 12. Tags

**Ask:** "Any tags for organization? Common patterns: category code (S=Scheduling, RS=Rescheduling), priority (must-have, nice-to-have), scenario ID."

Format: `["Category", "priority-level", "scenario-ID"]`

### 13. Folder

For new scenarios, ask where to place them. Use `mcp__cekura__scenarios_folders_list` to show existing folders, or create a new one with `mcp__cekura__scenarios_folder_create`.

### 14. Inbound Phone Number

For inbound agents using Approach B (Cekura mock tools): assign a unique phone number. Each scenario should get its own phone to avoid mock data collisions.

## Checkpoint — Review Before Creating/Updating

**Always present the full configuration for approval before making the API call:**

```
Scenario: [name]
Type: [adaptive / conditional actions]
Agent: [agent_id]
Language: [language code]
Personality: [personality_id] ([personality name])
Test profile: [profile_id] ([profile name]) or "none"
Metrics: [list of metric names and IDs]
Tools: [list of tool IDs]
Max duration: [seconds]
Tags: [tag list]
Folder: [folder path]

Instructions preview:
[first 3-5 lines of instructions or conditions summary]

Expected outcome:
[full expected outcome text]
```

Get explicit "looks good" before proceeding.

## Create or Update

**Create:** Use `mcp__cekura__scenarios_create` with the full payload.

**Update:** Use `mcp__cekura__scenarios_partial_update` with only the changed fields.

**Duplicate:** Use `mcp__cekura__scenarios_duplicate_create`; do not recreate
the evaluator payload with `scenarios_create`.

## After Creation

1. **Verify**: Fetch the scenario back to confirm all fields were set correctly
2. **Offer to run**: "Want to test this scenario now? I recommend text mode for quick iteration."
   - Text: `mcp__cekura__scenarios_run_text`
   - Voice: `mcp__cekura__scenarios_run_voice`

## Key Reminders

- Name field has 80-char limit
- `personality` is required — API returns 400 without it
- Ask about language BEFORE personality — language constrains personality options
- Instructions are first-person and behavioral (adaptive) or condition→action pairs (deterministic)
- Expected outcomes should be concise and behavioral, not exact
- Always use test profiles for identity data — never hardcode
- Always attach metrics — runs without them only report call completion
- Always enable `TOOL_END_CALL` at minimum — missing tools waste credits
- For conditional actions: `fixed_message: true` for exact lines, `false` for behavioral
- **VAPI agents use prefixed tool IDs** (e.g., `VAPI_TOOL_END_CALL`)
