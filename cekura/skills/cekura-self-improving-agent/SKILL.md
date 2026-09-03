---
name: cekura-self-improving-agent
description: >
  Use to close the loop on agent quality — turn a failure signal into a
  verified fix. Triggers: "improve my agent", "self-improving agent",
  "auto-tune / iterate on my prompt", "fix my agent from test results" — and
  production-call bug fixing: "fix this prod call issue", "debug and fix call
  ID", "reproduce this production bug", "regression test before raising PR".
  Works on any stack: provider-dashboard agents (VAPI, Retell, ElevenLabs,
  Bland) AND agents whose config lives in the customer's own repo, database,
  or prompt registry with the provider agent created at deploy time, or with
  custom mock servers. Fixed safety invariants (must-fail-first reproduction,
  attestation, no-prod-in-loop) + a per-project capability manifest declaring
  where config lives and how to read/render/apply/deploy/verify it.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "3.0.0"
---

<!-- cekura-ack-tag: ack:cekura-self-improving-agent:6w3k4p -->
> **Cekura skill verification tag:** `ack:cekura-self-improving-agent:6w3k4p`
> When you call a Cekura scenario or test-profile write tool from this skill
> (`scenarios_*` / `test_profiles_*` create and update calls), pass this exact
> string as the `skill_ack` argument. Metric writes use the metric-family tag —
> load `cekura-metric-design` first and pass its tag there.

Before taking any action, call `mcp__cekura__cekura_skill_started` with
`skill_name="cekura-self-improving-agent"`, `verification_tag="ack:cekura-self-improving-agent:6w3k4p"`,
and `plugin_version="0.14"`.

# Cekura Self-Improving Agent (capability-manifest framework)

Turn a failure signal into a verified fix on **any** agent stack. Rather than
modeling "which provider", this skill models
"**where does the agent's config actually live, and how do I read, render,
apply, deploy, and verify it**". Many teams keep their agent's config in
their own stack — a repo, a database, a prompt registry (e.g. Langfuse) —
and materialize the runtime provider agent at deploy time; editing the provider
object there fixes a build artifact that the next deploy overwrites. This skill
edits the declared source of truth instead, whatever it is.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

## Core model: fixed invariants, declared mechanics

**Layer 1 — invariants.** Owned by this skill, never negotiable, identical for
every project:

