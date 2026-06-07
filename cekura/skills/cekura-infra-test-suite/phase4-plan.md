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

If the user chose config-change included: for each required override, read Phase 2 Q12 (Local Run) to find the exact mechanism the bot uses to accept that configuration (env var export, `.env` file write, config file edit, CLI argument, API call to a running bot). Then document the override completely:

| Field | What to record |
|---|---|
| Config key | The exact env var name, config file key, or CLI flag (from Phase 2 Q12) |
| Injection mechanism | How to apply it: `export VAR=val`, write to `config/settings.yaml`, pass `--flag val` at startup, etc. |
| Test value | The value needed to trigger the behavior being tested |
| Restore value | The original value from Phase 2 (the value to restore after the batch) |
| Why it works | One sentence: why this value forces the tested behavior (e.g. "50ms is below any realistic LLM response time, guaranteeing the timeout fires") |
| Verification | How to confirm the override took effect before running the scenario (e.g. a startup log line, a config endpoint, or a known side effect) |
| TEST-NNN items covered | Which tests in this batch depend on this override |

**Do not guess the injection mechanism.** If Phase 2 Q12 says the bot reads from env vars, use `export`. If it reads from a `.env` file, write to that file. If it accepts a CLI flag, pass the flag. Using the wrong mechanism means the override silently has no effect and the bot runs with its default config — the test fires, appears to pass, and the failure mode was never actually exercised.

---

## 4c. Group tests into compact scenarios

The goal is the smallest number of Cekura scenarios that gives complete coverage of the included test items. A single scenario (one conversation) can test multiple things — a scenario that tests interruption can also verify pipeline recovery and the next-turn LLM response in the same call.

### Step 0 — Map test items to conversation arcs

**Do this before any other grouping.** A **conversation arc** is the complete realistic call flow that exercises a component from start to finish. One arc = one scenario. TEST-NNN items that are stages of the same arc belong in the same scenario — never split them.

Four arc patterns must always be recognised and collapsed:

**Pattern A — Full escalation arc**
If a component moves through N sequential stages (stage 1 → stage 2 → … → terminal action), all stage-level test items map to a **single scenario** that walks the full sequence. Never create one scenario per stage.

**Pattern B — Full input arc**
If a component accepts input in multiple forms (single item, multi-item sequence, sequence with a terminator, incomplete sequence that times out), all input-form test items map to a **single scenario** that exercises each form in turn within one call.

**Pattern C — Full state-gating arc**
If a component behaves differently depending on the current call state (accepted in state X, rejected in state Y, conditionally handled in state Z), all state-variant test items map to a **single scenario** that puts the call into each relevant state and verifies the behavior at each transition.

**Pattern D — Full error/recovery arc**
If a component has a failure path followed by retry and fallback logic, all items covering that failure path (trigger failure, observe retry, observe fallback) map to a **single scenario** that lets the full recovery sequence play out in one call.

**Before writing a new scenario for any TEST-NNN item, ask:** "Does this item belong to an arc I've already opened for this component?" If yes, add it to that arc's scenario. Only open a new scenario when the item genuinely cannot follow the previous arc's last step in the same call — because the success criteria conflict, the previous step ends the call, or a different bot configuration is required.

### Step 1 — Drop ambient tests first

Before grouping anything, identify TEST-NNN items that are **ambient** — behaviors that every scenario exercises as an unavoidable side effect of running. These do not need their own scenario. Creating a dedicated scenario for them wastes a slot and produces a test that tells you nothing a passing scenario from any other component wouldn't already tell you.

**A behavior is ambient if:** it must succeed for any other test to run at all, and its failure would cause every scenario in the suite to fail — not just one.

Common ambient behaviors and the rule for each:

| Behavior | Rule |
|---|---|
| Call connection / session establishment (happy path) | Ambient — every scenario connects. Drop the happy-path connection test; connection is implicitly exercised N times where N = number of scenarios. |
| Bot speaks first / opening message plays | Ambient — every scenario that starts with the bot speaking already exercises this. Drop a dedicated "bot greeting" scenario. |
| Basic STT — clean speech transcribed correctly | Ambient — every scenario where the caller says anything exercises basic STT. Drop a generic "STT works" scenario; keep STT tests that exercise specific conditions (noise, low confidence, empty transcript, fallback). |
| Basic LLM response — model returns a response | Ambient — every scenario that reaches the LLM exercises this. Drop a generic "LLM responds" scenario; keep LLM tests that exercise specific conditions (timeout, retry, empty response, tool call, concurrent turns). |
| Basic TTS — audio synthesised and played | Ambient — every scenario where the bot speaks exercises this. Drop a generic "TTS works" scenario; keep TTS tests that exercise specific conditions (streaming latency, mid-utterance error, fallback voice). |

