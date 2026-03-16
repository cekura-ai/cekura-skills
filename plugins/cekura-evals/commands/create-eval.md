---
name: create-eval
description: Create a single Cekura evaluator (test scenario) for a voice AI agent
argument-hint: "[eval type: workflow, red-team, edge-case] [description]"
allowed-tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "AskUserQuestion", "WebFetch"]
---

# Create a Cekura Evaluator

Create a single evaluator (test scenario) on the Cekura platform. The eval-design skill provides detailed guidance.

## Process

1. **Determine eval type**: Ask what kind of eval to create:
   - **Workflow**: Tests a standard agent workflow (scheduling, cancellation, etc.)
   - **Red-team**: Tests adversarial inputs (prompt injection, social engineering)
   - **Edge case**: Tests boundary conditions (tool failures, retries, multiple items)
   - **Deterministic/Unit test**: Conditional actions for repeatable, structured flow validation
   - **Error handling**: Tests unusual situations (angry caller, wrong number)
   - **Multi-language**: Tests behavior in non-primary language

2. **Determine testing approach**: Does the user need:
   - **Behavioral instructions** (adaptive, natural) — for most evals
   - **Conditional actions** (deterministic, unit testing) — for exact flow validation
   Ask if not obvious from the eval type.

3. **Get required info**:
   - Agent ID or project ID
   - Personality ID (list available ones if not provided)
   ```bash
   source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
   list_personalities
   ```

4. **Read the agent description** to understand available workflows and decision points:
   ```bash
   get_agent_description AGENT_ID
   ```

5. **Get baseline metrics**: List existing metrics for the agent/project to attach to the evaluator. Every eval MUST have metrics attached — without them, runs only report call completion, not correctness.
   ```bash
   list_metrics "agent=AGENT_ID"
   ```
   Collect the IDs for at minimum: Expected Outcome, Infrastructure Issues, Tool Call Success, Latency. If these don't exist yet, create them first using the cekura-metrics plugin.

6. **Set up test profile**: Check existing profiles first — clients often pre-build profiles tested against their backend. Only create new ones if needed.
   ```bash
   # Always check existing profiles first
   list_test_profiles "agent_id=AGENT_ID"
   # Only create if nothing suitable exists
   create_test_profile '{"name": "Profile Name", "agent": AID, "information": {...}}'
   ```
   Never hardcode identity data in instructions — always use test profiles.

7. **Write instructions**: First-person behavioral description from the testing agent's perspective. Wrap in `<scenario>` tags with step-by-step format.
   - Reference test profile data: "Provide your date of birth when asked for verification"
   - Use template variables if needed: `{{test_profile.date_of_birth}}` or `{{test_profile['key']}}`
   - Be explicit about exact phrases when mock behavior depends on them
   - For conditional actions: build the role + conditions array instead

8. **Write expected outcome**: Define what the main agent should achieve. Agent-centric, specific, measurable.

9. **Set tags**: Category code, priority, unique ID.

10. **Review with user**: Present the full payload before creating.

11. **Create via API** — ALWAYS include `metrics` and `tool_ids`:
```bash
create_scenario '{"name": "NAME", "personality": PID, "agent": AID, "instructions": "...", "expected_outcome_prompt": "...", "test_profile": PROFILE_ID, "metrics": [METRIC_ID1, METRIC_ID2, ...], "tool_ids": ["TOOL_END_CALL"], "tags": ["cat", "priority", "id"]}'
```

12. **Offer to run**: Ask if the user wants to execute the eval immediately (text mode for quick iteration, voice for final validation).
```bash
run_scenarios '{"agent_id": AID, "scenarios": [SCENARIO_ID]}'
```

## Key Reminders

- Name field has 80-char limit
- Instructions are first-person and behavioral, not scripted
- Expected outcome focuses on the agent, not the caller — keep them concise and behavioral, not exact
- Always use test profiles for identity data — never hardcode
- Personality ID is required — list available ones first. Personalities control voice characteristics (accent, interruption, noise) — instructions cannot alter how the testing agent sounds, only what it says.
- **Enable tools**: Add `TOOL_END_CALL` (so testing agent can hang up), `TOOL_END_CALL_ON_TRANSFER` (for transfer scenarios), `TOOL_DTMF` (for IVR flows). Missing tools = elongated calls and wasted credits.
- **ALWAYS attach metrics**: Include `"metrics": [ID1, ID2, ...]` in the creation payload. Every eval needs at minimum Expected Outcome, Infrastructure Issues, Tool Call Success, and Latency. Without them, runs report pass/fail based on call completion, not correctness.
- Don't include examples of what the main agent "may say" — reference actions by topic instead
- For deterministic flows, use conditional actions (see eval-design skill)
- **NEVER write filler steps** like "Listen to the agent's response", "Wait for agent to speak", "End the call politely", or "Respond accordingly". The testing agent does these automatically. Every instruction step must describe a specific caller action.
- **Consider using generate-evals first**: The generate API often produces better initial scenarios than manual creation. Use manual creation for specific edge cases, red-team tests, or when the generate output needs supplementing.