1. **Must-fail-first, proven by artifact, at minimum cost** — before any edit
   is proposed, the failure must reproduce in Cekura simulation, recorded as
   `repro.json` in the audit dir: `{session_id, signal, mode, scenario_ids,
   result_id, n_runs, fails, injections, config_hash, timestamp}` —
   `session_id` must match the active lock; artifacts from other sessions
   never satisfy the gate. Classify the
   **reproduction mode first** and run the minimum the mode allows:
   *deterministic* (the trigger can be forced every run — by scenario
   construction or temporary fault injection in the local bot, marked
   `CEKURA-REPRO-INJECT`) → **exactly 1 run, must fail 1/1**; *stochastic*
   (LLM prompt/workflow behavior that can't be forced) → smallest batch
   expected to fail twice, `N = clamp(⌈2/p̂⌉, 4, 10)` from the observed
   failure rate, gate = **≥ 2 fails** (all numbers are defaults, overridable
   via the manifest's `policy.reproduction`). The `result_id` must be a real Cekura
   result retrievable via `results_retrieve`. **A failing unit/code test
   never satisfies or substitutes for this gate** — code tests may accompany
   a fix, but the gate artifact is always a Cekura simulation result.
   Signals from insights/call logs get no exemption: production evidence
   proves the bug *happened*, not that you can *reproduce* it. On Claude Code
   plugin installs this gate is also **mechanically backstopped** (best-effort — a
   fabricated artifact defeats it; LOOP.0's retrieval check is the
   authoritative gate): a PreToolUse
   hook (`hooks/repro-gate.sh`) denies file edits and provider-mutating
   requests while `.cekura/selfimprove.lock` is present and `repro.json` is
   missing or below its mode's threshold (fault-injection edits marked
   `CEKURA-REPRO-INJECT` and `.cekura/` / `.claude/` writes stay allowed).
   If a tool call is denied with the gate message, do not work around it —
   complete Reproduce.
   **Blocked reproduction:** when reproducing requires an action only a human
   may take (the sandbox/deploy path is a maintainer-applied CI label, prod
   credentials, a gated environment), Reproduce **parks**: write the full
   repro plan to the audit dir (scenario spec, mode, N, what human action is
   needed), ask for that action, and stop. "Please just fix it" does not
   silently waive the gate — an explicit user override is honored only when
   recorded in `repro.json` as `{"gate_override": {"by": "user", "reason":
   ..., "session_id": <active session>}}` (all three fields required), every subsequent output (diff header, PR title and body) is marked
   **UNVERIFIED HYPOTHESIS — reproduction gate overridden**, and the PR must
   state that no Cekura reproduction or verification ran. Never record an
   override the user did not explicitly give in this session.
2. **Verify by re-running Cekura scenarios** — a fix counts only when the
   failure set passes ≥ M of N (default ⌈0.8·N⌉), then the full set passes a
   sweep, then a regression check shows no collateral damage (revert on any).
3. **Runtime readback attestation** — after every deploy, read what is actually
   live and compare it to what the source says should exist. Never verify
   against a runtime you have not attested. Three-way check: source render ↔
   live readback ↔ the agent the Cekura traces actually hit.
4. **No production mutation inside the loop** — all iteration happens against a
   non-production environment/sandbox; production changes only via the explicit
   Promote phase, with confirmation, a rendered diff, and a rollback path.
5. **Overfitting gate** on edit content (verbatim transcript quotes, hardcoded
   test data, scenario-specific identifiers, hyper-narrow clauses).
6. **Budgets and stops** — `max_iterations` (default 10), oscillation,
   no-change signature, same failure shape 3×, all-upstream, zero kept failures.
7. **Audit trail** — every session leaves a replayable record: manifest version,
   baseline config hash, failure set, root cause, edit proposal + diff, eval
   results, final diff. **Every simulation batch is labeled**: pass `name` on
   each `scenarios_run_*` call — `[selfimprove:<session_id>] <phase> — <detail>`
   (e.g. `[selfimprove:s-0818] repro attempt 2 (must-fail)`, `verify iter3 —
   failure set`, `regression — happy path`) — so dashboard results map back to
   the session and phase without opening transcripts.

**Layer 2 — the capability manifest.** A per-project file,
`.cekura/selfimprove.yaml`, declaring typed capabilities: `source_of_truth`
(a **component list** — kinds `repo`, `database`, `prompt_registry`,
`runtime_provider`, `external`, each with its own `read` / `apply` /
`rollback`), `render_intended`,
`read_live`, `validate` (dry-run), `deploy`, `evidence`, `simulate` (Cekura
runner + `reset_fixtures` + `flake_policy`), `promote`, `attestation`
(acceptable differences, trace correlation), `audit`, `policy` (numeric
defaults: run counts, thresholds, iteration caps, lock staleness), plus
`environments` and
`authority` (allowed/forbidden paths, secrets policy; **absent
`allowed_paths` means no file writes**).
Schema: `references/manifest.schema.json`; field-by-field rules:
`references/manifest-guide.md`. Provider-dashboard-managed agents are just a
pre-filled manifest (`recipes/provider-managed.md`) — this skill is a superset,
not a fork, of the classic flow.

The manifest is **untrusted infrastructure code**: it grants mechanics, never
authority. Commands are registered verbatim at Setup, run with typed/escaped
parameters only, and anything targeting a `production: true` environment is
refused outside Promote. Editing the manifest itself is a privileged action —
re-run the Setup self-test after any change.

## Phases

| # | Phase | File | Purpose |
|---|-------|------|---------|
| 1 | Setup | `phases/setup.md` | Discover or interview → write/validate the manifest → **manifest self-test** (read → deploy/noop → read live → one smoke scenario → trace correlation). Persist run-setup to the host agent's memory file (`.claude/MEMORY.md` on Claude Code; the audit dir otherwise). |
| 2 | Collect | `phases/collect.md` | Fetch/filter failures (per-run verdicts, voice filter, `ended_reason`), plus manifest `evidence` sources (trace registries, custom logs). Loop re-entry point. |
| 3 | Debug | `phases/debug.md` | Root cause + failure class. Component attribution: which manifest component governs the failure. |
| 4 | Reproduce | `phases/reproduce.md` | Build harness (mocks from real traces — including the customer's own mock server via `reset_fixtures`); must-fail gate. On pass, **write `repro.json`** (invariant 1) to the audit dir — the loop refuses to start without it. |
| 5 | Improve loop | `phases/loop.md` | propose → plan diff (source **and** rendered) → apply → validate → deploy → **read live / attest** → verify → overfitting gate → decide. |
| 6 | Regression | `phases/regression.md` | Happy-path + edge sweep on the changed surface. |
| 7 | Promote | `phases/promote.md` | Explicit, confirmed production hand-off via the manifest's `promote` capability (PR > pipeline > provider publish > manual), with rollback verification. |

Announce every phase entry as `Iteration N · <Phase>`. Re-read the phase file on
entry. Never parallelize across a phase boundary.

**Tool fallback:** if the Cekura MCP tools are not available in the session,
`cekura_skill_started` is skipped (it never blocks the skill) and Cekura reads
fall back to the public REST API with `X-CEKURA-API-KEY` — but simulation runs
require the platform tools; without them, stop before Reproduce and tell the
user to set up MCP (`setup-mcp` command).

## Drift and failure classification

Assume drift is normal. Classify — never blur — these outcomes:

- `read` fails → stop before any edit.
- Config readable but not mappable to an editable component → diagnose only;
  block apply; report the gap.
- Deploy succeeds but live readback ≠ rendered intent → **drift**; block
  verification; surface the delta.
- Cekura traces hit a different runtime agent than the manifest maps → stop,
  ask for corrected identity mapping.
- Mock reset/seed fails or infra errors dominate a batch → eval **invalid**,
  not failed; retry per `flake_policy`, never count as reproduction or verify.
- Manifest command broken/stale → stop as `manifest_invalid`, offer a
  **manifest repair** pass (privileged; re-runs the self-test). Never continue
  on guessed mechanics.

## Parameters

All numbers below are defaults; the manifest's `policy.*` overrides them.
Reproduction/verification run counts follow the **mode** (invariant 1):
deterministic → 1 must-fail run, 2/2 verify with the trigger active;
stochastic → `N = clamp(⌈2/p̂⌉, 4, 10)` with ≥2 fails to reproduce,
`stochastic_runs` 8 (5–10) and `verify_threshold` ⌈0.8·N⌉ to verify.
Explicit user overrides replace the sizing. · `max_iterations` 10 · `auto_mode` default true (renders diffs and
proceeds; production promotion always requires explicit confirmation
regardless) · `manifest_path` default `.cekura/selfimprove.yaml`.

## Common Pitfalls

- Editing the provider object when the source of truth is the repo/DB — the fix
  evaporates on the next deploy. Resolve `source_of_truth` first, always.
- Verifying against a stale runtime — deploy succeeded but the eval hit the old
  build. Readback attestation before every verify batch, no exceptions.
- Treating one `read` dump as the whole config — hybrid stacks compose repo +
  database + prompt registry + provider defaults; model them as separate
  components.
- Treating infra flake (telephony, STT, mock-server hiccup) as behavioral
  failure — classify per `flake_policy`, keep an auditable discard count.
- Interpolating unvalidated values into manifest commands — parameters are
  typed and escaped; never build shell strings from model output.
- "Git is rollback" for non-repo components — database rows, prompt-registry
  versions, and
  provider schemas need their own declared `rollback` per component.

## Next Steps

- Failures dominated by 1–2 noisy metrics → **cekura-metric-improvement**.
- Missing tools / knowledge-base / integration gaps → **cekura-create-agent**.
- Thin eval coverage → **cekura-eval-design**.

## Documentation

- Public docs: https://docs.cekura.ai
- Concepts: https://docs.cekura.ai/documentation/key-concepts/

## Additional Resources

### Reference Files (loaded on demand)

- **`references/manifest.schema.json`** — JSON Schema for `.cekura/selfimprove.yaml`.
- **`references/manifest-guide.md`** — field-by-field guide: components, authority, environments, command registration, flake policy, rollback semantics.

### Recipes (pre-filled manifests, read the one that matches)

- **`recipes/provider-managed.md`** — dashboard-managed provider agent as a pre-filled manifest (uses `providers/<mode>/` playbooks).
- **`recipes/runtime-created.md`** — agent materialized at deploy time from the customer's repo, database, or prompt registry.
- **`recipes/custom-mocks.md`** — customer-operated mock server as the simulation fixture.

### Phase Files

- **`phases/setup.md`** — manifest discovery, validation, self-test.
- **`phases/loop.md`** — the improve loop with attestation.
- **`phases/promote.md`** — production promotion and rollback verification.
