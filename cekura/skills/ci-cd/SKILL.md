---
name: ci-cd
description: >-
  Wire a voice-AI agent codebase's CI/CD around Cekura. Two halves: (CI) a gate
  that runs the Cekura eval suite against a candidate build, reports pass/fail,
  and adds LANGUAGE-SIDE invariant checks for things the Cekura simulation
  channel structurally cannot observe — tool/function-call ordering, idempotency,
  "no write before validation", required-step-before-terminal-action; and (CD)
  wiring the Cekura environment variables into the deploy correctly, gating
  per-environment behavior with dedicated flags, and routing a shared sandbox
  test line by the CALLER's number. Use this for the CI/CD phase of onboarding
  ANY repo/language/domain into Cekura, or whenever someone says "CI gate for my
  voice agent", "run Cekura evals in CI", "gate runner", "block the PR if evals
  fail", "advisory gate", "check tool-call ordering", "verify invariants the sim
  can't see", "tool sequence check", "no double-write / idempotency check",
  "set CEKURA env vars in deploy", "which Cekura env vars do I need", "the
  set-env-vars block broke / values got mangled", "gate this behavior per
  environment", "don't overload CEKURA_ENVIRONMENT", "route a shared sandbox test
  line by caller number", "SANDBOX_CALLER_ROUTING", or "each environment should
  target its own agent". The reference voice agent's Python tool-sequence check and its
  GitHub Actions + Cloud Run deploy are ONE concrete example; the contract is
  language-, framework-, CI-system-, domain-, and platform-agnostic — it works
  for custom/self-hosted code in any language, LiveKit Agents, Pipecat, or a
  managed platform (Vapi / Retell / ElevenLabs), run from any CI system (GitHub
  Actions, GitLab CI, Bitbucket Pipelines, CircleCI, Jenkins, …).
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

