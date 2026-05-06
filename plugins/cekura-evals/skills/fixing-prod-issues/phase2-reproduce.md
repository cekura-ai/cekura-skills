# Phase 2 — Reproduce the Issue

> ## ⚠️ E2E SIMULATION OVER TWILIO SIP TELEPHONY IS MANDATORY
>
> **Every test in this phase MUST be run as a full end-to-end voice simulation on Cekura using Twilio SIP telephony.** The local agent dials out via `twilio-sip-dial-out` over SIP — this is the only valid connection method.
>
> ### DO NOT use any of these — they are wrong:
> - ❌ **Daily / WebRTC** — do not use Daily rooms, do not use WebRTC transport, do not use `DailyTransport` for connecting to Cekura
> - ❌ **Text mode** — `run_text` is not a voice simulation
> - ❌ **WebSocket mode** — not the same as telephony
> - ❌ **Any direct connection** that bypasses Twilio SIP
>
> ### The ONLY correct flow:
> 1. Trigger `run_voice` on Cekura with `agent_number`
> 2. Get the Cekura outbound number from the response
> 3. Set `dialout_settings.sip_uri` in `local_runner.py` to dial that number via `cekura-pipecat-local.sip.twilio.com`
> 4. Run `LOCAL_RUN=1 python bot.py` — the bot dials Cekura over Twilio SIP
>
> The bot uses `twilio-sip-dial-out/` specifically because it dials via SIP telephony. If you find yourself touching `DailyTransport`, WebRTC, or `run_text`, stop — you are on the wrong path.

Build a controlled reproduction of the bug on Cekura **before writing any fix**. The goal is a Cekura eval that fails in exactly the same way as the production call.

---

## 2a. Create the evaluator using conditional actions

Use the `cekura-evals:conditional-actions` skill to build a deterministic evaluator.

Extract **Testing Agent** turns from `transcript_object` verbatim. Do **not** clean up or paraphrase — garbled text, truncated words, STT artifacts are exactly what the main agent's LLM received in production and are the bug trigger.

Map each turn to a fixed condition:
- First turn: `trigger: "call_start"`, `type: "fixed"`
- Subsequent turns: `trigger: "agent_speaks"`, `type: "fixed"`

