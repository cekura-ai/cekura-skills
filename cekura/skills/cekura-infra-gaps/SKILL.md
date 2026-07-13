---
name: cekura-infra-gaps
description: >
  Use when the user asks to "find infra gaps", "create infra edge cases", "stress test my
  voice agent", "test packet loss / network jitter / latency", "test background noise",
  "test barge-in", "test long silences / idle timeouts", "test accents / slow speech",
  "red team my voice infrastructure", "find where my voice pipeline breaks", or "generate
  edge cases to improve my infra". Builds a compact catalog of adversarial infra stressors
  (degraded network, ambient noise, boundary silence, barge-in, accent/speed,
  DTMF-during-speech) that apply to ANY voice pipeline whether or not the code handles
  them, runs them, and turns failures into concrete infra fixes. Complement to
  cekura-infra-test-suite, which only tests behavior the codebase already implements.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

# Cekura Voice AI Infrastructure Gaps

Find the gaps in a voice agent's infrastructure: run a canonical catalog of adversarial conditions against it, see where it breaks, and turn each break into a concrete infra fix.

## Purpose

`cekura-infra-test-suite` reads the codebase and tests **only what is implemented** ("only test what's there"). That is correct for a CI/CD regression gate, but it has a blind spot: if the pipeline never implemented handling for background noise, packet loss, or a caller who goes silent at the wrong moment, that suite creates **zero** tests for those conditions, and the resilience gap stays invisible.

This skill fills that blind spot. It applies a **fixed catalog of adversarial infra stressors** that every real-world voice call can throw at a pipeline, regardless of whether the code was written to handle them. The point is not coverage of implemented logic. The point is to **discover where the infra breaks so it can be improved.**

| | cekura-infra-test-suite | cekura-infra-gaps (this skill) |
|---|---|---|
| Source of tests | The codebase (discover then test) | A fixed adversarial catalog (no codebase needed) |
| Philosophy | Only test what's there | Test what a real call throws at it, handled or not |
| Expected result | Should pass (it tests real logic) | Often fails at first, on purpose |
| Purpose | Regression gate | Drive infra hardening, then graduate to the gate |
| Suite size | Large (200+ items) | Compact (roughly 12–20 scenarios) |

**These edge cases are not a CI/CD gate on day one.** An agent that never handled 30% packet loss will fail that test, and wiring it straight into CI just produces red builds. Run this suite as a resilience probe, use the failures to improve the pipeline, and **graduate a family into the CI/CD regression suite only once the infra actually handles it.**

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

## Delegate Authoring to the Dedicated Skills

This skill is the **orchestrator**: it decides *which* stressors to probe and *how to read the results*. It does **not** hand-roll scenario or metric creation. Whenever it needs to generate an evaluator or a metric, load the dedicated Cekura skill first and thread that skill's verification tag on every write call:

- **Generating scenarios / evaluators** → load and follow **cekura-eval-design** (use `cekura_load_skill(skill_name="cekura-eval-design")` when the plugin is not installed). It owns the scenario schema, the conditional-action XML tags, personality selection, and expected-outcome patterns. Pass its `skill_ack` tag on every `scenarios_*` create/update.
- **Creating or modifying a metric** → load and follow **cekura-metric-design**, and pass its metric-family ack tag on every `metrics_*` write. Only needed when the built-in baseline metrics do not capture a gap (e.g. a custom "recovered vs. looped forever" check for a stressor). Never write a metric prompt ad-hoc.
- **Just reusing existing metrics** needs no metric skill; attach the baseline metric IDs (Step 3).

Skipping these dedicated skills produces materially worse evaluators and metrics. Route through them every time.

## The Core Insight: Stressors Live at the Voice Layer, Not in Instructions

Infra stressors are injected at the **voice/infrastructure layer**, never through scenario instructions. Instructions only control what the testing caller *says*; they cannot make the line noisy or the network drop packets. There are **two injection paths**, and you will usually mix them:

| Stressor family | Personality field | Conditional-action tag (no personality needed) |
|---|---|---|
| Degraded network (packet loss) | `network_simulation` | `<network_simulation packet_loss="N" />` |
| Background / ambient noise | `background_noise`, `background_sound_volume` | `<background_noise ...>` |
| Long silence / idle at boundaries | `message_plan` idle fields | `<hold time="Ns" />` (dead air) / `<silence time="Ns" />` |
| Aggressive barge-in / interruption | `interruption_level`, `start/stop_speaking_plan` | `<interruption time="Xs" />` (action_followup) |
| Accent / non-native speech | `accent`, `language` | (personality only) |
| Slow / fast speech | `speed` | `<speed ratio="0.8..1.2" />` |
| DTMF, rapid turns, overlap | (n/a) | `<dtmf digits="..." />`, scripted quick turns |

