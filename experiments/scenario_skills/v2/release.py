"""Measure one skill directory, as the production runner delivers it, on a split of the v3 benchmark.

A release is judged on numbers for the text that ships. ``evaluate_revision`` runs a skill
directory (SKILL.md and its references, so a revision whose references differ is installed
whole) through the same evaluator, judge, cache, parallel workers and stage caps as a search
run, under the same signoff, approval, preflight and smoke gates, and records every trial under
a label. ``report`` turns the labels present in a run directory into one comparison: per task
and per check for each arm, the paired check-credit gain with its standard error on training,
and the consistent task-level comparison on sealed.
"""
from __future__ import annotations

import time
from decimal import Decimal
from pathlib import Path

from ..common import digest, read, write
from ..preflight import preflight
from ..runtime import delivered_skill
from ..skill import material
from . import gates
from .budget import trial_cost
from .experiment import Controller, Terminal, identity, judge_for, launch_gate, skill_not_loaded
from .review import gate


def revision_tasks(controller, split, protocol):
    tasks = {"training": controller.training, "validation": controller.validation, "sealed": controller.sealed}[split]
    wanted = protocol.get("release_%s_templates" % split)
    return [t for t in tasks if not wanted or t["template"] in wanted]


def evaluate_revision(config, directory, ledger, skill_dir, label, split="training", trials=3, cap="60", judge=None, evaluator=None,
                      skip_preflight=False, clock=time.time):
    """Every task of ``split`` ``trials`` times with the skill in ``skill_dir``; records are cached like any rollout."""
    skill_dir = Path(skill_dir)
    candidate = (skill_dir / "SKILL.md").read_bytes()
    protocol = config.get("v3_protocol") or {}
    if not gate(directory):
        raise Terminal("awaiting_fixture_and_gold_human_review", "Fixture/gold domain signoff is required before any inference")
    if not launch_gate(directory, identity(config), ledger.authorized_limits["total"]):
        raise Terminal("awaiting_launch_approval", "Launch approval bound to this experiment identity is required")
    if not skip_preflight:
        check = preflight(config)
        write(directory / "preflight.json", {k: v for k, v in check.items() if k != "configuration"})
        if not check["ready"]:
            raise Terminal("preflight_failed", "; ".join(check["failures"]))
        config = check["configuration"]
        from .smoke import smoke_passed
        if not smoke_passed(directory):
            raise Terminal("smoke_required", "Run `v2 smoke` on the current rollout code before any paid stage")
    judge = judge or judge_for(config, directory, ledger)
    if not judge.qualified() and not judge.qualify()["passed"]:
        raise Terminal("judge_not_qualified", "The judge did not meet its qualification threshold with zero critical false passes")
    if evaluator is None:
        from .evaluator import Evaluator
        evaluator = Evaluator(config, directory, ledger, judge)
    # The installed references are the revision's own, and the cache key covers them (``Evaluator.key`` hashes the material).
    evaluator.base_material = material(skill_dir / "SKILL.md")
    controller = Controller(config, directory, evaluator, None, judge, True, clock)
    tasks = revision_tasks(controller, split, protocol)
    if not tasks:
        raise Terminal("no_tasks", "No %s tasks selected" % split)
    stage = "release-%s-%s-%s" % (label, split, digest(candidate)[:12])
    try:
        with ledger.staged(stage, Decimal(str(cap))):
            records = controller.parallel([(candidate, t, "%s_%s" % (label, split), k, True) for k in range(trials) for t in tasks])
    except Exception as error:
        if "Stage allowance" in str(error):
            raise Terminal("release_cap_exhausted", "The %s stage did not fit its $%s cap" % (stage, cap))
        raise
    rows = [{"task": r["task_id"], "template": r["task_id"].split("-")[0], "repeat": r.get("repeat", 0), "status": r["status"],
             "score": r["grade"]["score"] if r.get("grade") else None, "checks": (r.get("grade") or {}).get("checks", {}),
             "failed_checks": (r.get("grade") or {}).get("failed_checks", []), "attribution": (r.get("grade") or {}).get("attribution", {}),
             "critical_failed": (r.get("grade") or {}).get("critical_failed", []), "skill_not_loaded": skill_not_loaded(r),
             "cost_usd": str(trial_cost(r)) if r["status"] == "complete" else None} for r in records]
    delivered = delivered_skill(candidate, config["target"]["snapshot"]["skill_max_chars"])
    out = {"label": label, "split": split, "trials": trials, "skill_dir": str(skill_dir), "sha256": digest(candidate),
           "characters": len(candidate.decode()), "delivered_characters": len(delivered.decode()), "truncated": delivered != candidate,
           "tasks": [t["id"] for t in tasks], "records": rows, "cost_usd": str(sum((Decimal(r["cost_usd"]) for r in rows if r["cost_usd"]), Decimal(0)))}
    write(directory / ("release-%s-%s.json" % (label, split)), out)
    return out


