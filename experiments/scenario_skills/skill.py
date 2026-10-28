"""A proposer may replace the body, but cannot change the protected wrapper."""
from __future__ import annotations

import re
from .common import REPO, digest

SKILL = REPO / "cekura/skills/cekura-eval-design/SKILL.md"


def split(content):
    end = content.index(b"\n---\n", 4) + len(b"\n---\n")
    return content[:end], content[end:]


def protected(body):
    text = body.decode()
    return (re.findall(r"^.*(?:ack:cekura|cekura_skill_started|verification_tag=|plugin_version=).*$", text, re.M),
            re.findall(r"(?:references|examples)/[\w./-]+", text))


def candidate(baseline, body, forbidden=()):
    if not isinstance(body, str) or not body.strip():
        raise ValueError("Proposal must contain a nonempty skill body")
    header, original = split(baseline)
    proposed = body.encode()
    if body.lstrip().startswith("---") or "\x00" in body:
        raise ValueError("Frontmatter is outside the editable surface")
    if protected(original) != protected(proposed):
        raise ValueError("Acknowledgement lines and reference links must remain exact")
    for token in forbidden:
        if len(str(token)) >= 4 and str(token).casefold() in body.casefold() and str(token).casefold() not in original.decode().casefold():
            raise ValueError("Proposal contains fixture-specific material")
    # Public-skill limits and obvious routes for embedding/evaluating a fixture oracle.
    if len((header + proposed).splitlines()) > 500:
        raise ValueError("Candidate exceeds the skill loading/packaging limits")
    if re.search(r"https?://(?:localhost|127\.0\.0\.1)|fixture[_ -]?id|sealed[_ -]?test", body, re.I):
        raise ValueError("Candidate contains benchmark or internal endpoint material")
    return header + proposed


def material(path=SKILL):
    """Exact bytes of the selected skill tree, including all references and bundle."""
    return {str(p.relative_to(path.parent)): p.read_bytes() for p in sorted(path.parent.rglob("*")) if p.is_file()}


def manifest(files):
    return {name: digest(data) for name, data in files.items()}


def apply_edits(parent, edits):
    """The parent's body with each edit's ``anchor`` (exact, occurring once) replaced by its ``replacement``.

    Edits are applied in order to the body only; a missed or ambiguous anchor is an error rather
    than a silent no-op, so a proposal that quotes text loosely cannot be charged for evaluation.
    """
    body = split(parent)[1].decode()
    for edit in edits:
        anchor, replacement = edit["anchor"], edit.get("replacement", "")
        if not anchor or not anchor.strip():
            raise ValueError("Edit %s has an empty anchor" % edit.get("id"))
        count = body.count(anchor)
        if count != 1:
            raise ValueError("Edit %s anchor occurs %d times; it must occur exactly once" % (edit.get("id"), count))
        body = body.replace(anchor, replacement, 1)
    return body