**Prefer selecting an existing enabled personality over creating one.** Two reasons: (1) `personalities_create` is frequently **403** for a scoped API session, so a create-first plan can hard-block; (2) most stressor traits (noise, accents, interruption tiers, slow speaker) already exist as global personalities you can enable on the project with `projects_enable_personalities_create`. For stressors that no available personality carries (packet loss, precise fast speech), author them as **conditional-action scenarios with the tag** on the Normal personality instead. Never let a create-permission block stop you from covering a family; the tag path always works.

The full catalog, with exact personality recipes, conditional-action tag recipes, and graded intensities, is in [references/stressor-catalog.md](references/stressor-catalog.md).

## Workflow

```
Phase 0          Step 1           Step 2           Step 3           Step 4           Step 5           Step 6
Scan code    →   Scope        →   Personalities →  Build        →   Verify       →   Run          →   Report
(optional)       target +         select/enable    scenarios in     retrieve each    live, as its     gaps quoted +
capability       families +       existing, or     the folder;      + patch every    own batch,       infra fix per
matrix           intensity        tag-carry it     metrics + ack    field vs plan    per-call cap     family + fixes
```

| Step | What happens | Hard gate |
|---|---|---|
| 0 (optional) | Scan the repo → capability matrix (which families will fail, and where the fix goes) | none; skipped when no repo |
| 1 | Retrieve the agent; auto-include all applicable families at auto-chosen intensity | **user approves the finished plan before anything is created** |
| 2 | Select/enable existing stressor personalities; fall back to tags | none |
| 3 | Create the scenarios in the `Infrastructure Gaps` folder, metrics attached, via cekura-eval-design | none |
| 4 | Retrieve every created scenario and patch mismatches | **0 unresolved before running** |
| 5 | Run the folder as its own batch on the matching connection | agent must be reachable/live |
| 6 | Read transcripts → per-family gap → infra fix → graduation status | none |

> **ANNOUNCE FIRST:** output `**Infra Gaps: starting**` before taking any action.

### Step 0 (optional): Pipeline Capability Scan, only when the repo is available

Skip this entirely for a hosted agent you can only reach through Cekura (no source). When you *do* have the codebase, a quick scan of the pipeline pays for itself: it tells you which families will likely fail and where the fix goes, before spending a single call credit.

Scan for the resilience mechanism behind each family (jitter buffer / STT reconnect, STT confidence gating, idle / no-transcript timer, interruption cancellation, endpointing adaptivity, turn serialization) and record each as yes / partial / no with a file:line. Produce a capability matrix.

**This scan never removes a family from the suite.** "No handling for X" means probe X *hardest* and you already know the fix location; it does not mean skip X. Using absence-of-handling to skip a test is the exact `infra-test-suite` blind spot this skill exists to avoid.

Full method, grep signals, matrix format, and a worked example are in [references/capability-scan.md](references/capability-scan.md). Feed the matrix into Step 1 (intensity) and Step 6 (grounded fixes).

### Step 1: Identify the target and pick stressor families

1. Confirm the target **agent** and **project**. If unknown, ask the user directly; do not guess.
2. `aiagents_retrieve` the agent to read its run connection (VAPI / Retell / ElevenLabs / SIP / web) and language. The connection determines which `scenarios_run_*` tool Step 5 uses; the language determines the personality language.
3. **Include every family applicable to the agent by default; do not make the user hand-pick the list.** Determine applicability automatically from the agent's connection (from step 2):
   - **Telephony / SIP / phone** → all families, including degraded network and DTMF-during-speech.
   - **Web widget / WebRTC / chat** → all families *except* network degradation and DTMF-during-speech (there is no PSTN layer to degrade or key into).
   Boundary silence, background noise, barge-in, accent, and speech-rate apply to essentially every voice agent, so they are always in.
