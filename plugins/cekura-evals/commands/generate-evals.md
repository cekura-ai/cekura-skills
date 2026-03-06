---
name: generate-evals
description: Auto-generate Cekura evaluators from an agent description
argument-hint: "[agent ID] [count]"
allowed-tools: ["Bash", "AskUserQuestion"]
---

# Auto-Generate Evaluators

Use Cekura's background generation to create evaluators from an agent's description automatically.

## Process

1. **Get agent ID and count**: How many evaluators to generate.

2. **Trigger generation**:
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
generate_scenarios '{"agent": AGENT_ID, "count": 10}'
```

3. **Poll for completion**: The generation runs in the background. Check progress:
```bash
check_generation_progress "PROGRESS_ID"
```

4. **Review generated evals**: Once complete, list the new evaluators:
```bash
list_scenarios "agent=AGENT_ID"
```

5. **Assess quality**: Review the generated evaluators:
   - Are instructions specific enough?
   - Are expected outcomes measurable?
   - Is coverage balanced across workflows?
   - Are there gaps to fill manually?

6. **Suggest improvements**: Offer to edit generated evals or create manual ones to fill coverage gaps.

## Post-Generation Checklist

After generation, review and fix each eval:
- **Test profiles**: Assign test profiles for identity/context data — never leave hardcoded names/DOBs in instructions
- **Tools**: Enable `TOOL_END_CALL`, `TOOL_END_CALL_ON_TRANSFER`, `TOOL_DTMF` as appropriate
- **Baseline metrics**: Attach Expected Outcome, Infrastructure Issues, Tool Call Success, Latency
- **Instructions quality**: First-person, behavioral, no examples of agent speech, using `<scenario>` tags

## Tips

- Auto-generation is a starting point, not a final product — always review and refine
- Generated evals may cluster around obvious happy paths — manually add edge cases
- Consider running the eval-suite-planner agent first to identify coverage gaps before generating
- After generation, assign test profiles to scenarios that need identity/context data
- Review that generated instructions are first-person and behavioral, not scripted
