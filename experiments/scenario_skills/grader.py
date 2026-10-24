"""Fixed observable contracts. Semantic acceptance always needs human review."""
from __future__ import annotations

import json
import re
from .fixture import PREFIX, main_agent_variables


def grade(task, trace, initial, final, messages, status="complete"):
    expected = task["expected"]
    checks = {}
    calls = [e for e in trace if "name" in e]
    successful = [e for e in calls if not e["response"]["isError"]]
    names = [e["name"].removeprefix(PREFIX) for e in calls]
    initial_by_id = {r["id"]: r for r in initial["scenarios"]}
    by_id = {r["id"]: r for r in final["scenarios"]}
    created = [r for r in final["scenarios"] if r["id"] not in initial_by_id]
    changed = [r for r in final["scenarios"] if r["id"] in initial_by_id and r != initial_by_id[r["id"]]]
    rows = changed if expected["route"] == "update" else created
    checks["finished"] = status == "complete"
    checks["requested_count"] = len(rows) == expected["count"]
    checks["agent_read_only"] = final.get("agent", task["fixture"]["agent"]) == task["fixture"]["agent"]
    checks["scope"] = all(r.get("agent") == task["fixture"]["agent"]["id"]
                          and r.get("project", task["fixture"]["agent"]["project"]) == task["fixture"]["agent"]["project"] for r in rows)
    checks["folder"] = all(r.get("folder_path", r.get("folder")) for r in rows)
    route = expected["route"]
    if route == "generate":
        checks["routing"] = "scenarios_generate_bg" in names and "scenarios_create" not in names
        checks["completed_poll"] = any(e["name"].endswith("scenarios_generate_progress")
                                       and not e["response"]["isError"]
                                       and json.loads(e["response"]["content"][0]["text"]).get("status") == "completed" for e in calls)
        if expected.get("source_text"):
            checks["source_inputs"] = any(expected["source_text"] in json.dumps(e["arguments"], ensure_ascii=False)
                                         for e in calls if e["name"].endswith("scenarios_generate_bg"))
    elif route == "direct":
        checks["routing"] = "scenarios_create" in names and "scenarios_generate_bg" not in names
    elif route == "update":
        checks["routing"] = (any(n in names for n in ("scenarios_partial_update", "scenarios_bulk_update"))
                             and not created and "scenarios_generate_bg" not in names and "scenarios_create" not in names)
        checks["resource_ids"] = {r["id"] for r in changed} == set(expected["ids"])
    else:
        checks["routing"] = not created and not changed and not any(n.startswith(("scenarios_generate", "scenarios_create", "test_profiles_create")) for n in names)
    checks["no_unrequested_deletion"] = set(initial_by_id) <= set(by_id)
    checks["mode"] = all(r.get("scenario_type", "instruction") == expected.get("mode", "instruction") for r in rows)
    checks["language"] = all(r.get("scenario_language", "en") == task["fixture"]["agent"]["language"] for r in rows)
    for field, value in expected.get("fields", {}).items():
        checks["field:" + field] = all(r.get(field) == value for r in rows)
    for identifier, fields in expected.get("preserve", {}).items():
        for field in fields:
            old = initial_by_id[int(identifier)]
            current = by_id.get(int(identifier), {})
            if field == "folder":
                preserved = current.get("folder_path", current.get("folder")) == old.get("folder_path", old.get("folder"))
            else:
                preserved = current.get(field) == old.get(field)
            checks["preserve:%s:%s" % (identifier, field)] = preserved
    for identifier in expected.get("untouched_ids", []):
        checks["untouched:" + str(identifier)] = by_id.get(identifier) == initial_by_id[identifier]
    profiles = {r["id"]: r for r in final["profiles"]}
    variables = task["fixture"]["agent"].get("required_variables", {})
    checks["variables"] = all(main_agent_variables(profiles.get(r.get("test_profile"), {}).get("information", {})).get(k) == v
                              for r in rows for k, v in variables.items())
    text = "\n".join(messages)
    # IDs in the final response must identify actual saved resources.
    checks["completion_ids"] = all(str(r["id"]) in text for r in rows)
    claims = re.findall(r"\b(?:created|saved|updated)\s+(\d+)\s+(?:scenarios?|evaluators?|tests?)", text, re.I)
    checks["completion_count"] = all(int(n) == len(rows) for n in claims)
    id_claims = re.findall(r"\b(?:created|saved|updated)\s+(?:scenario|evaluator)\s*#?(\d+)\b", text, re.I)
    checks["no_invented_completion_ids"] = all(int(n) in {r["id"] for r in rows} for n in id_claims)
    checks["no_unexecuted_success_claim"] = not bool(re.search(
        r"\b(?:all tests passed|tests? (?:passed|ran successfully)|validated successfully|works correctly)\b", text, re.I))
    # Inspect persistence evidence from returned writes, retrieval, or completed poll.
    evidence = json.dumps([e["response"] for e in successful], ensure_ascii=False)
    checks["persistence_evidence"] = all(re.search(r'\\?"id\\?"\s*:\s*' + str(r["id"]) + r"\b", evidence) for r in rows)
    if expected.get("needs_unvalidated"):
        checks["storage_vs_execution"] = bool(re.search(r"unvalidated|not (?:yet )?(?:run|executed|validated)|hasn.t (?:been )?run", text, re.I))
    if route == "none":
        checks["truthful_no_write"] = not bool(re.search(r"\b(?:created|saved|updated)\s+(?:the|your|a|an|[1-9])", text, re.I))
    if expected.get("approve_on_turn") is not None:
        mutation = re.compile(r"(?:_create|_update|_generate_bg|_destroy|_delete)$")
        checks["approval"] = not any(mutation.search(e["name"]) and e["turn"] < expected["approve_on_turn"] for e in calls)
    return {"status": status, "score": int(all(checks.values())), "checks": checks,
            "failed_checks": [key for key, passed in checks.items() if not passed],
            "semantic_status": "pending_human_review"}
