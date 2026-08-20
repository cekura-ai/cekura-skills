#!/usr/bin/env python3
"""Bump the plugin version everywhere it is declared, in one command.

The repo is the distribution artifact (Claude, Codex, Cursor, Gemini,
Copilot, and `npx skills` all read git directly), so the version must be
materialized
in-tree in several places. This script rewrites all of them together:

  1. the seven version-bearing manifests (see VERSION_SURFACES)
  2. the inline `plugin_version="X.Y"` telemetry tags in cekura/**/*.md, which
     carry major.minor only -- a patch release leaves every skill, bundle, and
     command file untouched

then runs the CI validators to confirm parity. It never reformats JSON --
each manifest edit is an exact single-occurrence string replacement.

Usage:
  python3 scripts/bump_version.py --patch          # 0.10.6 -> 0.10.7
  python3 scripts/bump_version.py --minor          # 0.10.6 -> 0.11.0
  python3 scripts/bump_version.py --major          # 0.10.6 -> 1.0.0
  python3 scripts/bump_version.py 0.11.2           # explicit version
  python3 scripts/bump_version.py --sync-with-main # origin/main's version + 1
                                                   # patch; no-op if already
                                                   # ahead of main

`--sync-with-main` is what CI runs for the `sync-version` label: it needs no
rebase (the version only has to beat what is published) and re-running it is a
no-op, so re-labelling a PR never inflates the version.

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
    "cekura/.github/plugin/plugin.json",
)

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def major_minor(version):
    return ".".join(version.split(".")[:2])


def parse(version):
    return tuple(int(x) for x in str(version).split("."))


def origin_main_version():
    out = subprocess.run(
        ["git", "show", "origin/main:package.json"],
        capture_output=True, text=True, cwd=REPO,
    )
    if out.returncode != 0:
        sys.exit("error: cannot read package.json on origin/main (fetch it first)")
    return json.loads(out.stdout)["version"]


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
    if arg == "--sync-with-main":
        main_version = origin_main_version()
        if parse(current) > parse(main_version):
            print(f"{current} is already ahead of origin/main ({main_version}); "
                  "nothing to do")
            return 0
        new = next_version(main_version, "--patch")
    elif arg in ("--patch", "--minor", "--major"):
        new = next_version(current, arg)
    elif SEMVER_RE.match(arg):
        new = arg
    else:
        sys.exit("error: expected --patch/--minor/--major/--sync-with-main "
                 f"or X.Y.Z, got {arg!r}")
    if new == current:
        sys.exit(f"error: new version {new} equals current version")

    changed = []
    for surface in VERSION_SURFACES:
        path = REPO / surface
        replace_exactly(path, f'"version": "{current}"', f'"version": "{new}"', 1)
        changed.append(surface)

    # Telemetry tags carry major.minor, so patch releases touch no markdown.
    old_inline = f'plugin_version="{major_minor(current)}"'
    new_inline = f'plugin_version="{major_minor(new)}"'
    if old_inline != new_inline:
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
