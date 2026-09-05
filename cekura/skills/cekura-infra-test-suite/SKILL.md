---
name: cekura-infra-test-suite
description: >
  Use when the user asks to create, update, or review a source-controlled Cekura JSON CI/CD test
  suite for a voice AI repository; create Tests-as-Code specs; turn a voice-agent code change into
  regression coverage; add deterministic Cekura voice tests to CI; or test an STT, LLM, TTS, VAD,
  interruption, idle-timer, DTMF, or call-lifecycle pipeline; or set up a CI gate that blocks a
  merge when the voice pipeline regresses. Inspects the repository before authoring a compact JSON
  suite, validates it safely with Cekura dry-run, and wires the workflow that runs it.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.3.0"
---

# Cekura Voice AI Infrastructure CI/CD Suite

Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="cekura-infra-test-suite"`, `verification_tag="ack:cekura-infra-test-suite:2h6r7k"`, and `plugin_version="0.15"`. It returns immediately and lets Cekura see which skills are in use.

Build a compact, reviewable Cekura test suite **in the voice-agent repository**. The deliverable is a
JSON spec that CI submits to Cekura's Tests-as-Code endpoint. It is not a folder of persistent
dashboard evaluators.

Use this skill when the repository, its deployment target, and the Cekura agent are in scope. For
one-off dashboard evaluators or adaptive quality scenarios, use `cekura-eval-design` instead.

## API Access — Cekura MCP Server

Authenticate the Cekura MCP server with OAuth or an API key before discovering the target. Use MCP
reads where the client provides them. Tests-as-Code validation is the public HTTPS endpoint below;
when using it directly, take the base URL and API key from the user's local environment or CI secret,
never from source control. If the target environment lacks the endpoint, report that fact and do not
fall back to creating dashboard evaluators.

## Safety and scope

- Inspect the repository before proposing coverage. Do not infer providers, transports, tools, or
  pipeline behavior from a framework name alone.
- Treat Cekura as read-only. You may `GET` agent, enabled metric, personality, test-profile, schema,
  and export data. The only permitted write-like request is
  `POST /test_framework/v1/scenarios/run_scenarios_json/?dry_run=true`.
- Never create, edit, delete, duplicate, or export-and-reimport scenarios, test profiles,
  personalities, metrics, agents, or folders. Never run the suite live unless the user separately
  asks for it after reviewing the spec and accepts the cost.
- Never place API keys, phone numbers, production customer data, or deployment secrets in a spec or
  committed workflow. Use CI secrets and non-sensitive, staging-compatible profile data.
- Preserve existing unrelated repository changes. Edits are limited to the spec, its coverage note,
  the two bundled scripts, and the CI file that runs them. Extend an existing Cekura workflow rather
  than adding a second one, and confirm the trigger before committing a job that places real calls.
- **If covering a behavior would need a change outside that set — runtime code, a deploy workflow,
  a Cekura record, a metric that does not exist — stop and report the blocker.** Do not make the
  change in order to make your own test possible, however small the diff and however sound the
  reasoning. Name what is untestable, say what it would take, and let the user decide. The one
  thing that is not a scope change is a guard whose whole job is policing this suite — a workflow
  step asserting the case count, say. Updating that is part of adding a case.

## Required inputs

Establish these before authoring. Discover them from the repository or Cekura where possible; ask
only for what cannot be safely inferred.

1. **Target** — Cekura base URL, project/agent ID, channel, and any request-only connection data.
   `agent_id` belongs in the run request, never in the JSON spec.
2. **Execution contract** — which deployed bot is under test, how CI reaches it, and whether this is
   a PR suite, deploy gate, or both. A spec is reusable, but the run request supplies the target.
3. **Available dependencies** — enabled metrics, usable personality IDs, and whether a saved
   personality is required because it has non-inline settings.
4. **Repository intent** — supported languages, user journeys, staging fixtures/mocks, and explicit
   non-goals. Do not fabricate a business flow that the code and fixtures cannot support.

If a required target, enabled metric, or staging fixture is unknown, prepare the repository-side
plan and mark that case blocked. Do not silently substitute a weaker check.

## Two different things are called "infrastructure tests"

Settle this before step 0 — an A/B run showed the request is ambiguous, and the wrong reading
costs a whole discovery pass:

| Ask | What it is | What to do |
|---|---|---|
| "add Cekura's **predefined** infrastructure suite" | 18+ ready-made latency / interruption / noise / packet-loss / hold scenarios Cekura ships | **Not reachable from the MCP tools.** Point the user at the dashboard's Evaluators → Infrastructure Suite → *Add to my Project* (or the `add_infrastructure_suite` API). Tell them it also adds an *AI Interrupting user = 0* rubric rule to the project, and tag the copies `infrastructure-suite` so CI can select them. Do not hand-build copies, and do not run the steps below. |
| "build infra/CI tests **for my bot**" | tests derived from the customer's own pipeline code | Run the steps below. |

If the request could be either, ask once — one short question — before step 0.

## Workflow

### 0. Decide whether this is a create or an update

Run this first; it decides everything after it.

```bash
grep -rl 'schemas/test-suite' --include='*.json' .       # definitive: a spec's $schema line
git ls-files | grep -Ei '(cekura|tests?).*\.json$'       # candidates
git ls-files '.github/workflows/*' '.gitlab-ci.yml' 'Jenkinsfile' | xargs grep -ln 'cekura' 2>/dev/null
```

- **No spec** → create. Work through steps 1–7.
- **A spec exists** → update it in place. Read it in full, keep every `key`, and start at step 5,
  the diff review. Do not regenerate the file: an existing suite is reviewed source code whose
  results are comparable across commits only while its keys hold still. The most common correct
  outcome of an update is **no change**.
  **Starting at step 5 is not skipping the rest.** Anything you go on to author runs through
  step 1b (read the agent record), step 4 (the expected-outcome contract) and step 6 (the dry run),
  exactly as it would on a create. An update is a smaller change, not a lower standard — a new case
  written to the old file's house style instead of the judge's contract is a worse case.
  Pre-existing lint warnings on cases this change does not touch are not yours to fix here: report
  them, leave them, and clean them in their own change.
- **A workflow already calls Cekura** → extend that file in step 7 rather than adding a second one,
  reusing its secret names and trigger conventions.

### 1. Read the actual agent path

Start from the runtime entrypoint and trace the call path rather than searching only for provider
names. Inventory, with source references:

- inbound/outbound direction and transport (phone, WebSocket, WebRTC, SIP, LiveKit, Pipecat, etc.);
- STT, LLM, TTS, VAD/turn detection, buffering, endpointing, and interruption processors;
- prompt/config loading and per-session variables;
- tools, handoff/end-call behavior, DTMF/IVR, voicemail, idle/timeout, retry, and error handling;
- supported languages and any code paths that switch language/provider; and
- test fixtures, mocks, staging dependencies, and existing Cekura JSON or workflow files.

`references/discovery.md` carries the question set — what to look for at each layer and, for each
answer, which assertion it unlocks. Its rule: record every threshold and every quoted agent phrase
with a `file:line`. A sourced number turns "the idle timer eventually fires" into "it fires at 8s
and says *Are you still there?*"; an unsourced one is a guess that will fail the suite, not the bot.

For every candidate behavior, record its **seat and transport**. The simulated caller and the
agent-under-test can execute different code. Coverage that exercises only one seat does not prove a
regression is covered in the other.

### 1b. Read the agent record before choosing metrics or a personality

Discovery has two halves. The repository says what the agent does; **Cekura says what the suite is
allowed to assert with.** Where a key or an authenticated session is available, read these before
authoring. They are all reads, and each turns a guess into a fact:

- **The enabled metrics for the target agent.** A spec can only reference metrics that already
  exist and are enabled for that agent, so this list is the ceiling on what the suite can measure.
  Attach the numeric ones — latency, interruption — alongside `expected_outcome`. They measure what
  a transcript-reading judge cannot, which for an infrastructure suite is most of the point.
- **Usable personalities.** Pin one by id so results stay comparable across commits, and note
  whether it carries settings an inline personality cannot (network simulation, speaking plans,
  message plans) — that decides reference-by-id versus inline.
- **The agent itself** — provider, channel, inbound or outbound, contact number, max duration.
  This confirms the channel the CI job should target *before* it is wired, rather than after a run
  is rejected for a channel the agent was never configured for.
- **The live spec schema**, which outranks any example in this skill.

With no credentials, say so plainly: use `expected_outcome` alone, pin no personality, and mark the
suite unvalidated. Never invent a metric slug or a personality id to fill the gap — an unenabled
slug is a hard rejection at the dry run, which is the right place to find out, but a guessed one
only wastes the round trip.

### 2. Make a coverage matrix before editing

Create or update a concise coverage note beside the spec. Use this table:

| Code path / source evidence | Behavior to prove | Seat + transport | Transcript-observable assertion | Case key | Status |
| --- | --- | --- | --- | --- | --- |

Only include behavior that the suite can exercise and judge. For example, assert that an expected
spoken response occurs after an interruption; do not assert that a volume tag, ambient sound, or
internal processor itself ran. Mark a row `uncovered` when it needs a different transport, test
fixture, metric, or backend capability, and state what is missing.

`references/case-catalog.md` holds nine proven case shapes, each with what it asserts at sequence
level versus threshold level, and the **drop-if** condition that makes it a dead test. Start there,
then add the cases this repository's own bug history argues for. Do not port a case whose drop-if
condition fires — a suite of 6 that covers the real pipeline beats 12 with 6 dead tests.

Prefer one 10–12 case deploy-grade suite unless the user asks for tiers. If a fast PR suite is also
needed, keep it compact (typically 4–6 cases) and make the broad suite a superset. Merge compatible
turns into a single case; add a case only for a distinct subsystem, seat, transport, provider, or
terminal call lifecycle.

### 3. Choose the spec shape

Use the live schema returned by the target environment as the authority. A v1 spec normally has:

```json
{
  "$schema": "https://docs.cekura.ai/schemas/test-suite/v1.json",
  "version": "1",
  "suite": { "name": "…", "description": "…" },
  "defaults": { "frequency": 1, "language": "en", "max_duration": 180 },
  "scenarios": []
}
```

Keep stable, descriptive `key` values. Put reusable defaults at the suite level only when every
case actually shares them. Set `language` explicitly on every conditional-actions case.

Supply test data only where a case needs it:

```json
"test_profile": {
  "name": "returning-caller-gold-tier",
  "agent_variables":  { "order_id": "ORD-4471" },
  "caller_variables": { "user_name": "Maria" }
}
```

`agent_variables` reach the agent under test as **dynamic variables** at call time, so a key does
something only if the agent already reads a variable by that name. Discovery tells you which exist;
inventing keys produces a profile the agent silently ignores. `caller_variables` never reach the
agent at all — they are context for the simulated caller and the source for `{{test_profile.key}}`
substitution inside a scripted action.

Do not move fields between the two sections, and do not invent a profile to make the JSON look
self-contained.

**One exception, which is not the common case:** a bot written to self-configure per call — taking
its prompt, providers and limits from the variables it is handed under an explicit test-harness mode
in its own source — receives its whole configuration through `agent_variables`. Preserve that blob
verbatim where the repository has such a mode. Where it does not, `agent_variables` are dynamic
variables and nothing more.

An inline personality is intentionally limited. If the required saved personality uses network
simulation, speaking plans, message plans, generation config, background volume, or interruption
level, keep the personality reference by ID and document that dependency. Do not drop those settings
to force an inline object through validation.

### 4. Author deterministic, observable cases

Use `type: "conditional_actions"` for deterministic infrastructure and regression coverage. All
conditions on **both seats** use `fixed_message: true`; no LLM-generated caller responses belong in
a CI gate. Every condition has `id`, `condition`, `action`, `type`, and `fixed_message`. The first
condition is `id: 0`, `condition: "FIRST_MESSAGE"`.

Use the public `cekura-eval-design` skill and its conditional-actions reference while authoring:

- `<interruption time="Xs" />` must open the action and its condition must be `action_followup`.
  Use a positive time after a greeting or lead-in; `0s` only when speech is already in progress.
- `<ivr text="…" />` and `<voicemail text="…" />` are self-closing and occupy the entire action —
  the block form `<voicemail>…</voicemail>` is rejected. Put follow-on speech in a later
  `action_followup`.
- `<silence>` can be interrupted; `<hold>` cannot. Test the behavior the code path actually selects.
- `<speed ratio="N" />` (0.1–2.0) and `<volume ratio="N" />` (0–2.0) are self-closing and apply from
  where they appear, so put them first. Use them to exercise a path; never make an inaudible
  property the assertion.
- `<network_simulation … />` takes `packet_loss` (0–100), `jitter` and `latency` (ms), and is
  self-closing. It degrades the audio — it never proves anything by itself.
- Do not reference stored audio clips. A recording is referenced by id against the scenario's
  `condition_audio` map, and a spec materialises transient scenarios that have no such map — so an
  `<audio>` id in a committed suite resolves against nothing. (Referencing recordings by name *is*
  supported for dashboard evaluators; see `cekura-eval-design`. It is the spec path that cannot.)

**Lint before you validate.** `scripts/lint_suite.py` checks all of the above plus spec structure,
duplicate keys, and inline-personality limits, offline and free:

```bash
python3 cekura/lint_suite.py cekura.tests.json --strict
```

It mirrors the server's own tag validators, so a clean lint means the dry run fails only for
reasons a local check genuinely cannot see — an unenabled metric, an agent that lacks the channel.

### The expected outcome is the judge's prompt — write it to that contract

`expected_outcome` is not a note to the reader. An LLM judge reads the call transcript and scores
each statement in it independently as `yes`, `no`, or `blocked`. A criterion written as narrative
prose scores worse than the same criterion written to the contract, so **read
`cekura-eval-design/references/expected-outcomes.md` before writing the first one.** These are its
rules that a CI suite breaks most often:

- **Every statement starts with "The main agent should", one statement per line.** Not a numbered
  essay, not a paragraph of prose. 2–6 atomic lines per case; never pad to a count.
- **"main agent" and "testing agent" are the only speaker labels.** Never "the agent", "the bot",
  "the caller", "the user", or "the assistant" — the judge reads a transcript with labelled
  speakers, and renaming them in the criteria costs accuracy on every run.
- **No test-setup rationale.** Why the case is built this way, what the tag does, what the
  threshold is — none of it belongs here. The judge should be told what to look for, not why you
  are looking.
- **No subjective descriptors** — "promptly", "briefly", "warmly", "clearly", "appropriately".
  Replace each with what the main agent observably says or does.
- **No grading of farewells, or who ended the call**, unless termination is the declared point of
  that case. What is *always* in scope, and is a different thing, is whether the main agent keeps
  engaging: when the testing agent signals completion ("that's everything I needed") and then asks
  one more question, an agent that has already disengaged fails a legitimate check. Grade the
  answering, never the goodbye.
- **Every statement must be fired by a written turn.** A statement whose trigger the script never
  produces comes back `blocked` on every run — it is dead weight, not a strict test. Where the turn
  list genuinely permits two acceptable behaviors, write one either/or line rather than demanding
  one of them.

Narrow and transcript-verifiable throughout: spoken content, absence of leaked literal tag text,
turn order. Do not weaken an assertion to turn a real failure green.

`scripts/lint_suite.py` flags the mechanical half of this — label leakage, missing "The main agent
should", subjective descriptors, closing grading — as warnings. Run it with `--strict`.

### Metrics

Select metrics by their enabled slug or ID only after checking the target agent. A missing or
disabled metric is a validation error to fix, not a reason to remove that metric from the case.

`expected_outcome` needs the Expected Outcome metric attached to be scored at all. For an
infrastructure suite, read the agent's enabled metrics and attach the numeric ones too — latency and
interruption metrics measure what an LLM judge reading a transcript cannot.

### 5. Review changes safely

For an update, determine the change against the PR merge base, not just the last commit:

```bash
git fetch origin main
BASE_REF="${PR_BASE_REF:-origin/main}"
MERGE_BASE="$(git merge-base "$BASE_REF" HEAD)"
git diff --name-status "$MERGE_BASE" HEAD
git diff "$MERGE_BASE" HEAD -- <runtime paths> <existing suite paths>
```

Before editing, complete the coverage matrix row for every changed runtime symbol. `No suite change`
is a valid conclusion when no observable behavior changed. Do not modify unrelated cases, relax
expected outcomes, or add generic provider tests merely because a nearby file changed.

### 6. Validate the committed artifact — the dry run is not optional

**A suite that has not returned `valid: true` from a dry run is not finished.** Say so in those
words rather than handing over a file that looks complete. Everything `lint_suite.py` cannot see
is checked here: whether every metric slug exists *and is enabled for this agent*, whether the
personality is reachable, whether the agent supports the channel the CI job will use, and whether
the server's own validators accept every tag. A spec that fails any of those is not a weaker
suite — it is a suite that cannot run at all.

So the order is: lint, then dry run, then fix, then dry run again, until it comes back valid.

**If there are no credentials in the session, ask for them** — an API key and the agent id, or an
authenticated MCP session. Do not quietly skip to the handoff. Only when the user cannot supply
them do you hand over unvalidated, and then you must (a) label the suite unvalidated in the
handoff and in the coverage note, (b) give the exact command below, and (c) point out that the
`validate` job in the CI workflow runs the same dry run, so the first pull request will catch
what this session could not.

A dry run validates syntax, metrics, personalities, profiles, target compatibility, planned runs,
and estimated cost without creating objects or placing a call:

```bash
python3 cekura/lint_suite.py cekura.tests.json --strict     # free, offline, first
CEKURA_API_KEY=… python3 cekura/run_suite.py --dry-run --agent-id 123
```

The runner posts the file and prints the returned plan. The raw form, when you want it:

```bash
curl -sS -X POST \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  "$CEKURA_BASE_URL/test_framework/v1/scenarios/run_scenarios_json/?dry_run=true" \
  -d '{"agent_id": 123, "spec": { ... }}'
