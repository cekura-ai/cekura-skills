---
name: manual-create-update-eval
description: Manually create or update a Cekura evaluator with full field walkthrough
argument-hint: "[create|update] [eval type or scenario ID]"
allowed-tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "AskUserQuestion", "mcp__cekura__personalities_list", "mcp__cekura__aiagents_retrieve", "mcp__cekura__aiagents_list", "mcp__cekura__metrics_list", "mcp__cekura__test_profiles_list", "mcp__cekura__test_profiles_create", "mcp__cekura__scenarios_create", "mcp__cekura__scenarios_retrieve", "mcp__cekura__scenarios_partial_update", "mcp__cekura__scenarios_list", "mcp__cekura__scenarios_run_scenarios_create", "mcp__cekura__scenarios_run_scenarios_text_create", "mcp__cekura__scenarios_create_folder_create", "mcp__cekura__scenarios_folders_list"]
---

# Manually Create or Update an Evaluator

Create a new evaluator (test scenario) or update an existing one on Cekura. This command walks through every field with the user — use it when you need precise control over the scenario configuration. For bulk/auto-generation, use `/autogen-eval` instead.

## Determine Mode: Create or Update

- **Create**: User says "create", "new", "add", or provides a scenario description without an ID
- **Update**: User says "update", "edit", "change", or provides a scenario ID

For updates, fetch the existing scenario first with `mcp__cekura__scenarios_retrieve` and show the user the current state before asking what to change.

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

**For conditional actions:** Build a conditions array. Each condition has: `id`, `condition` (trigger), `action` (what to say/do), `type` ("say" or "do"), `fixed_message` (true for exact scripted lines, false for general instructions). See `references/conditional-actions.md` for full structure.

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

**For conditional actions:** Build the conditions array. Use `fixed_message: true` for exact scripted lines (name, DOB, specific phrases), `fixed_message: false` for general behavioral instructions. Include `<break time="3s"/>` in fixed messages for speech pauses if needed.

### 5. Expected Outcome

What the main agent should achieve. Agent-centric, specific, measurable, but **concise** — overly specific prompts (exact dates/times) cause false failures. Focus on behavioral outcomes.

### 6. Mock Data Strategy & Test Profile

**Do NOT preemptively offer to create a test profile.** Instead, ask the mock data strategy question first, and only handle test profiles inside the path the user picks.

**Ask:** "How do you want to handle mock data for this test — **self-manage** (you run a staging backend or supply the data) or **use Cekura mock tools** (Cekura intercepts tool calls)?"

#### If **self-manage**, ask the sub-question immediately:

> "Do you want me to create the test profile and data for this scenario, or do you already have data you'd like me to use?"

- **User has existing data:** Ask them to share names, IDs, formats. Create a test profile that mirrors their data exactly. Never invent values.
- **Claude creates data:** Design a profile that fits the scenario shape, create it via `mcp__cekura__test_profiles_create`, attach it to the scenario, and **return JSON to the user** with two parts: (a) the test profile object(s) created, and (b) any mock tool input/output mappings the user will need to wire into their backend so the agent's tool calls return matching data. See the `eval-design` skill's "Self-Managed Mock Data → Sub-path 1b" section for the JSON shape.

#### If **Cekura mock tools**:

1. Check existing test profiles first: `mcp__cekura__test_profiles_list`
2. If creating new ones, **derive the profile fields from the mock tool outputs** — never independently. If `get_user_info` returns `{"first_name": "John", "dob": "01/15/1990"}`, the profile must use those exact values.
3. Show the full `information` dict for approval before creating.

**In all cases:** Never hardcode identity data in scenario instructions — put it in the test profile and reference it generically.

### 7. Language

**Ask about language BEFORE personality.** Language determines which personalities are valid.

Supported: `af, ar, bn, bg, zh, cs, da, nl, en, et, fi, fr, de, el, gu, hi, he, hu, id, it, ja, kn, ko, ms, ml, mr, multi, no, pl, pa, pt, ro, ru, sk, es, sv, th, tr, ta, te, uk, vi`

Default: `en`. Set via `scenario_language` field on the scenario.

### 8. Personality (Required)

**After confirming language**, select a personality. The API returns 400 without one.

Use `mcp__cekura__personalities_list` to list available personalities, filtered by the chosen language if possible.

**Recommended defaults:**
- **English:** 693 (Normal Male, en/American)
- **Spanish:** 362 (Normal Spanish Male)
- **Other languages:** Use 693 + set `scenario_language` to the correct code (platform uses `scenario_language` for TTS)

**Note:** Language-specific personalities may not be enabled on all projects. If you get "Personality is not enabled" errors, fall back to 693 with `scenario_language` set.

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
| `TOOL_END_CALL` | Almost always | Testing agent can hang up — without it, calls run until timeout |
| `TOOL_END_CALL_ON_TRANSFER` | Transfer scenarios | Ends call after transfer instead of sitting through hold music |
| `TOOL_DTMF` | IVR/phone menu flows | Send touch-tone inputs |
| `TOOL_SEND_DTMF` | Same as above (alternate name) | |
| `TOOL_RECEIVE_DTMF` | Receiving DTMF inputs | |

**VAPI agents use prefixed names:** `VAPI_TOOL_END_CALL`, `VAPI_TOOL_END_CALL_ON_TRANSFER`, etc.

Default recommendation: `["TOOL_END_CALL"]` for most scenarios, add `TOOL_END_CALL_ON_TRANSFER` for transfer scenarios.

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

For new scenarios, ask where to place them. Use `mcp__cekura__scenarios_folders_list` to show existing folders, or create a new one with `mcp__cekura__scenarios_create_folder_create`.

### 14. Inbound Phone Number

For inbound agents using Cekura mock tools: assign a unique phone number. Each scenario should get its own phone to avoid mock data collisions.

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

## After Creation

1. **Verify**: Fetch the scenario back to confirm all fields were set correctly
2. **Offer to run**: "Want to run this scenario now?" Do NOT recommend a run mode here — wait until the user says yes, then ask which mode (voice / text / websocket / pipecat) inside the `/run-evals` flow. Run mode is a separate decision from creation.

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
