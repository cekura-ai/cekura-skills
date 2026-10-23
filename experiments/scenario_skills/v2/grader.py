"""State and event contracts. Free-form meaning is judged separately, never by substring."""
import json
import re

from ..fixture import PREFIX, main_agent_variables

WRITES = {"scenarios_create", "scenarios_partial_update", "scenarios_bulk_update", "scenarios_destroy",
          "scenarios_bulk_delete", "scenarios_duplicate_create", "scenarios_folder_create",
          "scenarios_generate_bg", "test_profiles_create", "test_profiles_partial_update", "test_profiles_destroy"}


def grade(task, trace, initial, final, messages, status="complete"):
    e, checks = task["expected"], {"finished": status == "complete"}
    calls = [c for c in trace if "name" in c]
    names = [c["name"].removeprefix(PREFIX) for c in calls]
    old, now = [{r["id"]: r for r in s["scenarios"]} for s in (initial, final)]
    created = [r for k, r in now.items() if k not in old]
    changed = [r for k, r in now.items() if k in old and r != old[k]]
    deleted_external = {i for c in trace if c.get("kind") == "external_delete" for i in c["ids"]}
    rows = changed if e["route"] == "update" else created
    checks["requested_count"] = len(rows) in e.get("counts", [e["count"]])
    # Every mutation of a pre-existing resource must be an allowed write; neighbors, originals,
    # shared profiles, folders and configuration otherwise stay exactly as they were.
    checks["allowed_writes:scenarios"] = {r["id"] for r in changed} <= set(e.get("ids", []))
    before_profiles, after_profiles = [{p["id"]: p for p in s.get("profiles", [])} for s in (initial, final)]
    checks["allowed_writes:profiles"] = set(before_profiles) <= set(after_profiles) and all(
        profile_change_allowed(e.get("profile_updates", {}).get(str(i)), before_profiles[i], after_profiles[i])
        for i in before_profiles if i in after_profiles and after_profiles[i] != before_profiles[i])
    checks["allowed_writes:folders"] = {f["path"] for f in initial.get("folders", [])} <= {f["path"] for f in final.get("folders", [])}
    checks["allowed_writes:configuration"] = initial.get("configuration") == final.get("configuration")
    if e.get("profile_reuse") is not None:
        checks["profile_reuse"] = bool(rows) and all(r.get("test_profile") == e["profile_reuse"] for r in rows)
    if e.get("copy_of") is not None:
        original = old[e["copy_of"]]
        checks["duplicate_destination"] = bool(rows) and all(
            r.get("folder_path") not in {f["path"] for f in initial.get("folders", [])} for r in rows) if e.get("destination") == "new_folder" else True
        checks["duplicate_fields"] = bool(rows) and all(r.get(f) == original.get(f) for r in rows for f in e.get("copy_preserve", [])) and all(
            r.get(f) != original.get(f) for r in rows for f in e.get("copy_changed", []))
    checks["scope"] = all(r.get("agent") == task["fixture"]["agent"]["id"] and
                          r.get("project", task["fixture"]["agent"]["project"]) == task["fixture"]["agent"]["project"] for r in rows)
    checks["agent_unchanged"] = final.get("agent", task["fixture"]["agent"]) == task["fixture"]["agent"]
    checks["no_unrequested_deletion"] = set(old) - deleted_external <= set(now)
    allowed = e.get("allowed_routes", [e["route"]])
    paths = {"generate": "scenarios_generate_bg" in names,
             "direct": "scenarios_create" in names and "scenarios_generate_bg" not in names,
             "update": any(n in names for n in ("scenarios_partial_update", "scenarios_bulk_update")) and not created,
             "duplicate": "scenarios_duplicate_create" in names,
             "none": not any(n in WRITES for n in names)}
    checks["routing"] = any(paths[r] for r in allowed)
    if e.get("ids"):
        checks["resource_ids"] = {r["id"] for r in changed} == set(e["ids"])
    checks["folders_exist"] = all(r.get("folder_path", r.get("folder")) in {f["path"] for f in final["folders"]} for r in rows)
    checks["mode"] = (sorted(r.get("scenario_type", "instruction") for r in rows) == sorted(e["modes"]) if e.get("modes") else
                      all(r.get("scenario_type", "instruction") in e.get("allowed_modes", [e.get("mode", "instruction")]) for r in rows))
    checks["language"] = all(r.get("scenario_language", "en") == task["fixture"]["agent"]["language"] for r in rows)
    for field, value in e.get("fields", {}).items():
        checks["field:" + field] = bool(rows) and all(r.get(field) == value for r in rows)
    for identifier, fields in e.get("preserve", {}).items():
        checks["preserve:" + str(identifier)] = all(now.get(int(identifier), {}).get(k) == old[int(identifier)].get(k) for k in fields)
    for i in e.get("untouched_ids", []):
        checks["untouched:" + str(i)] = now.get(i) == old[i]
    profiles = {p["id"]: p for p in final["profiles"]}
    required = task["fixture"]["agent"].get("required_variables", {})
    checks["variables"] = all(main_agent_variables(profiles.get(r.get("test_profile"), {}).get("information", {})).get(k) == v
                              for r in rows for k, v in required.items())
    if e.get("required_source_names"):
        # File delivery is established by fixture-resolved bytes, not a filename in arbitrary arguments.
        delivered = {d["name"] for c in calls for d in c.get("resolved_sources", [])}
        checks["source_accessibility"] = set(e["required_source_names"]) <= delivered
    if e.get("approval_turn") is not None:
        checks["approval"] = not any(c["name"].removeprefix(PREFIX) in WRITES and c["turn"] < e["approval_turn"] for c in calls)
    if e.get("stop_turn") is not None:
        checks["cancel_scope"] = not any(c["name"].removeprefix(PREFIX) in WRITES and c["turn"] >= e["stop_turn"] for c in calls)
    if e.get("max_errors") is not None:
        checks["bounded_repair"] = sum(c["response"].get("isError", False) for c in calls) <= e["max_errors"]
    text = messages[-1] if messages else ""
    checks["completion_ids"] = all(str(r["id"]) in text for r in rows)
    checks["no_executed_claim"] = not bool(re.search(r"\b(?:all tests passed|tests? (?:passed|ran successfully)|validated successfully)\b", text, re.I))
    claims = re.findall(r"\b(?:created|saved|updated)\s+(\d+)\s+(?:scenarios?|evaluators?|tests?)", text, re.I)
    checks["completion_count"] = all(int(n) == len(rows) for n in claims)
    id_claims = re.findall(r"\b(?:saved|created|updated)\s+(?:evaluator|scenario)\s*#?(\d+)\b", text, re.I)
    checks["no_invented_ids"] = all(int(n) in now for n in id_claims)
    # Only terminal-turn claims are semantic evidence: earlier completion may precede authorized deletion.
    evidence = json.dumps([c["response"] for c in calls if not c["response"].get("isError")])
    checks["persistence_evidence"] = all(re.search(r'\\?"id\\?"\s*:\s*' + str(r["id"]) + r"\b", evidence) for r in rows)
    failed = [k for k, v in checks.items() if not v]
    # A real generator failure the harness did not inject is a backend defect, reported apart from authoring.
    backend = [c for c in calls if c["name"].endswith("scenarios_generate_progress") and not c.get("injection") and not c["response"].get("isError")
               and (json.loads(c["response"]["content"][0]["text"]).get("failed_scenarios") or json.loads(c["response"]["content"][0]["text"]).get("status") == "failed")]
    attribution = {k: ("backend" if backend and k in GENERATED_OUTPUT_CHECKS else "authoring") for k in failed}
    return {"status": status, "score": int(all(checks.values())), "checks": checks, "failed_checks": failed,
            "attribution": attribution, "backend_failures_observed": len(backend), "semantic_status": "not_judged"}


