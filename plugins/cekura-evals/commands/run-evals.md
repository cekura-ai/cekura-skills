---
name: run-evals
description: Execute Cekura evaluators (voice, text, or websocket)
argument-hint: "[evaluator IDs or 'all'] [mode: voice/text/websocket]"
allowed-tools: ["AskUserQuestion", "mcp__cekura__scenarios_list", "mcp__cekura__scenarios_run_scenarios_create", "mcp__cekura__scenarios_run_scenarios_text_create", "mcp__cekura__scenarios_run_scenarios_with_websockets_create", "mcp__cekura__scenarios_run_scenarios_pipecat_create", "mcp__cekura__results_list", "mcp__cekura__results_retrieve", "mcp__cekura__end_call_2"]
---

# Run Evaluators

Execute one or more evaluators against the target agent.

## Process

1. **Identify evals to run**: Get evaluator IDs or filter criteria.
   Use `mcp__cekura__scenarios_list` to find evaluators by agent or project.

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
   Use `mcp__cekura__scenarios_run_scenarios_create` with `agent_id`, `scenarios` (array of IDs), and `frequency`.

   For text mode: Use `mcp__cekura__scenarios_run_scenarios_text_create`.
   For websocket: Use `mcp__cekura__scenarios_run_scenarios_with_websockets_create`.
   For pipecat: Use `mcp__cekura__scenarios_run_scenarios_pipecat_create`.

5. **Monitor**: Check run status:
   Use `mcp__cekura__results_list` to list results.

6. **After completion**: Offer to fetch results:
   Use `mcp__cekura__results_retrieve` with the result ID.

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
- If a run hangs, use `mcp__cekura__end_call_2` to terminate it
