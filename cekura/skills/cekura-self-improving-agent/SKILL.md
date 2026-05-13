---
name: cekura-self-improving-agent
description: >
  Use when the user asks to "improve my agent", "self-improving agent",
  "auto-tune my agent", "iterate on my agent prompt", "fix my agent based
  on test results", "close the loop on agent quality", "auto-improve agent
  prompt", "use eval results to improve agent", "optimize my prompt based
  on failures", "rewrite my prompt", or describes agent self-improvement,
  prompt iteration from run results, or automated agent quality loops.
  Covers the full diagnose → propose → apply → re-validate loop for VAPI
  agents (squads + tool definitions) and for self-hosted agents (custom
  websocket servers, including the offline / pasted-prompt degenerate
  variant).
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.22.0"
---

# Cekura Self-Improving Agent

## Purpose

Close the loop on agent prompt and tool-config quality. Ingest evaluation signal (scenario IDs to run, completed runs, a result batch, or production call logs), classify failures, diagnose where the prompt or tool config has gaps / conflicts / ambiguities, propose targeted edits, apply them, and re-run validation — iterating until the agent reaches **100% pass rate on the validation set** or the iteration cap is reached.

**Exit gate.** The voice/channel/infra filter informs *what to fix* (the Optimization phase only proposes edits for prompt-following failures), not *when to stop*. Any remaining failure of any class keeps the loop alive. Only the iteration cap or a genuine 100% pass ends the loop.

Currently supported for **VAPI** and **self-hosted** (websocket). Retell support is intentionally disabled and will be re-enabled in a future revision.

## Architecture — orchestrator over a sequence of focused sub-phases

This SKILL.md is a thin orchestrator. Optimization is split into five sub-phases living in `phases/optimization/`, with Setup, Overfitting Gate, and Eval as standalone phases on either side:

```
                  ┌────────────────┐
   user input ─→  │  Setup phase   │  (phases/setup.md)
                  │  runs once     │
                  └───────┬────────┘
                          │  (mode, sub-flavor, agent, redeploy_command)
                          ▼
              ┌───  ┌───────────────────────────┐
              │     │ Optimization · Collect    │  (phases/optimization/collect.md)
              │     │ fetch + filter + inspect  │
              │     │ provider call state       │
              │     └───────┬───────────────────┘
              │             │  (kept failures + Signal 5 end-of-call attribution)
              │             ▼
              │     ┌────────────────────────────────────┐
              │     │ Optimization · Early-End-Call      │  (phases/optimization/
              │     │ Diagnose                           │   early-end-call-diagnose.md)
              │     │ flag main-agent-ended-early →      │
              │     │ propose closure-rule / code edits  │
              │     └───────┬────────────────────────────┘
              │             │  (early-end edits proposed; pass-through if none)
              │             ▼
              │     ┌────────────────────────────────────┐
              │     │ Optimization · Diagnose    │  (phases/optimization/
              │     │ classify Gap/Conflict/Ambig/       │   diagnose.md)
              │     │ CodeBug-other/Upstream →           │
              │     │ propose edits → present combined   │
              │     └───────┬────────────────────────────┘
              │             │  (user-approved combined edit set)
              │             ▼
              │     ┌───────────────────────────┐
              │     │ Optimization · Apply      │  (phases/optimization/apply.md)
              │     │ PATCH / Edit → redeploy   │
              │     └───────┬───────────────────┘
              │             │  (writes landed; live agent restarted)
              │             ▼
              │     ┌───────────────────────────┐
              │     │ Optimization · Sync       │  (phases/optimization/sync.md)
              │     │ re-fetch + verify         │
              │     └───────┬───────────────────┘
              │             │  (verified state matches intent)
              │             ▼
              │     ┌───────────────────────────┐
              │     │ Overfitting Gate          │  (phases/overfitting-gate.md)
              │     │ scrub transcript quotes / │
              │     │ scenario IDs / narrow     │
              │     │ clauses; apply cleanup    │
              │     │ (pass-through if clean)   │
              │     └───────┬───────────────────┘
              │             │  (gate-cleaned state)
              │             ▼
              │     ┌───────────────────────────┐
              │     │ Eval phase                │  (phases/eval.md)
              │     │ validate → re-collect →   │
              │     │ decide                    │
              │     └───────┬───────────────────┘
              │             │
              │     ┌───────┴────────────────────┐
              │     │                            │
   hand back  │     ▼                            ▼  exit
   to Collect │  failure set < 100%        full set = 100% (success)
              │  OR regression             OR iteration cap
              │  OR mitigation edits       OR all-Upstream
              │                            OR oscillation / no-change
              └────  (loop)                OR 3× same-shape failure
                                           (surface + pause for user)
```

**Setup runs once.** It resolves the run mode and sub-flavor, loads the agent (its config and prompt source), and (for self-hosted live targets) collects the `redeploy_command`. Setup is a hard gate — Optimization · Collect will not start until Setup is complete.

**Optimization is five sub-phases that run in series, each with one job:**

