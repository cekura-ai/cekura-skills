# Changelog

All notable changes to the Cekura plugin. Versions follow
[semantic versioning](https://semver.org); the Claude plugin version lives in
`cekura/.claude-plugin/plugin.json` (single source — see CLAUDE.md).

## 0.15.1 — 2026-09-04

**The LiveKit/Pipecat GitHub offers are `<clarification>` blocks, not prose.**
0.15.0 gave them as quoted prose, so on the Cekura platform they rendered as a
remark and the turn never paused: measured live, the assistant said "If you
connect it under Settings -> Integrations -> GitHub, I can pull all of that"
and continued straight into "A few questions to shape the setup:". The offer
was decorative and the user had nothing to answer. Both the connect offer and
the scan offer now specify the block and its options, in `phase2-agent.md`
2b' and `phase2-provider.md` 2a', with an explicit rule against batching the
config questions into the offer's turn — a scan answers most of them, and the
offer is branch-determining.

## 0.15.0 — 2026-09-04

**LiveKit and Pipecat onboarding now reads the user's repo instead of
interrogating them, and the SDK offer ends in a pull request.** Nothing about
these two providers auto-imports — the system prompt, language, dispatch name
and connection mode all had to be collected by hand, while every one of them
was sitting in the user's code.

- **`cekura-onboarding/phase2-agent.md`** — new §2b′ offers to read the
  connected repo before any config is collected, and offers to *connect*
  GitHub when no connection exists (these agents are code-based, so the
  connection is worth one sentence). The user can name the repo directly
  instead of having one guessed. Credentials are read from the deployment
  manifest, never the values, and the remaining ask points at
  Settings → Provider API Keys with a confirm-when-saved handshake. The
  "FIRST question is the connection mode" rule now yields to the scan — it
  had been bolded above a footnote saying the scan came first, and the bold
  rule won.
- **`cekura-create-agent/phase2-provider.md`** — the same offer as §2a′. It
  existed nowhere on this path, which is the one "onboard my LiveKit agent"
  actually takes.
- **`cekura-onboarding/phase6-testing-next.md`** — the SDK is now offered
  proactively once results are shown, with the testing / observability / both
  scope asked rather than inherited. Every other row in that table waits for
  the user to describe a problem, which they can only do if they know the data
  exists; the SDK *is* the data.
- **`cekura-create-agent/phase6-sdk-integration.md`** — new §6·0 surface check
  and §6P platform branch. The existing flow assumed local Claude Code
  (`pip install`, in-place `Edit`, "do not ask permission"), none of which is
  possible in the Cekura sandbox. §6P checks out the repo, shows a short plan
  plus per-file diffs, waits for explicit confirmation, then opens a PR whose
  code reads `CEKURA_API_KEY` and `CEKURA_AGENT_ID` from the environment — no
  secret in the diff. `tracing_enabled` flips only after the user confirms
  merge, env vars and redeploy; setting it at PR time makes every run wait on
  a webhook that never arrives.

Also corrects a stale claim in `phase2-agent.md` §2c that the Cekura platform
UI has no codebase access. It does, when the org's GitHub is connected.

## 0.14.0 — 2026-09-03

**`cekura-infra-test-suite` now produces a Tests-as-Code suite in the
repository, not dashboard evaluators.** The skill reads the voice-agent
codebase and writes a committed JSON spec that CI submits to
`run_scenarios_json`, so a prompt change and the cases covering it land in the
same pull request. It creates the spec, the runner and the CI workflow, or
updates them in place when they already exist — and `no suite change` is a
valid, common outcome of an update. Cekura stays read-only throughout: the only
permitted write-like request is a `dry_run=true` validation.

Bundled with the skill:

- `scripts/lint_suite.py` — offline spec and authoring-rule validator. No API
  key, no network, so it runs on every push including fork pull requests. Its
  tag rules mirror the server's own validators.
- `scripts/run_suite.py` — CI runner that posts the spec, polls every run to a
  terminal state and exits non-zero on failure. Runs are asynchronous, so a
  workflow that stops at the POST reports success before any call is judged;
  this is what makes the gate able to fail.
- `references/discovery.md`, `references/case-catalog.md`,
  `references/ci-wiring.md` and `examples/cekura.tests.json` — the stack
  questions and what each answer lets you assert, nine proven case shapes with
  the conditions under which each is a dead test, workflow templates for GitHub
  Actions and GitLab, and a worked three-case suite.

The five `phase*.md` files are removed; their discovery content is condensed
into `references/discovery.md`, and the parts that planned dashboard folders,
evaluator creation and scenario-id run scripts are gone with the output they
served. npx users: run `npx skills add cekura-ai/cekura-skills --all`.

**`cekura-infra-test-suite` now writes expected outcomes to the judge's
contract.** Two end-to-end tests — one Pipecat repo, one LiveKit repo, fresh
agent each time — produced 14 cases whose turn lists were flawless and whose
judge criteria broke five rules in
`cekura-eval-design/references/expected-outcomes.md`, in all 14. The cause was a
missing pointer: step 4 routed to the conditional-actions reference, which
teaches turn syntax, and never to the expected-outcomes reference, which teaches
the criteria. The skill got what it asked for.

Step 4 now names that reference and states the rules a CI suite breaks most
often: every statement starts with "The main agent should", one per line, 2–6
atomic lines; "main agent" and "testing agent" are the only speaker labels; no
test-setup rationale; no subjective descriptors; no grading of farewells or call
termination unless that is the case's declared point; and every statement must
be fired by a written turn, since one whose trigger never occurs returns
`blocked` on every run.

`scripts/lint_suite.py` enforces the mechanical half as warnings, so `--strict`
catches them in CI: speaker-label leakage, statements that are narrative rather
than "The main agent should…", subjective descriptors, embedded test rationale,
and closing/termination grading outside a case that declares itself about it.
The bundled `examples/cekura.tests.json` is rewritten to the contract and lints
clean under `--strict`.

Also documents that `expected_outcome` is scored only when the Expected Outcome
metric is attached, and that an infrastructure suite should attach the agent's
enabled numeric metrics — latency, interruption — which measure what a judge
reading a transcript cannot.

Two fixes from testing the skill against a 101,836-line repository and a
3,742-line TypeScript one. **Scope now has a stop condition:** if covering a
behavior would need a change outside the spec, its coverage note, the scripts
and the CI file — runtime code, a deploy workflow, a Cekura record, a metric
that does not exist — the skill reports the blocker instead of making the
change to enable its own test. On the large repo it had edited runtime code to
make a feature reachable from CI: sound reasoning, minimal diff, still not its
call. Updating a guard that exists to police the suite itself, such as a
workflow step asserting the case count, is explicitly not a scope change.

**New step 1b: read the agent record.** Enabled metrics, usable personalities,
the agent's provider and channel, and the live schema were listed as required
inputs but no workflow step fetched them, so a session with a working API key
still authored as though it had none — `expected_outcome` alone and no pinned
personality. The numeric metrics are the ones that measure what a
transcript-reading judge cannot, which for an infrastructure suite is most of
the point.

**The dry run is now a hard completion gate.** A suite that has not returned
`valid: true` is not finished, and the skill says so in those words instead of
handing over a file that looks complete. With no credentials in the session it
asks for them rather than skipping quietly; only if they cannot be supplied does
it hand over, and then it must label the suite unvalidated, give the exact
command, and point at the workflow's `validate` job as the backstop. It also
reads the returned plan rather than the flag alone — the metrics each case
resolved, and `test_profile: {mode: "inline"}` where an inline block was given.

**The update path no longer bypasses the authoring rules.** Step 0 routed an
update straight to step 5, which skipped the agent-record read and the
expected-outcome contract — measurably, the same repository produced 0 lint
warnings on a create and 3 on an update. Starting at step 5 is now stated as the
entry point, not a shortcut: anything authored still runs through steps 1b, 4
and 6. Pre-existing warnings on untouched cases are to be reported and left, not
silently rewritten.

**Version surfaces resynced.** The inline `plugin_version` telemetry tags had
drifted a minor behind the manifests, which `bump_version.py` cannot repair on
its own — it only rewrites tags matching the current major.minor. All 14 are
now level with the manifests, and `cekura/.github/plugin/plugin.json` rejoins
the other six.

## 0.13.0 — 2026-08-28

**The eval-design playbook now teaches conditional actions where agents actually
read it.** Production telemetry showed that every correlated conditional-actions
scenario was written without the 76 KB reference ever being opened, so the root
`cekura-eval-design` skill now carries the whole authoring contract — payload
shape, the five required condition fields, how the runtime matcher fires an
`asks …` trigger (only on a real question, so a condition written against an
agent that *states* a need never fires), the complete tag table with its real
placement and range constraints, functions, attached audio, and a ten-point
self-check to run before every write. The reference keeps the pattern library and
troubleshooting.

**Changing existing evaluators is a documented flow.** Editing, not creating, is
most of the real work, and the skill had no procedure for it: it now says to read
the evaluators first (including the export the Evaluators page attaches to the
chat), audit them against the rubric, send the smallest possible PATCH — the
whole `conditional_actions` object, because a partial one deletes the scenario's
functions — and read back a diff. Bulk edits, duplicates and version labels are
covered, as is the usual cause of a metric stuck at 50.

**Generation is the default write path in every mode.** The skill previously stated
that the generator could not produce conditional actions and sent every structured
scenario down the hand-authoring path, discarding the grounding the generator does
against the agent description, knowledge base and mock tools. Behavioural scenarios,
conditional actions and red-team plans now all come from the generator —
`simulation_type` picks the output format, the generator knows the full tag set and
honours tag requirements in `extra_instructions` — while one scenario whose
conduct the user has laid out — a dictated script, one persona with its exact
behaviour, an exact timing value, a patch — may be created directly under a new
pre-create self-check (first person in `<scenario>` tags, a trigger on every step, no
voice traits in the text, profile placeholders, outcome, personality, folder, tool ids
and the baseline metrics). Any count, category or "generate" request stays a
generation call, with the user's stated facts carried into `extra_instructions`. The
`/autogen-eval` and `/manual-create-update-eval` commands load `cekura-eval-design`
before their tracking call, and the coordinator routes create, update and generate
requests — and mock-data or test-profile requests for a test — to the skill first. The agent under test is read-only while authoring.

**Manual creates no longer ship without metrics.** `scenarios_create` starts with
none attached while generation attaches the project's set, and the skill now
carries the name-to-id lookup, the baseline four, and what to do when one is not
enabled for the project. Runs without metrics only report that a call happened.

**The checkpoint is one adaptive question.** The seven-item gate is replaced by a
single consolidated question covering only what the request and the agent record
do not already answer, skipped entirely when the user said to proceed.

**Expected outcomes account for what the transcript can prove.** New rules cover
providers whose tool calls never reach the transcript (grade what the agent says,
not what it did), branches a correct agent may skip, and success that runtime
state controls rather than the scenario.

**Bounded generation polling.** "Always poll" now carries the stop conditions the
0.10.11 reliability protocol added: report real counts about every 30 s, give up after
~5 minutes at zero progress (one retry with a smaller batch, then report), treat a
freeze short of the total as done, and let the stall rule override "proceed
autonomously". An A/B run against a stalled generator showed the unbounded instruction
producing 51 poll calls where the previous release made 6.

**Tag and generation-field corrections against backend validators.** `<speed>` accepts
0.1–2.0 (0.8–1.2 is the natural-speech band, not the API limit); `<network_simulation>`
supports `jitter` and `latency` in milliseconds alongside `packet_loss` percent — both
were wrong in 0.12.2 and in every reference site. `generation_files` accepts XML as well
as PDF/TXT/JSON/CSV/MD, up to 10 files. The expected-outcome judge reads the transcript
plus injected run metadata (per-turn timing, duration, call-end reason), not the
transcript alone. `manual-create-update-eval` no longer lists `TOOL_SEND_DTMF` /
`TOOL_RECEIVE_DTMF`, which are not in the accepted tool set, and no longer tells authors
to add a provider prefix.

**The commands defer to the skill's checkpoint.** `/autogen-eval`'s gate now fires when
the user asked to see a plan or something is unresolved, instead of on every request;
`/manual-create-update-eval`'s field-by-field interview applies when the user chose that
walkthrough, and its approval step is skipped when the skill's single checkpoint already
ran. Verbatim user-supplied scenario text is exempt from the direct-create style checks
that would require rewriting it.

**Corrections.** Reading the agent with `aiagents_retrieve` before the first
write is now explicit (the list endpoint returns no description).
`manual-create-update-eval` no longer documents condition `type` as `"say"`/`"do"`
— the only accepted values are `standard` and `action_followup`, so following it
produced a validation error. Red-team generation now carries a table of
the six `attack_type` values and what each one tries to make the agent do, with one
generation call per type; its output is a multi-turn conditional-actions plan, and
`generation_files` is workflow-only.
`<background_noise>` and `<noise>` volumes are 0–1.0, not the 0.5–2 the reference
claimed, and a payload with conditional-action content must set
`scenario_type` or it is stored as plain instruction text. And fixing
an evaluator whose metric sits at 50 re-checks every outcome line, not only the line
that blocks: a leftover hang-up or "politely" line keeps the evaluator wrong.

**Routing content the first rewrite dropped is back.** The which-mode-for-which-request
table, the infra-and-pipeline rule with its reason, the ask-first question, the
instruction style rules and `<scenario>` shape, closing gaps with another generation
run, mock-entry trigger closure, `X-` custom headers, the IVR inbound/outbound `id: 0`
split, and the hard gate on "first show me the plan" are in `SKILL.md` again.

**The skill body is guidance, not a tool script.** `cekura-eval-design` no longer
names MCP tools or describes server behaviour (validation errors, schema gaps,
defaults); it states what to do and leaves the call selection to the tool
descriptions in whichever harness is running it. The slash commands keep their
exact tool sequences.
## 0.12.3 — 2026-08-29

**Two crying sounds for `<noise>`.** `female-crying` and `male-crying` join
`office`, `beep`, `cough1` and `cough2` as one-shot sound names. Each is about
ten seconds of a person sobbing, for evaluators that check whether the agent
notices a caller in distress and asks if everything is okay. `cekura-eval-design`
lists them alongside the other one-shot sounds and shows how to shorten the clip
with `time`.

## 0.12.2 — 2026-08-26

Also corrects the `PUT` description: replacing a recording can rename it, and
repoints every tag, so it — not delete-and-re-add — is the way to change the
audio of a clip several steps use.

**Recording names follow one convention everywhere.** The upload endpoint now
derives a readable id from the filename when `name` is omitted, matching what the
editor proposes, so an evaluator created through MCP names its recordings the way
a person would instead of getting an opaque generated id. `cekura-eval-design`
says to omit `name` and documents the shape to follow when overriding it.

## 0.12.1 — 2026-08-25

**Attached audio can be referenced, not just uploaded.** A recording now
belongs to the scenario rather than to one step, so `<audio id="…"/>` may appear
in several conditions and more than once in one action, and a recording's id is
a name chosen at upload. `cekura-eval-design` no longer says never to emit an
`<audio>` tag: it says to reference recordings that already exist, reading the
available ids from the scenario's `condition_audio` map, and to reuse one rather
than asking for the same audio twice. A referenced recording that does not exist
now blocks the run rather than the save, so the guidance says what to do when
the wanted audio is not there.

## 0.12.0 — 2026-08-20

**Breaking — skill consolidation.** `cekura-self-improving-agent` is rewritten
around a per-project **capability manifest** (`.cekura/selfimprove.yaml`): it
now covers agents whose config lives in the customer's own stack (repo,
database, prompt registry, runtime-created provider agents, custom mock
servers) as well as dashboard-managed providers, with hard safety invariants —
artifact-based must-fail-first reproduction (mode-aware run counts), runtime
readback attestation, no production mutation inside the loop, and an explicit
Promote phase. **`cekura-fixing-prod-issues` is removed** — prod-call bug
fixing is covered by the rewritten skill (same must-fail-first gate and PR
hand-off). npx users: run `npx skills add cekura-ai/cekura-skills --all` to
pick up the rewrite and drop the removed skill.

