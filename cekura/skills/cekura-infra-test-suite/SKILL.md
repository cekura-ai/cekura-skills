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

Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="cekura-infra-test-suite"`, `verification_tag="ack:cekura-infra-test-suite:2h6r7k"`, and `plugin_version="0.14"`. It returns immediately and lets Cekura see which skills are in use.

Build a compact, reviewable Cekura test suite **in the voice-agent repository**. The deliverable is a
JSON spec that CI submits to Cekura's Tests-as-Code endpoint. It is not a folder of persistent
dashboard evaluators.

Use this skill when the repository, its deployment target, and the Cekura agent are in scope. For
one-off dashboard evaluators or adaptive quality scenarios, use `cekura-eval-design` instead.

## How this runs — two contexts, one procedure

The steps below are identical in both; what differs is where the code comes from, what is already
known, and where the result lands. Detect it, do not ask: **the repository is already the working
directory** → a terminal. **The code must be fetched with `mcp__github__github_checkout_repo`** →
launched from the Cekura dashboard.

| | Terminal | Dashboard |
|---|---|---|
| Repository | already the working directory | fetched with `github_checkout_repo` |
| Agent | infer from config, or ask | named in the launch message |
| Credentials | may genuinely be absent — asking is right | the MCP session is already authenticated; **never ask** |
| Result | the working tree, for the user to commit | one pull request, via `github_open_pull_request` |

### The interaction contract

**One question per run, asked in your first response, and this is it:**

> This will run on manual dispatch only — started from the Actions tab against a branch, placing real
> calls, with a `dry run` box for validating instead. Add a trigger too: push, PR, or a schedule?

Ask it while reporting what you found, then keep working. **Do not wait for the answer** — if none
has arrived by step 6, write manual dispatch and say in the handoff how to add a trigger. Nothing
else is a question: not which files to create, not where to put them, not whether to proceed, and —
in the dashboard context — not credentials.

## API Access — Cekura MCP Server

Authenticate the MCP server before discovering the target, and prefer MCP reads. Tests-as-Code
validation is the public HTTPS endpoint below; take its base URL and key from the environment or a
CI secret, never from source control. If the endpoint is absent, report that rather than falling
back to dashboard evaluators.

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
- Preserve existing unrelated repository changes. Edits are limited to the file list settled in
  *The deliverable* below. Extend an existing Cekura workflow rather than adding a second one.
- If a target, enabled metric, personality or staging fixture is unknown, mark that case blocked
  rather than substituting a weaker check.
- **If covering a behavior would need a change outside that set — runtime code, a deploy workflow,
  a Cekura record, a metric that does not exist — stop and report the blocker.** Do not make the
  change in order to make your own test possible, however small the diff and however sound the
  reasoning. Name what is untestable, say what it would take, and let the user decide. The one
  thing that is not a scope change is a guard whose whole job is policing this suite — a workflow
  step asserting the case count, say. Updating that is part of adding a case.

## Two different things are called "infrastructure tests"

Settle this before step 0 — the wrong reading costs a discovery pass:

| Ask | What it is | What to do |
|---|---|---|
| "add Cekura's **predefined** infrastructure suite" | 18+ ready-made latency / interruption / noise / packet-loss / hold scenarios Cekura ships | **Not reachable from the MCP tools.** Send them to Evaluators → Infrastructure Suite → *Add to my Project* (or the `add_infrastructure_suite` API); note it also adds an *AI Interrupting user = 0* rubric rule, and tag the copies `infrastructure-suite` so CI can select them. Do not hand-build copies or run the steps below. |
| "build infra/CI tests **for my bot**" | tests derived from the customer's own pipeline code | Run the steps below. |

If the request could be either, ask once — one short question — before step 0. This can only
happen in a terminal: a dashboard launch names the repository and the agent, which settles it.

## The deliverable — three files, fixed before you write

The baseline, and what almost every repository gets:

```
cekura.tests.json                    the suite
.github/workflows/cekura-tests.yml   the CI gate (created, or the existing Cekura job extended)
README.md                            a section: what runs, which secrets, which permissions
```

**Decide the exact list before writing anything, and name it in your first response.** Three is a
baseline, not a cap; what matters is that the list is settled up front, because discovering a fourth
file halfway through is what turns one pass into four rounds of steering. Add or substitute only
where the repository's own conventions demand it, and say why:

- CI is not GitHub Actions → `.gitlab-ci.yml`, a Jenkinsfile stage, a Makefile target. A
  substitution, not an addition.
- Docs live somewhere other than the README → put the section where that repo keeps them.
- Two independently deployable bots → two specs, if one cannot cover both.
- The repo's workflows call a `ci/` or `scripts/` directory by convention → the poller can live
  there instead of inline, matching what is already there.

Never as an addition: a coverage note (it goes in the README section and the PR body), a vendored
`lint_suite.py` or `run_suite.py`, or a config file this skill invented. Every extra file is one more
thing the customer maintains forever — if you cannot name the convention forcing it, it does not
belong. Write the whole list in one pass, before the dry run; the linter runs from this skill's own
directory and the workflow polls inline.

One question per run, asked first — see *The interaction contract* above. Everything else is
either discoverable from the repository or already supplied.

If a pull request is the destination, name the required GitHub App permissions before proposing it:
**Contents** and **Pull requests** read-and-write, plus **Workflows** read-and-write because the
payload writes `.github/workflows/`. Granting that last one on the App is not enough — an org admin
must accept the change on the installation.

## Workflow

### 0. Decide whether this is a create or an update

Run this first; it decides everything after it.

```bash
grep -rl 'schemas/test-suite' --include='*.json' .       # definitive: a spec's $schema line
git ls-files | grep -Ei '(cekura|tests?).*\.json$'       # candidates
git ls-files '.github/workflows/*' '.gitlab-ci.yml' 'Jenkinsfile' | xargs grep -ln 'cekura' 2>/dev/null
```

- **No spec** → create. Work through steps 1–8.
- **A spec exists** → update it in place. Read it in full, keep every `key`, and start at step 5,
  the diff review. Do not regenerate the file: an existing suite is reviewed source code whose
  results are comparable across commits only while its keys hold still. The most common correct
  outcome of an update is **no change**.
  **Starting at step 5 is not skipping the rest.** Anything you author still runs through step 1b,
  step 4's expected-outcome contract and step 7's dry run. An update is a smaller change, not a
  lower standard — a case written to the old file's house style instead of the judge's contract is a
  worse case. Pre-existing lint warnings on untouched cases are not yours to fix here.
- **A workflow already calls Cekura** → extend that file in step 6 rather than adding a second one,
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

**If the agent contradicts the repository, say so before authoring anything.** A repo that builds a
Pipecat pharmacy line pointed at a bare "helpful assistant" on another provider will fail every case
that is worth writing — and a wall of red on a first run reads as a broken suite rather than the
wrong agent id. Name the mismatch in your first response, lead the handoff with it, and put it at
the top of the pull-request body. Author the suite against the repository anyway: it is correct, and
it becomes right the moment the agent id is fixed.

With no credentials, say so plainly: use `expected_outcome` alone, pin no personality, and mark the
suite unvalidated. Never invent a metric slug or a personality id to fill the gap — an unenabled
slug is a hard rejection at the dry run, which is the right place to find out, but a guessed one
only wastes the round trip.

### 2. Make a coverage matrix before editing

Build the coverage table before editing. It is not a file — it goes into the README section and the
PR body, so a reviewer sees the reasoning without the repo carrying a document that rots:

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
python3 <skill>/scripts/lint_suite.py cekura.tests.json --strict
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

### 6. Write the files, in one pass

Everything is decided by now, including the file list. Write it all together, before validating
anything — not one file, then a question, then another. That loop is what this step exists to
prevent.

#### The workflow

A validated spec is not yet a gate. Runs are asynchronous: the POST returns as soon as they are
queued, so a job that ends at `curl` reports success before a single call has been judged — a gate
that cannot fail, which is worse than none because it reads as coverage. The workflow therefore
polls each run to a terminal state and exits non-zero on any failure. `references/ci-wiring.md`
carries the template; copy it rather than composing YAML from memory.

Two things are fixed and not up for discussion with the user:

- **`workflow_dispatch` with a `dry_run` checkbox, unchecked by default.** Dispatching by hand is a
  deliberate act whose point is to place the calls; the box is there for when it is not.
- **Every trigger other than a manual run validates only**, unless the user explicitly asks for
  live calls on that trigger. Real calls spend credit; a push that quietly bills is not a default
  anyone consents to.

**The default is `workflow_dispatch` and nothing else** — started from the Actions tab against
whichever branch the user picks. The trigger question was asked in
your first response; if an answer came back, add it to the template's `on:` block, and otherwise
write manual-only and note in the handoff how to add one. Never hold the run open waiting.

If the repository already has a workflow that calls Cekura, extend that one — never add a second.

#### The README section

Append the template in `references/ci-wiring.md`, filled in — what the suite proves, how to trigger
it, the two secrets, and step 2's coverage table including the uncovered rows.

### 7. Lint, then dry run — validation is not optional

**A suite that has not returned `valid: true` from a dry run is not finished.** Say so in those
words rather than handing over a file that looks complete. Everything `lint_suite.py` cannot see
is checked here: whether every metric slug exists *and is enabled for this agent*, whether the
personality is reachable, whether the agent supports the channel the CI job will use, and whether
the server's own validators accept every tag. A spec that fails any of those is not a weaker
suite — it is a suite that cannot run at all.

So the order is: lint, then dry run, then fix, then dry run again, until it comes back valid.

**In a terminal, if there are no credentials in the session, ask for them** — an API key and the
agent id, or an authenticated MCP session. Do not quietly skip to the handoff. In the dashboard the
MCP session is already authenticated, so a missing key is a bug to report, never a question: the
user has nothing to paste. Only when the user cannot supply
them do you hand over unvalidated, and then you must (a) label the suite unvalidated in the
handoff and in the coverage note, (b) give the exact command below, and (c) point out that the
`validate` job in the CI workflow runs the same dry run, so the first pull request will catch
what this session could not.

A dry run validates syntax, metrics, personalities, profiles, target compatibility, planned runs,
and estimated cost without creating objects or placing a call:

```bash
python3 <skill>/scripts/lint_suite.py cekura.tests.json --strict   # free, offline, first
CEKURA_API_KEY=… python3 <skill>/scripts/run_suite.py --dry-run --agent-id 123
```

Both run from this skill's directory — they are authoring tools, not files the repository keeps.
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

### 8. Deliver

Only once the dry run has returned `valid: true`.

**Dashboard** — one `github_open_pull_request` call carrying every file; never one at a time,
never for a suite that has not validated. The body carries what the repository does not: the
coverage table, the uncovered rows and why, the dry-run plan (cases, planned runs, estimated cost),
the two secrets, and — if step 1b found the agent contradicts the repository — that mismatch first.

If the write is refused with `403 Resource not accessible by integration`, the cause is the
`Workflows` permission named in *The deliverable* above — not repository access, which the checkout
already proved. Say that plainly instead of suggesting the connection is broken.

**Terminal** — leave the files in the working tree and stop. Do not commit, branch or
push unless asked; offer the commit message, and `gh pr create` if they want a PR. Report what the
PR body would have carried.

## Handoff

Leave the repository with:

- `cekura.tests.json`, formatted and source-controlled;
- `.github/workflows/cekura-tests.yml` — created, or the existing Cekura workflow extended — with
  the `dry_run` checkbox, and manual dispatch as the only trigger unless the user asked for more;
- the README section from step 6; and
- the dry-run result — `valid: true` with its plan — or the suite explicitly labelled
  **unvalidated** with the command that will validate it.

Report case count, channel/seat coverage, dependencies, anything needing a live run, and — if the
trigger question went unanswered — which trigger you wrote and how to add another. A dry run proves
the spec valid; it does not prove a deployment works.

## Bundled assets

Read when the step calls for them:

- **`references/discovery.md`** — the stack questions, and which assertion each answer unlocks
- **`references/case-catalog.md`** — nine proven case shapes with their drop-if conditions
- **`references/ci-wiring.md`** — workflow and README templates, run targets, triggers
- **`examples/cekura.tests.json`** — a three-case suite that lints clean in `--strict`

Run from this skill's directory while authoring; never copied into the user's repository:

- **`scripts/lint_suite.py`** — offline spec and authoring-rule validator; no key, no network
- **`scripts/run_suite.py`** — posts and polls; used here for the dry run
