"""Pure selection gates over cached, scored observations.

Every observation of a task counts. A task whose observations disagree, or whose judgment
is uncertain or contradicted by an audit, is unresolved. Unresolved results never
establish improvement: the baseline is credited with a pass and the candidate is charged
with a failure, so acceptance needs a strict gain and no regression even in that worst case.
"""
from __future__ import annotations

# Failures that make a candidate unacceptable whatever the baseline did.
CRITICAL = {"scope", "agent_unchanged", "no_unrequested_deletion", "approval", "cancel_scope", "no_executed_claim",
            "no_invented_ids", "allowed_writes:scenarios", "allowed_writes:profiles", "allowed_writes:folders",
            "allowed_writes:configuration"}


def generator_only(record):
    """A failure whose every failed check is attributed to the generation service, not the assistant."""
    failed = record["grade"]["failed_checks"]
    return bool(failed) and all(record["grade"].get("attribution", {}).get(c, "authoring") == "backend" for c in failed)


def observation(record, disputed=(), generator_unresolved=False):
    if record["status"] != "complete" or record.get("cost_usd") is None:
        raise ValueError("Inconclusive executions cannot support a comparison")
    if record["grade"].get("semantic_status") == "uncertain" or (record["task_id"], record["candidate_sha256"]) in disputed:
        return "unresolved"
    if generator_unresolved and not record["grade"]["score"] and generator_only(record):
        return "unresolved"  # No skill edit can move a generator defect behind a correct request.
    return "pass" if record["grade"]["score"] else "fail"


def verdicts(records, task_ids, disputed=()):
    grouped = {i: [] for i in task_ids}
    for record in records:
        if record["task_id"] in grouped:
            grouped[record["task_id"]].append(observation(record, disputed))
    if any(not group for group in grouped.values()):
        raise ValueError("Incomplete comparison: " + ", ".join(sorted(i for i, g in grouped.items() if not g)))
    return {i: group[0] if len(set(group)) == 1 else "unresolved" for i, group in grouped.items()}


def compare(baseline, candidate, task_ids, disputed=()):
    before, after = verdicts(baseline, task_ids, disputed), verdicts(candidate, task_ids, disputed)
    worst_before = {i: before[i] in ("pass", "unresolved") for i in task_ids}
    worst_after = {i: after[i] == "pass" for i in task_ids}
    regressions = sorted(i for i in task_ids if worst_before[i] and not worst_after[i])
    gain = sum(worst_after.values()) - sum(worst_before.values())
    return {"passed": gain > 0 and not regressions, "worst_case_gain": gain, "regressions": regressions,
            "baseline": before, "candidate": after,
            "determinate": {"baseline_passes": sum(v == "pass" for v in before.values()), "candidate_passes": sum(v == "pass" for v in after.values()),
                            "unresolved": sorted(i for i in task_ids if "unresolved" in (before[i], after[i]))}}


def critical_defects(records):
    return sorted({(r["task_id"], c) for r in records for c in r["grade"]["failed_checks"] if c in CRITICAL})


def passes(records, task_ids, disputed=()):
    return sum(v == "pass" for v in verdicts(records, task_ids, disputed).values())


def unstable(records, task_ids):
    """Tasks whose repeated observations of one arm disagree (diagnostic repeats are justified)."""
    out = []
    for i in task_ids:
        values = {observation(r) for r in records if r["task_id"] == i}
        if len(values) > 1:
            out.append(i)
    return out


# --- v3: noise-tolerant acceptance ---------------------------------------------------------------
def consistent(records, task_ids, disputed=(), generator_unresolved=False):
    """Per task: 'pass' or 'fail' when every observation agrees (and there are at least two), else 'inconsistent'."""
    out = {}
    for i in task_ids:
        values = [observation(r, disputed, generator_unresolved) for r in records if r["task_id"] == i]
        if not values:
            raise ValueError("Incomplete comparison: " + i)
        out[i] = values[0] if len(values) >= 2 and len(set(values)) == 1 and values[0] != "unresolved" else "inconsistent"
    return out


