---
name: run-evals
description: Execute Cekura evaluators (voice, text, or websocket)
argument-hint: "[evaluator IDs or 'all'] [mode: voice/text/websocket]"
allowed-tools: ["Bash", "AskUserQuestion"]
---

# Run Evaluators

Execute one or more evaluators against the target agent.

## Process

1. **Identify evals to run**: Get evaluator IDs or filter criteria.
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
list_scenarios "agent=AGENT_ID"
```

2. **Choose execution mode**:
   - **Voice** (default): Full voice call via provider
   - **Text**: Text-based chat (faster, cheaper, good for logic testing)
   - **WebSocket**: Real-time WebSocket connection
   - **Pipecat**: Via Pipecat framework

3. **Confirm scope**: Show the user what will run:
   - Number of evaluators
   - Execution mode
   - Estimated time/cost implications

4. **Execute using batch endpoint** (preferred for multiple evals):
```bash
# Batch run (preferred — handles multiple evals in one call)
run_scenarios '{"agent_id": AGENT_ID, "scenarios": [ID1, ID2, ID3], "frequency": 1}'

# Single eval (alternative — use individual run endpoints)
run_voice "SCENARIO_ID"
# or
run_text "SCENARIO_ID"
```

The batch `run_scenarios` endpoint is the standard way to execute multiple evaluators. It accepts:
- `agent_id` (required): The agent to test
- `scenarios` (required): Array of scenario IDs
- `frequency` (optional): How many times each scenario runs (default: 1)
- `personality_ids` (optional): Override default personalities
- `test_profile_ids` (optional): Override default test profiles

5. **Monitor**: Check run status:
```bash
list_runs "scenario=SCENARIO_ID"
# or check specific result
list_results "agent=AGENT_ID"
```

6. **After completion**: Offer to fetch results:
```bash
get_result "RESULT_ID"
```

## Execution Modes

| Mode | Speed | Cost | Best For |
|------|-------|------|----------|
| Voice | Slow | High | Final validation, voice-specific testing |
| Text | Fast | Low | Logic testing, rapid iteration |
| WebSocket | Medium | Medium | Real-time agents |
| Pipecat | Medium | Medium | Pipecat-based agents |

## Pre-Run Checklist

Before running, verify evals are properly configured:
- **Baseline metrics attached**: Expected Outcome, Infrastructure Issues, Tool Call Success, Latency. Without these, runs report pass/fail based on call completion — not correctness.
- **Tools enabled**: `TOOL_END_CALL` (testing agent can hang up), `TOOL_END_CALL_ON_TRANSFER` (for transfer scenarios). Missing tools = elongated calls, wasted credits.
- **Test profiles assigned**: Identity data in test profiles, not hardcoded in instructions.

## Tips

- Use text mode for rapid iteration during development
- Use voice mode for final validation before deployment
- Run must-have evals first, nice-to-have second
- If a run hangs, use `end_call` to terminate it