<!-- cekura-ack-tag: ack:ci-cd:8f3k2p -->
> **Cekura skill verification tag:** `ack:ci-cd:8f3k2p`
> Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="ci-cd"`, `verification_tag="ack:ci-cd:8f3k2p"`, and `plugin_version="0.9.0"`. It returns immediately and lets Cekura see which skills are in use.

# CI/CD around Cekura: eval gate + below-the-surface invariants + deploy env wiring

## What this skill does

This skill covers the **CI/CD plumbing** that ties a voice agent to Cekura. It
has a **CI half** (the eval gate) and a **CD half** (deploy env wiring). The CD
half is the foundation the rest of the integration runs on — get it wrong and
calls publish to the wrong sink (or not at all); the CI half is what guards
regressions before they ship.

### CI: the eval gate (two complementary checks)

1. **The Cekura half.** A gate runner triggers the Cekura eval suite against
   the candidate build, waits for the run to reach a terminal status, evaluates
   the returned metric scores against a threshold table, and collapses the
   outcome into a single gate result — a pass/fail bit plus a list of failures.
   It writes a human-readable summary into the CI step output. **Invoke the
   suite however your stack allows: the Cekura CLI (`cekura run …`) or the Cekura
   API**, called from whatever CI system you run (GitHub Actions, GitLab CI,
   Bitbucket Pipelines, CircleCI, Jenkins, …). The mechanism is language- and
   CI-agnostic — nothing here requires a particular language or CI vendor.
   **This skill runs and gates an existing suite; it does not author it.** To
   generate the voice-pipeline test suite in the first place (transport / STT / LLM
   / TTS / pipeline conditional-action tests), use `cekura-infra-test-suite`, and
   for scenario/metric authoring use `cekura-eval-design` / `cekura-metric-design`.

2. **The local-invariant half.** The agent logs **every tool/function call** to
   a per-call log *during the call*. The gate runner executes the Cekura
   scenarios **against the build under test**, so those logs are produced as a
   side effect of the run. After the Cekura run completes, a check written in
   **your own language and test framework** validates structural invariants
   (tool ordering, idempotency, write-after-validation, …) **from your own
   logs**, and appends any violation to the gate's failure list as a critical
   block. A managed-platform user (Vapi / Retell / ElevenLabs) without a
   codebase to log into may instead rely on Cekura metrics for whatever of
   these invariants is observable (see the note in **The local invariant
   layer**, below).

The gate is **advisory** by default: it runs and reports, but is not wired as a
required/merge-blocking check until the CI system's merge protection is
deliberately armed.

### CD: deploy env wiring (covered in **The CD half** section below)

Every deployment must inject the Cekura env vars the integration code reads (the
right value per environment, secrets as secrets), gate per-environment behavior
on **dedicated** flags rather than overloading a shared variable, and — for a
shared sandbox/test line only — route incoming calls by the caller's number.

## Why — the simulation channel can't see your tool calls

Cekura's simulation channel sees only the **conversation**: what the simulated
caller says and what your agent says back (audio + transcript). It does **not**
see your agent's internal function/tool invocations. So a metric graded purely
from the simulated transcript **structurally cannot** verify anything that lives
below the dialogue surface:

- Did a commit tool actually run *after* its validation tool, or did the
  agent just *say* it checked?
- Did a retry double-write (charge twice, commit twice)?
- Did a write tool fire before validation passed?

A judge prompted to grade these from dialogue can only ever guess — and a
well-written metric that *forbids* inferring tool calls from dialogue can only
ever return FALSE/N-A. That is not a metric bug; it is a property of the
channel. The fix is to assert these invariants where the truth lives: **your
own per-call tool-call logs**. Cekura covers everything observable in dialogue;
the local check covers everything beneath it. The two are complementary, not
redundant — neither subsumes the other.

If you're on a **managed platform** (Vapi / Retell / ElevenLabs) and have no
codebase to log tool calls in, you can't write the local check. Assert whatever
of these invariants is observable through Cekura metrics, and treat the
genuinely-below-surface ones as not verifiable on that platform — don't pretend a
transcript-only metric is checking them.

## The contract (durable — true for any repo/language/domain/CI system)

This is the vendor-and-architecture contract. It holds regardless of language,
framework, business domain, or CI system. The Python tool-sequence specifics and
the GitHub Actions wiring are confined to the reference sections — they are ONE
illustration; the steps below stand alone without them. A custom/self-hosted
agent (any language), a LiveKit Agents / Pipecat agent, and a managed-platform
agent (Vapi / Retell / ElevenLabs) all satisfy the same contract.

1. **Run the eval suite → a gate result.** The runner triggers the Cekura run
   for a known set of scenario IDs against the candidate agent — via the Cekura
   CLI or API, from any CI system — polls to a terminal status, extracts
   per-scenario metric scores, and dispatches each gated metric to its pass/fail
   criterion. The aggregate is a gate result holding a pass/fail bit, a list of
   failures, and a list of warnings (the reference calls this `GateResult {
   passed, failures, warnings }`; the shape, not the names, is what matters).
   **Critical** metrics that fail go to failures and flip the result to failed;
   **warn** metrics that fail go to warnings and do not block. A gated metric
   **absent** from results **fails closed** (don't silently pass when a metric
   didn't run).

2. **Per-metric aggregation is fail-if-any.** If Cekura emits one score per
   scenario for the same metric, ANY failing score fails that metric. A
   last-seen-wins reducer would mask a per-scenario regression behind a later
   passing scenario.

3. **The local invariant layer is fed by per-call tool-call logs produced by
   the run.** The agent must write each tool/function call to a per-call log *as
   it happens*. The gate runner runs the Cekura scenarios against the instance
   of the agent under test (e.g. the agent started locally / in a container and
   exposed to Cekura via a tunnel), so the run *produces* those logs. After the
   Cekura run returns, the gate walks the log directory and validates the
   invariants. The check itself is written in **the user's own language and test
   tooling** — the reference Python sequence-check is just one rendering of it; a
   Node/TS, Go, etc. user writes the equivalent in their own framework. A
   managed-platform user with no codebase to instrument relies on Cekura metrics
   for whatever portion of these invariants is observable in dialogue, and
   accepts that the rest is not assertable on that platform.

4. **Append violations as critical blocks.** Each invariant violation is
   appended to the gate's failure list (carrying the call identifier so a
   reviewer can pull the exact log) and flips the result to failed. The CI step
   then exits non-zero on any failure and renders the failures + warnings into
   the build summary — in whatever summary mechanism the CI system offers.

5. **Advisory vs blocking posture.** The gate's *output* (pass/fail) is
   independent of whether it is *enforced*. Start advisory: it runs on relevant
   PRs and reports, but is not a required check, so a red gate does not block
   merge. Arming it (the CI system's merge/branch protection making it required)
   is a separate, deliberate step — and carries its own caveats (see Gotchas).
   The gate concept — eval suite + local invariants must pass before
   merge/release — is what's portable; it maps onto any CI vendor independent of
   language.

## Choosing your below-the-surface invariants

Transaction ordering is just one instance. Generalize: any rule that is true about
your agent's **internal actions** but invisible in the dialogue is a candidate
for the local layer. Common shapes:

- **Tool-call ordering / dependency.** Tool B must be preceded by tool A in the
  same call (validation before commit, auth before charge, KYC before account
  open). First-seen ordering catches "B fired and A never did" and "A fired only
  *after* B".
- **Idempotency / no-double-write.** A committing tool must fire **at most
  once** per logical transaction (no two `capture_payment` for one order, no two
  commits for one transaction). The dialogue can sound perfectly clean while the
  backend wrote twice.
- **No-write-before-validation.** A write/commit tool must not fire until a
  validating step succeeded (don't commit before validating the request; don't
  submit before required fields are collected).
- **Required-step-before-terminal-action.** Before a terminal action (transfer,
  hang-up, "all set"), a prerequisite tool must have run (confirmation read-back
  recorded, ticket created, etc.).

> **"N/A when not attempted."** A call that never attempts the gated action
> produces NO violations — a cancel-only / transfer / FAQ call simply never
> emits the gated tool names, so no rule applies. Mirror this semantic: only
> assert ordering *when the downstream action was actually attempted*. Don't
> fail a call for "missing a step" of a flow it never entered.

Optionally consider the success of a tool result (not just that it fired) and
per-attempt sequencing (a caller retries after a failure). These are real but
strictly harder; a first-seen, fired-or-not check is a sound, low-false-positive
starting point — ship that first and refine only when a real failure mode
demands it.

## Adapt to your stack (checklist)

Work through these for the target repo:

- **Do you have a codebase to instrument at all?** A custom/self-hosted agent
  (Python, Node/TS, Go, …), a LiveKit Agents agent, or a Pipecat agent does. A
  managed-platform agent (Vapi / Retell / ElevenLabs) typically does not — there,
  skip the local-log steps and lean on Cekura metrics for the observable
  invariants (see the note in **Why**, above).
- **Do you log tool calls per call?** Find (or add) the layer that records every
  tool/function invocation. It must distinguish an *invocation* from a *result*
  and from an *utterance*, and carry the tool name + a per-call identifier. If
  no such log exists, this skill depends on the transcript/tool-logging skill —
  wire that first.
- **Where do the logs land?** One file per call, keyed by the call id, in a
  known directory the gate runner can read after the run. NDJSON (one JSON
  object per line) is convenient because it's append-only and partial-write
  tolerant.
- **How do you invoke the suite from CI?** Via the Cekura CLI or the Cekura API,
  from whatever CI system you use (GitHub Actions, GitLab CI, Bitbucket Pipelines, CircleCI, Jenkins,
  …). The reference shows GitHub Actions; the same call works from any of them.
- **Can your gate runner run scenarios against the build under test to produce
  those logs?** The whole mechanism depends on the Cekura run hitting *your*
  instance so the logs exist. Confirm the runner starts the agent (locally /
  tunneled / container) and that Cekura dials *that* instance — not a
  pre-deployed environment whose logs you can't see. **This requires an inbound
  connection Cekura can dial, which is a prerequisite these skills do not set up:
  for a telephony agent (Twilio/Telnyx/SIP) register the agent's phone number on
  Cekura (via `cekura-create-agent`) and Cekura calls it; a provider's own
  websocket framing (e.g. Twilio Media Streams) is not directly dialable by
  Cekura's websocket runner. Place one test call from Cekura before relying on the
  gate.**
- **How do you surface failures in CI?** Exit non-zero on any failure; write a
  Markdown/structured summary to the CI step output (whatever the CI system
  offers); include the call id on each invariant violation so a reviewer can
  fetch the offending log artifact.
- **Is the gate advisory or required?** Decide explicitly. Advisory first.
  Document the posture so nobody assumes a green/absent gate gated the merge. The
  gate concept ports to any CI vendor; only the wiring to make a check
  *required* is vendor-specific.
- **Where does gate coverage live?** Keep the scenario IDs and the
  metric→threshold table *in the repo* (code-reviewed), not buried in a secret —
  changing what the gate enforces is a change to merge criteria and should go
  through PR review.

## Reference implementation (ONE example — Python; illustration of the contract, adapt don't copy)

Everything below is **a single concrete illustration** of the contract above —
it happens to be Python, but the steps stand on their own and a Node/TS, Go,
LiveKit, Pipecat, or managed-platform user implements the same contract in their
own tooling. The reference voice agent is a Python/FastAPI speech-to-speech agent
(Telnyx + Gemini Live). Its gate lives in `scripts/cekura_gate/`. Treat the names
and shapes below as an **illustration of the contract**, not an API to copy, and
**do not transcribe these symbol names into another stack** — write the
equivalent idiomatically.

**The base runner** (`criteria.py`, `__main__.py`). `evaluate_run(metrics,
thresholds)` dispatches each gated metric (keyed by Cekura metric id) to a
`BinaryCriterion` / `NumericCriterion` `.evaluate(score)` and aggregates:

```python
@dataclass
class GateResult:
    passed: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