def critical_regressions(baseline, candidate, task_ids):
    """Critical checks the candidate fails on every observation of a task where the baseline never failed them."""
    out = []
    for i in task_ids:
        mine = [set(r["grade"].get("critical_failed", [])) for r in candidate if r["task_id"] == i]
        theirs = set().union(*[set(r["grade"].get("critical_failed", [])) for r in baseline if r["task_id"] == i])
        if mine:
            out += [(i, c) for c in sorted(set.intersection(*mine) - theirs)]
    return out


def compare_consistent(baseline, candidate, task_ids, min_gain, disputed=(), generator_unresolved=False):
    """Gain counts tasks the candidate passes on every trial and the baseline fails on every trial.

    A regression is the reverse. Acceptance needs at least ``min_gain`` gains, no regression and
    no new critical defect; inconsistent tasks are reported but neither credited nor charged.
    """
    before = consistent(baseline, task_ids, disputed, generator_unresolved)
    after = consistent(candidate, task_ids, disputed, generator_unresolved)
    gains = sorted(i for i in task_ids if before[i] == "fail" and after[i] == "pass")
    regressions = sorted(i for i in task_ids if before[i] == "pass" and after[i] == "fail")
    critical = critical_regressions(baseline, candidate, task_ids)
    return {"passed": len(gains) >= min_gain and not regressions and not critical, "gains": gains, "regressions": regressions,
            "critical_regressions": critical, "min_gain": min_gain, "baseline": before, "candidate": after,
            "inconsistent": sorted(i for i in task_ids if "inconsistent" in (before[i], after[i]))}


def needs_repeat(baseline, candidate, task_ids, generator_unresolved=False):
    """Tasks whose single paired observation could still decide a gain, a regression or a critical defect.

    Under ``compare_consistent`` a task counts only when each arm agrees with itself across trials,
    so a task where both arms first agree can never become a gain or a regression, and one with an
    unresolved observation can never count at all: only determinate disagreements and new critical
    failures are worth a second trial.
    """
    out = []
    for i in task_ids:
        before = [r for r in baseline if r["task_id"] == i]
        after = [r for r in candidate if r["task_id"] == i]
        if not before or not after:
            continue
        values = {observation(before[0], (), generator_unresolved), observation(after[0], (), generator_unresolved)}
        new_critical = set(after[0]["grade"].get("critical_failed", [])) - set(before[0]["grade"].get("critical_failed", []))
        if "unresolved" not in values and (len(values) > 1 or new_critical):
            out.append(i)
    return out


# --- pool search: per-check credit, a paired noise gate, and trial allocation ---------------------
def check_matrix(records, task_ids, generator_unresolved=True):
    """Per task and check, (passes, trials) over complete records; a backend-attributed failure is not a trial.

    The matrix is the unit of comparison for the pool search: a candidate that clears three of a
    task's checks and newly fails one has moved, whether or not the task as a whole flipped.
    """
    out = {i: {} for i in task_ids}
    for r in records:
        if r["task_id"] not in out or r["status"] != "complete":
            continue
        attribution = r["grade"].get("attribution", {})
        for check, passed in r["grade"].get("checks", {}).items():
            if generator_unresolved and not passed and attribution.get(check) == "backend":
                continue
            cell = out[r["task_id"]].setdefault(check, [0, 0])
            cell[0] += bool(passed)
            cell[1] += 1
    return out


def credit(cells):
    """Mean pass rate over a task's checks (None without evidence)."""
    rates = [p / n for p, n in cells.values() if n]
    return sum(rates) / len(rates) if rates else None


