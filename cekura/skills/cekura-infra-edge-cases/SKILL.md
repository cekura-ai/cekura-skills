---
name: cekura-infra-edge-cases
description: >
  Use when the user asks to "create infra edge cases", "stress test my voice agent",
  "test packet loss / network jitter / latency", "test background noise", "test barge-in",
  "test long silences / idle timeouts", "test accents / slow speech", "red team my voice
  infrastructure", "find where my voice pipeline breaks", or "generate edge cases to
  improve my infra". Builds a compact catalog of adversarial infra stressors (degraded
  network, ambient noise, boundary silence, barge-in, accent/speed, DTMF-during-speech)
  that apply to ANY voice pipeline whether or not the code handles them, runs them, and
  turns failures into concrete infra fixes. Complement to cekura-infra-test-suite, which
  only tests behavior the codebase already implements.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

# Cekura Voice AI Infrastructure Edge Cases

Generate a canonical catalog of adversarial infrastructure conditions, run them against the agent, and turn the failures into concrete infra fixes.

## Purpose

`cekura-infra-test-suite` reads the codebase and tests **only what is implemented** ("only test what's there"). That is correct for a CI/CD regression gate, but it has a blind spot: if the pipeline never implemented handling for background noise, packet loss, or a caller who goes silent at the wrong moment, that suite creates **zero** tests for those conditions, and the resilience gap stays invisible.

This skill fills that blind spot. It applies a **fixed catalog of adversarial infra stressors** that every real-world voice call can throw at a pipeline, regardless of whether the code was written to handle them. The point is not coverage of implemented logic. The point is to **discover where the infra breaks so it can be improved.**

| | cekura-infra-test-suite | cekura-infra-edge-cases (this skill) |
|---|---|---|
| Source of tests | The codebase (discover then test) | A fixed adversarial catalog (no codebase needed) |
| Philosophy | Only test what's there | Test what a real call throws at it, handled or not |
| Expected result | Should pass (it tests real logic) | Often fails at first, on purpose |
| Purpose | Regression gate | Drive infra hardening, then graduate to the gate |
| Suite size | Large (200+ items) | Compact (roughly 12–20 scenarios) |

**These edge cases are not a CI/CD gate on day one.** An agent that never handled 30% packet loss will fail that test, and wiring it straight into CI just produces red builds. Run this suite as a resilience probe, use the failures to improve the pipeline, and **graduate a family into the CI/CD regression suite only once the infra actually handles it.**

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

## The Core Insight: Stressors Live in the Personality

Infra stressors are injected at the **voice/infrastructure layer**, which on Cekura is the caller **personality**, not the scenario instructions. Instructions only control what the testing caller *says*; they cannot make the line noisy or the network drop packets. A personality created via `personalities_create` exposes exactly the adversarial knobs this catalog needs:

| Stressor family | Personality field(s) |
|---|---|
| Degraded network (packet loss, jitter, latency) | `network_simulation` |
| Background / ambient noise | `background_noise`, `background_sound_volume` |
| Long silence / idle at boundaries | `message_plan` (`idle_timeout_seconds`, `idle_message_max_spoken_count`) + instructions |
| Aggressive barge-in / interruption | `interruption_level`, `start_speaking_plan`, `stop_speaking_plan` |
| Accent / non-native / slow-or-fast speech | `accent`, `speed`, `language` |
| DTMF during speech, rapid turns, overlap | scenario instructions / conditional actions |

The workflow therefore **creates a small set of adversarial personalities** (one per stressor and intensity), then attaches each to a lightweight scenario whose only job is a simple task the agent must still complete despite the stressor.

The full catalog, with exact personality recipes and graded intensities, is in [references/stressor-catalog.md](references/stressor-catalog.md).

## Workflow

> **ANNOUNCE FIRST:** output `**Infra Edge Cases: starting**` before taking any action.

### Step 1: Identify the target and pick stressor families

1. Confirm the target **agent** and **project**. If unknown, ask the user directly; do not guess.
2. `aiagents_retrieve` the agent to read its run connection (VAPI / Retell / ElevenLabs / SIP / web) and language. The connection determines which `scenarios_run_*` tool Step 4 uses; the language determines the personality language.
3. Present the stressor catalog (families in the table above) and confirm scope. Two knobs to agree on:
   - **Which families apply.** Network degradation and DTMF-during-speech are only meaningful for telephony/SIP agents; a web-widget agent skips them. Noise, boundary silence, barge-in, and accent apply to essentially every voice agent.
   - **Intensity coverage.** For the graded families (network, noise) decide whether to test one severe level or the light/moderate/severe ladder. Default: light + severe per graded family, single level for the rest. That lands around 12–20 scenarios.

Do not proceed to create anything until the user confirms the family + intensity selection. Getting this wrong wastes simulation credits.

### Step 2: Create the adversarial personalities

