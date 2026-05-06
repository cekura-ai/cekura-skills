# Phase 2 — Reproduce the Issue

> ## ⚠️ E2E SIMULATION IS MANDATORY — USE THE SAME CONNECTION AS THE PROD CALL
>
> **Every test in this phase MUST be run as a full end-to-end simulation on Cekura using the same connection medium that the production call used.**
>
> Check the agent configuration via the Cekura API (`GET /test_framework/v1/ai-agents/{metadata.agent_id}/`) to see how the agent is set up — it will tell you which transport to use:
> - **Telephony / SIP** (most common) → use `run_voice`, local bot dials via `twilio-sip-dial-out` over Twilio SIP
> - **WebRTC** → use the appropriate WebRTC run endpoint for that provider
>
> Use the same agent (`metadata.agent_id` from the prod call) and the same transport it is configured for. Running the simulation over a different medium than the one that triggered the bug is not a valid reproduction.

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
`GET /test_framework/v1/predefined-metrics/`
```

Attach those metric IDs to the evaluator:

```bash
update_scenario "SCENARIO_ID" '{
  "metrics": [METRIC_ID_1, METRIC_ID_2, ...]
}'
```

> **If you are unsure which metrics to attach, stop and ask the user.** Do not guess — wrong metrics will make this entire phase meaningless.

---

## 2c. Look up how to run the local agent

Before configuring anything, check whether setup instructions for running the local agent and connecting it to Cekura already exist:

1. Read `memory.md` in the project root
2. Read `CLAUDE.md` in the project root

If instructions are found — follow them exactly. They are the source of truth for this project's local run setup.

**If no instructions are found in either file — you MUST ask the user before proceeding. Do not guess, do not assume, do not try to infer from other files.**

Ask:
> "I couldn't find local run setup instructions in `memory.md` or `CLAUDE.md`. How do I run the local agent and connect it to a Cekura simulation? (e.g. what command to start it, how to pass the Cekura outbound number, which config file to edit)"

Once the user explains, **save the instructions to `memory.md`** so this question never needs to be asked again for this project. Do not proceed to 2d until you have these instructions.

---

### Example setup (twilio-sip-dial-out) — for reference only

This is one possible setup. Your project may differ.

Configure `local_runner.py`:

| Field | Value |
|---|---|
| `scenario_config.instructions` | Agent system prompt (`description` from Phase 1) |
| `scenario_config.name` | `"Bug repro: <issue>"` |
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

Trigger a run on Cekura using the appropriate endpoint for the agent's configured transport (see Phase 2 header). For telephony:

```bash
run_voice "SCENARIO_ID" '{"agent_number": "<local_agent_caller_id>"}'
```

From the response, extract the connection details (e.g. outbound number for telephony, WebRTC token for WebRTC) and pass them to the local agent using the setup instructions from `memory.md` / `CLAUDE.md`.

Start the local agent with edge conditions active (follow the stored setup instructions).

Poll for results:

```bash
get_result "RESULT_ID"
```

---

## ⛔ Phase 2 Gate — ABSOLUTE HARD STOP. DO NOT PASS WITHOUT EVIDENCE.

**You MUST NOT move to Phase 3 until the eval definitively fails on Cekura. No exceptions, no shortcuts.**

This gate exists because a fix written without a confirmed reproduction is untestable — you have no way to know if the fix actually worked. Skipping this gate invalidates the entire workflow.

### What "fails" means

"Fails" means the **Cekura metric scores** show failure — not just that the call ended or the transcript looks wrong to you.

Check `runs[].evaluation.metrics[]` in the result. The exact metrics that were failing in the prod call must be scoring failure here too.

> `success: true` on a run only means the call reached a terminal state. It does **not** mean the bug was reproduced. Always read the metric scores.

**Read the transcript from this result and compare it turn-by-turn with the original prod call transcript.** The failure mode must be visibly present in the new transcript AND reflected in the metric scores.

### If the metrics pass or the result is ambiguous — stop and diagnose

Do NOT proceed. Work through this checklist:
- Are the metrics the exact ones that failed in the prod call? If not, go back to 2b.
- Are the edge conditions (invalid API key, sleep timers, etc.) actually active and strong enough? Check and re-apply.
- Is the evaluator sending the right turns in the right order? Re-check the conditional actions.
- Is the wrong code path being exercised? Re-read the root cause from Phase 1.

**If still unsure after checking all of the above — stop and ask the user.** Show them the transcript and metric scores and ask: "Does this match the failure you saw in the prod call?" Do not guess. Do not proceed.

Only when the **Cekura metric scores definitively show failure in the same way as the prod call** move to [Phase 3](phase3-fix.md).
