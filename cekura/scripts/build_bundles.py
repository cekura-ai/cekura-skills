#!/usr/bin/env python3
"""Build per-skill BUNDLE.md files for on-the-fly skill loading over MCP.

`cekura_load_skill` (Cekura MCP server) can only hand the model a single file.
Fetching SKILL.md alone omits the reference files that carry the full authoring
rules, so a loaded-not-installed session is weaker than a real install. This
script pre-concatenates SKILL.md with a curated, high-value subset of each
skill's references into `{slug}/BUNDLE.md`, which the server fetches in one GET.

Targeted, not exhaustive: only the "full rules" reference(s) per skill are
bundled — enough to close most of the quality gap without a multi-thousand-line
payload that clients may truncate. Skills not listed here have no bundle; the
server falls back to SKILL.md for them.

Usage:
  python3 cekura/scripts/build_bundles.py           # (re)write BUNDLE.md files
  python3 cekura/scripts/build_bundles.py --check    # CI: fail if any is stale
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "cekura" / "skills"

# slug -> ordered list of reference filenames (under {slug}/references/) to append.
KEY_REFERENCES = {
    "cekura-eval-design": ["expected-outcomes.md", "coverage-patterns.md"],
    "cekura-metric-design": ["prompt-patterns.md", "advanced-patterns.md"],
    "cekura-metric-improvement": ["feedback-examples.md"],
    "cekura-predefined-metrics": ["selection-by-use-case.md"],
}


def build_bundle(slug, refs):
    skill_dir = SKILLS / slug
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None, f"{slug}: SKILL.md missing"
    parts = [skill_md.read_text().rstrip()]
    for ref in refs:
        ref_path = skill_dir / "references" / ref
        if not ref_path.exists():
            return None, f"{slug}: reference {ref!r} missing"
        parts.append(
            f"\n\n---\n\n# Reference — {ref} (bundled from the {slug} skill)\n\n"
            + ref_path.read_text().rstrip()
        )
    # Trailing newline so the file is POSIX-clean.
    return "\n".join(parts) + "\n", None


def main():
    check = "--check" in sys.argv
    errors, stale, written = [], [], []
    for slug, refs in KEY_REFERENCES.items():
        content, err = build_bundle(slug, refs)
        if err:
            errors.append(err)
            continue
        bundle_path = SKILLS / slug / "BUNDLE.md"
        if check:
            current = bundle_path.read_text() if bundle_path.exists() else None
            if current != content:
                stale.append(slug)
        else:
            bundle_path.write_text(content)
            written.append(f"{slug} ({len(content.splitlines())} lines)")

    if errors:
        print("bundle build FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    if check:
        if stale:
            print("BUNDLE.md is stale (run build_bundles.py and commit):")
            for s in stale:
                print(f"  - {s}")
            return 1
        print(f"bundles up to date ({len(KEY_REFERENCES)} skills)")
        return 0
    for w in written:
        print(f"wrote BUNDLE.md: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
