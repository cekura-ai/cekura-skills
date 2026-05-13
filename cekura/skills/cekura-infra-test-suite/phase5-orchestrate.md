# Phase 5 — Create Scenarios and Write the Run Script

Read `/tmp/infra-test-plan.md` (written by Phase 4) before doing anything else. That file has the complete scenario plan — conversation flows, evaluation criteria, and configuration batches. This phase creates the Cekura scenarios from that plan and writes a script that runs them all.

---

## 5a. Create a folder on Cekura

Group all infra scenarios in a dedicated folder. Never create them in the root.

Use `mcp__cekura__scenarios_folder_create` with name `"Infrastructure Test Suite"`. Record the returned `folder_path` — it goes on every scenario created in this phase.

---

## 5b. Create each scenario

For every scenario in `/tmp/infra-test-plan.md`, create a Cekura evaluator using `mcp__cekura__scenarios_create`.

**All scenarios must use `scenario_type: "conditional_actions"`** — always, without exception. Behavioral instructions are not deterministic enough to reliably trigger specific infra behaviors like idle timers, interruptions, or DTMF input. Never use behavioral mode for this suite.

### Translating the Phase 4 plan into conditional_actions

**Condition 0 — who speaks first**

If the bot speaks first (recorded in Phase 2 Q10): the testing agent must wait silently.
```json
{ "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false }
```

If the caller speaks first: the testing agent opens with the first line from the Phase 4 conversation flow.
```json
{ "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "[opening line]", "fixed_message": false }
```

**All subsequent conditions — always `action_followup` with `fixed_message: true`**

Every condition after 0 must be `type: "action_followup"` with `fixed_message: true`. This delivers a scripted sequence regardless of the bot's exact phrasing. Infra tests have no business depending on what the bot says — only on triggering a specific pipeline behavior.

```
Condition 0 → FIRST_MESSAGE (standard)
Condition 1 → action_followup of 0, fixed_message: true
Condition 2 → action_followup of 1, fixed_message: true
...
```

Never use `standard` conditions after condition 0.

**Translating conversation steps into condition actions**

| Phase 4 step | Condition action |
|---|---|
| Say: "[text]" | `"action": "[text]"` |
| Stay silent for Ns | `"action": "<hold duration=\"Ns\" />"` |
| Interrupt bot after Xs | `"action": "<interruption time=\"Xs\" />[what to say after]"` |
| Send DTMF sequence | `"action": "<dtmf digits=\"XXXXX#\" />[spoken text to advance chain]"` |
| Simulate voicemail | `"action": "<voicemail />"` |
| Send SMS mid-call | `"action": "<send_sms text=\"...\" />[spoken text]"` |

Use `<hold>` (not `<silence>`) for idle timer tests — `<hold>` produces dead air, `<silence>` keeps background noise running and may prevent the idle timer from firing on sensitive VAD configurations.

**Expected Outcome field**

Translate the "Expected outcome" from the Phase 4 plan directly into the scenario's `expected_outcome` field. Keep it to observable call behavior — what the bot says or does — not internal state. Do not put timing assertions or audio quality checks in Expected Outcome; use dedicated predefined metrics for those.

### Attach metrics

For each scenario, attach the metrics listed in the Phase 4 evaluation criteria using `mcp__cekura__scenarios_partial_update` or by including metrics in the create payload.

Use the **cekura-predefined-metrics** skill to look up the exact metric IDs and confirm they are active at the project level before attaching them to scenarios.

Two activation steps are required — missing either means the metric never fires:
1. Toggle on at the project level
2. Add to the individual scenario

After creating each scenario, record its ID and which configuration batch it belongs to. This mapping drives the run script in 5c.

---

## 5c. Understand the connection model

Before writing the script, confirm how Cekura connects to the bot (from Phase 2 Q1 and Q11):

**Cekura calls the bot (inbound to bot)**
The bot must be reachable at a stable address before the run starts. The script starts the bot, waits for readiness, then triggers the Cekura run.

**Bot calls Cekura (outbound from bot)**
Cekura provides a number or endpoint for the bot to dial. The script triggers the Cekura run first to get connection details, then starts the bot with those details injected.

**WebRTC / WebSocket**
Cekura provides a room URL, token, or WebSocket endpoint. The script extracts connection details from the Cekura run response and passes them to the bot.

