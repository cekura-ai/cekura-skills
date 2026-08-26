#!/usr/bin/env python3
"""CI gate: plugin content changes must ship under a new, unpublished version.

Users only receive an update when the version changes, so any PR touching
`cekura/**` has to bump it. Two checks, because "different from my merge base"
is not the same as "not yet published":

  1. did this PR change `cekura/**`? (diff against the merge base) If not,
     no bump is required.
  2. is the version strictly greater than the one on `origin/main` RIGHT NOW?
     Comparing against the merge base lets two PRs branched off the same
     release both bump to the same number; whichever merges second would then
     ship its content under a version users already have.

Usage (CI, on pull requests):
  python3 scripts/check_version_bump.py
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN_JSON = "cekura/.claude-plugin/plugin.json"


def git(*args, check=True):
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=check, cwd=REPO
    )


def parse(version):
    try:
        return tuple(int(x) for x in str(version).split("."))
    except ValueError:
        return None


def main():
    merge_base = git("merge-base", "origin/main", "HEAD").stdout.strip()
    changed = git("diff", "--name-only", merge_base, "HEAD").stdout.splitlines()
    plugin_files = [f for f in changed if f.startswith("cekura/")]
    if not plugin_files:
        print("no cekura/** changes; bump not required")
        return 0

    head_version = json.loads((REPO / PLUGIN_JSON).read_text(encoding="utf-8"))["version"]
    main_raw = git("show", f"origin/main:{PLUGIN_JSON}", check=False)
    if main_raw.returncode != 0:
        print(f"{PLUGIN_JSON} absent on origin/main; nothing to compare")
        return 0
    main_version = json.loads(main_raw.stdout)["version"]

    head, main = parse(head_version), parse(main_version)
    if head is None or main is None:
        print(f"unparseable version (head={head_version} main={main_version})")
        return 1
    if head > main:
        print(f"version bumped: {main_version} (main) -> {head_version}")
        return 0

    if head == main:
        problem = f"still {head_version}, same as origin/main"
    else:
        problem = f"{head_version} is BEHIND origin/main ({main_version})"
    print(f"plugin content changed but {PLUGIN_JSON} is {problem}.")
    print("Users only receive updates when the version changes.")
    print()
    print("  git fetch origin main && git rebase origin/main")
    print("  python3 scripts/bump_version.py --patch")
    print()
    print("changed cekura/** files:")
    for f in plugin_files:
        print(f"  - {f}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
