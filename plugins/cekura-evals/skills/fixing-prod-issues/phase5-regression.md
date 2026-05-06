# Phase 5 — Regression Testing

> ## ⚠️ ALL REGRESSION TESTS MUST BE E2E SIMULATIONS OVER TWILIO SIP TELEPHONY
>
> **Every regression case MUST be run as a full end-to-end voice simulation on Cekura using Twilio SIP telephony** — real phone calls via `run_voice` with the local `twilio-sip-dial-out` bot dialing Cekura over SIP.
>
> ❌ Do NOT use Daily/WebRTC. ❌ Do NOT use text mode. ❌ Do NOT use any transport other than Twilio SIP.
>
> Passing regression tests over text or WebRTC while the fix breaks Twilio SIP voice behaviour is a false pass.

The fix works for the original bug. Now verify it hasn't broken anything else.

---

## 5a. Identify all affected flows

Think through every call flow that touches the changed code path:
- Standard happy path flows through the same handler
- Edge cases the fix might break (error paths, timeouts, retries)
- Scenarios with voice-specific stress: silence gaps, interruptions, background noise, DTMF input
- Any other caller intents that reach the same code

Produce a named list and **confirm with the user** before creating evaluators.

---

## 5b. Create evaluators for each case

Use the `cekura-evals:conditional-actions` skill to build each evaluator. Design the conversation flow for each case.

To **generate** voice-specific stress conditions, use XML tags in `fixed_message`: `<silence>`, `<interruption>`, `<background_noise>`, `<dtmf>`. These make the testing agent emit those conditions.

To **evaluate** the main agent's response to those conditions, attach predefined metrics:
- Silence / drops / non-response → **Infrastructure Issues**
- Slow replies → **Latency**
- Tool call behaviour → **Tool Call Success**

Do not write custom `expected_outcome_prompt` — attach the relevant predefined metrics that would catch a failure in each case.

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
create_scenario '{
  "agent": AGENT_ID,
  "personality": PERSONALITY_ID,
  "name": "Regression: <case name>",
  "instructions": "...",
  "metrics": [METRIC_ID_1, METRIC_ID_2],
  "conditional_actions": { "role": "caller", "conditions": [...] }
}'
```

---

## 5c. Run all cases

For each scenario, trigger a voice run, note the Cekura outbound number, update `local_runner.py`, run the bot in the background. Work through cases one at a time — restore any modified conditions between cases.

```bash
run_voice "SCENARIO_ID" '{"agent_number": "+19789751706"}'
# update SIP URI, then:
cd twilio-sip-dial-out && LOCAL_RUN=1 python bot.py &
```

Poll all results and build a summary:

| Case | Status | Pass/Fail | Notes |
|---|---|---|---|
| Happy path | completed | PASS | — |
| Silence gap | completed | PASS | — |

---

## Phase 5 Gate

**All cases must pass before proceeding.**

For any failure: read the transcript divergence point, fix the issue, rerun:

```bash
rerun_result "RESULT_ID"
```

Do not proceed to Phase 6 until every regression case passes.

Move to [Phase 6](phase6-pr.md).
