# Changelog

All notable changes to the Cekura plugin. Versions follow
[semantic versioning](https://semver.org); the Claude plugin version lives in
`cekura/.claude-plugin/plugin.json` (single source — see CLAUDE.md).

## 0.12.2 — 2026-08-26

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
