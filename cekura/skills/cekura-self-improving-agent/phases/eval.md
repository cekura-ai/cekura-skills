# Eval Phase — Validate, Re-collect, Decide

The Eval phase is the "verify the change and decide" half of the loop. It builds the validation set, runs it against the live agent (or asks for pasted failures in the offline variant), re-collects failures with the same logic the Optimization phase used, and decides whether to exit the loop (success / oscillation / cap / all-upstream), trigger a regression sweep, or hand back to the Optimization phase with a fresh failure summary.

The Eval phase never edits the agent. Its outputs are decisions: **exit**, **hand back to Optimization**, or **pause for the user**.

## Pre-flight check

Before any Step EVAL.x work, verify the upstream Overfitting Gate phase is complete:

- Optimization edits were applied (Optimization · Apply Step APPLY.1) AND sync was confirmed (Optimization · Sync Step SYNC.1), OR — for the offline variant — the rewritten prompt was rendered and the user has been asked for new pasted failures.
- The Overfitting Gate phase ran (Steps GATE.1–GATE.7). Either the gate found nothing and was a pass-through, OR cleanup edits were applied + synced. Either way the live state Eval is about to validate against is the gate-cleaned state, not the raw Optimization output.
- The failure set and full set are recorded on the run state (handed forward through Collect → diagnose sub-phases → Apply → Sync → Gate → Eval).
- The current iteration number is known (for cap tracking and oscillation detection).
- The cumulative iteration diff includes both Optimization edits (early-end + rest) AND any gate cleanup edits, so the orchestrator's iteration log is correct.

If any of the above is missing, return control to the orchestrator — one of the upstream sub-phases did not complete cleanly.

## Step EVAL.1 — Build the validation set

Pick the validation set based on the **original input type** (recorded on iteration 1, never changes):

| Original input | Validation set (full) |
|----------------|----------------|
| `scenario_ids` | Reuse the same scenario IDs. |
| `result_id` / `run_ids` | Extract `scenario_id` from every run (already fetched in Optimization · Collect Step COLLECT.2). De-duplicate. |
| `call_ids` | Synthesize one scenario per call from its transcript. Cache new scenario IDs on the first iteration so subsequent iterations reuse them. |
| Pasted failures (offline variant) | The validation set is whatever the user re-runs after applying the prompt — Step EVAL.3 collects new pasted failures (or zero, if everything passed). Record on iteration 1 which scenarios the user is testing against and ask before letting them silently widen the set. |

The skill tracks **two distinct sets** derived from the table above:

- **Full set** — every scenario in the original input batch (the table column above). Recorded on iteration 1; never changes mid-loop.
- **Failure set** — the subset of the full set that failed in the most recent iteration's Optimization · Collect Step COLLECT.3 (initial failure analysis) or in the most recent iteration's Step EVAL.3 re-collection.

**Iteration cadence:** Per iteration (Steps EVAL.2 → EVAL.3), run the **failure set only**. This is the cleanest signal that the edit fixed *those specific failures* and keeps iteration latency / cost down. If the failure set is exactly equal to the full set (every scenario failed initially), the two are the same and the distinction is moot until Step EVAL.4's regression sweep.