```

Critical failures append to `failures` and set `passed=False`; warn failures
append to `warnings`; a gated metric **absent** from results fails closed; and
per-metric aggregation is **fail-if-any** across scenarios.

**The local layer** (`sequence_check.py`). This is the reference rendering of the
invariant check — a Node/TS user would write it in their test runner, a Go user
in `testing`, etc.; the logic, not the language, is the point. Every Gemini tool
call is written to `transcripts/{telnyx_call_id}.jsonl` by
`modules/transcript_logger.py` during the call. The check enforces three
per-call, first-seen ordering rules:

```python
_TOOL_ORDER_RULES = (
    ("lock_record", "check_availability"),
    ("capture_transaction", "lock_record"),
    ("add_transaction_notes", "capture_transaction"),
)

@dataclass(frozen=True)
class SequenceViolation:
    telnyx_call_id: str
    rule: str    # e.g. "lock_record_without_check_availability"
    detail: str  # human-readable line for the gate summary
```

`check_call(telnyx_call_id, transcript_lines)` walks the parsed NDJSON, ignores
everything except `type == "function_call"` entries, tracks a `seen` set of tool
names, and emits a `SequenceViolation` whenever a downstream tool fires while its
required predecessor is not yet in `seen` (so a predecessor that appears *after*
the downstream tool still violates — order matters, mere presence doesn't).
`check_transcripts_dir(dir)` globs `*.jsonl`, runs `check_call` per file, and
concatenates the results. A call that never touches the transaction flow produces
zero violations — the "N/A when not attempted" semantic falls out for free.

**Wiring the two together** (`__main__.py`, after the Cekura run):

```python
result = evaluate_run(metrics, THRESHOLDS)

