# Phase 5 — Build and Run

Read `/tmp/infra-test-plan.md` (written by Phase 4) before doing anything else. That file has the complete scenario plan — conversation flows, evaluation criteria, and configuration batches. This phase creates the Cekura scenarios from that plan and writes a script that runs them all.

---

## 5a. Create a folder on Cekura

Group all infra scenarios in a dedicated folder. Never create them in the root.

Use `mcp__cekura__scenarios_folder_create` with name `"Infrastructure Test Suite"`. Record the returned `folder_path` — it goes on every scenario created in this phase.

---

## 5b. Create each scenario

**Read the conditional actions reference before writing a single scenario.**

Open and read `cekura/skills/cekura-eval-design/references/conditional-actions.md` in full before authoring any scenario payload. This is a one-time read at the start of 5b — not per scenario. It covers:

- What `action_followup` means and when to use it vs `standard` (critical — this is the most commonly misunderstood field)
- The full `conditions` array structure: required fields (`id`, `type`, `condition`, `action`, `fixed_message`), how `id` chains work, what `FIRST_MESSAGE` means
- Every XML tag with its exact syntax, placement constraints, and what breaks if the constraint is violated (`<interruption>`, `<hold>`, `<silence>`, `<dtmf>`, `<voicemail>`, `<endcall>`, `<spell>`, `<background_noise>`, `<network_simulation>`)
- The validation checklist — run this on every scenario before calling the API
- The full anti-patterns list — what not to do and why

Do not reconstruct this from memory or from the summary below. The reference is the authoritative source.

**Create all scenarios in parallel, not sequentially.** Do not create them one at a time — fire all `mcp__cekura__scenarios_create` calls concurrently. The API is stateless per scenario; there is no dependency between scenario creations. Parallel creation is significantly faster for large suites (25+ scenarios).

The workflow:
1. Read the full scenario list from `/tmp/infra-test-plan.md`
2. Build the complete payload for every scenario upfront (conditional_actions, language, personality, folder_path, name, expected_outcome, metrics)
3. Fire all `mcp__cekura__scenarios_create` calls at the same time
4. Collect all returned IDs and record the scenario name → ID mapping once all calls complete
5. If any individual creation fails, log the failure and retry that scenario only — do not retry the entire batch

For authoring each scenario's payload, invoke the **cekura-eval-design** skill.

**All scenarios must use `scenario_type: "conditional_actions"`** — always, without exception. Behavioral instructions are not deterministic enough to reliably trigger specific infra behaviors like idle timers, interruptions, or DTMF input. Never use behavioral mode for this suite.

**Use the exact scenario name from the Phase 4 plan — no indexes, no prefixes.** Do not add "Scenario 1:", "Test 3:", or any numeric prefix to the name. The name field must be the descriptive, component-first name written in Phase 4 (e.g. `"Idle-Full-Escalation-to-Hangup"`, `"STT-Empty-Transcript-NoTranscriptTimer"`). Indexes belong in the TEST-NNN tracking system, not in the scenario name visible on Cekura.

### Set language and personality on every scenario — mandatory before creation

Before creating each scenario, read its **Language** and **Personality** fields from the Phase 4 plan. Both are required — the API returns 400 without a personality, and `scenario_language` is required for `conditional_actions` scenarios.

**`scenario_language`** — set to the BCP-47 code from the Phase 4 plan (`"en"`, `"es"`, `"hi"`, etc.). Never omit this field. Never leave it as `"en"` for a non-English scenario.

**`personality`** — use the ID from the Phase 4 plan. If Phase 4 flagged a gap (no personality available for a non-primary language), call `mcp__cekura__personalities_list` filtered by that language code to check whether one exists. If still unavailable, pause and ask the user: create a custom personality, or defer that language's scenarios?

Do not reuse the primary-language personality on non-primary-language scenarios — a mismatched personality produces incorrect TTS pronunciation and invalidates STT accuracy tests for that language.

### Translating the Phase 4 plan into conditional_actions

The cekura-eval-design skill covers all of this in detail. The summary below is a quick reference — defer to the skill for edge cases, tag constraints, and anti-patterns.

**Condition 0 — who speaks first**

If the bot speaks first (recorded in Phase 2 Q10): the testing agent must wait silently.
```json
{ "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false }
```

If the caller speaks first: the testing agent opens with the first line from the Phase 4 conversation flow.
```json
{ "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "[opening line]", "fixed_message": false }
```

