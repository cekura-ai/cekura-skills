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
2. Set up test profiles, mock tool data, and dynamic variables (see subsection below — do this before building any payload)
3. Build the complete payload for every scenario upfront (conditional_actions, language, personality, folder_path, name, expected_outcome, metrics, test_profile)
4. Fire all `mcp__cekura__scenarios_create` calls at the same time
5. Collect all returned IDs and record the scenario name → ID mapping once all calls complete
6. If any individual creation fails, log the failure and retry that scenario only — do not retry the entire batch

### Set up test profiles, mock tool data, and dynamic variables

**Read `cekura/skills/cekura-eval-design/references/test-data-design.md` in full before configuring any of these.** That file is the authoritative guide for designing mock tools, test profiles, and dynamic variables as a cohesive trio. Do not design them independently — inconsistencies between them cause silent test failures.

**Step 1 — Determine what data the bot needs (from Phase 2):**
- **Q4 (LLM tools)**: does the bot define and call external tools? If yes, mock tool data may be needed. List the tools, their input fields, and what outputs they return.
- **Q1 (Call Connection) and Q4**: does the bot read dynamic variables at call start (caller ID, account context, inbound number)? List all registered variables via `GET /test_framework/v1/aiagents/{agent_id}/dynamic-variables/` and read each variable's description for expected format.
- **Q1 session metadata**: what caller context does the bot expect to be present (phone number, caller name, account ID)?

**Step 2 — Choose an approach (per test-data-design.md):**
- **Approach C (most infra scenarios)**: the scenario tests pipeline behavior (idle timer, interruption, VAD, LLM timeout, STT), not a business-logic workflow. The bot's tools are not exercised. A minimal test profile with caller identity is sufficient.
- **Approach B**: the bot's tools are exercised during the scenario (e.g. a tool call is part of the LLM response being tested). Mock tool entries must be configured — follow the full Approach B workflow in test-data-design.md.
- **Approach A**: the bot hits a real staging backend. Align test profile fields with the staging data formats.

**Step 3 — Generate the data trio together:**
Design test profile + mock tool entries + dynamic variable values as one synchronized unit. The same fact (e.g. caller phone number) must be an identical string across all three. Never design them independently.

**Four rules that must be followed (from the reference):**
- **Template variables only** — every data value used in scenario instructions must come from `{{test_profile.field_name}}`, never hardcoded inline
- **Append-not-replace** — when adding mock tool entries, always GET the existing `information` array → merge → PATCH the full combined array; PATCHing with new entries only wipes existing mappings
- **No partial profiles** — never assign a profile that is missing a field the scenario needs; the testing agent will improvise the missing value silently, breaking verification flows
- **Consistency** — the same fact must be the identical string in the test profile, the dynamic variable value, and the mock tool input; the only deliberate exception is the validation-failure pattern

### Register configurable parameters as Cekura dynamic variables

Before building any scenario payload, register every parameter identified in Phase 4 4a as a Cekura dynamic variable on the agent. Follow `cekura/skills/cekura-create-agent/phase8-dynamic-variables.md` for the registration workflow, naming conventions, and how to write detailed descriptions.

For each parameter from the Phase 4 plan:
1. Register it as a dynamic variable via `POST /test_framework/v1/aiagents/{agent_id}/dynamic-variables/` with a detailed description (data type, valid range, how the bot uses it, what happens if missing, realistic example value)
2. When building each scenario's payload, set the `dynamic_variables` field with the specific values for that scenario — use the test-specific values from the Phase 4 "Dynamic variable values" field
3. Scenarios that use only baseline values may omit the `dynamic_variables` field or set the defaults explicitly

This replaces any need for bot-side configuration changes. Cekura passes these values to the bot at connection time; the bot reads them and configures itself for that call.

For authoring each scenario's payload, invoke the **cekura-eval-design** skill.

**All scenarios must use `scenario_type: "conditional_actions"`** — always, without exception. Behavioral instructions are not deterministic enough to reliably trigger specific infra behaviors like idle timers, interruptions, or DTMF input. Never use behavioral mode for this suite.

**Use the exact scenario name from the Phase 4 plan — no indexes, no prefixes.** Do not add "Scenario 1:", "Test 3:", or any numeric prefix to the name. The name field must be the descriptive, component-first name written in Phase 4 (e.g. `"Idle-Full-Escalation-to-Hangup"`, `"STT-Empty-Transcript-NoTranscriptTimer"`). Indexes belong in the TEST-NNN tracking system, not in the scenario name visible on Cekura.

### Set language and personality on every scenario — mandatory before creation