**What to keep from these components:** only tests for non-default conditions — failure paths, edge cases, boundary values, fallback activation, and configuration-specific variants. The happy path of each layer is implicitly covered by every other scenario passing.

After dropping ambient items, mark them in the Phase 3 list as "covered implicitly — no dedicated scenario needed" and exclude them from the scenario count.

### Step 2 — Group the remaining tests

Group by two dimensions:

**1. Configuration context** — tests that share the same bot configuration run in the same batch. Tests that need different config changes form separate batches. Default-config tests are all one batch. This is the most important grouping because config changes require bot restarts.

**2. Conversation structure** — within a configuration batch, combine tests that naturally follow each other in a single call. A scenario might cover: normal turn → interruption → recovery → second turn → idle silence → escalation prompt. That is four TEST-NNN items in one scenario.

Rules for combining:
- Do not combine tests whose success criteria conflict (e.g. a test that expects the bot to hang up cannot be followed by another test in the same call)
- Do not combine tests that test the same component in contradictory configurations within the same call
- Do combine tests that are sequential stages of the same call (call setup → STT with noise → LLM response → interruption → idle silence)
- Do combine tests for adjacent pipeline layers when one flows naturally into the next (e.g. turn-end signal fires → LLM trigger fires → response streamed to TTS)

### Step 3 — Sanity-check the compactness

Apply the per-component caps below. If a component exceeds its cap, mandatory merge until it fits — exceeding the cap means Step 0 arc mapping was incomplete.

| Component | Max default-config scenarios |
|---|---|
| Any single side-channel (DTMF, SMS, voicemail, etc.) | 2 |
| Idle / silence timer | 2 |
| Interruption handling | 2 |
| STT | 3 |
| TTS | 2 |
| VAD / turn detection | 2 |
| LLM | 3 |
| Call transfer / hang-up | 2 |

Additional signs the plan is still too bloated:
- Any scenario covers only one TEST-NNN item and that item isn't a destructive endpoint (hang-up, transfer, call end) — it belongs in an adjacent arc
- Two scenarios have nearly identical conversation flows that differ by only one step — merge with a branch

For each group, write out which TEST-NNN items it covers and note any items marked ambient.

---

## 4d. Write the test plan

**Before writing any scenario entry, open `/tmp/infra-workflow-descriptions.md` and extract the exact values for that scenario's component.** Do not write a conversation flow or evaluation pointer from memory or inference — every numeric value, every phrase, and every behavior must come directly from Phase 2. This is the single most important rule in this phase: a plan grounded in Phase 2 produces aligned scenarios; a plan written from memory produces mismatches.

For each scenario, extract from Phase 2 before writing:
- The exact timing values (idle threshold in seconds, interruption offset, hold duration, timeout deadline)
- The exact phrases the bot says at each relevant stage (idle prompt text, closing phrase, fallback phrase, error message) — copy verbatim from Phase 2, do not paraphrase
- The exact behavior at each stage (how many retries, what fires on the Nth timeout, whether the bot speaks before hanging up)
- The exact configuration values that govern the behavior being tested (env var name, current value, what changing it to X would do)

For each planned scenario, write a plain-English entry. Phase 5 must be able to create a Cekura conditional_actions scenario from this description alone without going back to Phase 3.

Each entry must include:

**Scenario name** — short, descriptive, component-first (e.g. "LLM-Timeout-Fallback", "STT-Empty-Transcript-NoTranscriptTimer", "Idle-Full-Escalation-to-Hangup")

**Tests covered** — list the TEST-NNN IDs from Phase 3 this scenario exercises

**Configuration required** — either "Default — no changes" or a list of env vars / config keys to override and their test values. Every override must cite the Phase 2 source (file, line, current value) and have a restore value.