**The cardinal rule of action_followup — one condition per bot turn, not one condition per conversation step**

`action_followup` fires **after the bot produces a turn**. This is not the same as "after each step in the Phase 4 conversation flow." Before mapping any step to a condition, ask: *does the bot speak between the previous step and this step?*

- **Bot speaks between steps → new condition.** The testing agent waits for the bot's turn, then fires the next action.
- **Bot does NOT speak between steps → combine into one action.** Both steps happen within the same testing-agent turn. Combine them into a single action string (multiple XML tags, or text followed by a hold, etc.).

Getting this wrong produces conditions that never fire: the testing agent waits for a bot turn that never comes, and the scenario stalls or times out.

**Wrong — one condition per step regardless of bot turns:**
```json
{ "id": 3, "condition": "action_followup of 2", "action": "<hold duration=\"10s\" />", "type": "action_followup", "fixed_message": true },
{ "id": 4, "condition": "action_followup of 3", "action": "Goodbye", "type": "action_followup", "fixed_message": true }
```
This breaks if the bot does not speak after the hold — condition 4 waits for a bot turn that never arrives.

**Right — combine steps that have no bot turn between them:**
```json
{ "id": 3, "condition": "action_followup of 2", "action": "<hold duration=\"10s\" />Goodbye", "type": "action_followup", "fixed_message": true }
```
The hold and the goodbye are one action because the testing agent does both without waiting for the bot.

**Before writing each condition, explicitly verify:** look at the Phase 4 conversation flow and ask "after the previous step, does the bot produce a response before the next step?" If no → merge. If yes → new condition.

Common infra patterns where steps must be merged (no bot turn in between):
- Hold followed immediately by another hold (multiple silence windows)
- Hold followed by a closing phrase (bot is silent during hold, never responds)
- DTMF send followed by spoken text (sent together in one testing-agent action)
- Interruption tag followed by what to say after the interrupt (same action string)

---

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
| Stay silent for Ns (bot expected to respond after) | `"action": "<hold duration=\"Ns\" />"` — new condition |
| Stay silent for Ns (bot NOT expected to respond) | merge with next step into one action |
| Interrupt bot after Xs | `"action": "<interruption time=\"Xs\" />[what to say after]"` — one action, not two |
| Send DTMF sequence | `"action": "<dtmf digits=\"XXXXX#\" />[spoken text to advance chain]"` |
| Simulate voicemail | `"action": "<voicemail />"` |
| Send SMS mid-call | `"action": "<send_sms text=\"...\" />[spoken text]"` |

Use `<hold>` (not `<silence>`) for idle timer tests — `<hold>` produces dead air, `<silence>` keeps background noise running and may prevent the idle timer from firing on sensitive VAD configurations.

**Translating evaluation pointers into metrics and expected outcome**

Each scenario in Phase 4 has a set of plain-English evaluation pointers — what to check in the transcript to determine pass or fail. Translate those pointers into two things on the Cekura scenario:

1. **Expected Outcome field** — **read `cekura/skills/cekura-eval-design/references/expected-outcomes.md` in full before writing the `expected_outcome_prompt` for any scenario.** That file is the authoritative guide and contains the scoring model, all writing rules, prioritisation hierarchy, good/bad examples, and common pitfalls. Do not write a single expected outcome without having read it.

   Key rules from that reference that apply to every infra scenario:
   - Every statement must start with **"The main agent should"** — never "bot", "assistant", "AI"
   - Max 2 actions per statement — split if a step has 3 or more sub-actions
   - Semantic content only — do not quote verbatim phrases (paraphrasing is a pass); exception: exact values for KB/fact lookups
   - No subjective descriptors — "appropriately", "warmly", "professionally" are not verifiable; use functional descriptions
   - Binary verifiable — every statement must be objectively True/False from the transcript
   - Do not test call closing/farewells unless the test explicitly requires it
   - Attach the **Expected Outcome** predefined metric — the `expected_outcome_prompt` field alone does nothing without the metric

   Additionally, before writing the expected outcome, open `/tmp/infra-workflow-descriptions.md` and find the Phase 2 section for the behavior being tested. Use the actual bot behavior documented there — not the Phase 4 pointers alone, which are summaries. If Phase 2 documents an exact phrase, use the meaning (not the verbatim quote) to avoid false failures from paraphrasing.