Before creating, **`personalities_list` (filtered by the agent's language) and inspect one existing personality** to copy the exact JSON shape of `network_simulation` and `background_sound_volume`. These are provider-specific nested configs; copy a real one rather than inventing the structure.

Then `personalities_create` one personality per selected stressor/intensity, following the recipes in [references/stressor-catalog.md](references/stressor-catalog.md). Name them so the stressor is obvious in results, e.g. `Edge - Packet Loss 50%`, `Edge - Cafe Noise Loud`, `Edge - Barge-in High`. Keep the caller `prompt` neutral and cooperative: the caller is trying to complete a normal task, and the *only* variable under test is the infra stressor.

### Step 3: Create the edge-case scenarios

1. Create a folder named **`Infrastructure Edge Cases`** with `scenarios_folder_create`. Every scenario in this suite goes in it. Never mix these into the `Infrastructure Test Suite` folder; they have a different pass expectation and must not pollute the regression gate.
2. For each personality, create one scenario:
   - A **simple, universal task** the agent must complete regardless of stressor (e.g. "ask for business hours and confirm you heard them", "book the earliest available slot"). Pick a task the agent genuinely supports, from its description.
   - Attach the adversarial personality.
   - Write the expected outcome as **graceful degradation** (see next section), not task perfection.
3. Author scenarios with the **cekura-eval-design** skill; it owns the scenario schema, personality attachment, and expected-outcome patterns. Boundary-silence and DTMF-timing cases use `conditional_actions`; the rest are behavioral scenarios carried by the personality.

### Step 4: Run the suite

Run every scenario using the `scenarios_run_*` tool that matches the agent's connection from Step 1. Run the edge-case folder as its own batch, separate from any regression run, so a wall of expected failures does not get read as a regression.

### Step 5: Produce the improvement report

This is the deliverable. Read the runs (do not label failures from status alone; read the transcripts), group them by stressor family, and for each family write:

- **What broke**, quoted from the transcript (looping the greeting, permanent silence, garbled task completion, premature hang-up, ignoring the caller entirely).
- **The concrete infra fix**, at the pipeline layer, not the prompt (STT confidence gating, a "having trouble hearing you" fallback after N low-confidence turns, an idle re-prompt ladder, jitter buffering, endpointing tuning). See [references/improvement-loop.md](references/improvement-loop.md) for the failure-to-fix mapping.
- **CI/CD graduation status**: does this family now pass and belong in the regression gate, or does it stay in this probe suite until the fix lands?

Present it as a per-family table. That table is what "used to improve the infra" means in practice.

## Ground Rules

1. **Catalog first, codebase second.** These stressors apply whether or not the code handles them. Do not skip a family because "the code doesn't do that"; that omission is exactly the gap this skill exists to expose. (This is the deliberate inverse of infra-test-suite Rule 2.)
2. **One variable under test.** Each scenario isolates a single stressor (or a single named real-world combination like "mobile call = noise + packet loss"). Do not stack unrelated stressors, or a failure becomes unattributable.
3. **The stressor lives in the personality.** Never try to encode noise, packet loss, or accent in instructions; the voice layer ignores instruction phrasing. Only boundary timing (silence, DTMF bursts) belongs in instructions/conditional actions.
4. **Grade the tunable families.** For network and noise, test at least a light and a severe level. An agent may survive 10% packet loss and collapse at 40%; a single level hides the cliff.
5. **Evaluate resilience, not perfection.** Pass = graceful degradation (recovers, re-prompts, stays coherent, or ends cleanly). Fail = pathological behavior (infinite loop, permanent silence, hallucinated completion, crash). A pass does not require flawless task completion under severe stress.
6. **Keep it out of the CI/CD gate until it passes.** These scenarios are expected to fail at first. Graduate a family into the regression suite (the `Infrastructure Test Suite` folder / CI gate) only after the infra handles it.
7. **Confirm before creating.** Present the family + intensity plan as a checkpoint. Do not create personalities or scenarios until the user approves.

## Common Pitfalls

- **Putting the stressor in instructions.** "Speak with lots of background noise" in instructions does nothing. It must be a personality field.
- **Inventing the `network_simulation` / `background_sound_volume` JSON shape.** Copy it from a real personality via `personalities_list` first.
- **Mixing edge cases into the regression folder.** They have opposite pass expectations. Keep them in `Infrastructure Edge Cases`.
- **Marking failures from run status alone.** Read the transcript to see *how* it broke; that is what determines the infra fix. (See the "verify before labeling failures" discipline.)
- **Grading task success instead of resilience.** An agent that says "I'm having trouble hearing you, could you repeat that?" under 50% packet loss is passing, even if it never books the appointment.
- **Turning it into a 200-item suite.** This is a focused resilience probe, not the exhaustive coverage suite. Keep it compact.

## Next Steps

After running this skill, the user typically wants:
- **cekura-self-improving-agent**; if a failure is actually fixable in the prompt or tool config rather than the pipeline.
- **cekura-infra-test-suite**; to graduate a now-handled stressor family into the codebase-derived regression gate.
- **cekura-eval-design**; to author additional edge-case variants by hand.
