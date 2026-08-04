# Changelog

All notable changes to the Cekura plugin. Versions follow
[semantic versioning](https://semver.org); the Claude plugin version lives in
`cekura/.claude-plugin/plugin.json` (single source — see CLAUDE.md).

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