2. **Predefined metrics** — **invoke the `cekura-predefined-metrics` skill now, before writing a single metric onto any scenario.** Do not guess metric names, do not use the matching table below as a substitute for the skill, and do not skip this step even if the evaluation pointers seem straightforward. The skill has the full catalog, cost, audio requirements, configuration options, and known constraints for every metric. Using it is mandatory.

   Once the skill has been invoked and you have the current catalog in context, go through every evaluation pointer for every scenario and select the predefined metric that best covers it. The table below is a starting heuristic — the skill's output takes precedence:

   | Evaluation pointer | Likely predefined metric |
   |---|---|
   | Bot stops speaking immediately when interrupted | Interruption Score / AI Interrupting User |
   | Bot responds within N seconds | Response Latency / Time to First Token |
   | Transcription matches what was said despite noise | Transcription Accuracy |
   | Caller sounds satisfied / frustrated | Caller Sentiment / CSAT |
   | Bot stays on topic / does not hallucinate | Hallucination / Factual Accuracy |
   | Call ends correctly / task completed | Expected Outcome field (transcript-level) |
   | No long silences or connection drops | Infrastructure Issues |
   | Tool call succeeded / returned correct result | Tool Call Success |

   If no predefined metric covers a pointer, note it explicitly in the scenario as a transcript-only check (covered by Expected Outcome only).

### Activate and attach metrics

**Before attaching any metric to a scenario, confirm it is toggled on at the project level.** Use `mcp__cekura__metrics_list` to check which metrics are already active. Activate any that are not yet enabled. Missing this step means the metric is attached to the scenario but never fires — runs will return incomplete evaluations silently.

Then attach metrics to each scenario via `mcp__cekura__scenarios_partial_update` or include them in the create payload.

Two activation steps are required — missing either means the metric never fires:
1. Toggle on at the project level
2. Add to the individual scenario

After creating each scenario, record its ID and which configuration batch it belongs to. This mapping drives the run script in 5d.

---

## 5c. Cross-verify every created scenario against the plan

After all scenarios are created, fetch each one from Cekura using `mcp__cekura__scenarios_retrieve` and verify it against its entry in `/tmp/infra-test-plan.md`. Do this one scenario at a time — do not batch or skip any.

For each scenario, check every field listed below. If any field is wrong, patch it immediately before moving to the next scenario.

**Conversation flow fidelity**
- Does the number of conditions match the number of steps in the Phase 4 conversation flow? A missing condition means a test step was silently dropped.
- Does each condition's `action` correctly translate the corresponding Phase 4 step — right text, right XML tag, right tag parameters (duration, digit sequence, offset)?
- Is condition 0 correctly set: `FIRST_MESSAGE`, `type: "standard"`, and `action: ""` if the bot speaks first or the correct opening line if the caller speaks first?
- Is every condition after 0 using `type: "action_followup"` with `fixed_message: true`? Any `standard` condition after 0 is a bug.
- Are `<hold>` tags used (not `<silence>`) for all idle-timer steps?
- Are timing values in the conditions consistent with the values in Phase 4 — not rounded, not approximated?

**Coverage**
- Does the scenario's `name` and TEST-NNN list match what Phase 4 specified? A renamed or mis-tagged scenario breaks traceability.
- Is the scenario placed in the correct folder (`Infrastructure Test Suite`)?
- Is the scenario assigned to the correct configuration batch (as recorded in 5b)?

**Language and personality**
- Does `scenario_language` match the BCP-47 code from the Phase 4 plan? A missing or wrong language code causes incorrect TTS and invalidates language-specific tests.
- Does the assigned `personality` ID match the Phase 4 plan? Verify the personality's configured language matches `scenario_language` — a mismatch (English voice on a Spanish scenario) produces wrong pronunciation and unreliable STT.

**Metrics and expected outcome**
- Are all intended metrics attached and active at the project level?
- Does the `expected_outcome` field reflect the Phase 4 evaluation pointers — not blank, not generic, not copied from a different scenario?
- Does the `expected_outcome` use the actual bot phrases and behaviors from Phase 2 — not a paraphrase? Open `/tmp/infra-workflow-descriptions.md` and compare: if Phase 2 says the idle prompt is "Are you still with me?" and the expected_outcome says "bot prompts caller about silence", that is a mismatch — patch it with the exact phrase.
- Do the `action` timing values in the conditions match the Phase 2 values exactly — not rounded, not estimated? A `<hold duration="10s"/>` that should be `<hold duration="12s"/>` based on Phase 2's documented threshold will cause the idle timer test to fail silently.