violations = check_transcripts_dir(_DEFAULT_TRANSCRIPTS_DIR)
if violations:
    for v in violations:
        result.failures.append(f"Tool sequence ({v.telnyx_call_id}): {v.detail}")
    result.passed = False
```

The dropped Cekura metric `toolcall_sequence_correctness` (id `<metric-id>`)
was **removed** from the threshold table precisely because the simulation could
not observe the function calls — that assertion now lives entirely in
`sequence_check.py`. The `_DEFAULT_TRANSCRIPTS_DIR` resolves to the same
`transcripts/` dir the in-process `main.py` writes to during the gate run, which
is what makes the side-effect-of-the-run mechanism work.

**Advisory posture.** In the reference repo, the gate is documented as **not currently
merge-blocking** in both `CLAUDE.md` ("Cekura pre-deploy gate" section) and
`docs/DEPLOY.md`: it runs on PRs touching the prompt templates and reports
pass/fail, but is not a required status check; arming branch protection is
deferred. (On GitLab CI / Bitbucket Pipelines / CircleCI / Jenkins / etc. the same posture is achieved
with that system's merge-request approval rules or required-job settings — the
"advisory until deliberately armed" idea is what ports, not the GitHub term.) The
gate self-skips (with a warning, not a failure) if its scenario IDs are unset, so
the workflow can land before the prereq ops tickets resolve.

**A worked example to learn from.** A worked example in the reference repo (the
`cekura-gate-tags` branch, unmerged but ready) shows the gate exercised in practice: a feature-flag +
`check_availability` wiring change plus tests, demonstrating the gate catching a
real ordering regression end-to-end. Use it as an illustrative reference for how
the pieces fit; you don't need it checked out to apply this skill.

## Gotchas

- **CI runs in a CLEAN env — the app's fail-fast config will bite you.** Many
  agents hard-exit at import when a required runtime key is missing (e.g. a
  config module that does `process.exit(1)` / `sys.exit(1)` on absent
  `OPENAI_API_KEY` / `ELEVENLABS_API_KEY`). Any test or gate step that transitively
  imports that config then **dies in CI** even though it passed locally — because
  the dev shell has the keys and the CI runner does not. Two rules: (1) keep the
  Cekura integration code (publishers, tracing, sync) **decoupled** from the app's
  fail-fast config so importing it never triggers the exit — read `CEKURA_*` from
  their own small config, not the module that enforces the app's keys; and (2)
  **verify the gate in a clean env** before trusting it — run it with the app keys
  unset (`env -u KEY …`, a fresh container, or an unset CI job) so "passes on my
  machine" can't mask a CI-only failure. A green local run with the keys present
  is not evidence the CI job passes.
- **In-process or it's pointless.** If Cekura dials a pre-deployed environment
  instead of the build under test, the logs the gate reads won't correspond to
  the run — the local layer silently verifies nothing. The runner must own the
  instance the scenarios hit.
- **Missing/empty log dir is "nothing to check", not "pass".** Treat an absent
  or empty log directory as *no transcripts to validate* (trivially zero
  violations) — but know that a runner that crashed before any call landed is a
  real failure surfaced elsewhere (e.g. the metric layer's fail-closed). Don't
  let the local layer paper over it.
- **Malformed/truncated log lines can hide a violation.** A process killed
  mid-write can drop a `function_call` line that would have proven a violation.
  Skip the bad line but **log a warning** so a green gate over corrupt logs is
  triageable.
- **Fail closed on absent metrics.** A gated Cekura metric that didn't run must
  fail, not pass — otherwise a Cekura-side error reads as a green gate.
- **Required-check caveats when you arm it (deferred).** Making the gate a
  required check has subtle traps that exist on every CI system, illustrated here
  with GitHub Actions: a path-filtered gate that never ran leaves a required
  check stuck "expected, waiting" — GitHub does NOT auto-pass it; you need a
  companion always-runs job reporting the same check name or a path-filter-aware
  action. And a concurrency group with `cancel-in-progress: false` keeps only one
  pending run, so a third queued PR cancels the second pending one, and a
  `cancelled` status reads red under a required check until re-run. The portable
  lesson (true on GitLab CI / Bitbucket Pipelines / CircleCI / Jenkins too): a required gate that is
  skipped, queued, or cancelled must not silently read as pass or wedge the
  merge — confirm your CI system's behavior for each before arming it. These bite
  only when the gate becomes required.

## Common mistakes to avoid

- **Trying to make Cekura grade tool ordering from the transcript.** It can't
  see the calls; a transcript-only metric for an internal invariant can only
  guess. Move the assertion to the local layer.
- **Asserting a flow's steps on a call that never entered the flow.** Honor "N/A
  when not attempted" — only check ordering when the downstream action actually
  fired. Otherwise every FAQ/cancel/transfer call fails spuriously.
- **Treating mere presence of the predecessor as sufficient.** The predecessor
  must precede the downstream tool. A predecessor appearing *after* still
  violates; pin first-seen ordering so a refactor can't quietly accept reversed
  calls.
- **Last-seen-wins metric aggregation.** Fail-if-any across scenarios; a later
  passing scenario must not mask an earlier regression.
- **Burying gate coverage in a secret.** Scenario IDs and the threshold table
  are merge criteria — keep them code-reviewed in the repo.
- **Assuming advisory == enforced.** An advisory gate's red result does not
  block merge. Document the posture, and don't claim "the gate gated it" until
  branch protection is actually armed.
- **Skipping the dependency.** No per-call tool-call log → no local layer. Wire
  the transcript/tool-logging layer first; this skill builds on top of it.

---

# The CD half: deploy env wiring

The CI gate above guards regressions; this half is the **deploy plumbing** the
whole Cekura integration depends on. Every environment, every platform, you do
three things:

1. **Inject the Cekura env vars** the integration code reads — the right value
   per environment, secrets handled as secrets and everything else as plain
   config.
2. **Gate per-environment behavior on a DEDICATED flag**, never by overloading a
   variable that already means something else.
3. **(Shared test line only)** Route incoming calls by the **caller's** number
   when the dialed-to number is a single shared line that can't tell tenants
   apart — preferring a caller→profile registry and falling back to normal
   dialed-number routing, gated so prod/dev are byte-for-byte unchanged.

If a deploy injects the wrong value, the wrong agent, or a corrupted value, calls
publish to the wrong Cekura sink (or silently don't publish) and you find out
only when eval/observability data is missing or polluted.

## The Cekura env-var catalog (what each one controls)

| Variable | Secret? | Scope | Controls |
|---|---|---|---|
| `CEKURA_API_KEY` | **secret** | account | Auth for every Cekura API/sink call. Goes in your platform's secret store, never in plain config. |
| `CEKURA_AGENT_ID` | plain | **per-environment** | Which Cekura agent this deployment syncs to and publishes as. **Each environment targets its OWN agent id** — prod, dev, and each sandbox have distinct ids so their data never mixes. |
| `CEKURA_PROJECT_ID` | plain (NOT a secret) | project | Project that scopes OTEL traces (`x-cekura-project-id`). Project-scoped, so it's shared across environments and is plain config. |
| `CEKURA_ENVIRONMENT` | plain | per-environment | The per-environment **sink split selector**, used **only when both sinks are wired** and `CEKURA_ROUTE_TO` is unset: `prod` → observability sink only; `sandbox` → eval/scenarios webhook only. The recommended default split. Irrelevant to a single-sink integration. (Routing semantics: see the "Running both sinks: the split" section in `observability` / `custom-transcript-provider`.) |
| `CEKURA_ROUTE_TO` | plain | per-deployment | **Explicit sink override — rarely needed.** When set, wins over the `CEKURA_ENVIRONMENT` split. Valid values: `both`, `observability`, `evals`. Unknown values are ignored (falls back to the split). Leave **unset for the default split** (the normal case); set only for the rare deployment that needs a different mode (e.g. `both` to fire both sinks on every call). |
| `CEKURA_OTEL_ENDPOINT` | plain | account | OTLP/HTTP traces endpoint. Defaults to the standard endpoint; only set to override. |
| `OTEL_SERVICE_NAME` | plain | service | Service name stamped on emitted traces. |
| `RECORD_CALLS` | plain | **dedicated flag** | Opt-in call-audio recording → `voice_recording_url`. **Default false.** A privacy/compliance choice — set ONLY when the user explicitly wants audio recorded and sent to Cekura (also needs the telephony creds). |
| `SANDBOX_CALLER_ROUTING` | plain | **dedicated flag** | Turns on caller-number routing for a shared test line. **Default false.** Set ONLY by the deploy that has a shared line — see the gating principle below. |

> The exact variable names belong to the integration code, not to Cekura. If the
> code renames a field, the deploy variable must change with it. Verify the names
> against your config loader (in the reference repo, `config.py`'s `Settings`).
> The routing modes themselves (the recommended `CEKURA_ENVIRONMENT` split plus
> the rare `CEKURA_ROUTE_TO` overrides) are documented in the "Running both sinks:
> the split" section of each sink skill (`observability` /
> `custom-transcript-provider`), and only apply when both sinks are wired;
> this skill owns **how the env vars that select them get injected into each
> deploy**.

## Principle: each environment targets its own agent and sink

Resolve `CEKURA_AGENT_ID` per environment from a **single source of truth** so
the running service and any post-deploy "sync config to Cekura" step (see
`config-sync`) can't drift (deploy one agent, sync a different one). In the
reference repo the workflow sets `CEKURA_AGENT_ID` once in the job `env:` and
reuses it in both the deploy command and the sync step.

## Principle: never overload one flag for two behaviors

A variable that already drives one decision must not be reused to gate an
unrelated behavior — its existing value in OTHER environments will switch your
new behavior on (or off) where you never intended.

Concretely: `CEKURA_ENVIRONMENT=sandbox` selects the shared eval sink, and it is
**also set on the dev deployment** (dev publishes to the same sandbox sink). So
gating a new behavior on `CEKURA_ENVIRONMENT == "sandbox"` would wrongly enable
it on dev too. The fix is a **dedicated flag** (`SANDBOX_CALLER_ROUTING`,
default false) set only by the deploy that actually wants the behavior. Prod and
dev are then untouched. Whenever you reach for an existing variable to gate
something new, stop and ask "does this variable's value in any OTHER environment
mean what I want there?" — if not, add a dedicated flag.

## Pattern: route a shared test line by the caller's number

When a sandbox/test deployment shares **one** inbound phone line across many
tenants/profiles, the dialed-to number can't distinguish them — every test call
dials the same number. Add a **sandbox-only registry** mapping the **caller's**
number → a profile, and have the incoming-call handler:

- **Prefer** the caller→profile lookup, then
- **Fall back** to the normal dialed-number routing when the caller isn't mapped
  (so a shared gate-test line and any real dialed-number routing keep working).

The whole thing is **gated on the dedicated flag** so prod and dev never load the
file. The registry is empty in every non-gated environment, which makes the
lookup collapse to the original dialed-number behavior — prod/dev routing is
**byte-for-byte unchanged**. Express the precedence as a single short-circuit:

```
cfg = caller_registry.get(from_number) or dialed_registry.get(to_number)
```

When `caller_registry` is empty (the default everywhere but the gated deploy),
this is exactly `dialed_registry.get(to_number)` — the original code path.

## Adapt to your stack (CD checklist)

- **How does your platform inject env vars?** Kubernetes env/ConfigMap/Secret,
  Cloud Run `--set-env-vars` / `--set-secrets`, ECS task-def `environment` /
  `secrets`, Lambda `Environment.Variables`, a `.env` rendered by CI, a systemd
  `Environment=` block, Helm `values.yaml`. Map each catalog row to the right
  mechanism.
- **Which values are secrets vs plain?** `CEKURA_API_KEY` is the only secret;
  route it through your secret store. Everything else (`CEKURA_PROJECT_ID`
  included — it's project-scoped, not a credential) is plain config.
- **How many environments, and which sink does each use?** Enumerate them (prod,
  dev, one or more sandboxes). Set `CEKURA_ENVIRONMENT` per environment to pick
  the sink. Give each its OWN `CEKURA_AGENT_ID` from one source of truth.
- **Do you have a shared test line?** If yes, build the caller→profile registry,
  prefer-then-fallback in the incoming-call handler, and gate loading on a
  dedicated flag (default false). If no, skip the routing pattern entirely —
  don't add the flag.
- **Are you about to gate a new behavior on an existing variable?** Check that
  variable's value in every OTHER environment first. If it's not what you want
  there, add a dedicated flag instead.
- **Whatever the platform, verify the RENDERED config** the service actually
  receives — not just the template you wrote (see CD Gotchas).

## Reference implementation (ONE example — GitHub Actions/Cloud Run; illustration, adapt don't copy)

This is **a single illustration** of the CD contract; the same env-var injection,
dedicated-flag gating, and caller-routing pattern map onto GitLab CI, CircleCI,
Jenkins, raw Kubernetes manifests, ECS task defs, etc. — see the CD checklist
above for the per-platform mechanisms. Here: a Python/FastAPI speech-to-speech
voice agent on Telnyx + Gemini Live, deployed to Cloud Run via GitHub Actions.
Three workflows: `.github/workflows/deploy-prod.yml`, `deploy-dev.yml`,
`deploy-sandbox.yml`.

### Single source of truth for the per-environment agent id

Each workflow sets `CEKURA_AGENT_ID` once in the job `env:` and reuses it:

```yaml
# deploy-prod.yml          CEKURA_AGENT_ID: "<prod-agent-id>"
# deploy-dev.yml           CEKURA_AGENT_ID: "<dev-agent-id>"
# deploy-sandbox.yml       (picked from the sandbox_owner input)
env:
  CEKURA_AGENT_ID: ${{ inputs.sandbox_owner == '<owner-a>' && '<sandbox-a-agent-id>'
                       || inputs.sandbox_owner == '<owner-b>' && '<sandbox-b-agent-id>'
                       || '<default-sandbox-agent-id>' }}