**Conversation flow** — step by step, using exact values from Phase 2, not placeholders. Every duration, digit sequence, phrase, and timing offset must be the real value, not `[idle threshold + 2s]` or `[the bot's greeting]`:
> 1. Wait silently — bot speaks first (Phase 2 Q10: opening message is "Hello, how can I help you today?")
> 2. Say: "I need to reschedule my appointment"
> 3. Wait for bot to respond
> 4. Interrupt the bot after 1s with: "Actually, cancel it"  ← 1s from Phase 2 Q6 interruption offset
> 5. Wait for bot to process interruption and respond
> 6. Hold for 10s  ← Phase 2 Q7: idle threshold is 8s, so 8+2=10s
> 7. Bot says: "Are you still there?"  ← Phase 2 Q7: exact idle prompt phrase
> 8. Hold for another 10s; bot says: "I'll wait a moment longer."  ← Phase 2 Q7: second escalation phrase
> 9. Hold for another 10s until bot hangs up  ← Phase 2 Q7: 3 prompts then hang-up

**Evaluation pointers** — grounded in Phase 2 actual behavior, not generic descriptions. Each pointer must reference the specific Phase 2 finding it is checking:
- Quote the actual phrase the bot should say (from Phase 2), not a paraphrase. "Bot says 'Are you still there?'" not "Bot prompts the caller."
- State the actual timing or count from Phase 2. "Idle prompt fires after 8s (Phase 2 Q7: IDLE_TIMEOUT=8)" not "Bot prompts after a period of silence."
- Call out the exact failure mode. "If no idle prompt appears in the transcript, or if it appears before 8s, the test fails."

---

## 4e. Assign language and personality to every scenario

Every scenario needs a language and a personality. Both are planning decisions — choose them here, before writing the scenario entries, so Phase 5 can create each scenario correctly without guessing.

### Step 1 — Distribute languages across the suite

Read the supported languages from Phase 2 Q11. Every fully-configured language must appear in at least one scenario. The distribution rule:

- **Primary language**: the majority of scenarios run in the primary language. All infra-behavior tests (interruption, idle timer, DTMF, STT fallback, LLM timeout, etc.) default to the primary language unless the test is specifically about language.
- **Each additional supported language**: gets at minimum one full pipeline E2E scenario and one STT accuracy scenario. If Phase 2 found language-specific component differences (different STT model, different TTS voice, different system prompt), each difference gets its own test scenario in that language.
- **Do not spread language tests across every scenario**: concentrate non-primary language coverage into dedicated scenarios. Mixing languages within a single scenario (unless testing mid-call switching) produces confusing transcripts that are hard to evaluate.

Record the language assignment for each scenario as a BCP-47 code (e.g. `en`, `es`, `fr`, `hi`).

### Step 2 — Choose a personality for each scenario

**Read `cekura/skills/cekura-eval-design/references/choosing-personality.md` before assigning any personality.** That file is the authoritative guide covering what personality controls, the core selection rule (sustained vs. temporary behaviors), the interruption quantification tiers, how to handle conditional-actions scenarios, the language-first selection order, enabled/disabled status checks, fallback logic, and the full decision tree. Do not guess or invent personality names — always list available personalities via `mcp__cekura__personalities_list` filtered by language before assigning.

The single most important rule for infra scenarios (from that reference): **conditional-actions scenarios strongly prefer Normal for the scenario's language.** Behavioral logic is encoded in `conditions[]`, not in personality. Use a non-Normal personality only when a call-wide, sustained trait is needed alongside the scripted conditions (e.g. persistent background noise, a specific accent throughout). Never pick an Interruptive personality just to simulate one interruption — encode it in a `conditions[]` entry instead.

If no personality exists for a supported non-primary language, note it as a gap — Phase 5 will need to create a custom personality or ask the user.

Record the chosen personality ID and the reason for each scenario.

### Step 3 — Add language and personality to the scenario entry

Each scenario entry in 4f must include:

**Language**: `[BCP-47 code]`
**Personality**: `[ID or name] — [one-line reason]`

---

## 4g. Handle the "not testable" items

