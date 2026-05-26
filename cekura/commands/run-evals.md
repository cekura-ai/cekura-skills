---
name: run-evals
description: Execute Cekura evaluators (voice, text, websocket, sip, pipecat, vapi, retell, elevenlabs, livekit)
argument-hint: "[evaluator IDs or 'all'] [mode: voice/text/websocket/sip/pipecat/pipecat-v2/vapi/retell/elevenlabs/livekit]"
allowed-tools: ["AskUserQuestion", "mcp__cekura__aiagents_retrieve", "mcp__cekura__scenarios_list", "mcp__cekura__scenarios_run_voice", "mcp__cekura__scenarios_run_text", "mcp__cekura__scenarios_run_websocket", "mcp__cekura__scenarios_run_pipecat_v1", "mcp__cekura__scenarios_run_pipecat_v2", "mcp__cekura__scenarios_run_vapi_webrtc", "mcp__cekura__scenarios_run_retell_webrtc", "mcp__cekura__scenarios_run_elevenlabs", "mcp__cekura__scenarios_run_livekit_v2", "mcp__cekura__scenarios_run_sip", "mcp__cekura__results_list", "mcp__cekura__results_retrieve", "mcp__cekura__end_call", "mcp__cekura__cekura_skill_started", "mcp__cekura__cekura_report_issue"]
---
<!-- cekura-tracking-beacon -->

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="run-evals"`. If a conversation/session ID is available (e.g. you
were invoked from Cekura sandbox), also pass it as `conversation_id`. The call
returns immediately; it lets us understand which skills are actually being used.

If anything in this skill turns out to be ambiguous, broken, or missing a
needed tool, call `mcp__cekura__cekura_report_issue` to flag it. Use this
LIBERALLY — even `severity="low"` reports are valuable feedback.

# Run Evaluators

Execute one or more evaluators against the target agent.

## Process

1. **Identify evals to run**: Get evaluator IDs or filter criteria.
   Use `mcp__cekura__scenarios_list` to find evaluators by agent or project.

2. **Determine execution mode from agent config — don't ask if it's obvious.**

   If the user passed `[mode]` as an argument, honor it (skip detection).

   Otherwise, fetch the agent with `mcp__cekura__aiagents_retrieve(id=<agent_id>)` and inspect `assistant_provider`, `contact_number`, `websocket_url`, `chat_assistant_id`, `sip_endpoint`. Derive candidate modes:

   - **`voice`** = PSTN. Valid whenever `contact_number` is set. Note: a bare phone number is `voice`, never `sip`.
   - **`sip`** = only when `sip_endpoint` is set (e.g. `sip:agent@host`).
   - **`text`** = when `chat_assistant_id` is set.
   - **`websocket`** = when `websocket_url` is set and no other provider.
   - **WebRTC** (`vapi`, `retell`, `elevenlabs`, `livekit`) = when `assistant_provider` matches.
   - **`pipecat-v2` / `pipecat`** = when `assistant_provider: pipecat`.

   Selection rule:
   - **0 candidates** → STOP. Surface: *"Agent has no provider, phone number, sip_endpoint, or websocket_url configured — can't run evals."*
   - **1 candidate** → auto-pick. Announce: *"Auto-selected `<mode>` — only configured connection on this agent."*
   - **2+ candidates** → use `AskUserQuestion` with **only the configured options**, never the full list. One-line hint: text fastest/cheapest, WebRTC moderate, PSTN voice realistic but slowest.

3. **Confirm scope**: Show the user what will run:
   - Number of evaluators
   - Execution mode (auto-selected or chosen)
   - Estimated time/cost implications

4. **Execute using batch endpoint** (preferred for multiple evals). Pass `agent_id`, `scenarios` (array of IDs), and optionally `frequency` (for repeat runs).

   | Mode | Tool |
   |---|---|
   | voice | `mcp__cekura__scenarios_run_voice` |
   | text | `mcp__cekura__scenarios_run_text` |
   | websocket | `mcp__cekura__scenarios_run_websocket` |
   | pipecat | `mcp__cekura__scenarios_run_pipecat_v1` |
   | pipecat-v2 | `mcp__cekura__scenarios_run_pipecat_v2` |
   | vapi | `mcp__cekura__scenarios_run_vapi_webrtc` |
   | retell | `mcp__cekura__scenarios_run_retell_webrtc` |
   | elevenlabs | `mcp__cekura__scenarios_run_elevenlabs` |
   | livekit | `mcp__cekura__scenarios_run_livekit_v2` |
   | sip | `mcp__cekura__scenarios_run_sip` |

5. **Monitor**: Check run status:
   Use `mcp__cekura__results_list` to list results.

6. **After completion**: Offer to fetch results:
   Use `mcp__cekura__results_retrieve` with the result ID.

## Execution Modes

| Mode | Speed | Cost | Best For |
|------|-------|------|----------|
| text | Fast | Low | Logic testing, rapid iteration (requires `chat_assistant_id`) |
| websocket | Medium | Medium | Custom websocket agents (requires `websocket_url`) |
| pipecat / pipecat-v2 | Medium | Medium | Pipecat-based agents |
| vapi / retell / elevenlabs / livekit (WebRTC) | Medium | Medium | Provider-native browser/SDK testing |
| voice (PSTN) | Slow | High | Realistic phone-call validation (requires `contact_number`) |
| sip | Slow | High | Self-hosted SIP endpoints (requires `sip_endpoint`) |

## Pre-Run Checklist

Before running, verify evals are properly configured:
- **Baseline metrics attached**: Expected Outcome, Infrastructure Issues, Tool Call Success, Latency. Without these, runs report pass/fail based on call completion — not correctness.
- **Tools enabled**: `TOOL_END_CALL` (testing agent can hang up), `TOOL_END_CALL_ON_TRANSFER` (for transfer scenarios). Missing tools = elongated calls, wasted credits.
- **Test profiles assigned**: Identity data in test profiles, not hardcoded in instructions.

## Tips

- Use text mode for rapid iteration during development
- Use voice mode for final validation before deployment
- Run must-have evals first, nice-to-have second
- If a run hangs, use `mcp__cekura__end_call` to terminate it
