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

   Otherwise, fetch the agent with `mcp__cekura__aiagents_retrieve(id=<agent_id>)` and inspect `provider.type`, `telephony.phone_number`, `telephony.websocket_url`, `provider.chat_agent_details`, `telephony.sip_uri`. Derive candidate modes:

   - **`voice`** = PSTN. Valid whenever `telephony.phone_number` is set. Note: a bare phone number is `voice`, never `sip`.
   - **`sip`** = only when `telephony.sip_uri` is set (e.g. `sip:agent@host`).
   - **`text`** = when `provider.chat_agent_details` is set.
   - **`websocket`** = when `telephony.websocket_url` is set and no other provider (JSON/text protocol).
   - **`chirp`** = when `telephony.websocket_url` is set on a voice agent (raw-PCM audio websocket).
   - **WebRTC** (`vapi`, `retell`, `elevenlabs`, `livekit`, `agora`) = when `provider.type` matches.
   - **`pipecat-v2` / `pipecat`** = when `provider.type: pipecat`.

   Selection rule:
   - **0 candidates** → STOP. Surface: *"Agent has no provider, phone number, SIP endpoint, or websocket URL configured — can't run evals."*
   - **1 candidate** → auto-pick. Announce: *"Auto-selected `<mode>` — only configured connection on this agent."*
   - **2+ candidates** → use `AskUserQuestion` with **only the configured options**, never the full list. One-line hint: text fastest/cheapest, WebRTC moderate, PSTN voice realistic but slowest.
   - **Pipecat exception:** when the choices are `pipecat` and `pipecat-v2`, ask exactly: *"Your agent uses Pipecat. `pipecat` (v1) uses a manually provided room URL for each evaluator run; `pipecat-v2` uses configured Pipecat Cloud project credentials and creates sessions automatically."* Offer only `pipecat (v1)` and `pipecat-v2` as the options.

3. **Confirm scope**: Show the user what will run:
   - Number of runs: evaluators × `frequency` × test profiles × personalities passed on the run
   - Execution mode (auto-selected or chosen)
   - Worst-case call length: each scenario's `max_duration`, or the project's `max_call_duration` where it is unset. A stalled main agent runs to that cap on every run, so name any scenario without a cap of its own before a voice run.

4. **Execute using batch endpoint** (preferred for multiple evals). Pass `agent_id`, `scenarios` (array of IDs), and optionally `frequency` (for repeat runs).

   **Smoke cohort first on paid transports.** For voice, SIP and WebRTC runs of more than five evaluators, launch 3–5 representative ones first and read their results — connected, finished inside the cap, no setup error — before launching the rest. Text and websocket runs may go in one batch. Skip the cohort only when the user explicitly asks for the whole suite at once, and say that you skipped it.

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
   | agora | `mcp__cekura__scenarios_run_agora` |
   | chirp | `mcp__cekura__scenarios_run_chirp` |
   | sip | `mcp__cekura__scenarios_run_sip` |

5. **Monitor**: Check run status:
   Use `mcp__cekura__results_list` to list results.

   **Fail fast on terminal errors — never retry-loop through them:**
   - **Billing** ("insufficient balance", "subscription expired/inactive"): stop immediately, quote the exact error, and tell the user to top up / renew before re-running. Do not poll again until they confirm.
   - **Setup / configuration errors** (the provider rejected a configuration or mock-tool change, the outbound phone-number record is missing, credentials are invalid, `status=failed` before any call connected): every run in the batch hits the same wall. Stop, do not launch the remaining evaluators, quote the exact `failed_reasons` text, and fix the configuration before re-running.
   - **Call never connects** (still dialing/ringing after ~2 minutes): stop polling and diagnose — wrong/unreachable phone number, agent not answering, telephony misconfiguration — instead of "keep polling".
   - **Infra errors** (LiveKit/SIP worker failures, timeouts): surface the error verbatim and which scenario hit it; suggest text/chat mode as a fallback for logic validation rather than retrying voice blindly.

6. **After completion**: Offer to fetch results:
   Use `mcp__cekura__results_retrieve` with the result ID.

   Read a run's `success` correctly: when the project has rubric rules, `success` is the rubric verdict over every attached metric (all rules must pass by default), not the Expected Outcome score alone. Report the Expected Outcome score and the failing rubric rule separately — a scenario whose Expected Outcome passed but whose run shows `success: false` failed a project-wide gate, possibly on a metric the scenario never exercised, not the behaviour under test.

## Execution Modes

| Mode | Speed | Cost | Best For |
|------|-------|------|----------|
| text | Fast | Low | Logic testing, rapid iteration (requires a configured chat agent) |
| websocket | Medium | Medium | Custom websocket agents (requires a websocket URL) |
| pipecat | Medium | Medium | Pipecat/Daily WebRTC with a manually supplied room URL per evaluator run |
| pipecat-v2 | Medium | Medium | Pipecat Cloud with configured project credentials; Cekura creates sessions |
| vapi / retell / elevenlabs / livekit (WebRTC) | Medium | Medium | Provider-native browser/SDK testing |
| voice (PSTN) | Slow | High | Realistic phone-call validation (requires a phone number) |
| sip | Slow | High | Self-hosted SIP endpoints (requires a SIP endpoint) |

## Pre-Run Checklist

Before running, verify evals are properly configured:
- **Baseline metrics attached**: Expected Outcome, Infrastructure Issues, Tool Call Success, Latency. Without these, runs report pass/fail based on call completion — not correctness.
- **Tools enabled**: `TOOL_END_CALL` (testing agent can hang up), `TOOL_END_CALL_ONLY_ON_TRANSFER` (for transfer scenarios). Missing tools = elongated calls, wasted credits.
- **Duration cap set**: `max_duration` (10–3600 s) on every scenario, a little above the longest legitimate call for that flow. Unset means the project's `max_call_duration`, which is sized for production calls — a stalled agent burns that whole cap.
- **Test profiles assigned**: Identity data in test profiles, not hardcoded in instructions.

## Tips

- Use text mode for rapid iteration during development
- Use voice mode for final validation before deployment
- Run must-have evals first, nice-to-have second
- If a run hangs, use `mcp__cekura__end_call` to terminate it