```

That same `$CEKURA_AGENT_ID` is consumed by the `--set-env-vars` block (below)
AND by the post-deploy Cekura-sync step, so the deployed service and its synced
config can't point at different agents.

### The corrected `--set-env-vars` block (sandbox)

Plain config goes in `--set-env-vars`, the one secret in `--set-secrets`:

```yaml
- name: Deploy new revision
  run: |
    gcloud run deploy "$SERVICE_NAME" \
      --image "${{ steps.image.outputs.tag }}" \
      --region "$REGION" \
      --project "$PROJECT_ID" \
      --set-env-vars="SERVER_BASE_URL=${{ steps.url.outputs.uri }},\
                      BOT_WEBHOOK_BASE_URL=https://<your-webhook-host-for-dev>,\
                      CEKURA_AGENT_ID=$CEKURA_AGENT_ID,\
                      CEKURA_PROJECT_ID=<your-project-id>,\
                      CEKURA_ENVIRONMENT=sandbox,\
                      CEKURA_ROUTE_TO=${{ inputs.route_to }},\
                      SANDBOX_CALLER_ROUTING=true" \
      --set-secrets="CEKURA_API_KEY=cekura_api_key:latest,\
                      ...other secrets..."
```

Note: `CEKURA_PROJECT_ID` (project-scoped, not a secret) sits in `--set-env-vars`;
only `CEKURA_API_KEY` is in `--set-secrets`. Prod sets `CEKURA_ENVIRONMENT=prod`
and omits `CEKURA_ROUTE_TO`/`SANDBOX_CALLER_ROUTING`; dev sets
`CEKURA_ENVIRONMENT=sandbox` but does **not** set `SANDBOX_CALLER_ROUTING`.

Each `\` at end of line is a shell line-continuation, and the commas separate
env-var entries. Both are load-bearing — see CD Gotchas.

### The dedicated-flag gating (config + startup)

The config loader gives the flag a safe default and documents WHY it's separate
(`config.py`):

```python
# Sandbox-only caller-number routing. ... Set ONLY on the sandbox deployment —
# NOT on dev, which shares CEKURA_ENVIRONMENT=sandbox but must keep normal
# routing. Default false, so prod/dev are byte-for-byte unchanged.
sandbox_caller_routing: bool = False
```

Startup loads the registry **only** when the dedicated flag is set (`main.py`),
so prod and dev never read the file:

```python
# Gated on its own SANDBOX_CALLER_ROUTING flag — NOT cekura_environment, which
# is "sandbox" on the dev deployment too — so prod AND dev never read the file
# and their dialed-number routing is completely unchanged.
if settings.sandbox_caller_routing:
    _sandbox_caller_to_entity = load_sandbox_caller_registry()