- **Added** run labeling: every `scenarios_run_*` call now passes `name`
  (`[selfimprove:<session>] <phase> — <detail>` / `[prod-fix <call_id>]
  phase<N> ...`) so dashboard results map back to session and phase across the
  self-improve and prod-fix workflows.

- **Added** two reproduce-phase guards from observed multi-run money pits:
  a **metric-fit check** (a thresholded prod metric can be structurally blind
  in sim when the testing agent's timing differs from the prod counterpart —
  assert the defect itself via expected_outcome bullets or a custom-code
  metric instead) and a **mechanics-doc consult** (read cekura-eval-design's
  `conditional-actions.md` before authoring tag-driven scenarios; two
  consecutive non-triggering runs with an unchanged harness → stop firing
  and re-diagnose the harness, not the bug).

- **Added** a deterministic reproduction-gate hook (`hooks/repro-gate.sh`,
  `PreToolUse`): while a `.cekura/selfimprove.lock` session is active with no
  valid `repro.json`, file edits and provider-mutating requests are denied at
  the tool layer — prose gates were reinterpreted twice in the wild (pytest
  substituted for simulation reproduction). Fault-injection edits marked
  `CEKURA-REPRO-INJECT` and `.cekura`/`.claude` writes remain allowed;
  sessions without the lockfile are untouched. Claude Code installs only.

