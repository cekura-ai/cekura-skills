#!/usr/bin/env python3
"""Validate marketplace-eligibility invariants. Safe to run locally or from CI.

  1. every cekura/skills/*/SKILL.md has spec-compliant frontmatter: name
     matches its directory, description present and <= 1024 chars, body
     <= 500 lines, no `cekura-internal:*` references
  2. version declarations are consistent: plugin.json == package.json, and
     the marketplace plugin entry declares no version (plugin.json is the
     single source -- Claude Code silently prefers it, so a stale duplicate
     would mask releases)
  3. all four platform manifests point at the same MCP URL
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
        text = path.read_text()
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


def check_versions(errors):
    plugin = json.loads((REPO / "cekura/.claude-plugin/plugin.json").read_text())
    pkg = json.loads((REPO / "package.json").read_text())
    if plugin["version"] != pkg["version"]:
        errors.append(
            f"plugin.json {plugin['version']} != package.json {pkg['version']}"
        )
    marketplace = json.loads((REPO / ".claude-plugin/marketplace.json").read_text())
    for entry in marketplace.get("plugins", []):
        if "version" in entry:
            errors.append(
                "marketplace plugin entry must not declare a version - "
                "plugin.json is the single source"
            )


def check_mcp_url_parity(errors):
    # Codex reads the file referenced by .codex-plugin/plugin.json's mcpServers
    # field and requires the camelCase `mcpServers` wrapper (or a direct server
    # map) — snake_case `mcp_servers` silently registers zero servers
    # (openai/codex codex-rs/codex-mcp/src/plugin_config.rs).
    codex_manifest = json.loads(
        (REPO / "cekura/.codex-plugin/plugin.json").read_text()
    )
    codex_mcp_file = REPO / "cekura" / codex_manifest["mcpServers"]
    codex_mcp = json.loads(codex_mcp_file.read_text())
    if "mcpServers" not in codex_mcp:
        errors.append(
            f"{codex_mcp_file}: Codex MCP companion file must use camelCase "
            "'mcpServers' (snake_case 'mcp_servers' registers zero servers)"
        )
        codex_url = None
    else:
        codex_url = codex_mcp["mcpServers"]["cekura"]["url"]
    urls = {
        "cekura/.mcp.json": json.loads((REPO / "cekura/.mcp.json").read_text())
        ["mcpServers"]["cekura"]["url"],
        f"codex ref {codex_manifest['mcpServers']}": codex_url,
        "cekura/.cursor-plugin/plugin.json": json.loads(
            (REPO / "cekura/.cursor-plugin/plugin.json").read_text()
        )["mcpServers"]["cekura"]["url"],
        "gemini-extension.json": json.loads((REPO / "gemini-extension.json").read_text())
        ["mcpServers"]["cekura"]["httpUrl"],
    }
    if len(set(urls.values())) != 1:
        listing = ", ".join(f"{k}={v}" for k, v in urls.items())
        errors.append(f"MCP URL mismatch across manifests: {listing}")


def check_docs_inventory(errors):
    readme = (REPO / "README.md").read_text()
    claude_md = (REPO / "CLAUDE.md").read_text()
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
