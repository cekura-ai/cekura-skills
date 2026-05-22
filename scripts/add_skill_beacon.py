#!/usr/bin/env python3
"""Add `cekura_skill_started` beacon hook to every cekura-skills command.

Edits each `.md` file under `cekura/commands/`:
  1. Adds `mcp__cekura__cekura_skill_started` and `mcp__cekura__cekura_report_issue`
     to the YAML `allowed-tools` list (if not already present).
  2. Inserts a top-of-body "## Tracking (do this first)" block telling the
     agent to call the beacon before any other work.

Idempotent: re-running on an already-edited file is a no-op.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path("/Users/dileep/cekura/repo/cekura-skills/cekura/commands")
NEW_TOOLS = (
    "mcp__cekura__cekura_skill_started",
    "mcp__cekura__cekura_report_issue",
)

TRACKING_MARKER = "<!-- cekura-tracking-beacon -->"
TRACKING_BLOCK_TEMPLATE = """{marker}

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="{skill_name}"`. If a conversation/session ID is available (e.g. you
were invoked from Cekura sandbox), also pass it as `conversation_id`. The call
returns immediately; it lets us understand which skills are actually being used.

If anything in this skill turns out to be ambiguous, broken, or missing a
needed tool, call `mcp__cekura__cekura_report_issue` to flag it. Use this
LIBERALLY — even `severity="low"` reports are valuable feedback.

"""

FRONTMATTER_RE = re.compile(r"^---\n(.*?\n)---\n", re.DOTALL)


def patch_allowed_tools(frontmatter: str) -> tuple[str, bool]:
    """Return (new_frontmatter, changed)."""
    m = re.search(r'^(allowed-tools:\s*)(\[.*?\])\s*$', frontmatter, re.MULTILINE | re.DOTALL)
    if not m:
        return frontmatter, False
    list_text = m.group(2)
    changed = False
    for tool in NEW_TOOLS:
        if tool not in list_text:
            list_text = list_text.rstrip().rstrip("]")
            if list_text.endswith(","):
                list_text = list_text + f' "{tool}"]'
            elif list_text.endswith("["):
                list_text = list_text + f'"{tool}"]'
            else:
                list_text = list_text + f', "{tool}"]'
            changed = True
    if not changed:
        return frontmatter, False
    return frontmatter[: m.start(2)] + list_text + frontmatter[m.end(2) :], True


def patch_file(path: Path) -> str:
    text = path.read_text()
    m = FRONTMATTER_RE.search(text)
    if not m:
        return f"skip (no frontmatter): {path.name}"

    front = m.group(1)
    body = text[m.end():]

    new_front, front_changed = patch_allowed_tools(front)

    if TRACKING_MARKER in body:
        body_changed = False
    else:
        # Locate the first heading after the frontmatter and inject above it.
        skill_name = path.stem  # filename without .md
        block = TRACKING_BLOCK_TEMPLATE.format(marker=TRACKING_MARKER, skill_name=skill_name)
        body = block + body.lstrip("\n")
        body_changed = True

    if not (front_changed or body_changed):
        return f"no-op: {path.name}"

    new_text = "---\n" + new_front + "---\n" + body
    path.write_text(new_text)
    return f"patched: {path.name} (frontmatter={front_changed}, body={body_changed})"


def main() -> int:
    if not ROOT.is_dir():
        print(f"missing: {ROOT}", file=sys.stderr)
        return 2
    for md in sorted(ROOT.glob("*.md")):
        print(patch_file(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
