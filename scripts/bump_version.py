#!/usr/bin/env python3
"""Bump the plugin version everywhere it is declared, in one command.

The repo is the distribution artifact (Claude, Codex, Cursor, Gemini, and
`npx skills` all read git directly), so the version must be materialized
in-tree in several places. This script rewrites all of them together:

  1. the six version-bearing manifests (see VERSION_SURFACES)
  2. every inline `plugin_version="..."` telemetry string in cekura/**/*.md

then runs the CI validators to confirm parity. It never reformats JSON --
each manifest edit is an exact single-occurrence string replacement.

Usage:
  python3 scripts/bump_version.py --patch          # 0.10.6 -> 0.10.7
  python3 scripts/bump_version.py --minor          # 0.10.6 -> 0.11.0
  python3 scripts/bump_version.py --major          # 0.10.6 -> 1.0.0
  python3 scripts/bump_version.py 0.11.2           # explicit version

Remember to add a CHANGELOG.md entry for the new version (the script
reminds you but does not write it).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Keep in sync with VERSION_SURFACES in cekura/scripts/validate_skills.py.
VERSION_SURFACES = (
    "package.json",
    ".claude-plugin/marketplace.json",
    "cekura/.claude-plugin/plugin.json",
    "cekura/.codex-plugin/plugin.json",
    "gemini-extension.json",
    "cekura/.cursor-plugin/plugin.json",
)

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def next_version(current, bump):
    major, minor, patch = (int(x) for x in current.split("."))
    if bump == "--major":
        return f"{major + 1}.0.0"
    if bump == "--minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def replace_exactly(path, old, new, expected):
    text = path.read_text()
    count = text.count(old)
    if count != expected:
        sys.exit(
            f"error: {path.relative_to(REPO)}: expected {expected} "
            f"occurrence(s) of {old!r}, found {count}"
        )
    path.write_text(text.replace(old, new))


def main():
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 1
    arg = sys.argv[1]

    current = json.loads((REPO / "package.json").read_text())["version"]
    if arg in ("--patch", "--minor", "--major"):
        new = next_version(current, arg)
    elif SEMVER_RE.match(arg):
        new = arg
    else:
        sys.exit(f"error: expected --patch/--minor/--major or X.Y.Z, got {arg!r}")
    if new == current:
        sys.exit(f"error: new version {new} equals current version")

    changed = []
    for surface in VERSION_SURFACES:
        path = REPO / surface
        replace_exactly(path, f'"version": "{current}"', f'"version": "{new}"', 1)
        changed.append(surface)

    old_inline = f'plugin_version="{current}"'
    new_inline = f'plugin_version="{new}"'
    md_files = subprocess.run(
        ["git", "ls-files", "cekura/*.md"],
        capture_output=True, text=True, check=True, cwd=REPO,
    ).stdout.splitlines()
    for rel in md_files:
        path = REPO / rel
        text = path.read_text()
        if old_inline in text:
            path.write_text(text.replace(old_inline, new_inline))
            changed.append(rel)

    print(f"bumped {current} -> {new} in {len(changed)} files:")
    for rel in changed:
        print(f"  {rel}")
    sys.stdout.flush()

    for validator in ("validate_skills.py", "validate_ack_tags.py"):
        subprocess.run(
            [sys.executable, str(REPO / "cekura/scripts" / validator)],
            check=True, cwd=REPO,
        )

    print(f"\nreminder: add a CHANGELOG.md entry for {new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
