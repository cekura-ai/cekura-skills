# Phase 5 — Regression Testing

> ## ⚠️ ALL REGRESSION TESTS MUST BE E2E SIMULATIONS ON CEKURA
>
> **Every regression case MUST be run as a full end-to-end simulation on Cekura using the same connection medium as the production call** — same agent, same transport.
>
> ❌ Do NOT use text mode. ❌ Do NOT switch transports between phases.
>
> Passing regression tests over a different medium than production is a false pass.

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

Use the the `cekura-eval-design` skill (`references/conditional-actions.md`) skill to build each evaluator. Design the conversation flow for each case.

To **generate** voice-specific stress conditions, use XML tags in `fixed_message`: `<silence>`, `<interruption>`, `<background_noise>`, `<dtmf>`. These make the testing agent emit those conditions.

To **evaluate** the main agent's response to those conditions, attach predefined metrics:
- Silence / drops / non-response → **Infrastructure Issues**
- Slow replies → **Latency**
- Tool call behaviour → **Tool Call Success**

Do not write custom `expected_outcome_prompt` — attach the relevant predefined metrics that would catch a failure in each case.

```bash

create_scenario '{
  "agent": AGENT_ID,
  "personality": PERSONALITY_ID,
  "name": "Regression: <case name>",
  "scenario_type": "conditional_actions",
  "instructions": "...",
  "metrics": [METRIC_ID_1, METRIC_ID_2],
  "conditional_actions": { "role": "caller", "conditions": [...] }
}'
```

**`scenario_type: "conditional_actions"` is required, not optional.** Omit it and the API defaults the scenario to `instruction`, silently ignoring the `conditions` you just built — the replay then improvises instead of reproducing the bug. (Behavioral scenarios are the one type this direct-create path is not for; those are always generated.)


---

## 5c. Run all cases

For each scenario, trigger a run using the agent's configured transport, extract connection details from the response, start the local agent using the setup instructions from `memory.md` / `CLAUDE.md`. Work through cases one at a time — restore any modified conditions between cases.

```bash
run_voice "SCENARIO_ID" '{"agent_number": "<local_agent_caller_id>"}'
# pass connection details to local agent per stored setup instructions
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
