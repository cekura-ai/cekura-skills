# Phase 4 — Design the Test Plan

Read `/tmp/infra-test-list.md` (written by Phase 3) before doing anything else. That is the authoritative list of everything that needs testing. This phase turns that list into a concrete, compact test plan written in plain English. No Cekura scenarios are created here — that is Phase 5.

---

## 4a. Ask the user one question before planning anything

Some test items from Phase 3 require temporarily changing the bot's configuration to create the condition being tested — for example, reducing `LLM_TIMEOUT_MS` to 50ms to reliably trigger the timeout path, or setting a mock STT endpoint to return empty transcripts. Other items can be exercised with the bot running at its default configuration.

Ask the user:

> "Some tests require temporarily changing the bot's configuration to force a specific failure path (for example, reducing the LLM timeout to trigger the timeout handler, or setting the STT confidence threshold to 1.0 to force empty transcripts). Should I include these config-change tests in the plan, or only tests that run against the bot's default configuration?
>
> - **Default-only**: the test suite runs entirely against the bot's normal config. Simulated failure paths are excluded. Faster to set up, but some failure-handling code will not be exercised.
> - **Config-change included**: the script temporarily applies env var or config overrides per test group, then restores defaults. Full coverage, but requires that each override is safe to apply in a local/CI environment."

Wait for the user's answer before proceeding. Record the choice — it determines which TEST-NNN items from Phase 3 are included in the plan.

---

## 4b. Decide which tests require config changes

Go through the TEST-NNN list from `/tmp/infra-test-list.md`. For each item, classify it:

**Default-config test** — the behavior can be triggered by what the testing agent says or does (speaking, staying silent, interrupting, sending DTMF) without any change to the bot's configuration.

**Config-change test** — the behavior can only be triggered reliably by temporarily changing a bot configuration value. Examples:
- Reducing a timeout value so it fires within a short test call
- Setting a threshold (confidence, word count) to an extreme value to force a specific branch
- Pointing the bot at a mock provider endpoint that returns an error or empty result
- Disabling a fallback to test the primary's failure behavior in isolation

If the user chose default-only: mark all config-change tests as **excluded** and note why. They will appear in the plan's exclusion list but will not be built.

If the user chose config-change included: list each required config override clearly — the env var name, the test value, and which TEST-NNN items it covers.

---

## 4c. Group tests into compact scenarios

The goal is the smallest number of Cekura scenarios that gives complete coverage of the included test items. A single scenario (one conversation) can test multiple things — a scenario that tests interruption can also verify pipeline recovery and the next-turn LLM response in the same call.

Group by two dimensions:

**1. Configuration context** — tests that share the same bot configuration run in the same batch. Tests that need different config changes form separate batches. Default-config tests are all one batch. This is the most important grouping because config changes require bot restarts.

**2. Conversation structure** — within a configuration batch, combine tests that naturally follow each other in a single call. A scenario might cover: normal turn → interruption → recovery → second turn → idle silence → escalation prompt. That is four TEST-NNN items in one scenario.

Rules for combining:
- Do not combine tests whose success criteria conflict (e.g. a test that expects the bot to hang up cannot be followed by another test in the same call)
- Do not combine tests that test the same component in contradictory configurations within the same call
- Do combine tests that are sequential stages of the same call (call setup → STT → LLM → TTS → interruption → recovery)

For each group, write out which TEST-NNN items it covers.

---

## 4d. Write the test plan

For each planned scenario, write a plain-English entry. Be specific — Phase 5 must be able to create a Cekura conditional_actions scenario from this description alone without going back to Phase 3.

Each entry must include:

**Scenario name** — short, descriptive, component-first (e.g. "LLM-Timeout-Fallback", "STT-Empty-Transcript-NoTranscriptTimer", "Idle-Full-Escalation-to-Hangup")

**Tests covered** — list the TEST-NNN IDs from Phase 3 this scenario exercises

**Configuration required** — either "Default — no changes" or a list of env vars / config keys to override and their test values. Every override must have a restore value (the original value from Phase 2 descriptions).

**Conversation flow** — step by step, in plain English, what the testing agent does:
> 1. Wait silently for bot greeting (bot speaks first)
> 2. Say: "I need to reschedule my appointment"
> 3. Wait for bot to respond
> 4. Interrupt the bot after 1 second with: "Actually, cancel it"
> 5. Wait for bot to process the interruption and respond
> 6. Go silent for [idle threshold + 2s] to trigger idle prompt
> 7. Stay silent through two escalation prompts
> 8. Stay silent until hang-up fires

**Evaluation criteria**:
- **Predefined metrics to attach**: list each metric by name (use the cekura-predefined-metrics skill to look up which metrics apply). For each metric, note what it is measuring in this scenario.
- **Expected outcome**: one or two sentences describing what a passing call looks like — what the bot should do, say, or not say. Keep this to observable call behavior, not internal state.
- **Failure signal**: what a failing result looks like — bot does the wrong thing, says the wrong thing, or the call ends in an unexpected way.

---

## 4e. Handle the "not testable" items

The Phase 3 exclusion list contains items Phase 2 documented as outside testable scope (internal state, provider-level failures that can't be forced from the testing agent side). For each one, confirm it stays excluded and add a one-line note explaining why (e.g. "LLM retry count — internal state, not visible in transcript").

---

## Phase 4 Output

Write the complete test plan to `/tmp/infra-test-plan.md` using this structure:

```markdown
# Infra Test Plan

Source: /tmp/infra-test-list.md
Config-change tests: [included / excluded per user choice]
Read by Phase 5 before creating any scenarios.

---

## Configuration Batches

### Batch A — Default configuration
Scenarios: [list scenario names]

### Batch B — [Config override description, e.g. "LLM_TIMEOUT_MS=50"]
Scenarios: [list scenario names]
Override: LLM_TIMEOUT_MS=50 (restore to [original value] after batch)

---

## Scenarios

### [SCENARIO-001] Scenario Name

**Tests covered:** TEST-004, TEST-007, TEST-012
**Configuration:** Default — no changes

**Conversation flow:**
1. [step]
2. [step]
...

**Evaluation criteria:**
- Metrics: [metric name] — [what it measures here]; [metric name] — [what it measures here]
- Expected outcome: [plain English description of a passing call]
- Failure signal: [what a failing call looks like]

---

### [SCENARIO-002] ...
```

End the file with:

```markdown
## Excluded Tests

### Config-change tests (excluded per user choice)
- TEST-NNN — [name] — would require [config change]; excluded because [reason]

### Not testable
- TEST-NNN — [name] — [why it can't be tested via Cekura]

## Summary

Total scenarios planned: N
Total TEST-NNN items covered: N / [total from Phase 3]
Items excluded: N ([M] config-change, [K] not testable)
Configuration batches: N
```

---

## Phase 4 Gate

`/tmp/infra-test-plan.md` exists. Every included TEST-NNN item from Phase 3 maps to at least one scenario. Every scenario has a configuration context, a conversation flow, and evaluation criteria.

Confirm the plan with the user before moving to Phase 5. Present the summary block and ask whether any scenarios should be adjusted, merged, or split.

Move to [Phase 5 — Build and Run](phase5-build-run.md).