- **Collect** ([`phases/optimization/collect.md`](phases/optimization/collect.md)) — fetch runs / call logs / pasted failures, pre-filter by per-run verdict (keep `failure` + `reviewed_failure`, drop `success` + `reviewed_success`), apply the voice/channel filter, inspect provider call state for every kept failure (Signals 1–5, including end-of-call attribution), build the failure summary. Output: kept failure set + per-failure signals.
- **Early-End-Call Diagnose** ([`phases/optimization/early-end-call-diagnose.md`](phases/optimization/early-end-call-diagnose.md)) — specialized triage for failures where the main agent ended the call before the scenario's required steps completed. Flags failures matching {main-agent-ended + scenario-incomplete in expected-outcome bullets} via a two-check verdict-first checklist (no rationale, no borderline cases), diagnoses root cause (too-permissive closure rules / orchestration-code end-of-call detection / VAPI handoff misconfigured), proposes minimal closure-rule prompt edits or — for websocket / `file` mode — orchestration-code edits gating closure on captured state. Pass-through if no failures match. Proposed edits are NOT applied here; they flow into the combined proposal in Diagnose.
- **Diagnose** ([`phases/optimization/diagnose.md`](phases/optimization/diagnose.md)) — classify every non-early-end failure (Gap / Conflict / Ambiguity / non-early-end CodeBug / Upstream), propose minimal scoped edits, de-conflict with early-end proposals, then **present the combined proposal** (early-end + rest) to the user. This is where the user-facing diff-approval gate fires in `auto_mode: false`.
- **Apply** ([`phases/optimization/apply.md`](phases/optimization/apply.md)) — land the approved edits via per-provider apply machinery (VAPI PATCH / Cekura platform tools / `Edit` on source file / render rewritten prompt), then run `redeploy_command` (or fire the manual restart gate).
- **Sync** ([`phases/optimization/sync.md`](phases/optimization/sync.md)) — re-fetch the just-edited artifacts and verify each changed field landed correctly. Catches VAPI nested-object replacement and `Edit` ambiguous-anchor drift. Roll back to Apply on drift.

**Overfitting Gate is the "scrub the just-applied edits" phase.** Because the diagnose sub-phases read failing transcripts, they sometimes leak transcript-specific phrasing into proposals — verbatim quotes, scenario IDs / names, hardcoded test data, hyper-narrow case clauses, transcript-cloned few-shot examples. The gate re-reads what was just synced, scores each edit against five overfitting signatures, and emits cleanup edits (REVISE to a generalized form, or STRIP entirely) before Eval validates. On clean iterations the gate is a one-line pass-through. Full procedure: [`phases/overfitting-gate.md`](phases/overfitting-gate.md).

**Eval is the "verify and decide" phase.** It builds the validation set, runs it against the gate-cleaned live agent, re-collects failures with the same logic Collect uses, and decides: hand back to Collect with a new failure summary, trigger a final regression sweep, declare success, or surface a stop condition (oscillation / no-change / 3× same-shape / iteration cap / all-Upstream). Full procedure: [`phases/eval.md`](phases/eval.md).

**Run phases strictly sequentially — never parallelize across phase boundaries.** Each phase consumes the previous phase's outputs as hard pre-conditions (Diagnose reads Collect's kept-failure set + Signal 5; Apply reads Diagnose's approved combined proposal; Sync reads Apply's written artifacts; Eval reads the gate-cleaned live state). Pre-fetching artifacts from a later phase "to save round-trips" — e.g., fetching the `result_id` payload during Setup, reading the source file before Diagnose has classified failures, or running validation before Sync has verified the writes landed — produces work against premature assumptions, conflates phase responsibilities, and makes failures harder to localize. The orchestrator enters phase N+1 only after phase N's hand-off conditions are met. Parallelizing tool calls *within* a single phase step is fine when those calls are genuinely independent (e.g., fetching multiple referenced tools during Setup Step 1.3); the rule is about phase boundaries, not intra-phase tool batching.

**Loop hand-off rules:**
- **Setup → Collect** when mode + sub-flavor + agent + `redeploy_command` are all resolved.
- **Collect → Early-End-Call Diagnose** when the kept failure set is populated and Signal 5 (end-of-call attribution) is recorded for every kept failure. If kept = 0, skip the rest of Optimization (and the Gate, and Eval) — surface the funnel summary and stop.
- **Early-End-Call Diagnose → Diagnose** always (whether or not any failures were flagged as early-end; the pass-through case is the no-edit branch).
- **Diagnose → Apply** when the combined proposal is non-empty AND the user has approved it (in `auto_mode: false`) or auto-mode auto-accepted it. If the combined proposal is empty (all-Upstream or all-KEEP-on-low-confidence), skip Apply / Sync / Gate / Eval — surface upstream hand-offs and stop.
- **Apply → Sync** after writes lands and the redeploy step (for self-hosted live targets) completes successfully. A non-zero `redeploy_command` exit halts the loop here; the user decides retry vs. abort.
- **Sync → Overfitting Gate** after every changed field is verified. Drift detection rolls back to Apply rather than proceeding to the Gate.
- **Overfitting Gate → Eval** after gate scoring finishes. If cleanup edits were needed, after Step GATE.7 sync confirms; if no flags were found, straight to Eval as a pass-through.
- **Eval → Collect** when the failure set is non-empty AND none of the stop conditions fire (oscillation, no-change, 3× same-shape, iteration cap, all-Upstream, all-voice-with-no-mitigation). Each Eval → Collect hand-back counts toward `max_iterations`.
- **Eval → Exit** on 100% pass on the full set (after the regression sweep), or on any stop condition (surfaced to user, loop halted).

## Modes and providers (resolved during Setup)

The skill organizes providers under `providers/`:

- **`vapi`** — VAPI agents. Both system prompts and tool definitions are editable directly via the VAPI API. Tool config covers function declarations, referenced tool definitions (`name`, `description`, `parameters`, spoken `messages` like `request-start` / `request-complete` / `request-failed`, and handoff `destinations`), and which tools each squad member references via its `toolIds` array. Edits land on VAPI; the live agent picks them up immediately. See [`providers/vapi/overview.md`](providers/vapi/overview.md).
- **`self_hosted`** — umbrella for any agent the user runs themselves. The supported sub-flavor is **`websocket`**: custom websocket servers (e.g., Python / Node / Go) whose system prompt, tool definitions, **and conversation-orchestration code** live in the user's source code. Editable surface is the user's source file via the `Edit` tool — covering the system prompt, tool schemas, AND orchestration code (conversation-history management, message wiring, state-preservation logic, keepalive / retry plumbing) when a failure's root cause is in code rather than prompt wording. Business logic (what a tool *computes* or what an external service returns) and security-sensitive code (API keys, auth, signing) remain out of scope. **The Cekura agent record's `llm_system_prompt` field is NOT the source of truth in this mode — do not read it, and never ask the user to paste their prompt while a workspace is reachable.** Always source the prompt from the workspace: start with the file currently open in the IDE (`ide_opened_file`), then grep project files for the system-prompt string constant. The user restarts their websocket server before re-validation; in auto mode the gate is skipped. A degenerate `offline` variant covers the "no live websocket reachable" case — the skill renders the rewritten prompt for manual application and asks for pasted failures each iteration (offline variant supports prompt edits only, never code edits). See [`providers/self-hosted/websocket.md`](providers/self-hosted/websocket.md).

The `providers/self-hosted/overview.md` file documents the self-hosted routing.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

- VAPI mode: VAPI write operations (assistant PATCH, tool create / PATCH / delete) are not exposed through Cekura platform tools — they go directly to the VAPI API with `VAPI_KEY`. Full curl bodies in [`providers/vapi/phase-4-apply.md`](providers/vapi/phase-4-apply.md).
- Self-hosted / websocket: file edits land via the `Edit` tool on the user's source code — system prompt, tool schemas, and conversation-orchestration code (history management, message wiring, state) are all in scope; optional `mcp__cekura__aiagents_partial_update` to sync the Cekura description as a mirror. Full flow in [`providers/self-hosted/websocket.md`](providers/self-hosted/websocket.md).

## How to Use This Skill

This is an **interactive, multi-iteration workflow**. The user supplies one of:

- **VAPI / self-hosted modes (any live target)** — an `agent_id` plus exactly one of: `scenario_ids`, `result_id`, `run_ids`, or `call_ids`.
- **Self-hosted / websocket / offline variant** — a `prompt` (pasted text or read-only file path) plus pasted `{transcript, expected_outcome, verdict}` blocks. No live agent required.

Optionally:

- `max_iterations` (default 10) — caps the loop. Each Eval → Optimization hand-back counts as one iteration.
- `mode` (`vapi` / `self_hosted`) — explicit override if the resolution would otherwise be ambiguous.
- `self_hosted_flavor` (`websocket`) — explicit override; self-hosted resolves to websocket.
- `redeploy_command` (self-hosted only) — shell command(s) the skill should run after each apply step to restart the live agent before re-validation. If provided, the Optimization phase runs this automatically and the user-side restart gate is skipped entirely. If set to the literal string `"manual"` (or not provided in `auto_mode: false`), the skill falls back to the canonical "pause and ask the user to restart" gate. Collected at the end of Setup Step 1.3 for self-hosted modes — see Setup Step 1.4. VAPI mode ignores this field (VAPI edits land live; nothing to redeploy).
- `auto_mode` (default **true**) — when true, skip the diff-approval gate at the end of Diagnose (Step DIAGNOSE.5) and the overfitting-gate cleanup approval (Step GATE.5) on every iteration. With `redeploy_command` configured, the skill is fully end-to-end autonomous for self-hosted modes (auto-apply → auto-redeploy → auto-validate). Without `redeploy_command`, auto_mode skips the routine user-side deployment pauses too and trusts the user to keep their live system in sync (the no-change detector in Eval Step EVAL.3 catches stale-state cases after the fact). The iteration cap, oscillation detection, validation-set stability, and the user's ability to interrupt mid-loop all still apply. Set `auto_mode: false` only when you want a per-iteration diff-approval pause AND (if `redeploy_command` is unset) explicit user-side deployment gates before validation.

## When to ask for feedback or clarification (applies in every phase)

**Ask for feedback or clarification wherever required, even in auto mode.** Auto mode skips *routine* gates; it does NOT make the skill silent on genuinely ambiguous inputs or risky decisions. Pause and ask when:

- The user's input is ambiguous or incomplete (e.g., `agent_id` + `prompt` supplied without a mode; structured-config file where the prompt field can't be identified safely; empty / one-line / clearly-non-production prompt).
- **Self-hosted live targets — the `redeploy_command` must be resolved at Setup Step 1.4 before Optimization begins** (see Setup Step 1.4's hard-gate note). Even in `auto_mode: true`, this one-time setup question is required — auto-mode skips the *per-iteration* restart pauses, not the one-time question that defines how the restart happens. Reply must be a real shell command OR the literal `"manual"`. Do not silently default to "hope the user restarted."
- **Websocket / `file` variant — confirm which file is the live source before any `Edit`.** The IDE-opened file is a hint, not authority. Grep the workspace for the system-prompt string constant; if >1 file matches, ask which is live. Files named `original_*.py`, `*.bak`, `*.snapshot.py`, anything under `archive/` or `backup/` are strong "probably not the live source" signals — pause and confirm rather than editing them.
- Self-hosted / websocket / offline variant — there is no automated path to re-collect failures, so the skill must ask for pasted failures after each iteration.
- The skill needs to widen the validation set, switch input types mid-loop, or change the validation comparison set in any way — never silent in either mode.
- Oscillation is detected (same scenario flipping pass/fail across iterations) or a no-change signature appears (identical post-edit failures two iterations in a row). Surface and pause; do not burn the iteration cap.
- **Same failure shape persists across three consecutive iterations** — stop iterating at the same edit surface and escalate to a *larger* change. After two no-change iterations the prompt/tool layer has demonstrably failed to fix the issue; a third same-shape failure is the cue to surface architectural alternatives instead of producing iter 4 of the same kind of edit. Concretely: (a) switch to a stronger model (e.g. `gpt-4o-mini → gpt-4o`, a single-line edit in the user's code or a Cekura agent config field); (b) add a programmatic guard in orchestration code that enforces the missed behavior deterministically (websocket / `file` only); (c) restructure the agent flow into explicit named states gated on collected fields rather than relying on natural-conversation prompting; (d) split the scenario into a narrower validation set and hand off to `cekura-eval-design` if the evaluator is the issue. Present these options to the user; do not pick one autonomously, since each carries real cost (model swap → ~10× per-token spend, programmatic guard → invasive code, flow restructure → larger refactor). The exception is when the user has already explicitly directed one of these paths — then proceed.
- Most kept failures cluster on one or two metrics whose explanations look subjective — hand off to `cekura-metric-improvement` instead of iterating blindly.
- All kept failures classify as Upstream/data — surface the hand-off and stop the loop early; do not propose phantom prompt edits.
- A diagnosis is low-confidence ("could be Conflict or Ambiguity, depending on intent") — ask the user to disambiguate rather than guessing.

When in doubt, ask. A short clarifying question costs less than a wrong PATCH against a live agent or a wasted iteration. The "don't pre-emptively pause" rule applies to *per-iteration* user-side gates only — auto mode runs validation directly after each apply without asking "have you restarted?" each time, because the one-time `redeploy_command` collected at Setup Step 1.4 either handles the restart automatically (real command) or has explicit user buy-in to a manual cadence (`"manual"` sentinel). Do NOT use this rule to skip Setup Step 1.4 itself, or to skip clarifying which file is the live source — those are one-time setup questions, not per-iteration pauses.

## Orchestration flow

The orchestrator runs the referenced files in sequence, with the loop point at Eval handing back to Optimization · Collect:

1. **Setup** — load [`phases/setup.md`](phases/setup.md) and walk through Steps 1.1–1.4. On completion, verify the Setup completion checklist before continuing.
2. **Optimization · Collect (iteration N)** — load [`phases/optimization/collect.md`](phases/optimization/collect.md) and walk through Steps COLLECT.1–5. On iteration 1, reads the raw input (`scenario_ids` / `result_id` / `run_ids` / `call_ids` / pasted failures). On iteration 2+, reads the failure set Eval handed back. Produces the kept failure set + Signal-5 end-of-call attribution per failure.
3. **Optimization · Early-End-Call Diagnose (iteration N)** — load [`phases/optimization/early-end-call-diagnose.md`](phases/optimization/early-end-call-diagnose.md) and walk through Steps EARLY.1–3. Flags failures matching the early-end pattern, diagnoses the responsible layer (prompt closure rules / orchestration-code end-of-call detection / VAPI handoff), proposes minimal fixes. Pass-through if zero failures match.
4. **Optimization · Diagnose (iteration N)** — load [`phases/optimization/diagnose.md`](phases/optimization/diagnose.md) and walk through Steps DIAGNOSE.1–5. Classifies every non-early-end failure (Gap / Conflict / Ambiguity / non-early-end CodeBug / Upstream), proposes minimal edits, de-conflicts with early-end proposals, and presents the combined diff to the user. If the combined proposal is empty (all-Upstream or all-KEEP), stop the loop here — skip Apply / Sync / Gate / Eval and surface upstream hand-offs.
5. **Optimization · Apply (iteration N)** — load [`phases/optimization/apply.md`](phases/optimization/apply.md) and walk through Steps APPLY.1–2. Lands the combined edit set per-provider; runs `redeploy_command` (or fires manual restart gate) for self-hosted live targets. A non-zero `redeploy_command` exit halts here for user decision.
6. **Optimization · Sync (iteration N)** — load [`phases/optimization/sync.md`](phases/optimization/sync.md) and walk through Step SYNC.1. Re-fetches the just-edited artifacts and verifies each changed field landed. Drift rolls back to Apply.
7. **Overfitting Gate (iteration N)** — load [`phases/overfitting-gate.md`](phases/overfitting-gate.md) and walk through Steps GATE.1–7. Inventories this iteration's edits, scores them against five overfitting signatures (verbatim transcript quote, scenario-specific identifier, hardcoded test-data value, hyper-narrow case clause, transcript-cloned few-shot example), decides REVISE / STRIP / KEEP per flagged edit, and applies cleanup edits if needed. On no-flag iterations the gate is a one-line pass-through to Eval (no extra apply round-trip). Code-stream edits (websocket / `file` orchestration code) and pure-deletion edits are not scored by the gate.
8. **Eval (iteration N)** — load [`phases/eval.md`](phases/eval.md) and walk through Steps EVAL.1–4. Eval's Step EVAL.4 emits exactly one of these decisions:
   - **Exit (success)** — 100% pass on the full set (after the regression sweep, when applicable). Report cumulative diff + iterations used. Stop.
   - **Exit (stop condition)** — iteration cap hit, oscillation detected, no-change signature for the second time, 3× same-shape failure, all-Upstream re-classified, or stochastic flake. Surface to the user and stop.
   - **Hand back to Optimization · Collect** — failure set still has failures (post-iteration or post-regression-sweep). Re-enter step 2 above with the new failure summary as input. Increment iteration counter.

When `auto_mode: false`, every Step DIAGNOSE.5 (combined proposal approval) AND every Step GATE.5 (gate cleanup approval) is a user-gated decision. All other phase boundaries happen automatically once their phase completes.

When `auto_mode: true`, the routine diff-approval gate at Step DIAGNOSE.5 and the routine cleanup approval at Step GATE.5 are both skipped (still rendered for transparency, then auto-accepted). The Setup hard gate at Step 1.4 is NOT skipped. The Gate's tension-case pause ("REVISE would invalidate the fix") and the large-strip-set pause ("gate would strip > half the iteration's edits") fire even in auto mode. Every "ask for feedback or clarification" trigger from the list above still pauses the orchestrator.

**Announce every phase entry in your user-facing output.** At each phase boundary state which iteration and phase you are entering — e.g., a one-line header like `Iteration 3 · Overfitting Gate` or a sentence that names the phase as you begin its first step. This is a hard requirement, not stylistic — a missing announcement in the trace is the same signal as a missing phase, and it is the single most effective check against silently skipping a phase. The Overfitting Gate is the most-skipped phase on iter 2+ (the iteration feels incremental, the previous-iter Gate was a pass-through, and the orchestrator is tempted to apply-and-validate without re-walking the full pipeline); naming the phase before doing its work makes the elision impossible. Re-load the phase file (`Read` on the relevant `phases/...md`) on each entry rather than working from memory — phase files carry pre-flight checklists that catch upstream-incomplete states, and those checklists are useless if the orchestrator never re-reads them. Cost is one line per phase boundary plus one Read per phase per iteration.

## Common Pitfalls

- **Parallelizing across phase boundaries.** Pre-fetching artifacts a later phase will consume — most commonly fetching the `result_id` payload during Setup, but also reading the source file before Diagnose has classified failures, or running validation before Sync verified the writes landed — produces work against premature assumptions and makes failures harder to localize. Each phase's pre-conditions are the previous phase's outputs; enter phase N+1 only after phase N completes. Batching independent tool calls *inside* a single phase step is fine (e.g., fetching multiple VAPI tool definitions during Setup Step 1.3); the rule is about phase boundaries.
- **Skipping Setup Step 1.4 in self-hosted modes — the deploy-path foot-gun.** Setup Step 1.4 collects `redeploy_command` and is a HARD GATE before Optimization · Collect; auto-mode does NOT skip it. The failure mode looks like this: edits land in the user's file, the live process still runs the old code, validation comes back with transcripts that *look* slightly different (different LLM nondeterminism) but the same bullets failing for the same reasons. You then attribute the persistent failures to "weak instruction-following" and write stronger prompt edits — the wrong root cause. The skill burns its iteration cap iterating on prompts that never reach the live agent. Auto-mode's no-change detector (Eval Step EVAL.3) is a backstop, not a primary control — by the time it fires, real iterations are already spent. **Fix**: before Optimization, the run state MUST have either (a) `redeploy_command` set to a shell command the skill will run after every apply, OR (b) `redeploy_command == "manual"` with user buy-in to the per-iteration restart pause. Ask once, at Setup Step 1.4. Don't conflate "skip the *per-iteration* restart pause" (which auto-mode does) with "skip the *one-time* setup question" (which it must not).
- **Editing the wrong source file in websocket / `file` variant.** Trusting the IDE-opened file as authoritative without grepping the workspace for the system-prompt string constant. Filenames like `original_*.py`, `*.bak`, `*.snapshot.py`, anything under `archive/` / `backup/` / `old/` are strong "not the live source" signals — pause and confirm before editing. Symptom is identical to the Setup Step 1.4 skip above: edits land in a file the server doesn't read. **Fix**: always grep for the prompt constant (e.g. `SYSTEM_PROMPT = {` or whatever the constant is named). If grep returns >1 hit, ask which is live. The IDE pointer is a hint to start from, not authority.
- **Treating an iter-1 result that looks "slightly improved" as confirmation that edits landed.** If iter 1 flips a small number of scenarios but the remaining failures show the same bullets failing for the same reasons with transcripts within nondeterminism distance of the originals, the most likely explanation is that edits DIDN'T reach the live process — not that the prompt change was "directionally right but too weak." Strengthening the prompt in iter 2 in this state is the wrong move. Verify the deploy path first (Setup Step 1.4's `redeploy_command` actually ran without error; the file you edited is the file the server reads).
- **Asking the user to redeploy / restart / re-apply before triggering evals in auto mode.** `auto_mode` is on by default and skips BOTH the diff-approval gate AND the *per-iteration* user-side deployment pauses. The skill proceeds straight to validation. Don't render "before continuing, redeploy your server" instruction blocks in the default path. If results come back unchanged, surface the no-change hypothesis *after the fact* (Eval Step EVAL.3 already does this). **This rule applies only when Setup Step 1.4 has already resolved `redeploy_command`** — it does NOT license skipping Setup Step 1.4 itself.
- **Exiting on failure-set 100% without running the regression sweep.** A 2/2 pass on the originally-failing subset is a milestone, not the finish line. The exit gate is 100% on the **full set** (every scenario the user originally provided), and the only way to confirm that is to actually run the full set after the failure subset hits 100%. Skipping the sweep masks regressions where an edit fixed scenarios A & B but broke scenario C. Eval Step EVAL.4's decision tree enforces this — never declare success on failure-set 100% alone.
- **Skipping the early-end-call-diagnose sub-phase or treating it as redundant with diagnose.** The two sub-phases are NOT interchangeable. Early-end is triaged first because the pattern dominates any other diagnosis on the same scenario — if the call ended at turn 4 of a required 8-step scenario, prompt edits targeting step-5-onward behavior are wasted work. Diagnose explicitly skips the early-end CodeBug pattern (Step DIAGNOSE.3 notes this); without the early-end sub-phase, those failures fall through unclassified and get attributed to weak instruction-following.
- **Treating auto mode as fully silent.** Auto mode skips *routine* gates, NOT the skill's responsibility to ask for clarification on genuinely ambiguous inputs or risky decisions. Ambiguous mode resolution, prompt-source ambiguity (which file? which variable?), low-confidence diagnoses, oscillation, no-change signatures, all-upstream failure sets, and metric-quality clusters all require an explicit pause-and-ask.
- **Auto mode masking diagnosis quality.** Without the per-iteration human read on the diff, a bad diagnosis lands silently and shows up only as a failed re-validation. Treat oscillation and no-change signatures as harder stops in auto mode — surface and pause rather than burn the iteration cap.
- **Producing iter 4 of the same edit kind after three same-shape failures.** When the same scenario fails with the same sub-outcome bullet across three consecutive iterations of prompt-layer (or tool-config-layer) edits, the layer being edited is demonstrably not the layer that fixes it. Keep going and you're paying compute to confirm a known result. Eval Step EVAL.4 case 6 mandates a stop: present architectural alternatives (model swap, programmatic guard, flow restructure, evaluator hand-off) and wait for the user to choose. Don't autonomously pick one — each has real cost. Also don't paper over the situation with "let me try once more, slightly stronger wording" — that is iter 4 of the same edit kind.
- **Forcing `auto_mode: false` for routine work.** The diff-approval + deployment-gate pauses are useful when calibrating the skill against a new agent. For repeat use against an agent whose diagnosis quality you've already validated, the default `auto_mode: true` is correct.
- **Proposing tool-config edits in the offline variant.** Only prompt edits are valid there — tool findings must be surfaced as upstream hand-offs, not edits.
- **Proposing VAPI-shaped edits in self-hosted modes.** Spoken `messages` (`request-start`, `request-complete`, `request-failed`), handoff `destinations`, squad `model.toolIds` — none of these exist outside VAPI. Diagnose must filter these edit candidates out for self-hosted mode.
- **Treating Cekura's `description` as the source of truth in websocket mode.** It is at best a mirror; the live prompt is in the user's source code. Editing the description does nothing to the live agent unless the user's code reads from it.
- **Reading `llm_system_prompt` from the Cekura agent record in self-hosted mode, or asking the user to paste their prompt.** For `assistant_provider == "self_hosted"` (websocket), `llm_system_prompt` is almost always empty — the live prompt lives in the user's workspace (source file). Do NOT pull `llm_system_prompt` and do NOT ask "paste your current system prompt so I can run improve-prompt against it." Instead, locate the prompt in the workspace: first the IDE-opened file (`ide_opened_file` context), then grep project files for the prompt string constant, and edit it directly via the `Edit` tool. Asking the user to paste is only acceptable in the explicit `offline` variant where no workspace is reachable.
- **Applying `Edit` with a non-unique `old_string` in websocket / `file` variant.** The Edit tool fails on ambiguous matches. Use enough surrounding context (5–10 lines on either side) for every anchor.
- **Hallucinating variable-injection findings without runtime state.** Especially common in the websocket / `offline` variant. Don't claim "the runtime didn't receive `{{accountId}}`" unless the transcript itself shows the placeholder leaking.
- **Shortcutting Optimization · Collect Step COLLECT.3 by reading result-level summary fields instead of per-run `evaluation_status`.** A `results_retrieve` payload exposes both: per-run `evaluation_status` (post-review, authoritative) AND result-level aggregates (`failed_workflow_runs`, `failed_reasons.issues`, `failed_runs_count`, `success_rate`) computed from raw machine scores **before** human review. The aggregates lump `failure` and `reviewed_success` into the same buckets — using them silently smuggles human-overridden passes into the kept set and produces edits that contradict the reviewer. The four-bucket filter only works when applied to each run's own `evaluation_status`. Same rule for `run_ids` (use per-item verdict) and `call_ids` (use per-log verdict). The Step COLLECT.5 funnel line must cite `per-run evaluation_status` as the source so the skip is auditable.
- **Skipping the variable-state inspection (Optimization · Collect Step COLLECT.4) and mapping failures only to prompt sections.** Produces phantom prompt fixes for failures actually rooted upstream. Also breaks the early-end-call-diagnose sub-phase, which depends on Signal 5 (end-of-call attribution) being captured in COLLECT.4.
- **Quitting the loop the moment failures look non-prompt.** The exit gate is 100% pass rate or the iteration cap — not "first sight of an infra-shaped failure." Re-classify with fresh eyes before declaring upstream. In websocket / `file` mode, also check whether the failure is a **CodeBug** (history truncation, missing forwarding, broken state) — those are in-scope for editing, not hand-offs.
- **Iterating prompt-wording when the diagnosis is CodeBug.** If oscillation or a no-change signature surfaces and the failure shape matches a CodeBug signal (agent forgets earlier turns, agent ignores explicit don't-re-ask rules despite the prompt being clear, etc.) — stop iterating the prompt. Move to the orchestration-code stream. Repeated prompt-only edits will not converge if the plumbing prevents the agent from following the instructions.
- **Touching business logic, auth code, or dependencies in websocket-mode code edits.** Orchestration-code edits are scoped to plumbing: history management, message wiring, state preservation, keepalive. Tool implementation bodies, API keys / auth code, secrets handling, dependency lists, and framework imports remain out of scope. When in doubt, hand off rather than edit.
- **Proposing code edits in VAPI or websocket `offline`.** The orchestration-code stream exists only for websocket / `file`. In other modes, code-shaped findings become upstream hand-offs — the skill cannot reach VAPI infrastructure code, and the offline variant has no live file to edit.
- **Skipping the per-iteration user gate in `auto_mode: false`.** The skill applies edits to a live agent. Every PATCH / Edit must be preceded by explicit approval of *that iteration's* proposed diff.
- **Skipping the Optimization · Sync Step SYNC.1 re-fetch.** VAPI's PATCH semantics replace nested objects wholesale; a malformed body can silently wipe `messages` or `destinations` while returning 200. For websocket / `file`, an `Edit` call with an ambiguous anchor can land in the wrong spot. Always re-read and verify.
- **Editing dynamic-variable placeholders (`{{...}}`).** They're owned by the calling system. Touch them only if the user explicitly asks.
- **Patching a tool's spoken `messages` to mask a prompt issue.** If the agent says the wrong thing, fix the prompt — unless the tool's `request-start` message is itself the offending utterance.
- **Iterating with a noisy metric.** If most kept failures come from one metric whose explanations look subjective, the metric is probably miscalibrated — hand off to `cekura-metric-improvement` first.
- **Surfacing small-sample / overfitting caveats.** Internal calibration of confidence is fine; user-facing hedging reads as a stall. Note that *mechanical* overfitting in proposed edits (verbatim transcript quotes, scenario IDs in the prompt, hardcoded test-data values) is a different concern — the Overfitting Gate phase handles that automatically by scrubbing the just-applied edits before Eval. The "no caveats" rule applies to user-facing language about worry; it does not turn off the gate's mechanical scrub.
- **Skipping the Overfitting Gate or treating it as a one-shot pre-flight.** The gate runs every iteration where Optimization produced non-zero edits. On no-flag iterations it's a one-line pass-through; on iterations where the LLM diagnosing pulled phrasing directly from the failing transcripts, it's the only thing standing between a memorized fix and a passing-but-non-generalizing agent. Do not short-circuit the gate to "save time" — its cost when there's nothing to scrub is negligible. **The drift is most likely on iter 2+** when later edits feel incremental, the previous-iter Gate was a pass-through, and the orchestrator is tempted to apply-and-validate without re-walking the full pipeline — that is exactly when transcript-leak risk compounds (the LLM has now seen the failing transcripts on multiple diagnoses). The countermeasure is the phase-announcement rule in the Orchestration flow section above: if you can't point to the line in your output where you said "Iteration N · Overfitting Gate", you skipped it. Also: a new or revised system-prompt string literal embedded in a source file (e.g., a `SYSTEM_PROMPT = {...}` or an `OVERRIDE_PROMPT = {...}` block) is a prompt edit and MUST be scored — only orchestration-control-flow code is skipped within the Gate.
- **Treating expected-outcome failures and metric failures the same.** Expected-outcome failures are first-class signal about agent behavior; metric failures may reflect either the agent or the metric.
- **Mass-deleting "unused"-looking tools.** A tool with no references in this agent's squad members may still be referenced elsewhere. Prefer reference removal over delete.

## Next Steps

After this skill, the user typically needs:

- For tool / KB / provider-integration issues surfaced in Eval Step EVAL.4 → invoke **cekura-create-agent**
- For metric-quality issues (noisy or miscalibrated metric judges) → invoke **cekura-metric-improvement**
- For test-suite gaps (the eval set itself is too narrow) → invoke **cekura-eval-design**
- For metric definition / design questions → invoke **cekura-metric-design**

## Documentation

- Public docs: https://docs.cekura.ai
- Concepts: https://docs.cekura.ai/documentation/key-concepts/
- Integrations: https://docs.cekura.ai/documentation/integrations/
- VAPI assistant API: https://docs.vapi.ai/api-reference/assistants
- VAPI tool API: https://docs.vapi.ai/api-reference/tools

## Directory Layout

```
cekura-self-improving-agent/
├── SKILL.md                                  # this file — orchestrator (loop point: Eval → Optimization · Collect)
├── phases/
│   ├── setup.md                              # Resolve mode, fetch agent, collect redeploy_command
│   ├── optimization/
│   │   ├── collect.md                        # Fetch + filter failures + inspect provider call state (incl. Signal 5)
│   │   ├── early-end-call-diagnose.md        # Triage main-agent-ended-early failures → closure-rule / code edits
│   │   ├── diagnose.md               # Classify Gap/Conflict/Ambig/CodeBug-other/Upstream → propose → present
│   │   ├── apply.md                          # Land combined edit set → redeploy
│   │   └── sync.md                           # Re-fetch + verify; drift rolls back to apply
│   ├── overfitting-gate.md                   # Scrub the just-applied edits for transcript/scenario overfitting
│   └── eval.md                               # Build validation set → run → re-collect → decide loop/exit/sweep
├── agents/                                   # MCP-agnostic helpers
└── providers/
    ├── vapi/
    │   ├── overview.md                       # VAPI-mode editable surfaces, anti-patterns
    │   ├── phase-1-fetch.md                  # assistant/squad/tool fetch curl bodies, edge cases
    │   └── phase-4-apply.md                  # PATCH/POST/DELETE curl bodies, loop guardrails
    └── self-hosted/
        ├── overview.md                       # self-hosted overview, shared characteristics
        └── websocket.md                      # websocket sub-flavor — file Edit + restart gate; offline variant
└── references/                               # cross-cutting (shared by every phase)
    ├── phase-2-failure-collection.md         # failure summary template, metric hand-off
    ├── phase-3-diagnosis.md                  # classification table, before/after templates
    └── dynamic-variables-debugging.md        # variable-state per-signal decision tree
```

### Phase Files (loaded on demand)

- **[`phases/setup.md`](phases/setup.md)** — Mode and sub-flavor resolution, agent fetch per provider, `redeploy_command` hard gate, Setup completion checklist.
- **[`phases/optimization/collect.md`](phases/optimization/collect.md)** — Scenario execution wait, fetch runs / call logs, verdict pre-filter (per-run `evaluation_status`), voice-channel filter, accumulate, provider call-state inspection with Signals 1–5 (including end-of-call attribution), failure summary.
- **[`phases/optimization/early-end-call-diagnose.md`](phases/optimization/early-end-call-diagnose.md)** — Two-check verdict-first triage ({main-agent-ended + scenario-incomplete in expected-outcome bullets}; no rationale, no borderline cases), diagnose responsible layer (closure rules / orchestration code / VAPI handoff), propose minimal early-end fixes. Pass-through if no matches.
- **[`phases/optimization/diagnose.md`](phases/optimization/diagnose.md)** — Re-read the agent's prompt + tool config, map non-early-end failures to those artifacts + variable state, classify (Gap / Conflict / Ambiguity / non-early-end CodeBug / Upstream), propose minimal scoped edits, de-conflict with early-end proposals, present the combined diff.
- **[`phases/optimization/apply.md`](phases/optimization/apply.md)** — Apply the combined edit set per-provider machinery, then run `redeploy_command` (or fire manual restart gate). Non-zero exit halts.
- **[`phases/optimization/sync.md`](phases/optimization/sync.md)** — Re-fetch / re-read just-edited artifacts, verify each changed field landed. Drift handling per failure mode; rolls back to apply on drift.
- **[`phases/overfitting-gate.md`](phases/overfitting-gate.md)** — Inventory the just-applied edits, score against five overfitting signatures (verbatim transcript quote, scenario-specific identifier, hardcoded test-data value, hyper-narrow case clause, transcript-cloned few-shot example), decide REVISE / STRIP / KEEP, apply + sync cleanup edits when needed; pass-through when no flags.
- **[`phases/eval.md`](phases/eval.md)** — Validation-set construction (failure set vs. full set), validation execution, failure re-collection, decision tree (loop / sweep / exit / stop condition), iteration cap.

### Reference Files (loaded on demand)

- **[`providers/vapi/overview.md`](providers/vapi/overview.md)** — VAPI editable surfaces, what's PATCHable directly, anti-patterns.
- **[`providers/vapi/phase-1-fetch.md`](providers/vapi/phase-1-fetch.md)** — Provider-gate error message shapes, VAPI assistant + squad + tool fetch curl bodies, member summary template, Setup phase edge cases.
- **[`providers/vapi/phase-4-apply.md`](providers/vapi/phase-4-apply.md)** — VAPI PATCH / POST / DELETE curl bodies, tool-backup pattern, validation-set construction, loop guardrails, iteration-cap exit messaging.
- **[`providers/self-hosted/overview.md`](providers/self-hosted/overview.md)** — Self-hosted umbrella; self-hosted routes to websocket.
- **[`providers/self-hosted/websocket.md`](providers/self-hosted/websocket.md)** — Websocket sub-flavor gate, source-file discovery, `Edit`-based apply path, restart-server gate, pasted-prompt / pasted-failures degenerate `offline` variant, websocket-specific edge cases.
- **[`references/phase-2-failure-collection.md`](references/phase-2-failure-collection.md)** — Full failure-summary template, the metric-improvement hand-off wording, edge cases (no failures / all-errored / mixed inputs), and the no-overfitting-caveats rule.
- **[`references/phase-3-diagnosis.md`](references/phase-3-diagnosis.md)** — Full classification table with examples, before/after templates per edit surface, tool-edit anti-patterns, the manual-vs-automated-improver guidance, Optimization-phase anti-patterns.
- **[`references/dynamic-variables-debugging.md`](references/dynamic-variables-debugging.md)** — Per-signal decision tree for variable state, where each signal lives in the Cekura payload, the direct-VAPI fallback, the `runs_bulk_retrieve` bare-string gotcha, squad per-member-message caveats.
