"""Check audit over scored rollouts: which checks never move, which flip between identical trials, which never fail.

Reads ``scored/*.json`` from one or more run directories and labels each revision (the baseline
skill or a ``candidate-N.md`` of that run). It reports, never changes: a check that failed under
every revision of a task may be a benchmark defect or a capability limit, a check that flipped
between repeated baseline trials is noise the gate must tolerate, and a check that never failed
in any rollout is not discriminating in this data.

    python3 -m experiments.scenario_skills.v3.audit ~/cekura-scenario-v3-run1 ~/cekura-scenario-v3-run2
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from ..common import digest, read, write
from ..skill import SKILL


def labels_for(directory):
    out = {digest(SKILL): "baseline"}
    for p in sorted(Path(directory).glob("candidate-*.md")):
        out[digest(p.read_bytes())] = "%s/%s" % (Path(directory).name, p.stem)
    return out


def records(directories):
    rows = []
    for directory in directories:
        labels = labels_for(directory)
        for p in sorted(Path(directory).glob("scored/*.json")):
            r = read(p)
            if r.get("status") != "complete" or "grade" not in r:
                continue
            checks = r["grade"].get("checks") or {}
            rows.append({"run": Path(directory).name, "task": r["task_id"], "template": r["task_id"].split("-")[0],
                         "revision": labels.get(r.get("candidate_sha256"), "unknown"), "repeat": r.get("repeat", 0),
                         "checks": {c: bool(v) for c, v in checks.items()}, "score": r["grade"].get("score")})
    return rows


def audit(rows):
    """Per (template, check): pass counts per revision; the three findings; per-template trial counts."""
    cells = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # (template, check) -> revision -> [passed, trials]
    baseline_trials = defaultdict(list)
    for r in rows:
        for check, passed in r["checks"].items():
            cell = cells[(r["template"], check)][r["revision"]]
            cell[0] += passed
            cell[1] += 1
            if r["revision"] == "baseline":
                baseline_trials[(r["template"], check)].append(passed)
    never_move, flaky, never_fail = [], [], []
    for (template, check), by_revision in sorted(cells.items()):
        revisions = {rev: n for rev, (p, n) in by_revision.items()}
        passes = {rev: p for rev, (p, n) in by_revision.items()}
        if len(revisions) >= 2 and all(p == 0 for p in passes.values()):
            never_move.append({"template": template, "check": check, "revisions": len(revisions), "trials": sum(revisions.values())})
        if all(p == n for (p, n) in by_revision.values()):
            never_fail.append({"template": template, "check": check, "trials": sum(revisions.values())})
        trials = baseline_trials.get((template, check), [])
        if len(trials) >= 2 and len(set(trials)) > 1:
            flaky.append({"template": template, "check": check, "baseline_pass_rate": round(sum(trials) / len(trials), 2), "trials": len(trials)})
    matrix = {"%s:%s" % key: {rev: "%d/%d" % tuple(cell) for rev, cell in by_revision.items()} for key, by_revision in sorted(cells.items())}
    return {"rollouts": len(rows), "never_move": never_move, "flaky_baseline": flaky, "never_fail": never_fail, "matrix": matrix}


def markdown(report):
    lines = ["# Check audit (%d rollouts)" % report["rollouts"], "",
             "## Checks that failed under every revision", ""] + \
            ["- %s `%s` (%d revisions, %d trials)" % (r["template"], r["check"], r["revisions"], r["trials"]) for r in report["never_move"]] + \
            ["", "## Checks that flipped between baseline trials", ""] + \
            ["- %s `%s` (pass rate %.2f over %d trials)" % (r["template"], r["check"], r["baseline_pass_rate"], r["trials"]) for r in report["flaky_baseline"]] + \
            ["", "## Checks that never failed in any rollout (not discriminating here)", ""] + \
            ["- %s `%s` (%d trials)" % (r["template"], r["check"], r["trials"]) for r in report["never_fail"]]
    return "\n".join(lines) + "\n"


def main(argv):
    directories = [Path(a).expanduser() for a in argv] or [Path.cwd()]
    report = audit(records(directories))
    out = directories[-1] / "check-audit"
    write(out / "audit.json", report)
    (out / "audit.md").write_text(markdown(report))
    print({"rollouts": report["rollouts"], "never_move": len(report["never_move"]), "flaky_baseline": len(report["flaky_baseline"]),
           "never_fail": len(report["never_fail"]), "report": str(out)})


if __name__ == "__main__":
    main(sys.argv[1:])