- **Changed** reproduction to run the minimum simulations the failure allows
  (self-improve and prod-fix workflows): classify the reproduction mode first —
  deterministic failures (trigger forced via scenario construction or
  temporary `CEKURA-REPRO-INJECT` fault injection in the local bot) reproduce
  with a single must-fail run and verify 2/2 with the trigger active;
  stochastic LLM prompt/workflow failures size the batch from the observed
  failure rate (`clamp(⌈2/p̂⌉, 4, 10)`) and must fail at least twice.

- **Changed** the reproduction gate to be artifact-based across
  the self-improve and prod-fix
  workflows: reproduction is passed only by a recorded
  Cekura `result_id` with fail counts (`repro.json` / gate line), restated
  verbatim by every downstream phase and cited in the final PR. Failing
  unit/code tests, logs, and original production calls explicitly never
  satisfy the gate — closes the observed insight-entry shortcut where a
  coding agent substituted pytest for simulation reproduction.

- **Added** the capability-manifest framework underpinning the rewritten
  self-improve loop for agents whose real config lives in the customer's own
  stack (prompts in a repo, tools in a DB, prompt registry in Langfuse,
  provider agents created at deploy time, customer-operated mock servers).
  Fixed safety invariants (must-fail-first, runtime readback attestation,
  no production mutation inside the loop, overfitting gate, budgets, audit
  trail) plus a per-project `.cekura/selfimprove.yaml` declaring typed
  read/render/apply/deploy/verify capabilities. Ships a JSON schema, a
  manifest guide, setup/loop/promote phases, and three recipes
  (provider-managed, runtime-created, custom-mocks). Collect/Debug/Reproduce/
  Regression semantics are reused from `cekura-self-improving-agent`.