```

Require `valid: true`, and read the returned plan rather than glancing at the flag: each case must
list the metrics you intended, and any case given an inline `test_profile` must report
`mode: "inline"`. A case reporting `existing` means the inline block did not take effect.

Errors come back keyed by their location in the file — `scenarios[2].metrics[0]` — and all at once,
so one round trip tells you everything to fix. Fix them; never drop a metric or loosen a case to
get past one. An unenabled metric is a configuration problem in the workspace, not a defect in the
suite. Save the validation response only if it contains
no credentials or sensitive caller data. If dry-run validation needs a write beyond `dry_run=true`,
stop and report the blocker.

### 7. Wire CI so the gate can fail

A validated spec is not yet a gate. Runs are asynchronous: the POST returns as soon as they are
queued, so a job that ends at `curl` reports success before a single call has been judged — a gate
that cannot fail, which is worse than none because it reads as coverage.

Install the two bundled scripts into the repository and wire them:

```bash
mkdir -p cekura && cp <skill>/scripts/{lint_suite.py,run_suite.py} cekura/
```

`run_suite.py` posts the spec, polls every run to a terminal state, writes `cekura-report.md`, and
exits non-zero when any case fails, errors or times out. Both scripts are Python 3 standard library
only — nothing to install on a runner.

Then create `.github/workflows/cekura-tests.yml`, **or extend the workflow that already calls
Cekura** — never add a second one. `references/ci-wiring.md` has the GitHub Actions and GitLab
templates, the fork-PR rule (a job needing secrets must not run on forks), how to point a run at a
per-PR deployment with `pipecat_v2` / `livekit_v2`, and how to pick a trigger that does not spend
credit on every push.

Confirm the trigger with the user before committing a workflow that places real calls.

## Handoff

Leave the repository with:

- the JSON spec or specs, formatted and source-controlled;
- a coverage note mapping code paths to stable case keys, including explicit uncovered rows;
- `cekura/lint_suite.py` and `cekura/run_suite.py`, and the workflow that runs them — created, or
  the existing Cekura workflow extended;
- a short README note describing the target assumptions, Cekura dependencies (metrics,
  personalities, channels), and how CI invokes the suite; and
- the dry-run result — `valid: true` with its plan — or, if no credentials were available, the
  suite explicitly labelled **unvalidated** together with the command that will validate it.

Report case count, target channel/seat coverage, dependencies, and anything that needs a live run or
a backend capability. A dry-run proves the spec is valid; it does not prove a bot deployment works.

## Bundled assets

Reference files, read when the step calls for them:

- **`references/discovery.md`** — the stack questions, and which assertion each answer unlocks
- **`references/case-catalog.md`** — nine proven case shapes with their drop-if conditions
- **`references/ci-wiring.md`** — workflow templates, run targets, per-PR deployments, triggers

Example, read when the shape of a case is in question:

- **`examples/cekura.tests.json`** — a three-case suite: an interruption gauntlet, an idle
  escalation, and an instruction case with test data. Lints clean in `--strict`

Scripts, copied into the user's repository:

- **`scripts/lint_suite.py`** — offline spec and authoring-rule validator; no key, no network
- **`scripts/run_suite.py`** — CI runner: posts, polls, reports, exits non-zero on failure