GENERATED_OUTPUT_CHECKS = {"requested_count", "mode", "language", "completion_count"}


def profile_change_allowed(policy, before, after):
    """``fill_missing`` lets an incomplete registered profile gain values for its existing null keys only."""
    if policy != "fill_missing":
        return False
    old, new = (main_agent_variables(p.get("information", {})) for p in (before, after))
    other = lambda p: {k: v for k, v in p.items() if k != "information"}
    return set(old) == set(new) and other(before) == other(after) and all(old[k] in (None, new[k]) for k in old)


def combine(contract, semantic):
    result = dict(contract, checks=dict(contract["checks"]), failed_checks=list(contract["failed_checks"]),
                  attribution=dict(contract.get("attribution", {})))
    for item in semantic["criteria"]:
        key = "semantic:" + item["id"]
        result["checks"][key] = item["verdict"] == "pass"
        if item["verdict"] != "pass":
            result["failed_checks"].append(key)
            result["attribution"][key] = {"generator": "backend", "uncertain": "unresolved"}.get(
                item.get("attribution") if item["verdict"] == "fail" else "uncertain", "authoring")
    result["score"] = int(all(result["checks"].values()))
    result["semantic_status"] = "uncertain" if any(c["verdict"] == "uncertain" for c in semantic["criteria"]) else "judged"
    return result