Before creating each scenario, read its **Language** and **Personality** fields from the Phase 4 plan. Both are required — the API returns 400 without a personality, and `scenario_language` is required for `conditional_actions` scenarios.

If personality was not assigned in Phase 4, or you need to verify the choice is correct: read `cekura/skills/cekura-eval-design/references/choosing-personality.md` and follow its decision tree. Key rules for infra scenarios: strongly prefer Normal for the scenario's language; only deviate for a call-wide sustained trait (persistent noise, specific accent). Always verify the personality is enabled for the project via `mcp__cekura__personalities_list` before using it.

**`scenario_language`** — set to the BCP-47 code from the Phase 4 plan (`"en"`, `"es"`, `"hi"`, etc.). Never omit this field. Never leave it as `"en"` for a non-English scenario.

**`personality`** — use the ID from the Phase 4 plan. If Phase 4 flagged a gap (no personality available for a non-primary language), call `mcp__cekura__personalities_list` filtered by that language code to check whether one exists. If still unavailable, pause and ask the user: create a custom personality, or defer that language's scenarios?

Do not reuse the primary-language personality on non-primary-language scenarios — a mismatched personality produces incorrect TTS pronunciation and invalidates STT accuracy tests for that language.

### Translating the Phase 4 plan into conditional_actions

Read `cekura/skills/cekura-eval-design/references/conditional-actions.md` before writing any condition. That file is the authoritative source for the full conditions array structure, every field's semantics (`id`, `type`, `condition`, `action`, `fixed_message`), when to use `action_followup` vs `standard`, XML tag syntax and placement constraints, the validation checklist, and the anti-patterns list.

One infra-specific rule not in that reference: **use `<hold>` (not `<silence>`) for idle timer tests**. `<hold>` produces dead air; `<silence>` keeps background noise running and may register as caller activity on sensitive VAD configurations, preventing the idle timer from firing.

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

The script starts the bot once and runs all scenarios sequentially per connection type. Per-scenario configuration variations are handled by the Cekura dynamic variables set on each evaluator — there is no need to restart the bot or change its environment between scenarios.

Write the script as `infra_test_run.sh` (or `.py` if the bot's ecosystem is Python-first — match the language to what the team already uses for CI).

### Script structure

```bash
#!/usr/bin/env bash
set -euo pipefail

# ── Scenario ID map (from 5b, verified in 5c) ────────────────────────────────
declare -A SCENARIO_IDS=(
    ["Idle-Full-Escalation-to-Hangup"]="<id>"
    ["STT-Empty-Transcript-NoTranscriptTimer"]="<id>"
    ["LLM-Timeout-Fallback"]="<id>"
    # ...
)

# ── Helpers ──────────────────────────────────────────────────────────────────
start_bot() {
    # Exact start command from 5d deployment steps
    <start command here> &
    BOT_PID=$!
    # Wait for exact readiness signal from Phase 2 Q12
    wait_for_log "<readiness signal>" 30 || { echo "Bot failed to start"; exit 1; }
}
stop_bot() { kill "$BOT_PID" 2>/dev/null; wait "$BOT_PID" 2>/dev/null; }
trap 'stop_bot' SIGINT SIGTERM

run_scenario() {
    local name=$1 transport=$2
    local id="${SCENARIO_IDS[$name]}"
    # Trigger via appropriate Cekura runner for this transport
    # Cekura passes each scenario's dynamic variable values to the bot at connection time
    # Poll until completed or 2× max call duration timeout
    # Return pass/fail based on evaluation_status
}

# ── Connection type loop ──────────────────────────────────────────────────────
for TRANSPORT in websocket sip; do   # ← transports selected in Phase 1
  echo "=== Transport: $TRANSPORT ==="
  start_bot
  for scenario_name in "${!SCENARIO_IDS[@]}"; do
      run_scenario "$scenario_name" "$TRANSPORT"
  done
  stop_bot
done

# ── Results ──────────────────────────────────────────────────────────────────
print_summary   # pass/fail per scenario per transport, total pass rate
```

### Key implementation requirements

**Default bot configuration** — the bot must start with its normal default configuration. Per-scenario variations are handled by the Cekura dynamic variables set on each evaluator; the script does not need to manage any configuration state.

**Deployment steps verbatim** — embed the exact start/stop commands and env vars confirmed in 5d as executable lines (not comments). Label each block clearly so the user can edit them later.

**Readiness gating** — use the exact readiness signal confirmed in 5d (log line, health endpoint, port). Do not use a fixed `sleep`.

**Per-scenario timeout** — each `run_scenario` call must have a deadline. Use 2× the longest expected call duration from the Phase 2 descriptions. A scenario that exceeds its deadline is recorded as a timeout failure, not a pass.

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