The Phase 3 exclusion list contains items Phase 2 documented as outside testable scope (internal state, provider-level failures that can't be forced from the testing agent side). For each one, confirm it stays excluded and add a one-line note explaining why (e.g. "LLM retry count — internal state, not visible in transcript").

---

## 4h. Self-review the plan before writing the output

After drafting all scenarios in 4d and handling exclusions in 4e, stop and independently review the full plan before writing `/tmp/infra-test-plan.md`. Read it as if you had not written it. For each issue found, fix it in place before proceeding to output.

Check for the following categories of problem:

**Coverage gaps**
- Is every included TEST-NNN item from Phase 3 covered by at least one scenario? List any that are missing.
- Does every boundary condition in Phase 3 (threshold-at, threshold-below, threshold-above) have a corresponding scenario step that actually exercises that value? Or was the step written vaguely ("go silent for a while") when the value was known?

**Contradictions within a scenario**
- Does any scenario include steps that cannot coexist — e.g. the conversation flow expects the bot to hang up mid-call, but later steps assume the call is still active?
- Do the evaluation pointers contradict the conversation flow — e.g. a pointer says "bot should not interrupt" but the flow deliberately sends an `<interruption>` tag?
- Does the configuration for a scenario conflict with what that scenario is trying to test — e.g. a scenario testing the LLM timeout fallback but the config override is on the STT layer?

**Contradictions across scenarios**
- Do two scenarios claim to test the same TEST-NNN item but with conversation flows that would produce opposite results (one would pass, one would fail for the same behavior)?
- Do two scenarios in the same configuration batch apply contradictory config values?

**Grounding failures**
- Does any evaluation pointer reference a behavior that Phase 2 did not document — something invented rather than derived from the stack analysis?
- Does any conversation flow use a timing value (silence duration, interruption offset) that contradicts the actual threshold recorded in Phase 2?
- Does any scenario test a feature Phase 2 marked as absent?

**Configuration correctness**
- Does every config-change scenario have a restore value for every override? (Missing a restore means the next batch inherits a corrupted config.)
- Are the override values actually sufficient to trigger the behavior being tested — e.g. is `LLM_TIMEOUT_MS=50` low enough to reliably fire within a normal call, or should it be lower?

**Evaluation pointer quality**
- Are any evaluation pointers so vague they could pass regardless of what the bot does (e.g. "bot behaves correctly")? Rewrite them as specific observable signals.
- Are any pointers checking internal state that cannot appear in a transcript? Remove them.

**Compactness**
- Are there scenarios that could be safely merged without losing coverage or creating contradictions?
- Are there scenarios so long that a single failure mid-call would prevent all later steps from being reached, making the scenario effectively untestable as a unit? Consider splitting them.

Write a brief review note at the top of the output file listing issues found and how each was resolved. If no issues were found, write "Self-review: no issues found."

---

## Phase 4 Output

Write the complete test plan to `/tmp/infra-test-plan.md` using this structure:

```markdown
# Infra Test Plan

Source: /tmp/infra-test-list.md
Config-change tests: [included / excluded per user choice]
Self-review: [issues found and resolved, or "no issues found"]
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
**Language:** en
**Personality:** 693 (Normal Male) — neutral default; no voice challenge needed for this infra test

**Conversation flow:**
1. [step with exact value from Phase 2 — e.g. "Hold for 10s (Phase 2 Q7: IDLE_TIMEOUT=8s, +2s buffer)"]
2. [step]
...

**Evaluation pointers:**
- [Exact phrase or behavior from Phase 2 — e.g. "Bot says 'Are you still there?' (Phase 2 Q7: IDLE_PROMPT_1 exact text)"]
- [What the bot should NOT do — grounded in Phase 2]
- [Exact failure signal — what is missing or wrong in the transcript]
- [Sequencing constraint with actual values — e.g. "Prompt must appear within 1s of the 8s hold completing"]

---

### [SCENARIO-002] ...
```

End the file with:

```markdown
## Excluded Tests

### Covered implicitly — no dedicated scenario needed
- TEST-NNN — [name] — ambient: exercised by every scenario in the suite

### Config-change tests (excluded per user choice)
- TEST-NNN — [name] — would require [config change]; excluded because [reason]

### Not testable
- TEST-NNN — [name] — [why it can't be tested via Cekura]

## Summary

Total scenarios planned: N
Total TEST-NNN items covered by dedicated scenarios: N
Items covered implicitly (ambient): N
Items excluded: N ([M] config-change, [K] not testable)
Total TEST-NNN items accounted for: N / [total from Phase 3]
Configuration batches: N
```

---

## Phase 4 Gate

`/tmp/infra-test-plan.md` exists. Self-review (4h) has been completed and its findings recorded in the file header. Every included TEST-NNN item from Phase 3 maps to at least one scenario. Every scenario has a configuration context, a conversation flow, and plain-English evaluation pointers. No metric names or expected outcome text — those are Phase 5's job.

Confirm the plan with the user before moving to Phase 5. Present the summary block and ask whether any scenarios should be adjusted, merged, or split.

Move to [Phase 5 — Build and Run](phase5-build-run.md).