```

### The caller-routing prefer/fallback (incoming-call handler)

In the `direction == "incoming"` branch (`main.py`):

```python
to_number = payload.get("to", "")
from_number = payload.get("from", "")
# Prefer routing by the CALLER's number; fall back to normal dialed-number
# routing when the caller isn't mapped (so the gate-test line still works).
# _sandbox_caller_to_entity is empty in every non-sandbox environment,
# so this is a no-op there.
entity_cfg = _sandbox_caller_to_entity.get(from_number) or _phone_to_entity.get(to_number)
```

### The caller registry loader and JSON file

`load_sandbox_caller_registry()` mirrors the dialed-number loader but keys on
`caller_number`, and **returns an empty map when the file is absent** — the
default in every non-sandbox environment (`locations/__init__.py`):

```python
def load_sandbox_caller_registry(json_path=None) -> dict[str, dict]:
    if json_path is None:
        json_path = _LOCATIONS_DIR.parent / "sandbox_caller_routes.json"
    if not Path(json_path).exists():
        return {}
    with open(json_path, encoding="utf-8") as f:
        entries = json.load(f)
    return _build_registry(entries, "caller_number")
```

`sandbox_caller_routes.json` is a flat list of `{caller_number, entity_name,
entity_id}` rows. `tests/test_sandbox_caller_routing.py` pins the four things
that matter: the loader keys by caller number, returns `{}` when the file is
absent, the caller map takes precedence over the dialed map, and the flag
defaults false.

## CD Gotchas

- **Backslash/comma line-continuation corruption in multi-value flags
  (a bug seen in the reference repo).** In a `--set-env-vars="A=1,\<newline>B=2,\<newline>..."`
  block, a **stray space after a `\`** escapes the space instead of the newline,
  embedding a literal newline + spaces into the *value*. And a line that **loses
  its trailing `,\`** merges the next key onto the previous value, producing one
  mangled key. Both corrupt values **silently** — the deploy succeeds, but the
  service reads garbage (wrong/empty `CEKURA_AGENT_ID`, two keys fused). The
  durable lesson: backslash line-continuations inside multi-value env flags are
  fragile. After editing such a block, **verify the rendered command** (echo it,
  or read back the deployed service's env) rather than trusting the template.
  Prefer formats that avoid hand-maintained continuations where the platform
  allows it (repeated `--set-env-vars` flags, a YAML/`env_file`, a Helm map).
- **Flag-overloading enables behavior on the wrong environment (a bug seen in the reference repo).**
  Gating on `CEKURA_ENVIRONMENT=sandbox` looks right until you remember dev also
  sets `CEKURA_ENVIRONMENT=sandbox` (to share the sink). The behavior then turns
  on in dev. Always gate new behavior on a dedicated flag and confirm its value
  in every other environment.

## CD common mistakes to avoid

- Putting `CEKURA_API_KEY` in plain env vars, or putting `CEKURA_PROJECT_ID`
  (project-scoped, not a credential) in the secret store. Key = secret; the rest
  = plain config.
- Sharing one `CEKURA_AGENT_ID` across environments — their sync and call data
  then collide. Give each environment its own.
- Letting the deployed agent id and the post-deploy sync step's agent id drift —
  resolve from one source of truth.
- Reusing `CEKURA_ENVIRONMENT` (or any existing variable) to gate a new behavior
  instead of adding a dedicated default-off flag.
- Setting `SANDBOX_CALLER_ROUTING=true` on dev or prod, or shipping the
  caller-routes file to an environment that doesn't gate its loading.
- Inverting the precedence (dialed-number first) or dropping the fallback — the
  shared gate-test line then breaks for unmapped callers.
- Trusting the template you wrote instead of verifying the **rendered** config
  the service actually received.
