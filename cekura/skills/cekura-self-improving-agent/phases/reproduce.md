# Reproduce Phase — Build the Harness, Then Gate on a Definitive FAIL

Runs **once**, after Debug (Setup / Clone / Collect precede it), before the Optimization loop. Debug has established the root cause and failure class, and Collect (COLLECT.6) recorded the replay artifacts; Reproduce turns them into a controlled Cekura harness and **proves it fails** before any edit. If it can't be made to fail, stop.

## Entry branch (on the signal)

- **Prod-call inputs** (`call_ids`, or a `result_id` / `run_ids` pointing at production call logs) → full procedure. Auto-build the harness from the call's own trace (mocks, expected returns, dynamic vars, testing-agent vars), construct the evaluator, branch on failure class, run the gate.
- **Simulation-run inputs** (`scenario_ids`, or a `result_id` / `run_ids` from a Cekura simulation) → artifacts already exist as scenarios. Skip REPRO.3 and REPRO.4; run REPRO.2 (drives harness shape) and REPRO.6 against the existing scenarios. A scenario that doesn't fail on re-run is not a reproduction — surface and stop.
- **Render-only** (pasted prompt + pasted failures, no reachable live target) → skip this phase. The pasted `{transcript, expected_outcome, verdict}` blocks are the only signal; the gates degrade to "user re-pastes failures each iteration" (handled in Eval).

Owned-source-code bugs (orchestration / STT / transport / timing / forked-SDK) are **not** a separate branch — reproduce them on Cekura like any other failure by injecting the triggering condition (REPRO.3e) into the live self-hosted agent so the bug fires in the simulation. The root cause is consumed as given.

> ## ⚠️ ALWAYS CEKURA, SAME TRANSPORT — NO SUBSTITUTES
>
> Every reproduction / verification / regression run uses Setup's saved Cekura simulation runner. Do not switch runners between phases or substitute a code/unit test. If the failure cannot be forced in that simulation, stop (REPRO.6).

---

## Step REPRO.2 — Classify the failure class (drives harness shape only)

This drives **one** decision — harness shape (REPRO.5). The re-run policy is the **same 5–10× ≥ M of N gate** for every class. The class is a *preview* from prod evidence, not the authoritative Fix verdict (per-failure, in-loop — see [`optimization/fix.md`](optimization/fix.md) FIX.4).

| Class / target | Fix buckets | Harness shape |
|---|---|---|
| **LLM-based** on a managed provider (VAPI / ElevenLabs) | Gap / Conflict / Ambiguity (over-eager-transfer, premature-exit) | **dataset** of N varied scenarios |
| **Infra**, or **any self-hosted target** | CodeBug (source truncation, broken state, missing tool-result forwarding) / Upstream-infra (mock wiring, idle timer, DTMF, telephony) | **single** evaluator |

All classes re-run 5–10× at the gate because real behavior — LLM and real-transport infra alike — is intermittent: a bug that's deterministic in *cause* still fires only sometimes over telephony/SIP/WebRTC (timing/audio/latency/interruption races), so a single run can false-PASS. When symptoms mix, default to a **dataset** (larger sample is the safe error) unless the target is self-hosted.

---

## Step REPRO.3 — Auto-build the reproduction harness (prod-call inputs)

Replay the call faithfully with zero manual setup by the user. Derive every artifact from the call's own trace — never from prompt-guessing.

- **REPRO.3a — Mock tool entries.** Every tool the call invoked must appear in the agent's mock-tool JSON (name + parameter schema matching what the agent actually sent). Self-hosted: mocks are the testing contract — set the full desired `mock_tools` on the agent (fetch → merge → write back). VAPI / ElevenLabs: tools already exist on the cloned agent; here you only set their return values (3b).
- **REPRO.3b — Expected return values.** Set each mock's return to the **actual production response** (read the req→resp pairs from the call object / provider `/logs`, not what the prompt says it "should" return). Same tool, different args → different responses: encode the per-invocation mapping (`freetext_params` / argument-keyed mock data). A plausible-but-different value won't reproduce the bug.
- **REPRO.3c — Main-agent dynamic variables.** Copy `dynamic_variables` from call metadata onto the agent (assistant-/squad-level, per provider) **verbatim** — the bug may depend on them. Don't invent or normalize. Leave `{{...}}` placeholders in the prompt untouched; you're setting the values they resolve to.
- **REPRO.3d — Testing-agent variables.** Populate the testing-agent/scenario layer (caller persona, context payload, scripted fields, test-profile vars) from the call. Use the prod `personality_id`; extract caller turns from `transcript_object` **verbatim** — garbled text, truncations, STT artifacts are exactly what the LLM received and are often the trigger. Do not clean them up.
- **REPRO.3e — Force the trigger (infra / code bugs).** When the failure is environmental rather than wording — STT/transcript corruption, LLM latency/timeout, tool slowness or bad data, auth failure, silence/interruption/near-timeout — inject the same condition so it fires in the sim instead of hoping it recurs. Generic levers: replay the exact garbled/truncated transcript verbatim; delay or force a timeout/retry on the STT, LLM, or tool call; return the malformed tool response seen in prod; use invalid credentials on auth paths; inject `<silence>` / `<interruption>` or lower `maxDurationSeconds` for audio/telephony. Self-hosted: apply these in the live agent per the run-setup and keep them active through verification (Eval); remove only after the fix passes.

