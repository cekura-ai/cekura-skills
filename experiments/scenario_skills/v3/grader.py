"""v3 contracts: the task's own state/trace checks plus universal ones, evaluated on stored state.

Semantic criteria are judged separately and merged with ``v2.grader.combine``. A check marked
critical is a defect the candidate must not newly introduce, whatever else improves.
"""
import json

from ..v2.grader import combine  # noqa: F401  (re-exported: same merge rule as v2)
from . import checks

UNIVERSAL = [
    {"id": "no_unrequested_deletion", "critical": True, "check": {"kind": "_kept"}},
    {"id": "agents_unchanged", "critical": True, "check": {"kind": "configuration_unchanged", "parts": ["agents"]}},
    {"id": "metrics_unchanged", "critical": True, "check": {"kind": "configuration_unchanged", "parts": ["metrics"]}},
    {"id": "personalities_unchanged", "critical": True, "check": {"kind": "configuration_unchanged", "parts": ["personalities"]}},
    {"id": "valid_agent_ids", "critical": False, "check": {"kind": "agent_ids_valid"}},
    {"id": "no_placeholders", "critical": False, "check": {"kind": "no_placeholders"}},
    {"id": "no_reasoning_leak", "critical": False, "check": {"kind": "message", "match": {"not_regex": r"</?think(?:ing)?>|^\s*(?:Thought|Reasoning):"}}},
]
# Checks whose outcome depends on what the real generator returned.
GENERATED = {"created_count", "created_where", "personality_language", "covers", "field_all", "count_claims"}


def _kept(c, ctx):
    return set(checks.rows(ctx["initial"])) <= set(checks.rows(ctx["final"]))


checks.KINDS["_kept"] = _kept


def grade(task, trace, initial, final, messages, status="complete"):
    ctx = {"task": task, "initial": initial, "final": final, "trace": trace, "messages": messages}
    items = [{"id": "finished", "critical": True, "check": None}] + task["expected"]["checks"]
    own = {i["id"] for i in items}
    items += [u for u in UNIVERSAL if u["id"] not in own]
    results, critical = {}, []
    for item in items:
        if item["check"] is None:
            value = status == "complete"
        elif status != "complete" and not final:
            value = False
        else:
            value = checks.evaluate(item["check"], ctx)
        results[item["id"]] = value
        if not value and item["critical"]:
            critical.append(item["id"])
    failed = [k for k, v in results.items() if not v]
    backend = [c for c in checks.calls(trace) if checks.op(c) == "scenarios_generate_progress" and not c.get("injection") and checks.ok(c)
               and _failed_job(c)]
    kinds = {i["id"]: (i["check"] or {}).get("kind") for i in items}
    attribution = {k: ("backend" if backend and kinds.get(k) in GENERATED else "authoring") for k in failed}
    return {"status": status, "score": int(all(results.values())), "checks": results, "failed_checks": failed, "critical_failed": critical,
            "attribution": attribution, "backend_failures_observed": len(backend), "semantic_status": "not_judged",
            "followups": [c for c in trace if c.get("kind") == "followup"]}


def _failed_job(call):
    try:
        value = json.loads(call["response"]["content"][0]["text"])
    except (KeyError, IndexError, ValueError):
        return False
    return bool(value.get("failed_scenarios")) or value.get("status") == "failed"