**Final regression sweep (Step EVAL.4):** Once an iteration achieves 100% on the failure set, the skill does NOT exit immediately. Instead it runs the **full set** as a one-shot confirmation pass to catch any regression in scenarios that had been passing all along (e.g., a prompt edit that fixes scenario A but breaks scenario B). The sweep only happens once, on the iteration that hits 100% on the failure set; see Step EVAL.4 for the exit logic. Skip the sweep when failure set ≡ full set on iteration 1 (no scenarios were previously passing, so there's nothing to regress).

Never widen the failure set or the full set mid-loop without telling the user — the stopping criterion depends on stable comparison sets.

## Step EVAL.2 — Run validation (with the must-pass stochastic gate)

Execute the validation set in voice mode for VAPI and ElevenLabs (both are voice agents whose edits already landed live). Capture `result_id`, poll until terminal (same 30s cadence and 15-min cap as Optimization · Collect Step COLLECT.1). For self-hosted / pipecat and self-hosted / websocket / `file`, the same Cekura-driven execution applies — the validation runs hit the live agent the user just (hopefully) redeployed / restarted.

**Stochastic re-run policy — mirror Reproduce REPRO.6 on the verification side.** A single passing run no longer ends the iteration; that single-shot pass is the source of most "looked good in dev, regressed in prod" miscalls. Branch on the **failure class** recorded in the Reproduce phase (or, for simulation-run inputs that skipped harness construction, the REPRO.2 LLM-vs-infra classification):

- **LLM-based failures →** the skill **auto-triggers the verification runs itself** (do NOT ask the user to fire each one). Run the failure-set evaluator(s) **5–10 times** (default `N = 8`, `stochastic_runs`). **The fix counts as verified for a scenario only if it passes in ≥ M of N runs** (default `M = ⌈0.8·N⌉` — e.g. ≥7/8 or ≥4/5, allowing at most a small number of stochastic flakes; tune via `verify_threshold`). A scenario that passes fewer than M of N is NOT fixed — it stays in the failure set and the loop continues. Report the pass-rate per scenario (`7/8 pass`), not a single verdict.
- **Infra failures →** a single run is sufficient (deterministic). One clean pass verifies the fix.

In **self-hosted / websocket / `offline` variant**, the skill does not run validation itself. Step EVAL.2 collapses into "ask the user for the new failure set" — a fresh batch of pasted `{transcript, expected_outcome, verdict}` blocks. Treat zero new failures as a 100% pass. The stochastic gate degrades to whatever the user re-pastes.

## Step EVAL.3 — Re-collect failures with the same Optimization-phase logic

Run the new result through Optimization · Collect end to end — verdict pre-filter (keep `failure` + `reviewed_failure`, drop `success` + `reviewed_success`), accumulate, voice filter, **and re-run Step COLLECT.4 provider-call-state inspection** against the new runs. Re-running Step COLLECT.4 each iteration matters: a Step APPLY.1 edit only changes prompts and tool definitions; it cannot change variable injection. If iteration N-1's failures were rooted upstream, iteration N's variable state should look identical — that's the signal the upstream issue is unresolved (and the loop should stop and surface, not iterate further). Re-running COLLECT.4 also re-captures Signal 5 (end-of-call attribution) so the early-end-call-diagnose sub-phase can detect whether the iteration's edits actually closed the early-end pattern.

In **self-hosted modes**, also watch for the "no-change" signature: if the new failures look identical to the prior iteration's (same scenarios fail with same transcript shapes), the most likely cause is that the live agent didn't pick up the new state — pipecat redeploy didn't happen, websocket server wasn't restarted, or (offline variant) the rewritten prompt didn't land in the user's system. Surface this hypothesis explicitly in Step EVAL.4 before iterating further. Self-hosted / websocket / `offline` is the most prone to this — the user has to apply the rewritten prompt to *their* system manually.

In **VAPI and ElevenLabs modes** the edit always lands live (no redeploy), so a no-change signature does NOT point at a stale deploy. For ElevenLabs specifically, an identical-failures repeat most often means the prompt PATCH silently no-op'd at the wrong JSON path — verify the Sync re-fetch (Step SYNC.1) actually showed the new `conversation_config.agent.prompt.prompt` value before concluding the edit "didn't help". If the re-fetch confirmed the new prompt is live, treat the no-change signature as a genuine "this edit didn't address the root cause" signal and follow the normal oscillation / 3×-same-shape handling.

## Step EVAL.4 — Decide: exit, sweep, or loop

The final exit criterion is **100% pass rate on the full set** (not just the failure set) — zero failures of any class on every scenario in the validation set (the reproduction dataset for prod-call inputs; the original input batch otherwise). "Pass" here means a scenario cleared its **must-pass stochastic gate** from Step EVAL.2 (LLM-based: ≥ M of N runs; infra: a single clean run), not a single lucky pass. Reaching 100% on the failure set is a necessary but not sufficient milestone; the regression sweep and the dedicated Regression phase are what close the loop.

Decision tree, in order:

1. **Failure set < 100%** → **hand back to Optimization · Collect.** Treat this as a *full iteration restart*, not a "small tweak and re-validate" shortcut. Re-enter the Collect sub-phase with the new failure signal AND walk every subsequent phase in order on the way back here: Collect → Early-End-Call Diagnose → Diagnose → Apply → Sync → **Overfitting Gate** → Eval. Re-load each phase file (`Read` on `phases/...md`) at its boundary and announce the boundary in your output (e.g., `Iteration 3 · Overfitting Gate`) per the phase-announcement rule in SKILL.md's Orchestration flow section — a missing announcement is the same signal as a missing phase. The Overfitting Gate is mandatory whenever Optimization produced non-zero edits, *especially* on iter 2+ where the LLM has now diagnosed the same failing transcripts multiple times and transcript-leak risk has compounded. The only case where the Gate is skipped is when this iteration produced literally zero prompt/tool/orchestration edits (all-Upstream); a single prompt-shaped change — including a new or revised system-prompt string literal embedded in source code, even when it sits next to control-flow code — must be inventoried and scored. Diagnose Step DIAGNOSE.5 surfaces a fresh combined proposal and **waits for explicit approval** before Apply (in `auto_mode: false`; in auto mode, render and proceed). The failure set may shrink across iterations (some failing scenarios start passing) — track that as progress but stay on the same set; don't drop now-passing scenarios from the in-loop failure set until the sweep, or you lose the ability to detect oscillation.

2. **Failure set = 100% AND a sweep has not yet been run this loop** → **trigger the final regression sweep.**
   - Build the **full set** (every scenario in the original input batch, per the Step EVAL.1 table).
   - If the full set equals the failure set (no scenarios were initially passing), skip the sweep and treat as case 3 (100% on full).
   - Otherwise: announce the sweep to the user ("All N originally-failing scenarios now pass — running the full M-scenario set as a regression check"), then execute Steps EVAL.2 → EVAL.3 once against the full set.
   - On the result:
     - **Full set = 100%** → case 3 (success).
     - **Full set < 100%** → case 4 (hand back to Optimization · Collect with the new failures as the new failure set, regardless of whether each scenario had been passing originally or had been failing-then-fixed). Previously-failing-now-fixed scenarios stay in the validation set so the loop catches re-regressions.

3. **Full set = 100%** → the loop has converged — **hand off to the Regression phase, then the PR phase.** Do NOT exit yet. The in-loop sweep above only confirms the reproduction dataset is green; the dedicated [`regression.md`](regression.md) phase generates and runs the happy-path + edge-case sweep that catches collateral damage the reproduction dataset can't see, and [`pr.md`](pr.md) ships the result (raise a PR, or emit a PR-ready summary). Pass forward: the cumulative diff, total iterations used, which scenarios changed verdict, and the full set of result URLs (reproduction fail-runs from REPRO.6 + verification pass-runs from EVAL.2). Only after Regression passes and PR/summary is emitted does the skill report success and stop.

4. **Regression detected during sweep** → do NOT exit. **Hand back to Optimization · Collect** with the new failure set = the scenarios that regressed. Mention explicitly that this iteration's edit broke a previously-passing scenario, so Diagnose can consider scoping the fix more narrowly (e.g., conditional clauses for the specific failing scenario type rather than blanket prompt-wide changes).

## Iteration cap

Default 10. The user can override with `max_iterations` or stop / extend mid-loop ("keep going" / "stop"). The regression sweep counts as part of the iteration that triggered it (not a separate iteration). Don't loop silently past the cap. After hitting the cap, surface what's been fixed, what's still failing, and a recommended next skill.

## Early-exit shortcut

If Optimization · Collect's first pass collected zero failures of any class from the initial input, the diagnose sub-phases were skipped — the orchestrator reports success before the Eval phase runs at all. If everything was filtered out (e.g. all voice/infra failures), Collect surfaces the situation and stops the loop directly — see [`optimization/collect.md`](optimization/collect.md).

For the full PATCH curl bodies, the tool-backup pattern, the loop guardrails (oscillation detection, validation-set stability, cumulative-diff tracking), and the per-iteration scope rules, see [`../providers/vapi/phase-4-apply.md`](../providers/vapi/phase-4-apply.md) (VAPI specifics) or [`../providers/elevenlabs/phase-4-apply.md`](../providers/elevenlabs/phase-4-apply.md) (ElevenLabs specifics) — the loop guardrails apply across modes.
