"""One cumulative $150 authorization; forecasts reserve the complete comparison before search."""
from decimal import Decimal
from pathlib import Path

from ..budget import Ledger, BudgetError, require_cumulative

MARGIN = Decimal("1.25")
COST_DISCOVERY_CAP = Decimal("15")
CLAUDE_SESSION_RESERVATION = Decimal("2.5")
INFRASTRUCTURE_RESERVATION = Decimal("0.10")


def open_ledger(config):
    ledger = Ledger(Path(config["budget_ledger_path"]), config["budget_policy"])
    require_cumulative(ledger)
    return ledger


def trial_cost(record):
    """Authoring model, nested generator inference and infrastructure, all charged to one ledger."""
    parts = (record.get("cost_usd"), record.get("generator_cost_usd", 0), record.get("infrastructure_reserved_usd", 0))
    if any(p is None for p in parts):
        raise BudgetError("Unbounded usage cannot support forecasting")
    return sum((Decimal(str(p)) for p in parts), Decimal(0))


def family_costs(results):
    """Highest observed first-trial cost per family: a planning estimate, never a billing cap."""
    costs = {}
    for r in results:
        if not r.get("repeat"):
            costs[r["family"]] = max(costs.get(r["family"], Decimal(0)), trial_cost(r))
    return costs


def headroom(config):
    """One maximal request at each metered endpoint plus one sandbox may be in flight when a stage ends."""
    from ..gateway import request_bound
    target = config["target"]
    total = request_bound({}, target) + INFRASTRUCTURE_RESERVATION
    for endpoint in config.get("backend", {}).get("generator", {}).get("endpoints", []):
        # Admission limits and rates are pinned per model; one maximal request at the costliest model per endpoint.
        sections = [m for m in endpoint.get("models", {}).values() if m.get("admission")] or ([endpoint] if endpoint.get("admission") else [])
        if sections:
            total += max(request_bound({}, m) for m in sections)
    return total


def plan_cost(costs, tasks):
    missing = {t["family"] for t in tasks} - costs.keys()
    if missing:
        raise BudgetError("No observed cost for families: " + ", ".join(sorted(missing)))
    return sum((costs[t["family"]] for t in tasks), Decimal(0))


def comparison_tasks(validation, sealed, repeats):
    """Paired baseline/finalist validation and sealed trials plus both arms of every scheduled repeat."""
    return list(validation) * 2 + list(sealed) * 2 + list(repeats) * 2


def minimum_plan(results, training_remaining, training, validation, sealed, repeats, config):
    """The cheapest complete comparison: rest of baseline training, one full candidate, then held-outs."""
    costs = family_costs(results)
    tasks = list(training_remaining) + list(training) + comparison_tasks(validation, sealed, repeats)
    work = plan_cost(costs, tasks)
    return {"rollouts": len(tasks), "estimate_usd": str(work), "margin": str(MARGIN), "headroom_usd": str(headroom(config)),
            "needed_usd": str(work * MARGIN + headroom(config)),
            "family_costs_usd": {k: str(v) for k, v in sorted(costs.items())}}


def admit(ledger, results, candidate_tasks, validation, sealed, repeats, config):
    """Fund one more candidate only while the complete held-out comparison remains reserved."""
    costs = family_costs(results)
    needed = (plan_cost(costs, candidate_tasks) + plan_cost(costs, comparison_tasks(validation, sealed, repeats))) * MARGIN + headroom(config)
    return ledger.can_finish(needed, CLAUDE_SESSION_RESERVATION), needed