**What to do when a mismatch is found**
- Fix it with `mcp__cekura__scenarios_partial_update` immediately.
- Note the mismatch and the fix in a short verification log written to `/tmp/infra-verification-log.md` (create if it doesn't exist). Format: `SCENARIO-NNN: [field] was [wrong value], patched to [correct value]`.
- If the mismatch cannot be fixed via PATCH (e.g. a fundamental structural problem requiring recreation), delete the scenario with `mcp__cekura__scenarios_destroy`, recreate it correctly, and update the scenario ID in the batch mapping.

At the end of the verification pass, write a summary line to `/tmp/infra-verification-log.md`:
```
Verification complete. N scenarios checked. M mismatches found and fixed. 0 unresolved.
```

Do not proceed to 5d until every scenario has been verified and the log confirms 0 unresolved issues.

---

## 5d. Read connection types and deployment steps from Phase 1

The answers to both of these were collected in Phase 1 before Phase 2 began. Read them from the Phase 1 gate output — do not ask the user again.

**Selected connection types** — from Phase 1 "Selected connection types" answer. These determine how many run-loops the script has and which Cekura runner each loop uses:

| Connection type | Cekura runner |
|---|---|
| Plain voice / phone | `mcp__cekura__scenarios_run_voice` |
| WebSocket | `mcp__cekura__scenarios_run_websocket` |
| SIP | `mcp__cekura__scenarios_run_sip` |
| VAPI WebRTC | `mcp__cekura__scenarios_run_vapi_webrtc` |
| Retell WebRTC | `mcp__cekura__scenarios_run_retell_webrtc` |
| Pipecat v1 | `mcp__cekura__scenarios_run_pipecat_v1` |
| Pipecat v2 | `mcp__cekura__scenarios_run_pipecat_v2` |
| LiveKit v2 | `mcp__cekura__scenarios_run_livekit_v2` |
| ElevenLabs | `mcp__cekura__scenarios_run_elevenlabs` |
| Chirp | `mcp__cekura__scenarios_run_chirp` |

**Deployment steps** — from Phase 1 "Deployment steps" answer (confirmed by the user at the end of Phase 1). Use exactly as recorded: start command, readiness signal, stop command. If the Phase 1 answer was incomplete or the user indicated something has changed, ask now for the missing parts only — do not re-ask everything.

---

## 5e. Write the run script

The script runs every scenario from the test plan against the local bot. It is structured in two outer loops:

1. **Connection type loop** — one pass per connection type the user selected in Phase 1. Each pass runs all batches.
2. **Configuration batch loop** — within each connection type pass, scenarios are grouped by configuration batch. A new batch triggers a bot restart with the new config applied.

Write the script as `infra_test_run.sh` (or `.py` if the bot's ecosystem is Python-first — match the language to what the team already uses for CI).

### Script structure

Before writing the script, read Phase 4's configuration batch table and for each batch produce a concrete apply/restore block using the exact injection mechanism documented in Phase 4 (env var export, `.env` file write, config YAML edit, CLI flag, etc.). Do not write pseudocode — write the actual shell commands the script will execute.

Example of what a concrete batch block looks like when the bot reads from env vars:

```bash
# ── Batch B — LLM timeout forced to 50ms ─────────────────────────────────────
# Phase 4: LLM_TIMEOUT_MS → env var; inject via export; restore to 8000
echo "=== Batch B: LLM_TIMEOUT_MS=50 ==="
ORIG_LLM_TIMEOUT_MS="${LLM_TIMEOUT_MS:-8000}"          # save original
export LLM_TIMEOUT_MS=50                                # apply override
start_bot                                               # bot starts with override
# verify override took effect (Phase 4 verification step: bot logs "LLM timeout: 50ms")
wait_for_log "LLM timeout: 50ms" 10                     # fail-fast if not applied
run_scenario "LLM-Timeout-Fallback" "websocket"
stop_bot
export LLM_TIMEOUT_MS="$ORIG_LLM_TIMEOUT_MS"           # restore
```

Example when the bot reads from a `.env` file:

```bash
# ── Batch C — STT confidence threshold set to 1.0 ────────────────────────────
echo "=== Batch C: STT_CONFIDENCE_THRESHOLD=1.0 ==="
cp .env .env.backup                                     # save original file
sed -i 's/STT_CONFIDENCE_THRESHOLD=.*/STT_CONFIDENCE_THRESHOLD=1.0/' .env
start_bot
run_scenario "STT-Empty-Transcript-NoTranscriptTimer" "websocket"
stop_bot
cp .env.backup .env                                     # restore original file
rm .env.backup
```

The full script structure:

```bash
#!/usr/bin/env bash
set -euo pipefail

# ── Baseline configuration (from Phase 2 Q12) ────────────────────────────────
# These must match the exact values Phase 2 analyzed. Any deviation means
# the bot's behavior will not match the expected outcomes in the scenarios.
export LLM_TIMEOUT_MS=8000          # Phase 2 Q4: config.py:34
export IDLE_TIMEOUT_S=8             # Phase 2 Q7: config.py:61
export STT_MODEL=nova-2             # Phase 2 Q2: deepgram config
# ... all config-governing values from Phase 2 ...

# ── Scenario ID map (from 5b, verified in 5c) ────────────────────────────────
declare -A SCENARIO_IDS=(
    ["Idle-Full-Escalation-to-Hangup"]="<id>"
    ["STT-Empty-Transcript-NoTranscriptTimer"]="<id>"
    ["LLM-Timeout-Fallback"]="<id>"
    # ...
)

# ── Helpers ──────────────────────────────────────────────────────────────────
start_bot() {
    # Exact start command from 5d Q2
    <start command here> &
    BOT_PID=$!
    # Wait for exact readiness signal from Phase 2 Q12
    wait_for_log "<readiness signal>" 30 || { echo "Bot failed to start"; exit 1; }
}
stop_bot() { kill "$BOT_PID" 2>/dev/null; wait "$BOT_PID" 2>/dev/null; }
trap 'stop_bot; restore_all_configs' SIGINT SIGTERM

run_scenario() {
    local name=$1 transport=$2
    local id="${SCENARIO_IDS[$name]}"
    # Trigger via appropriate Cekura runner for this transport
    # Poll until completed or 2× max call duration timeout
    # Return pass/fail based on evaluation_status
}

# ── Connection type loop ──────────────────────────────────────────────────────
for TRANSPORT in websocket sip; do   # ← transports selected in Phase 1
  echo "=== Transport: $TRANSPORT ==="

  # Batch A — Default configuration
  start_bot
  run_scenario "Idle-Full-Escalation-to-Hangup" "$TRANSPORT"
  run_scenario "Interruption-BackToBack" "$TRANSPORT"
  # ... all default-config scenario names ...
  stop_bot

  # Batch B — [description from Phase 4, using concrete inject/restore]
  <concrete apply block here>
  start_bot
  run_scenario "LLM-Timeout-Fallback" "$TRANSPORT"
  stop_bot
  <concrete restore block here>

done

# ── Results ──────────────────────────────────────────────────────────────────
print_summary   # pass/fail per scenario per transport, total pass rate
```

### Key implementation requirements

**Base configuration must match Phase 2** — the bot must start with the exact configuration that was analyzed in Phase 2. Before writing the startup block, read Phase 2 Q12 (Local Run) and Q1–Q11 for any configuration values that govern the behaviors being tested (idle timeout, LLM timeout, STT model, etc.). Hardcode these as the baseline env vars in the script. If the bot starts with a different configuration than what Phase 2 analyzed, the expected outcomes will not match and every config-sensitive test will produce a meaningless result.

**Deployment steps verbatim** — embed the exact start/stop commands and env vars confirmed in 5d Q2 as executable lines (not comments). Label each block clearly so the user can edit them later.

**Readiness gating** — use the exact readiness signal confirmed in 5d Q2 (log line, health endpoint, port). Do not use a fixed `sleep`.

**Per-scenario timeout** — each `run_scenario` call must have a deadline. Use 2× the longest expected call duration from the Phase 2 descriptions. A scenario that exceeds its deadline is recorded as a timeout failure, not a pass.

**Config isolation** — every override must be fully reversed before the next batch. Trap SIGINT/SIGTERM to call `restore_config()` and `stop_bot()` so the script is safe to kill mid-run.

**Scenario ID mapping** — embed a static mapping of scenario name → Cekura scenario ID (recorded during 5b). Do not look up IDs dynamically at run time.

**Connection detail injection** — if the bot is outbound (bot calls Cekura), inject the Cekura connection details returned by the run trigger using the mechanism confirmed in 5d Q2. Document the injection point as a comment in the script.

---

## 5f. Verify end-to-end before committing the script

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
