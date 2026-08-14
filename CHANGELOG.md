# Changelog

All notable changes to the Cekura plugin. Versions follow
[semantic versioning](https://semver.org); the Claude plugin version lives in
`cekura/.claude-plugin/plugin.json` (single source — see CLAUDE.md).

## 0.11.0 — 2026-08-11

- **Changed** the reproduction gate to be artifact-based across
  `cekura-self-improve-1`, `cekura-self-improving-agent`, and
  `cekura-fixing-prod-issues`: reproduction is passed only by a recorded
  Cekura `result_id` with fail counts (`repro.json` / gate line), restated
  verbatim by every downstream phase and cited in the final PR. Failing
  unit/code tests, logs, and original production calls explicitly never
  satisfy the gate — closes the observed insight-entry shortcut where a
  coding agent substituted pytest for simulation reproduction.

- **Added** `cekura-self-improve-1`, a capability-manifest variant of the
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