4. **Choose intensity automatically; do not ask per family.** Default: light + severe for each graded family (network, noise), a single level for the rest (~12–20 scenarios). If Step 0 ran, let the capability matrix tune it: families whose resilience mechanism is **absent** (predicted to fail) get the fuller light / moderate / severe ladder to locate the failure cliff; families whose mechanism is **present** get a single severe level (a pass there confirms it holds). The user sees a finished plan, not an intensity questionnaire.
5. Present the finished plan once: all applicable families, the auto-chosen intensities, and the resulting scenario count, as **one approve-or-trim checkpoint**. Do not create anything until the user approves. The default is comprehensive, not minimal; they subtract only if they want less.

### Step 2: Select (or create) the adversarial personalities

**Select existing enabled personalities first.** `personalities_list` (filtered by the agent's language), find the global ones that already carry each trait (noise, accent, interruption tier, slow speaker), and enable them on the project with `projects_enable_personalities_create`. This avoids the common `personalities_create` **403** and reuses curated voices.

Only fall back to `personalities_create` when no existing personality carries the trait. If create is available, first inspect one existing personality to copy the exact JSON shape of `network_simulation` / `background_sound_volume` rather than inventing it. If create is **403**, do not stop: cover that family via a conditional-action tag instead (Step 3).

Keep every selected/created personality's caller `prompt` neutral and cooperative: the caller just wants to complete a normal task, so the *only* variable under test is the infra stressor.

### Step 3: Create the scenarios

1. Create a folder named **`Infrastructure Gaps`** with `scenarios_folder_create`. Every scenario in this suite goes in it. Never mix these into the `Infrastructure Test Suite` folder; they have a different pass expectation and must not pollute the regression gate.
2. Two authoring paths (see the injection table above):
   - **Personality-carried (behavioral):** for traits an enabled personality provides (noise, accent, barge-in tier, slow speaker); a `scenario_type: "instruction"` scenario with the simple task, the adversarial personality attached, and `TOOL_END_CALL` so the caller can hang up.
   - **Tag-carried (conditional-actions):** for stressors no personality provides or that need exact timing (packet loss, fast speech, boundary silence, rapid turns); a `scenario_type: "conditional_actions"` scenario on the Normal personality, with the tag at the start of each `fixed_message: true` action.
3. Every scenario runs the same **simple, universal task** the agent genuinely supports (e.g. "book the earliest available slot"), so the only variable is the stressor. Write the expected outcome as **graceful degradation** (see below), not task perfection.
4. **Attach baseline metrics to every scenario**: Expected Outcome, Infrastructure Issues (fires on agent silence; key here), Tool Call Success, Latency, plus Transcription Accuracy for noise/accent/network and the interruption metrics for barge-in. **Predefined metrics must be activated at the project level before they fire** (a global metric ID attached to a scenario is stored but never evaluated). Use **cekura-predefined-metrics** to activate/verify. If the built-ins miss a gap, author a custom metric via **cekura-metric-design** (see Delegation); do not hand-roll it here.
5. Author every scenario through the **cekura-eval-design** skill (load it first; thread its `skill_ack`). It owns the scenario schema, conditional-action tags, and expected-outcome patterns; this skill only supplies the stressor and the task.
6. **Create scenarios in parallel** (fire the create calls concurrently); there is no dependency between them.

### Step 4: Verify the built suite before running

Mirror of the regression skill's cross-verify pass. After creating, `scenarios_retrieve` **every** scenario and confirm each field, patching any mismatch immediately with `scenarios_partial_update`. Skipping this produces silent failures: a metric that never fires, a stressor tag stored as literal text, a scenario in the wrong folder.

Check per scenario:
- **Personality** is the intended adversarial one (not silently defaulted to Normal where a trait was meant to be carried).
- **Metrics** are attached **and active at project level** (attached-but-inactive = never fires).
- **Folder** is `Infrastructure Gaps` (not root, not the regression folder).
- **Tag-carried scenarios:** the `<network_simulation>` / `<speed>` / `<hold>` tag is actually present at the start of each `fixed_message: true` action; the API will store a malformed tag as plain spoken text, silently neutering the stressor.
- **`expected_outcome_prompt`** is set and phrased as graceful degradation, not blank or generic.
- **`TOOL_END_CALL`** present on personality-carried scenarios (absent = the caller can never hang up, so the call runs to timeout); deliberately absent on silence-at-end, which instead sets a `max_duration` cap.

Do not run until this pass reports 0 unresolved mismatches.

### Step 5: Run the suite

1. **Readiness first.** The agent must be reachable on its run connection; for a telephony agent the bot must be live on its number, or every call fails at *connection* and the results say nothing about resilience. Confirm before spending credits.
2. Run the `Infrastructure Gaps` folder **as its own batch** using the `scenarios_run_*` tool matching the connection from Step 1, separate from any regression run so a wall of expected failures is not read as a regression.
3. Give any silence- or hang-prone scenario a `max_duration` cap so a non-terminating call is recorded as a timeout, not left running on the meter.

### Step 6: Produce the improvement report

This is the deliverable. Read the runs (do not label failures from status alone; read the transcripts), group them by stressor family, and for each family write:

- **What broke**, quoted from the transcript (looping the greeting, permanent silence, garbled task completion, premature hang-up, ignoring the caller entirely).
- **The concrete infra fix**, at the pipeline layer, not the prompt (STT confidence gating, a "having trouble hearing you" fallback after N low-confidence turns, an idle re-prompt ladder, jitter buffering, endpointing tuning). When Step 0 ran, cite the file:line from the capability matrix. See [references/improvement-loop.md](references/improvement-loop.md) for the failure-to-fix mapping.
- **CI/CD graduation status**: does this family now pass and belong in the regression gate, or does it stay in this probe suite until the fix lands?

Present it as a per-family table. That table is what "used to improve the infra" means in practice.

## Ground Rules

1. **Catalog first, codebase second.** These stressors apply whether or not the code handles them. Do not skip a family because "the code doesn't do that"; that omission is exactly the gap this skill exists to expose. (This is the deliberate inverse of infra-test-suite Rule 2.)
2. **One variable under test.** Each scenario isolates a single stressor (or a single named real-world combination like "mobile call = noise + packet loss"). Do not stack unrelated stressors, or a failure becomes unattributable.
3. **The stressor lives at the voice layer, never in instructions.** Encode it via a personality field or a conditional-action tag (`<network_simulation>`, `<speed>`, `<hold>`, `<background_noise>`). Instruction phrasing like "speak with background noise" is ignored by the voice layer. Prefer selecting an enabled personality; use the tag path when create is 403 or no personality carries the trait.
4. **Grade the tunable families.** For network and noise, test at least a light and a severe level. An agent may survive 10% packet loss and collapse at 40%; a single level hides the cliff.
5. **Evaluate resilience, not perfection.** Pass = graceful degradation (recovers, re-prompts, stays coherent, or ends cleanly). Fail = pathological behavior (infinite loop, permanent silence, hallucinated completion, crash). A pass does not require flawless task completion under severe stress.
6. **Keep it out of the CI/CD gate until it passes.** These scenarios are expected to fail at first. Graduate a family into the regression suite (the `Infrastructure Test Suite` folder / CI gate) only after the infra handles it.
7. **Decide scope, then confirm once.** Auto-include every family the agent's connection supports and auto-choose intensity (do not make the user assemble the family list or answer per-family intensity questions). Present the one finished plan as a single approve-or-trim checkpoint; do not create personalities or scenarios until the user approves.
8. **Verify before running.** After creating, retrieve every scenario and patch mismatches (Step 4). A metric that never fires or a stressor tag stored as plain text fails silently and wastes the whole run.

## Common Pitfalls

- **Putting the stressor in instructions.** "Speak with lots of background noise" in instructions does nothing. It must be a personality field or a conditional-action tag.
- **Skipping the verify pass.** A metric attached but not project-activated, or a stressor tag the API stored as literal text, fails silently; Step 4 catches both.
- **Inventing the `network_simulation` / `background_sound_volume` JSON shape.** Copy it from a real personality via `personalities_list` first.
- **Mixing edge cases into the regression folder.** They have opposite pass expectations. Keep them in `Infrastructure Gaps`.
- **Marking failures from run status alone.** Read the transcript to see *how* it broke; that is what determines the infra fix. (See the "verify before labeling failures" discipline.)
- **Grading task success instead of resilience.** An agent that says "I'm having trouble hearing you, could you repeat that?" under 50% packet loss is passing, even if it never books the appointment.
- **Turning it into a 200-item suite.** This is a focused resilience probe, not the exhaustive coverage suite. Keep it compact.

## Next Steps

After running this skill, the user typically wants:
- **cekura-self-improving-agent**; if a failure is actually fixable in the prompt or tool config rather than the pipeline.
- **cekura-infra-test-suite**; to graduate a now-handled stressor family into the codebase-derived regression gate.
- **cekura-eval-design**; to author additional edge-case variants by hand.
- **cekura-metric-design**; to build a custom resilience metric when the built-ins do not capture a gap.