## 0.10.12 — 2026-08-18

Generation reliability, driven by production call-log triage (18 conversations)
and validated with recorded E2E runs plus a repeated-trial failure hunt
(cekura-ai/cekura-skills#138).

- **Added** a hard confirmation gate to the pre-creation checkpoint: no
  `scenarios_generate_bg`/`scenarios_create` before the user approves the plan
  (only an explicit "proceed autonomously" skips it). Unreadable source files
  override autonomy — stop and ask, never generate from a stand-in.
- **Added** § Reliability Protocol to the eval-design auto-generation
  reference: readable-input checks, source-count reconciliation, per-language
  generation batches, ~10s polling with ~30s progress reports stating real
  elapsed time, a 5-minute 0/N stall rule (one smaller retry, then a clear
  stop — overrides autonomous mode), a 4-minute frozen-short-of-total rule,
  and post-generation verification (count, 1:1 plan diff, language/roles,
  expected outcomes, tools, metrics).
- **Added** "generate scenarios" trigger phrasings to the eval-design skill
  description — the most common generation wording previously never loaded
  the skill.
- **Added** fail-fast rules to `run-evals` (billing errors, capped dialing
  waits, verbatim LiveKit/SIP errors) and to `create-agent` phase 5 (max two
  provider-credential attempts; never build an agent on a guessed prompt).

## 0.10.11 — 2026-08-18

Adds **GitHub Copilot** as a natively supported platform. Purely additive — the
Claude, Codex, Cursor, Gemini, and `npx skills add` paths are untouched.

- **Added** `.github/plugin/marketplace.json` (root) and
  `cekura/.github/plugin/plugin.json` — a Copilot CLI plugin registry and
  manifest (Open Plugin Spec) resolving into the same `cekura/` plugin root, so
  `copilot plugin marketplace add cekura-ai/cekura-skills` +
  `copilot plugin install cekura@cekura-skills` installs all 12 skills and the
  Cekura MCP server (OAuth on first tool use).
- **Why separate manifests:** Copilot CLI falls back to `.claude-plugin/` for
  both marketplace and plugin manifests, so it would have half-worked off
  Claude's files. Its own `.github/plugin/` files rank higher in Copilot's
  resolution order, which keeps the two platforms from constraining each other.
- **Deferred:** slash commands (Copilot plugins have no equivalent) and
  subagents (Copilot only discovers `agents/*.agent.md`; ours are Claude-style
  `*.md`). Copilot hooks (camelCase `sessionStart`, `version: 1`) are not
  shipped, so there is no daily auto-update hook on Copilot yet — use
  `copilot plugin update cekura`.
- **Changed** `validate_skills.py` to treat the Copilot manifest as a seventh
  version-bearing surface, assert its MCP URL matches the other four, and
  reject a `version` on either marketplace's plugin entries;
  `scripts/bump_version.py` now rewrites it too.
- **Documented** the Copilot CLI install, the `.github/skills/` path for the
  Copilot coding agent / code review / IDE extensions
  (`npx skills add ... --agent github-copilot --output .github/skills`), and a
  Copilot row in the platform compatibility table. The coding agent and code
  review don't support OAuth remote MCP, so those surfaces need the
  `X-CEKURA-API-KEY` credential — noted in the README.

## 0.10.10 — 2026-08-12

Release-tooling change; no skill content changes.

- **Changed** the inline `plugin_version="..."` telemetry tags in skills,
  bundles, and commands to carry **major.minor only** (`"0.10"`). A patch
  release now rewrites 6 files instead of 21 — the tags only change on a
  minor/major bump. `validate_ack_tags.py` compares them against the
  major.minor of `package.json`. Requires the MCP server to compare versions
  at the precision reported (cekura-ai/docs#872), otherwise every install on
  the latest patch would get a spurious update nudge.
- **Added** `scripts/bump_version.py` — one command rewrites all six
  version-bearing manifests (and the telemetry tags when major.minor moves),
  then runs the validators. Never hand-edit versions across files.
- **Added** `scripts/check_version_bump.py`, replacing the inline CI gate. The
  version must now be strictly greater than the one on `origin/main` at CI
  time, not merely different from the PR's merge base — two PRs branched off
  the same release could otherwise both bump to the same number, and whichever
  merged second shipped content under an already-published version.

## 0.10.3 — 2026-08-07

- **Added** the `<voice provider="P" id="X" model="Y" />` conditional-action tag
  to `cekura-eval-design` (SKILL.md, `references/conditional-actions.md`) and
  `codex/AGENTS.md` / `GEMINI.md`. It switches the testing agent's TTS voice
  mid-call, which is the only way to put a second speaker in one simulated call
  — a caller handing the phone over, a supervisor taking the line. Previously
  this needed an attached audio recording, which also fixes the dialogue.
  Documents the provider/voice-id format pairing (Cartesia ids are UUIDs,
  ElevenLabs ids are alphanumeric), the per-provider default models, and that
  the provider itself cannot change mid-call.

## 0.10.2 — 2026-08-05

Manifest version-parity release (no functional changes).

- **Fixed** version drift found by the Gate 0 closure re-run: the 0.10.1
  release bumped `package.json` and the Claude/Codex manifests but missed
  `gemini-extension.json` and `cekura/.cursor-plugin/plugin.json`, so a
  clean Gemini install resolved 0.10.0. All six version-bearing release
  surfaces now declare 0.10.2.
- **Changed** `validate_skills.py` `check_versions` to enforce equality
  across every version-bearing manifest (package, top-level marketplace,
  Claude, Codex, Gemini, Cursor) with path-specific mismatch errors, so CI
  rejects any future partial release bump.

## 0.10.1 — 2026-08-04

Gate 0 acceptance-test fixes.

- **Fixed** Codex MCP registration: `cekura/.codex-plugin/plugin.json` now
  points at `cekura/.mcp.json` (camelCase `mcpServers`, the shape Codex
  actually parses) and the snake_case `cekura/codex-mcp.json` was removed —
  it registered zero servers because Codex read `mcp_servers` as a server
  name. CI now asserts the referenced companion file uses the camelCase
  wrapper.
- **Fixed** first-launch delay on fresh Claude Code installs: the
  SessionStart auto-update hook now stamps and skips its first run instead
  of hitting the network (~7 s observed) before the first session. Daily
  update checks begin with the next session at least 24h later.

## 0.10.0 — 2026-08-04

Marketplace-eligibility release.

- **Added** MIT `LICENSE`, `CHANGELOG.md`, and CI validation
  (`.github/workflows/validate.yml` + `cekura/scripts/validate_skills.py`):
  JSON manifests, ack tags, bundle freshness, `codex/AGENTS.md`/`GEMINI.md`
  sync, Agent Skills frontmatter limits, MCP URL parity across all platform
  manifests, docs inventory, and a mandatory version bump whenever `cekura/**`
  changes.
- **Changed** `cekura-flag-call-log-failures` and `cekura-generate-scenarios`
  to be fully public-facing (removed internal skill references and
  customer-specific details; spec-compliant frontmatter). The
  `cekura-generate-scenarios` verification tag was rotated (old tags remain
  valid).
- **Changed** Codex packaging: `cekura/.codex-plugin/plugin.json` now points
  at `cekura/codex-mcp.json` (snake_case `mcp_servers`, per OpenAI plugin
  packaging docs). Claude Code continues to use `cekura/.mcp.json`.
- **Changed** version declaration to a single source: the marketplace plugin
  entry no longer declares a `version`; `cekura/.claude-plugin/plugin.json`
  is authoritative.
- **Fixed** invalid YAML frontmatter in `cekura/commands/cekura-report.md`
  that failed `claude plugin validate`.
- **Changed** all example content to fully anonymized placeholders (customer
  names, identifiers, and infrastructure details replaced with fictional
  values); added a README "Data & privacy" section documenting the
  skill-usage ping, the local failure log, and auto-update behavior.
- **Docs** README/CLAUDE.md now list all 12 skills and describe the current
  per-platform MCP wiring.

## 0.9.0 and earlier

Pre-changelog releases: single `cekura` plugin with 12 skills, 14 commands,
2 sub-agents, MCP auto-config, and MCP-failure/auto-update hooks. See git
history.
