# Phase 5 · Improve loop — propose → plan → apply → attest → verify

Entered after Reproduce's must-fail gate passes. One pass below = one
iteration; announce `Iteration N · Improve`. Diagnosis semantics (failure
classes Gap / Conflict / Ambiguity / CodeBug / Upstream, early-end triage,
smallest-scoped-change, same-shape escape hatch) are identical to
`cekura-self-improving-agent` `phases/optimization/fix.md` — reuse them. This
file defines what changes under the manifest framework.

## LOOP.0 — reproduction gate check (every iteration, before anything else)

Read `repro.json` from the audit dir. Refuse to propose — return to
Reproduce — unless ALL hold:

1. The file exists and its `result_id` retrieves via
   `mcp__cekura__results_retrieve`.
2. The fail count satisfies the recorded mode's gate: `deterministic` → 1/1
   failed; `stochastic` → ≥ 2 fails on the batch (or the user's explicit
   `repro_threshold` override).
3. The gate line is restated verbatim at the top of this iteration's output:
   `Repro gate: result <result_id> — <fails>/<n_runs> failed (mode: <mode>)`.

A proposal without a passing LOOP.0 is invalid regardless of how compelling
the diagnosis is. Failing unit/code tests, log analysis, or the original
production calls do not pass this check — only the Cekura simulation result
does. This check repeats every iteration precisely because agents under time
pressure reinterpret prose gates; the artifact is the gate.

## LOOP.1 — propose

- Re-read each touched component's source if stale (>few minutes).
- Map every kept failure to a **component** in the manifest. Failures mapping
  to no component are manifest gaps: report, hand off, never edit blind.
- Produce a structured edit proposal per component: component name, editable
  target (file/row/version), before → after, rationale, failure ids addressed.

## LOOP.2 — plan diff (blast radius)

Render before applying anything:

1. **Source diff** per component.
2. **Rendered diff**: run `render_intended` against a scratch copy where
   possible, else after apply but before deploy — template expansion can turn
   a small source edit into a large runtime change.
3. **Blast-radius summary**: components, files, environments touched.
4. The LOOP.0 gate line is present in the presented diff header.
5. Hard checks: nothing outside `authority.allowed_paths` — and if
   `allowed_paths` is absent, **no file writes at all** (component `apply`
   commands are then the only mutation path); nothing in `forbidden_paths`;
   no secret-looking strings in the diff (redact policy); no
   `production: true` environment referenced.

`auto_mode: true`: render and proceed. `auto_mode: false`: wait for approval.
Zero edits (all Upstream) → stop the loop, report.

## LOOP.3 — apply + validate

- Apply per component by its declared mode: `file_patch` via Edit on the
  session branch; `command` via the registered apply command (proposal fed on
  stdin, never interpolated); `manual` → pause with exact instructions and
  wait for "done".
- Repo components: commit (`selfimprove iter {N}: <summary>`).
- Run `validate` (dry-run) if declared; non-zero → fix the proposal, do not
  deploy broken config.

## LOOP.4 — deploy + attest (the invariant that makes verification real)

1. Deploy to the session's non-production target (or noop for live-on-save).
   Non-zero exit halts the iteration — never swallow it.
2. `read_live`; compare against the fresh `render_intended` output. Mismatch
   beyond `attestation.acceptable_differences` = **drift**: do not verify;
   re-apply once, then stop as `manifest_invalid` if it persists.
3. Confirm identity continuity: the runtime identity (`produces`) matches what
   the simulation runner will hit. Record all three hashes (source, rendered,
   live) in the audit trail — verify batches only count against these hashes.

## LOOP.5 — verify

- `reset_fixtures` before the batch (customer mock server reset/seed). A
  failed reset → batch invalid, retry; never count invalid batches.
- Run the failure set via `simulate.runner`, N runs per scenario
  (`stochastic_runs`). Apply `flake_policy`: infra-classified errors are
  retried up to `max_infra_failures`, discarded runs are counted and reported.
- Trace correlation per batch: the traces must reference the attested runtime
  identity. A batch that hit something else is invalid.
- Pass follows the reproduction mode: `deterministic` → 2/2 passes with the
  forced trigger / `CEKURA-REPRO-INJECT` injection still active; `stochastic`
  → passes ≥ `verify_threshold` of N.

## LOOP.6 — overfitting gate

Identical to `cekura-self-improving-agent` `phases/overfitting-gate.md` (five
signatures, STRIP/REVISE/KEEP), applied to the **source** edits. Cleanup edits
re-enter LOOP.3–4 (including a fresh attest) before re-verify.

## LOOP.7 — decide

- Failure set < 100% → next iteration (back through Collect re-entry).
- Failure set = 100%, no sweep yet → run the full set once.
- Full set = 100% → Regression phase.
- Regression on the sweep → hand the regressed scenarios back as the new
  failure set, scope narrower.
- Stops: `max_iterations`, oscillation, no-change signature (a no-change with
  a deploy step present → stale-deploy hypothesis: re-run LOOP.4 attestation
  before concluding wrong-root-cause), same shape 3×, all-upstream.
- On any stop or convergence: restore/report best state honestly. Repo
  components sit on the session branch (nothing to revert on the mainline);
  command/DB components — if the final state is not the best state, run their
  declared `rollback` and re-attest.