def paired_delta(baseline, candidate, task_ids, se_multiplier=1.65, regression_floor=0.34, weights=None, generator_unresolved=True):
    """Check-credit gain of the candidate over the baseline, paired by task, with a noise gate.

    Per task the credit is the mean pass rate over the checks both arms observed; the aggregate is
    the (weighted) mean of the per-task differences and its standard error comes from those same
    differences, so a gain has to be larger than the spread between tasks before it counts. The
    candidate is accepted when the gain exceeds ``se_multiplier`` standard errors, no single
    check's pass rate fell by more than ``regression_floor`` (one trial in three), and it never
    fails a critical check the baseline never failed (``critical_regressions``).
    """
    before, after = check_matrix(baseline, task_ids, generator_unresolved), check_matrix(candidate, task_ids, generator_unresolved)
    weights = weights or {}
    deltas, regressions, cells = {}, [], {}
    for i in task_ids:
        shared = [c for c in after[i] if c in before[i] and before[i][c][1] and after[i][c][1]]
        if not shared:
            continue
        rates = {c: (before[i][c][0] / before[i][c][1], after[i][c][0] / after[i][c][1]) for c in shared}
        deltas[i] = sum(b - a for a, b in rates.values()) / len(rates)
        cells[i] = {c: {"baseline": round(a, 3), "candidate": round(b, 3), "trials": [before[i][c][1], after[i][c][1]]} for c, (a, b) in rates.items()}
        regressions += [(i, c) for c, (a, b) in sorted(rates.items()) if a - b > regression_floor]
    n = len(deltas)
    if n == 0:
        return {"passed": False, "gain": None, "se": None, "tasks": 0, "regressions": [], "critical_regressions": [], "cells": {}, "deltas": {}}
    w = {i: float(weights.get(i, 1)) for i in deltas}
    total = sum(w.values())
    gain = sum(w[i] * d for i, d in deltas.items()) / total
    variance = sum(w[i] * (d - gain) ** 2 for i, d in deltas.items()) / total
    se = (variance / n) ** 0.5 if n > 1 else float("inf")
    critical = critical_regressions(baseline, candidate, task_ids)
    passed = n >= 2 and gain > se_multiplier * se and not regressions and not critical
    return {"passed": passed, "gain": round(gain, 4), "se": (round(se, 4) if se != float("inf") else None), "tasks": n,
            "se_multiplier": se_multiplier, "regression_floor": regression_floor, "regressions": sorted(regressions),
            "critical_regressions": critical, "deltas": {i: round(d, 4) for i, d in deltas.items()}, "cells": cells}


def priority(baseline, candidate, task_ids, exploration=0.5, generator_unresolved=True):
    """Tasks ordered by how much another paired trial could tell: |delta| plus an exploration bonus for few trials.

    An upper-confidence rule: a task whose arms differ most, or has been tried least, is tried next.
    Tasks without a candidate observation come first.
    """
    import math
    before, after = check_matrix(baseline, task_ids, generator_unresolved), check_matrix(candidate, task_ids, generator_unresolved)
    trials = {i: max([n for _, n in after[i].values()] or [0]) for i in task_ids}
    total = max(sum(trials.values()), 1)
    scores = {}
    for i in task_ids:
        if not trials[i]:
            scores[i] = float("inf")
            continue
        b, c = credit(before[i]), credit(after[i])
        gap = abs((c or 0) - (b or 0))
        scores[i] = gap + exploration * math.sqrt(math.log(total + 1) / trials[i])
    return sorted(task_ids, key=lambda i: (-scores[i], i))


def best_trial_credit(records, task_ids, generator_unresolved=True):
    """Per task, the highest single-trial credit any of its records reached (None without evidence).

    A single-trial screen is compared with this rather than with a mean over trials, so a flaky
    task cannot make one lucky trial look like a gain over the parent.
    """
    out = {}
    for i in task_ids:
        mine = [r for r in records if r["task_id"] == i]
        values = [credit(check_matrix([r], [i], generator_unresolved)[i]) for r in mine]
        values = [v for v in values if v is not None]
        out[i] = max(values) if values else None
    return out
