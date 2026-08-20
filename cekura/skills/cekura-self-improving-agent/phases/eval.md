# Eval Phase — Validate, Re-collect, Decide

The "verify the change and decide" half of the loop. Builds the validation set, runs it under the **must-pass stochastic gate**, re-collects failures with Collect's logic, and decides: **exit**, **hand back to Optimization · Collect**, or **pause for the user**. Eval never edits the agent.

**Validation mechanism** is **always Cekura scenarios** (simulation over the agent's transport) — never a code / unit test. Gates stochastically (≥ M of N). Everywhere below, "scenario" = one validation unit.

## Pre-flight check

Before any EVAL.x work, verify:

- Optimization edits applied (APPLY.1) AND sync confirmed (SYNC.1); OR — render-only (no live target) — the rewrite was rendered and the user asked for new pasted failures.
- Overfitting Gate ran (GATE.1–GATE.7): either a clean pass-through, or cleanup edits applied + synced. Eval validates the gate-cleaned state.
- Failure set and full set are on the run state; current iteration number known.
- Cumulative diff includes Optimization edits (early-end + rest) AND gate cleanup edits.

Any missing → return control to the orchestrator; an upstream sub-phase didn't complete cleanly.

## Step EVAL.1 — Build the validation set

Pick by **original input type** (recorded iter 1, never changes):

| Original input | Full set |
|---|---|
| `scenario_ids` | Same scenario IDs. |
| `result_id` / `run_ids` | `scenario_id` from every run (fetched in COLLECT.2), de-duped. |
| `call_ids` | One scenario synthesized per call from its transcript; cache IDs iter 1, reuse after. |
| Pasted failures (render-only) | Whatever the user re-runs after applying the rewrite; EVAL.3 collects new pasted failures (zero = 100%). Record iter 1 which scenarios are tested; ask before widening. |

Two tracked sets:

- **Full set** — every unit in the original input batch. Recorded iter 1; never changes mid-loop.
- **Failure set** — the subset that failed in the most recent COLLECT.3 (initial) or EVAL.3 (re-collection).

**Iteration cadence:** per iteration (EVAL.2 → EVAL.3), run the **failure set only** — cleanest signal the edit fixed those failures, lower latency/cost. If failure set ≡ full set (all failed iter 1), the distinction is moot until EVAL.4's sweep.

**Final sweep (EVAL.4):** hitting 100% on the failure set does NOT exit. Run the **full set** once to catch regressions in previously-passing units. Sweep runs only once, on the iteration that hits 100% on the failure set. Skip when failure set ≡ full set iter 1 (nothing was passing).

Never widen either set mid-loop without telling the user — the stop criterion depends on stable comparison sets.

## Step EVAL.2 — Run validation (must-pass stochastic gate)

Run the failure set with Setup's saved simulation runner. For self-hosted targets, use the saved launch/connect steps and keep REPRO.3e triggers active. Capture `result_id` and poll to terminal (as COLLECT.1).

**Re-run policy — mirror REPRO.6's mode on the verification side.** The skill **auto-triggers the verification runs itself** (do NOT ask the user to fire each). Label every batch via the run call's `name`: `[selfimprove] verify iter<N> — failure set` / `[selfimprove] full-set sweep iter<N>`.

- **Deterministic-mode reproductions** (forced trigger / `CEKURA-REPRO-INJECT` fault injection): verify with **2 runs, both passing (2/2), with the trigger still active**. The bug fired every time before the fix; two clean runs under the same forced trigger is conclusive, and more runs add cost, not confidence. Any fail → not fixed.
- **Stochastic-mode reproductions**: a single passing run never ends the iteration (that's the source of most "looked good in dev, regressed in prod" miscalls). Run **5–10 times** (default `N = 8`, `stochastic_runs`); a scenario is **verified only if it passes in ≥ M of N** (default `M = ⌈0.8·N⌉` — e.g. ≥7/8, ≥4/5; tune via `verify_threshold`). Below M → not fixed, stays in the failure set. Report pass-rate per scenario (`7/8 pass`), not a single verdict.

This is uniform across classes — the only difference is harness shape:

- **LLM-based failures** (managed provider) — dataset of N varied scenarios.
- **Infra failures / self-hosted targets** — the single evaluator, re-run N times (over real transport, timing/audio/latency/interruption failures are intermittent; a deterministic fix passes all N).

In a **render-only run** the skill runs nothing: EVAL.2 collapses to "ask the user for the new failure set" (fresh pasted `{transcript, expected_outcome, verdict}` blocks). Zero new failures = 100%. The gate degrades to whatever the user re-pastes.

## Step EVAL.3 — Re-collect failures (same Collect logic)

Run the new result through Collect end to end: verdict pre-filter (keep `failure` + `reviewed_failure`, drop `success` + `reviewed_success`), accumulate, voice filter, **and re-run COLLECT.4 provider-call-state inspection** on the new runs. Re-running COLLECT.4 matters — an APPLY.1 edit changes prompts/tool defs, never variable injection; if iter N-1's failures were upstream, iter N's variable state looks identical (signal the upstream issue is unresolved → stop and surface, don't iterate). COLLECT.4 also re-captures Signal 5 (end-of-call attribution) so the FIX.1 early-end triage can tell whether the edits closed the early-end pattern.

**No-change signature** (new failures identical to prior — same scenarios, same transcript shapes):

- **Self-hosted / render-only** — most likely the live agent didn't pick up the new state (redeploy skipped, server not restarted, or the user never applied the rewrite). Surface this hypothesis in EVAL.4 before iterating. Render-only is most prone — the user applies the rewrite manually.
- **Managed providers** — edits land live, so no-change is NOT a stale deploy. First confirm SYNC.1 showed the changed provider field. If it is confirmed live, treat the result as a genuine "this edit didn't address the root cause" and follow oscillation / 3×-same-shape handling.

## Step EVAL.4 — Decide: exit, sweep, or loop

Final exit criterion: **100% pass on the full set** — zero failures of any class, every unit clearing its **must-pass stochastic gate** from EVAL.2 (≥ M of N, all classes), not a single lucky pass. 100% on the failure set is necessary but not sufficient; the sweep + Regression phase close the loop.

Decision tree, in order:

1. **Failure set < 100% → hand back to Optimization · Collect.** A *full iteration restart*, not a tweak-and-revalidate: re-enter Collect with the new failure signal and walk every phase in order back to here — Collect → Fix → Apply → Sync → **Overfitting Gate** → Eval. Re-`Read` each phase file at its boundary and announce it (e.g. `Iteration 3 · Overfitting Gate`) per SKILL.md's phase-announcement rule — a missing announcement is the same signal as a missing phase. The Gate is mandatory whenever Optimization produced non-zero edits, *especially* iter 2+ (transcript-leak risk compounds); the only skip is an iteration with literally zero prompt/tool/orchestration edits (all-Upstream). A single prompt-shaped change — including a system-prompt string literal embedded in source, even beside control-flow code — must be inventoried and scored. FIX.6 surfaces a fresh combined proposal and **waits for explicit approval** before Apply (`auto_mode: false`; in auto mode, render and proceed). The failure set may shrink across iterations — track as progress but stay on the same set; don't drop now-passing scenarios until the sweep, or you lose oscillation detection.

2. **Failure set = 100% AND no sweep yet this loop → trigger the final regression sweep.**
   - Build the **full set** (EVAL.1 table).
   - Full set ≡ failure set (nothing was passing) → skip, treat as case 3.
   - Else: announce ("All N originally-failing scenarios now pass — running the full M-scenario set as a regression check"), run EVAL.2 → EVAL.3 once against the full set.
     - **Full set = 100%** → case 3.
     - **Full set < 100%** → case 4 (hand back with the new failures as the failure set, whether each was originally passing or failing-then-fixed). Fixed scenarios stay in the validation set so re-regressions are caught.

3. **Full set = 100% → converged. Hand off to Regression.** Do NOT exit yet. The in-loop sweep only confirms the reproduction dataset is green; [`regression.md`](regression.md) runs the happy-path + edge-case sweep that catches collateral damage the dataset can't see. Pass forward: cumulative diff, iterations used, which scenarios changed verdict, and all result URLs (REPRO.6 fail-runs + EVAL.2 pass-runs). After Regression passes, hand the validated diff and evidence to the apply-diff workflow and stop.

4. **Regression detected during sweep → do NOT exit. Hand back to Optimization · Collect** with the regressed scenarios as the new failure set. State explicitly that this iteration's edit broke a previously-passing scenario, so Fix can scope the fix more narrowly (conditional clauses for the specific type rather than blanket prompt-wide changes).

## Iteration cap

Default 10; override with `max_iterations` or stop/extend mid-loop ("keep going" / "stop"). The sweep counts as part of its triggering iteration, not a separate one. Don't loop silently past the cap — surface what's fixed, what's still failing, and a recommended next skill.

## Early-exit shortcut

If Collect's first pass collected zero failures of any class, the fix sub-phases were skipped and the orchestrator reports success before Eval runs. If everything was filtered out (e.g. all voice/infra failures), Collect surfaces and stops the loop directly — see [`collect.md`](collect.md).

For PATCH curl bodies, the tool-backup pattern, loop guardrails (oscillation detection, validation-set stability, cumulative-diff tracking), and per-iteration scope rules, see [`../providers/vapi/phase-4-apply.md`](../providers/vapi/phase-4-apply.md) or [`../providers/elevenlabs/phase-4-apply.md`](../providers/elevenlabs/phase-4-apply.md) — the guardrails apply across modes.