Identify which model applies — it determines the step ordering in the run script.

---

## 5d. Write the run script

The script runs every scenario from the test plan against the local bot, grouped by configuration batch. Scenarios within the same batch run sequentially against the same bot instance. A new batch triggers a bot restart with the new config applied.

Write the script as `infra_test_run.sh` (or `.py` if the bot's ecosystem is Python-first — match the language to what the team already uses for CI).

### Script structure

```
# ── Setup ────────────────────────────────────────────────────────────────────
# Load base env vars from Phase 2 Q11 (start command, readiness signal, etc.)
# Define helper: start_bot(config_overrides) — applies overrides, starts bot,
#   waits for readiness signal, returns PID
# Define helper: stop_bot(PID) — graceful stop, fallback to SIGKILL
# Define helper: run_scenario(scenario_id) → pass|fail
#   - Trigger the Cekura run for this scenario (via API or MCP)
#   - If bot-calls-Cekura: inject connection details into running bot
#   - Poll until run status is completed or timeout (use 2× the longest
#     expected call duration from Phase 2 descriptions)
#   - Return pass if evaluation_status == "success", fail otherwise
# Define helper: apply_config(overrides) — writes env overrides to a temp
#   file or exports them; records what was changed for restore
# Define helper: restore_config() — undoes overrides applied by apply_config

# ── Batch A — Default configuration ─────────────────────────────────────────
echo "=== Batch A: Default configuration ==="
start_bot({})
for scenario_id in [SCENARIO-001-id, SCENARIO-002-id, ...]:
    result = run_scenario(scenario_id)
    record(scenario_id, result)
stop_bot()

# ── Batch B — [Config override description] ──────────────────────────────────
echo "=== Batch B: LLM_TIMEOUT_MS=50 ==="
apply_config({ LLM_TIMEOUT_MS: 50 })
start_bot({})
for scenario_id in [SCENARIO-008-id, SCENARIO-009-id, ...]:
    result = run_scenario(scenario_id)
    record(scenario_id, result)
stop_bot()
restore_config()

# (repeat for each batch)

# ── Results ──────────────────────────────────────────────────────────────────
print_summary()   # pass/fail per scenario, total pass rate
exit 0 if all passed, else exit 1
```

### Key implementation requirements

**Readiness gating** — after starting the bot, wait for the exact readiness signal documented in Phase 2 Q11 (log line, health endpoint, port open) before triggering any run. Do not use a fixed `sleep`. A timeout that fires a non-functional bot is not a test result — it is a connection error.

**Per-scenario timeout** — each run_scenario call must have a deadline. Use 2× the longest expected call duration from the Phase 2 descriptions. A scenario that exceeds its deadline is recorded as a timeout failure, not a pass.

**Config isolation** — every config override must be fully reversed before the next batch starts. The script must be safe to kill mid-run: use a trap to call restore_config() and stop_bot() on SIGINT/SIGTERM.

**Scenario ID mapping** — the script must contain a static mapping of scenario name → Cekura scenario ID (recorded during 5b). Do not look up IDs dynamically at run time.

**Connection detail injection** — if the bot is outbound (bot calls Cekura), use the mechanism documented in Phase 2 Q11 (env var, config file, CLI arg, API endpoint) to inject the Cekura connection details returned by the run trigger. Document the injection point as a comment in the script.

---

## 5e. Verify end-to-end before committing the script

Run one scenario manually before running the full suite:

1. Apply the scenario's configuration batch (if any)
2. Start the bot and confirm the readiness signal fires
3. Trigger the Cekura run for that scenario
4. Confirm the bot connects to Cekura's testing agent
5. Confirm the run moves through `pending → in_progress → completed`
6. Confirm the result is a real pass or a meaningful failure — not a timeout or connection error
7. Restore config and stop the bot

Fix any connection or timing issues before running the full suite. A timeout or connection error is a script problem, not a test result.

---

## Phase 5 Complete

The suite is ready as a CI gate. The run script is the entry point — run it before merging any PR that touches the pipeline stack. Every scenario must pass.

```
./infra_test_run.sh
# or
python infra_test_run.py
```

**Next steps:**
- To add behavioral (non-infra) test coverage → **cekura-eval-design**
- To debug a failing production call → **cekura-fixing-prod-issues**
- To improve metric accuracy on failing scenarios → **cekura-metric-improvement**
