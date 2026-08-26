#!/usr/bin/env python3
"""Validate marketplace-eligibility invariants. Safe to run locally or from CI.

  1. every cekura/skills/*/SKILL.md has spec-compliant frontmatter: name
     matches its directory, description present and <= 1024 chars, body
     <= 500 lines, no `cekura-internal:*` references
  2. version declarations are consistent: plugin.json == package.json, and
     no marketplace plugin entry declares a version (the platform plugin.json
     is the single source -- Claude Code and Copilot CLI silently prefer it,
     so a stale duplicate would mask releases)
  3. all five platform manifests point at the same MCP URL
  4. every skill directory is listed in README.md and CLAUDE.md

Usage:
  python3 cekura/scripts/validate_skills.py
"""
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "cekura" / "skills"

MAX_DESCRIPTION_CHARS = 1024
MAX_SKILL_LINES = 500


def check_skill_frontmatter(errors):
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO)
        if not text.startswith("---\n") or "\n---\n" not in text[4:]:
            errors.append(f"{rel}: missing frontmatter")
            continue
        raw = text[4:].split("\n---\n", 1)[0]
        try:
            fm = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            errors.append(f"{rel}: frontmatter YAML parse error: {e}")
            continue
        if fm.get("name") != path.parent.name:
            errors.append(f"{rel}: name must match directory ({path.parent.name})")
        desc = (fm.get("description") or "").strip()
        if not desc:
            errors.append(f"{rel}: missing description")
        elif len(desc) > MAX_DESCRIPTION_CHARS:
            errors.append(f"{rel}: description {len(desc)} chars > {MAX_DESCRIPTION_CHARS}")
        n = len(text.splitlines())
        if n > MAX_SKILL_LINES:
            errors.append(f"{rel}: {n} lines > {MAX_SKILL_LINES}")
        if "cekura-internal:" in text:
            errors.append(f"{rel}: references internal plugin (cekura-internal:*)")


# Every file that declares a release version. A partial bump ships stale
# versions to whichever platform reads the missed manifest (Gate 0 re-run
# 2026-08-05: a clean Gemini install resolved 0.10.0 after the 0.10.1
# release bumped only package/Claude/Codex).
VERSION_SURFACES = (
    "package.json",
    ".claude-plugin/marketplace.json",
    "cekura/.claude-plugin/plugin.json",
    "cekura/.codex-plugin/plugin.json",
    "gemini-extension.json",
    "cekura/.cursor-plugin/plugin.json",
    "cekura/.github/plugin/plugin.json",
)


def check_versions(errors):
    versions = {
        path: json.loads((REPO / path).read_text(encoding="utf-8"))["version"]
        for path in VERSION_SURFACES
    }
    expected = versions["package.json"]
    mismatches = {p: v for p, v in versions.items() if v != expected}
    if mismatches:
        listing = ", ".join(f"{p}={v}" for p, v in sorted(mismatches.items()))
        errors.append(
            f"version drift across release manifests: expected {expected} "
            f"(package.json) but {listing}"
        )
    # Both registries: Claude Code and Copilot CLI resolve the plugin's own
    # manifest first and ignore the marketplace value, so an entry version can
    # only ever go stale and mask a release.
    for registry in (".claude-plugin/marketplace.json", ".github/plugin/marketplace.json"):
        marketplace = json.loads((REPO / registry).read_text(encoding="utf-8"))
        for entry in marketplace.get("plugins", []):
            if "version" in entry:
                errors.append(
                    f"{registry}: plugin entry must not declare a version - "
                    "plugin.json is the single source"
                )


def check_mcp_url_parity(errors):
    # Codex reads the file referenced by .codex-plugin/plugin.json's mcpServers
    # field and requires the camelCase `mcpServers` wrapper (or a direct server
    # map) — snake_case `mcp_servers` silently registers zero servers
    # (openai/codex codex-rs/codex-mcp/src/plugin_config.rs).
    codex_manifest = json.loads(
        (REPO / "cekura/.codex-plugin/plugin.json").read_text(encoding="utf-8")
    )
    codex_mcp_file = REPO / "cekura" / codex_manifest["mcpServers"]
    codex_mcp = json.loads(codex_mcp_file.read_text(encoding="utf-8"))
    if "mcpServers" not in codex_mcp:
        errors.append(
            f"{codex_mcp_file}: Codex MCP companion file must use camelCase "
            "'mcpServers' (snake_case 'mcp_servers' registers zero servers)"
        )
        codex_url = None
    else:
        codex_url = codex_mcp["mcpServers"]["cekura"]["url"]
    # Copilot CLI reads the file referenced by .github/plugin/plugin.json's
    # mcpServers field (a path, per the Open Plugin Spec) — same shape as Codex.
    copilot_manifest = json.loads(
        (REPO / "cekura/.github/plugin/plugin.json").read_text(encoding="utf-8")
    )
    copilot_mcp = json.loads(
        (REPO / "cekura" / copilot_manifest["mcpServers"]).read_text(encoding="utf-8")
    )
    urls = {
        "cekura/.mcp.json": json.loads((REPO / "cekura/.mcp.json").read_text(encoding="utf-8"))
        ["mcpServers"]["cekura"]["url"],
        f"codex ref {codex_manifest['mcpServers']}": codex_url,
        f"copilot ref {copilot_manifest['mcpServers']}":
            copilot_mcp["mcpServers"]["cekura"]["url"],
        "cekura/.cursor-plugin/plugin.json": json.loads(
            (REPO / "cekura/.cursor-plugin/plugin.json").read_text(encoding="utf-8")
        )["mcpServers"]["cekura"]["url"],
        "gemini-extension.json": json.loads((REPO / "gemini-extension.json").read_text(encoding="utf-8"))
        ["mcpServers"]["cekura"]["httpUrl"],
    }
    if len(set(urls.values())) != 1:
        listing = ", ".join(f"{k}={v}" for k, v in urls.items())
        errors.append(f"MCP URL mismatch across manifests: {listing}")


def check_docs_inventory(errors):
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    claude_md = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    for path in sorted(SKILLS.iterdir()):
        if not (path / "SKILL.md").exists():
            continue
        for doc, text in (("README.md", readme), ("CLAUDE.md", claude_md)):
            if path.name not in text:
                errors.append(f"{doc}: skill `{path.name}` is not listed")


def main():
    errors = []
    check_skill_frontmatter(errors)
    check_versions(errors)
    check_mcp_url_parity(errors)
    check_docs_inventory(errors)
    if errors:
        print("skill validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    n = len(list(SKILLS.glob("*/SKILL.md")))
    print(f"skill validation OK ({n} skills; versions, MCP URLs, docs inventory consistent)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