**Use `metadata.agent_id` from the production call as the `agent` field — not the top-level `agent_id` which may be the monitoring agent.** The evaluator must be created under the same agent that handled the failing call so it runs against the correct agent configuration.

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
create_scenario '{
  "agent": METADATA_AGENT_ID,
  "personality": PERSONALITY_ID,
  "name": "Bug repro: <brief issue description>",
  "instructions": "Replay the production call that caused <issue>.",
  "conditional_actions": { "role": "caller", "conditions": [...] }
}'
```

Save the `scenario_id`.

---

## 2b. Attach the exact metrics that were failing in the prod call

**Do not write a custom `expected_outcome_prompt`.** Use the exact metrics that were already failing in the production call — they already know how to detect the problem.

From Phase 1, you noted which metrics were failing in `runs[].evaluation.metrics[]`. List predefined metrics to get their IDs:

```bash
cekura:predefined_metrics_list
```

Attach those metric IDs to the evaluator:

```bash
update_scenario "SCENARIO_ID" '{
  "metrics": [METRIC_ID_1, METRIC_ID_2, ...]
}'
```

> **If you are unsure which metrics to attach, stop and ask the user.** Do not guess — wrong metrics will make this entire phase meaningless.

---

## 2c. Configure the local agent with the same edge conditions

Display values for `twilio-sip-dial-out/local_runner.py`:

| Field | Value |
|---|---|
| `scenario_config.instructions` | Agent system prompt (`description` from Phase 1) |
| `scenario_config.name` | `"Bug repro: <issue>"` |
| `configuration.model` | `llm_model` from agent config |
| `call_details.call_id` | `"patronus_<timestamp>"` |
| `dialout_settings.sip_uri` | `sip:<CEKURA_OUTBOUND_NUMBER>@cekura-pipecat-local.sip.twilio.com?X-CallerId=+19789751706` |

**Role swap:** If instructions mention "main agent" or "testing agent" by name, swap the labels — locally the roles are inverted.

Apply the **same conditions that caused the bug** in production. There are no limits here — go as far as needed to replicate the exact environment that triggered the failure. The goal is a faithful reproduction, not a clean one.

### Examples of conditions to inject

**STT / transcript pipeline:**
- **Delay interim transcripts from Deepgram** — add `asyncio.sleep(N)` in the STT callback before forwarding interim results to the LLM, simulating a slow or lagging STT stream
- **Drop or corrupt a transcript segment** — skip forwarding one interim result entirely to simulate a missed utterance
- **Replay a garbled transcript** — force the exact STT-mangled string from the prod call into the transcript pipeline instead of what the microphone captures

**LLM timeouts and latency:**
- **Force LLM timeout** — add `asyncio.sleep(N)` before the LLM call where `N` exceeds the agent's configured timeout threshold, triggering the timeout handler
- **Slow first token** — add delay specifically after the LLM call starts but before the first token arrives, simulating a slow model response
- **Introduce retry conditions** — make the LLM call raise a transient error on the first attempt to trigger retry logic

**API keys and credentials:**
- **Invalid API key** — set the relevant env var to a garbage value (`export OPENAI_API_KEY=invalid`) to trigger auth failures
- **Expired token** — use a well-formed but invalid token to get 401 responses rather than connection errors
- **Rate limit simulation** — intercept the API client and raise a rate limit error after N calls

**Tool calls and external services:**
- **Slow tool response** — wrap the tool handler with `asyncio.sleep(N)` to simulate a slow downstream API
- **Tool returning wrong data** — monkey-patch the tool response to return the malformed or missing data that was observed in the prod call logs
- **Tool call failure** — make the tool raise an exception or return a 500 to trigger error handling paths

**Audio and telephony:**
- **Silence injection** — use `<silence>` in conditional actions to simulate the caller going silent at a specific point in the conversation
- **Interruption** — use `<interruption>` to simulate the caller cutting off the agent mid-sentence
- **Connection instability** — lower `maxDurationSeconds` to force a near-timeout condition

**Any other condition you can think of** — if the prod logs or transcript suggest a specific environmental factor caused the issue, replicate it. The point is to make the local environment as close to the prod failure environment as possible.

These conditions stay active through Phase 2 and Phase 4. Remove or fix them only after the Phase 4 E2E simulation passes.

---

## 2d. Run the evaluator

Trigger a voice run on Cekura, passing `agent_number` = `X-CallerId` from `local_runner.py` (`+19789751706`):

```bash
run_voice "SCENARIO_ID" '{"agent_number": "+19789751706"}'
```

From the response, note the **Cekura outbound number** and update `dialout_settings.sip_uri` in `local_runner.py` with it.

Run the local bot in the background (edge conditions active):

```bash
cd twilio-sip-dial-out && LOCAL_RUN=1 python bot.py &
```

Poll for results:

```bash
get_result "RESULT_ID"
```

---

## ⛔ Phase 2 Gate — HARD STOP

**The eval MUST fail on Cekura before proceeding to Phase 3. This is non-negotiable.**

"Fails" means the **Cekura metric scores** show failure — not just that the call ended or the transcript looks wrong.

Check `runs[].evaluation.metrics[]` in the result. The metrics from the prod call must be scoring failure here too.

> `success: true` on a run only means the call reached a terminal state. It does **not** mean the bug was reproduced. Always read the metric scores.

**Read the transcript from this result and compare it turn-by-turn with the original prod call transcript.** The failure mode must be visibly present in the new transcript AND reflected in the metric scores.

**If the metrics pass or the result is ambiguous:**

Do not proceed. Stop and diagnose:
- Are the metrics the exact ones that failed in the prod call? If not, go back to 2b.
- Are the edge conditions (invalid API key, sleep timers, etc.) actually active? Check and re-apply.
- Is the evaluator sending the right turns in the right order? Re-check the conditional actions.
- Is the wrong code path being exercised? Re-read the root cause from Phase 1.

**If still unsure, stop and ask the user** what they observed in the original prod call. Do not guess.

Only when the **Cekura metric scores definitively show failure in the same way as the prod call** move to [Phase 3](phase3-fix.md).
