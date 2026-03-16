---
name: generate-evals
description: Auto-generate Cekura evaluators from an agent description using the generate API
argument-hint: "[agent ID] [count]"
allowed-tools: ["Bash", "AskUserQuestion", "Read"]
---

# Auto-Generate Evaluators

Use Cekura's generate API to create evaluators from an agent's description. This is the **recommended** approach for creating evaluators — it produces higher quality scenarios than manual creation because it understands the agent's full workflow context.

## Process

1. **Get agent ID and count**: Ask the user for the agent ID and how many evaluators to generate (default: 10).

2. **Read the agent description first** to understand what workflows exist — this helps you validate the generated output later:
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
get_agent_description AGENT_ID
```

3. **Trigger background generation**:
```bash
generate_scenarios '{"agent": AGENT_ID, "count": COUNT}'
```
This returns a response with a progress tracking ID. Extract it from the response.

4. **Poll for completion**: The generation runs asynchronously. Poll every 10 seconds:
```bash
check_generation_progress "PROGRESS_ID"
```
The response will include a `status` field. Keep polling until status is `completed` or `failed`. Do NOT give up after one check — generation can take 30-60 seconds for 10+ evals.

5. **Fetch the generated evals**: Once complete, list the new evaluators:
```bash
list_scenarios "agent=AGENT_ID"
```

6. **Validate output quality**: Review each generated evaluator and check:
   - Does it have meaningful instructions (not 1-line stubs)?
   - Are instructions in first-person, behavioral format?
   - Are expected outcomes agent-centric and measurable?
   - Is coverage balanced across workflows (scheduling, cancellation, etc.)?

   If the output is poor (1-line scenarios, random format, missing instructions), report this to the user and offer to:
   a. Re-run generation with different count
   b. Manually create evals using the create-eval command instead
   c. Use generated evals as a starting point and improve them

7. **Post-generation fixup**: For each generated eval, update with:
   - **Metrics**: Attach baseline metrics (Expected Outcome, Infrastructure Issues, Tool Call Success, Latency)
   - **Test profiles**: Assign test profiles — check existing ones first
   - **Tools**: Enable `TOOL_END_CALL`, `TOOL_END_CALL_ON_TRANSFER`, `TOOL_DTMF` as appropriate
   - **Tags**: Add category codes and priority tags

   ```bash
   # Get existing metrics and profiles
   list_metrics "agent=AGENT_ID"
   list_test_profiles "agent_id=AGENT_ID"

   # Update each generated eval with metrics and tools
   update_scenario SCENARIO_ID '{"metrics": [MID1, MID2, ...], "tool_ids": ["TOOL_END_CALL"], "test_profile": PROFILE_ID}'
   ```

8. **Report summary**: Show the user a table of what was generated, organized by coverage area.

## When to Use Generate vs Manual

| Approach | When |
|----------|------|
| **Generate (this command)** | Starting from scratch, need broad coverage quickly, agent has clear workflows |
| **Manual (create-eval)** | Specific edge cases, red-team scenarios, conditional/deterministic tests |
| **Bulk create** | You have a CSV or structured list of pre-designed scenarios |

## Tips

- Generation quality depends on agent description quality — agents with well-structured descriptions produce better evals
- Always validate output — the generate endpoint can sometimes produce inconsistent results
- Use this as a starting point, then supplement with manual edge-case and red-team evals
- Consider running the eval-suite-planner agent first to identify coverage gaps
- If generation fails or produces poor output, fall back to manual creation — don't retry the same call repeatedly
