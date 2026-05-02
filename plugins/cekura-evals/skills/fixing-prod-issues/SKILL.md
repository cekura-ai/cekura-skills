---
name: fixing-prod-issues
description: Debugs a failing production call, creates a fix, runs comprehensive regression tests across all affected flows using Cekura evaluators and the local twilio-sip-dial-out agent, then raises a PR with evidence. Use when the user wants to fix a production call bug, investigate a failing prod call, reproduce and fix a production issue, run regression tests before a PR, or says things like "fix this prod call issue", "debug and fix call ID", "test my fix against prod scenarios", "reproduce this production bug", or "regression test before raising PR".
---

# Fixing Production Call Issues

Full workflow — two rounds of testing, no deployment required:

```
Phase 1        Phase 2              Phase 3         Phase 4              Phase 5       Phase 6
Debug    →   Reproduce setup   →  Confirm bug  →  Fix + re-run     →  Regression  →  PR
Understand     Evaluators +          Run shows       Same setup on       Happy paths    All result
root cause     metrics that          eval FAILS      fixed code →        + edge cases   URLs in PR
               define failure        as expected     eval PASSES         pass too
```

## Progress checklist

```
- [ ] Phase 1:  Debug the issue
- [ ] Phase 2:  Build reproduction setup
  - [ ] 2a. Create conditional-actions evaluator(s) for the failing case
  - [ ] 2b. Attach predefined metrics + write expected outcome (describes correct behaviour)
  - [ ] 2c. Configure local agent with edge conditions to reproduce bug
- [ ] Phase 3:  Confirm reproduction — eval must FAIL before fix
- [ ] Phase 4:  Apply fix, re-run same setup — eval must PASS
- [ ] Phase 5:  Regression testing
  - [ ] 5a. Identify happy paths + edge cases affected by the fix
  - [ ] 5b. Create evaluators with conditional actions + metrics
  - [ ] 5c. Run all — everything must PASS
- [ ] Phase 6:  Raise PR with all result URLs
```

---

## Phase 1 — Debug the Issue

Fetch the production call:

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
get_call "CALL_ID"
```

Extract:

| Field | Path |
|---|---|
| Real agent ID | `metadata.agent_id` (not top-level `agent_id`) |
| Personality ID | `metadata.personality_id` |
| Project ID | `project` field on the agent |
| Customer data | `dynamic_variables` |
| Ended reason | `metadata.ended_reason` |
| Transcript | `transcript_object` (array of turns with role + content) |

Fetch agent config:

```
cekura:aiagents_retrieve  →  id = metadata.agent_id
```

Extract: `description` (system prompt), `llm_model`, `llm_temperature`, `llm_max_tokens`.

Use Datadog MCP tools to check logs around the call timestamp. Search by `call_id`, `session_id`, or agent ID. Cross-reference with the transcript to pinpoint exactly where and why the call went wrong.

Confirm the root cause with the user before proceeding.

---

## Phase 2 — Build the Reproduction Setup

### 2a. Create the evaluator using conditional actions

Use the `cekura-evals:conditional-actions` skill to build a deterministic evaluator.

Extract **Testing Agent** turns from `transcript_object` verbatim. Do **not** clean up STT artifacts — garbled text, truncated words, odd punctuation are exactly what the main agent's LLM received in production and are the bug trigger.

Map each turn to a fixed condition:
- First turn: `trigger: "call_start"`, `type: "fixed"`
- Subsequent turns: `trigger: "agent_speaks"`, `type: "fixed"`
- Use tags if the scenario involves voice-specific behaviour: `silence`, `interruption`, `background_noise`, `dtmf`, etc.

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
create_scenario '{
  "agent": AGENT_ID,
  "personality": PERSONALITY_ID,
  "name": "Bug repro: <brief issue description>",
  "instructions": "Replay the production call that caused <issue>.",
  "expected_outcome_prompt": "<describe what CORRECT behaviour looks like — this defines pass/fail>",
  "conditional_actions": { "role": "caller", "conditions": [...] }
}'
```

Save the `scenario_id`.

### 2b. Attach metrics and write the expected outcome

List available predefined metrics and choose the ones most relevant to the failure:

```bash
# Use MCP tool to list predefined metrics
cekura:predefined_metrics_list
```

Attach the relevant metric IDs to the scenario and write an `expected_outcome_prompt` that clearly describes what **correct** behaviour looks like after the fix. This is the success criterion — the eval will **FAIL** when the bug is present and **PASS** when the fix works.

```bash
update_scenario "SCENARIO_ID" '{
  "metrics": [METRIC_ID_1, METRIC_ID_2],
  "expected_outcome_prompt": "..."
}'
```

### 2c. Configure the local agent to reproduce the bug

Display values for `twilio-sip-dial-out/local_runner.py`:

| Field | Value |
|---|---|
| `scenario_config.instructions` | Agent system prompt from Phase 1 |
| `scenario_config.name` | `"Bug repro: <issue>"` |
| `configuration.model` | `llm_model` from agent config |
| `call_details.call_id` | `"patronus_<timestamp>"` |
| `dialout_settings.sip_uri` | `sip:<CEKURA_OUTBOUND_NUMBER>@cekura-pipecat-local.sip.twilio.com?X-CallerId=+19789751706` |

**Role swap:** If instructions mention "main agent" or "testing agent" by name, swap the labels.

Apply the **same conditions that caused the bug** in production. Examples:
- **Invalid / expired API key**: set the env var to a bad value
- **Slow upstream / latency**: add `asyncio.sleep(N)` in the relevant handler
- **Timeout boundary**: lower `maxDurationSeconds` in the config
- **Missing data**: omit a field from `dynamic_variables` that the agent expects

These conditions stay in place for Phase 3. They are removed (or fixed) for Phase 4.

---

## Phase 3 — Confirm Reproduction

Trigger the evaluator on Cekura, passing `agent_number` = `X-CallerId` from `local_runner.py` (`+19789751706`):

```bash
run_pipecat "SCENARIO_ID" '{"agent_number": "+19789751706"}'
```

Note the **Cekura outbound number** from the response and update `dialout_settings.sip_uri` in `local_runner.py` with it.

Run the local bot in the background (bug conditions still active):

```bash
cd twilio-sip-dial-out && LOCAL_RUN=1 python bot.py &
```

Poll for results:

```bash
get_result "RESULT_ID"
```

**Expected outcome: the eval FAILS.** If it passes, the reproduction setup is not correctly simulating the bug — revisit Phase 2 before continuing. Do not apply the fix until the eval reliably fails.

---

## Phase 4 — Apply the Fix and Re-run

### 4a. Fix the code

Apply the fix. Keep the same edge conditions active (invalid API key, sleep timers, etc.) — the fix must handle those, not just work under ideal conditions.

### 4b. Commit locally

```bash
git add <changed files>
git commit -m "fix: <description>"
```

Do not push yet.

### 4c. Re-run the same evaluator

Trigger a new run for the same `scenario_id` — do not create a new evaluator:

```bash
run_pipecat "SCENARIO_ID" '{"agent_number": "+19789751706"}'
```

Update the SIP URI with the new Cekura outbound number, run the bot in background, poll for results.

**Expected outcome: the eval PASSES.** If it still fails, iterate on the fix and re-run. Do not proceed to Phase 5 until this passes.

---

## Phase 5 — Regression Testing

### 5a. Identify happy paths and edge cases

Think through every flow that touches the changed code path:
- Standard happy path flows through the same handler
- Edge cases the fix might break (error paths, timeouts, retries)
- Scenarios with voice-specific stress: silence gaps, interruptions, background noise, DTMF input
- Any other caller intents that reach the same code

Produce a named list and confirm with the user.

### 5b. Create evaluators for each case

Use the `cekura-evals:conditional-actions` skill for each. Design the conversation flow for each case. Use relevant tags where applicable (`silence`, `interruption`, `background_noise`, `dtmf`, etc.).

For each evaluator, attach predefined metrics and write a precise `expected_outcome_prompt`.

```bash
create_scenario '{
  "agent": AGENT_ID,
  "personality": PERSONALITY_ID,
  "name": "Regression: <case name>",
  "instructions": "...",
  "expected_outcome_prompt": "...",
  "metrics": [...],
  "conditional_actions": { "role": "caller", "conditions": [...] }
}'
```

### 5c. Run all regression cases

For each scenario, trigger a pipecat run, note the Cekura outbound number, update `local_runner.py`, run the bot in background. Work through cases one at a time — restore any modified conditions between cases.

Poll all results. Build a summary:

| Case | Status | Pass/Fail | Notes |
|---|---|---|---|
| Happy path | completed | PASS | — |
| Silence gap | completed | PASS | — |
| Interruption | completed | FAIL | Agent stopped mid-sentence |

For any failure: show the transcript divergence point, fix, and rerun:

```bash
rerun_result "RESULT_ID"
```

All cases must pass before proceeding.

---

## Phase 6 — Raise the PR

```bash
gh pr create --title "<fix title>" --body "..."
```

The `project_id` is the `project` field from the agent config (Phase 1).

Include in the PR body:

```
## Test evidence

### Bug reproduction (before fix — expected to FAIL)
| Scenario | Result |
|---|---|
| Bug repro | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID_FAIL ❌ (confirmed bug) |

### Fix verification (after fix — expected to PASS)
| Scenario | Result |
|---|---|
| Bug repro | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID_PASS ✅ |

### Regression tests
| Case | Result |
|---|---|
| <Happy path> | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID_1 ✅ |
| <Edge case>  | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID_2 ✅ |

Prod call: #CALL_ID
Root cause: <one sentence>
Edge conditions used to reproduce: <e.g. invalid API key, 2s sleep in handler>
```