def _records(entry):
    """Scored records in the shape the gates read, skipping rollouts where the skill never loaded."""
    return [{"task_id": r["task"], "candidate_sha256": entry["sha256"], "status": r["status"], "repeat": r["repeat"], "cost_usd": r["cost_usd"],
             "grade": {"score": r["score"], "checks": r["checks"], "failed_checks": r["failed_checks"], "attribution": r["attribution"],
                       "critical_failed": r["critical_failed"], "semantic_status": "judged"}}
            for r in entry["records"] if r["status"] == "complete" and not r["skill_not_loaded"]]


def report(directory, reference=None):
    """One markdown comparison of every ``release-*.json`` in ``directory``; ``reference`` names the arm others are measured against."""
    entries = [read(p) for p in sorted(Path(directory).glob("release-*.json"))]
    by_split = {}
    for e in entries:
        by_split.setdefault(e["split"], []).append(e)
    lines = ["# Release measurement", "", "Production target as configured; every arm installed whole (SKILL.md and references) and delivered as the runner delivers it.", ""]
    summary = {}
    for split, arms in sorted(by_split.items()):
        lines += ["## %s" % split, "", "| Arm | Characters (delivered) | Tasks | Trials | Task passes | Mean check credit | Cost |", "|---|---:|---:|---:|---:|---:|---:|"]
        matrices = {}
        for e in arms:
            recs = _records(e)
            ids = sorted({r["task_id"] for r in recs})
            matrix = gates.check_matrix(recs, ids)
            credits = [gates.credit(matrix[i]) for i in ids if matrix[i]]
            matrices[e["label"]] = (recs, ids, matrix)
            lines.append("| %s | %d (%d%s) | %d | %d | %d / %d | %.3f | $%s |" % (
                e["label"], e["characters"], e["delivered_characters"], ", truncated" if e["truncated"] else "", len(ids), e["trials"],
                sum(r["grade"]["score"] for r in recs), len(recs), sum(credits) / len(credits) if credits else 0, e["cost_usd"]))
        lines.append("")
        ref = reference or (arms[0]["label"] if arms else None)
        for e in arms:
            if e["label"] == ref or ref not in matrices:
                continue
            base, ids_b, _ = matrices[ref]
            mine, ids_m, _ = matrices[e["label"]]
            ids = sorted(set(ids_b) & set(ids_m))
            delta = gates.paired_delta(base, mine, ids)
            consistent = gates.compare_consistent(base, mine, ids, min_gain=1, generator_unresolved=True) if split != "training" else None
            summary.setdefault(split, {})[e["label"]] = {"vs": ref, "gain": delta["gain"], "se": delta["se"], "passed": delta["passed"],
                                                          "regressions": delta["regressions"], "critical_regressions": delta["critical_regressions"],
                                                          "consistent": {k: consistent[k] for k in ("gains", "regressions", "inconsistent")} if consistent else None}
            lines += ["### %s vs %s" % (e["label"], ref), "",
                      "- Paired check-credit gain: %s (SE %s, %d tasks); clears 1.65 SE with no regression: **%s**" % (delta["gain"], delta["se"], delta["tasks"], delta["passed"]),
                      "- Check regressions (pass rate fell by more than one trial in three): %s" % (delta["regressions"] or "none"),
                      "- New critical failures: %s" % (delta["critical_regressions"] or "none")]
            if consistent:
                lines.append("- Consistent task-level gains %s, regressions %s, inconsistent %s" % (consistent["gains"], consistent["regressions"], consistent["inconsistent"]))
            lines += ["", "| Task | %s | %s | Δ credit |" % (ref, e["label"]), "|---|---:|---:|---:|"]
            for i in ids:
                cells = delta["cells"].get(i, {})
                b = sum(c["baseline"] for c in cells.values()) / len(cells) if cells else 0
                m = sum(c["candidate"] for c in cells.values()) / len(cells) if cells else 0
                lines.append("| %s | %.2f | %.2f | %+.3f |" % (i, b, m, delta["deltas"].get(i, 0)))
            lines.append("")
    (Path(directory) / "release-report.md").write_text("\n".join(lines) + "\n")
    write(Path(directory) / "release-summary.json", summary)
    return summary
