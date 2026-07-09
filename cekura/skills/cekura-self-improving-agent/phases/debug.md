# Debug — Establish the Root Cause

Runs **once**, after Setup (and Clone), **before** Reproduce. One job: establish *what is broken and why*. Debug never edits the target and never chooses a fix — selecting and scoping an edit is the Optimization loop's **Fix** step, which runs strictly after the harness fails.

## Entry (on the signal)

- **Cause supplied** (diagnosed code bug, or a user-stated cause) → consume as-is; do not re-derive. Confirm only that the named responsible path exists, then hand off.
- **Cause to derive** (prod call, simulation run, pasted failure) → derive it below.
- **Render-only** → the pasted verdicts are the cause; keep it light.

## Derive

Full picture before any theory:

1. **Orientation** — fetch the failing call / run record: status, transcript, ended / termination reason, failing metrics or expected-outcome bullets, agent + scenario refs, dynamic-variable / tool-call trace.
2. **Authoritative telemetry** — pull the logs / traces / DB state the target exposes around the failure window (search by call / session / run id + timestamp), including the **lead-up**, not just the symptom. Orientation records are never the root cause; telemetry is.
3. **Cross-reference** telemetry against the transcript turn-by-turn to pin the divergence. Cite the exact evidence before naming a cause.

## Gate

Produce a **root-cause summary** — input, what the target did wrong, evidenced cause, responsible surface (prompt / tool config / owned code / upstream variable), failing metrics / bullets — plus the **failure class** (LLM-behavioral vs. infra / code), which Reproduce reads to shape the harness. Present and confirm. In `auto_mode`, render it and **proceed to Reproduce** — pause only if the *root cause* is ambiguous or low-confidence. Multiple *possible fixes* is **not** a pause reason; choosing among fixes is Fix's job and never happens before the harness fails.

## Hand-off to Reproduce

Pass the root-cause summary + responsible surface + failure class. If the cause is **owned code**, Reproduce still builds a Cekura evaluator and forces the bug's trigger to fire in the simulation (REPRO.3e) — never a code test.