---

## Step REPRO.4 — Construct the evaluator (prefer `expected_outcome`)

**Default: derive pass/fail bullets from the scenario's `expected_outcome`** — express the behavior that should have happened as bullets. Higher-signal, and aligned with how Fix keys off expected-outcome bullets. Defaulting to the prod metric drags metric-judge noise in as a confounder.

**Fallback — attach the prod metric directly — only when the failure is out of scope for `expected_outcome`** (latency / sentiment / interruption-score / infrastructure metrics that don't map to behavioral bullets). Attach the exact failing metric(s) from Collect's failing-metric record (COLLECT.6).

If unsure whether `expected_outcome` can express the failure, prefer it and add the prod metric as a secondary check — do not silently drop to metric-only. Genuinely ambiguous → ask.

Create the scenario(s) under the agent that handled the failing call:

```bash
create_scenario '{
  "agent": AGENT_ID,
  "personality": PERSONALITY_ID,
  "name": "Bug repro: <brief issue>",
  "instructions": "Replay the production call that caused <issue>.",
  "expected_outcome": "<behavioral bullets derived from the prod failure>",
  "conditional_actions": { "role": "caller", "conditions": [ /* verbatim testing-agent turns from REPRO.3d */ ] }
}'
```

(Fallback path: omit inexpressible bullets and attach `"metrics": [METRIC_ID_1, ...]`.) Save the `scenario_id`(s).

---

## Step REPRO.5 — Branch harness shape on the failure class (REPRO.2)

- **LLM-based (managed provider) → dataset of N scenarios.** One scenario gives too little signal to tell a real fix from a lucky sample. Build `N` (default 8, `dataset_size` 5–10) exercising the *same* failure mode with light variation — vary caller phrasing / order / incidental details, hold the trigger constant. Prod replay is scenario 1; the rest are near-variants. This dataset is the **full set** for the loop (Eval, regression).
- **Infra, or any self-hosted target → a single evaluator** (still re-run 5–10× at the gate). One faithful replay is the right harness; the trigger is fixed. The single repro scenario is the full set.

---

## Step REPRO.6 — Must-fail-first gate

> ## ⛔ HARD STOP — DO NOT ENTER THE LOOP WITHOUT A DEFINITIVE FAIL.

Run the evaluator(s) with Setup's saved runner and require a definitive FAIL before any edit.

### Re-run policy (all classes)

The skill **auto-fires N runs itself** — never ask the user to trigger each. Run **5–10×** (default `N = 8`, `stochastic_runs`). **Reproduced only if it fails ≥ M of N** (default `M = ⌈N/2⌉`, e.g. ≥4/8, ≥5/10, ≥3/5 — `repro_threshold`). Fewer than M → not reliably reproducible; surface and stop.

- **LLM-based (managed provider):** dataset of N varied scenarios.
- **Infra / self-hosted:** the same single evaluator ×N.

The only thing the class changes is harness shape, not the run count.

Fire N runs with the saved runner and poll each result to terminal.

**Self-hosted targets:** launch the main agent with the per-run Cekura connection details using the run-setup steps in `.claude/CLAUDE.md` / `.claude/MEMORY.md` (Setup 1.4a), with any REPRO.3e trigger conditions active. If those weren't captured, ask now and persist before the first run — don't guess how to start the agent.

### What "fails" means

The **Cekura metric / expected-outcome scores** show failure — not merely that the call ended, errored, or "looks wrong." Read `runs[].evaluation.metrics[]` (or expected-outcome verdict) per result. The prod failure mode must be present in the replay transcript **and** reflected in the scores; compare replay vs. prod turn-by-turn.

### Errors are NOT a reproduction

A run that errored / didn't connect / crashed → **fix and retry that run.** An error is not a FAIL and doesn't count toward M-of-N. If the sim won't run at all, stop and ask.

### If it PASSES (below the fail threshold) — STOP and surface

Below M-of-N fails → not reproduced. Most likely causes, in order:

1. **Mock/variable mismatch** — a mock returns a different value than prod (3b), a dynamic var wasn't copied (3c/d), or caller turns were cleaned up instead of replayed verbatim (3d). Re-check the harness against the trace.
2. **Trigger not forced** — an infra / code bug's condition (3e) isn't active or strong enough. Re-apply and strengthen it.
3. **Stale fix** — already fixed on the live agent since the call. Confirm; if so, nothing to do.
4. **Wrong evaluator** — bullets / metric don't detect this failure (REPRO.4).

Show the replay transcript + scores side-by-side with prod and ask: "this didn't reproduce the prod failure — is the harness wrong, or was this already fixed?" Do not guess or proceed into the loop on an unreproduced bug.

---

## Hand-off to the Optimization loop

When the must-fail gate is satisfied (definitive FAIL in ≥ M of N), hand off to the Optimization loop ([`optimization/fix.md`](optimization/fix.md)) with:

- The **harness** — reproduction scenario IDs — as the loop's validation target; from here the loop iterates against it, not the raw prod log.
- The **full set** (N-scenario dataset for LLM-based; single scenario for infra / self-hosted) and the **failure class**, which Eval reads for its must-pass re-run policy.
- The harness inventory (mocks + variables + any REPRO.3e trigger conditions) and the failing result URLs (reproduction evidence for the PR / summary). The root-cause summary + replay artifacts (from Debug / Collect) travel on run state.
