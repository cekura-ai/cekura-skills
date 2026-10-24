"""Offline structural contracts against the captured original MCP schemas.

Known oracle actions are engineering controls, not model rollouts or semantic proofs.
"""
import copy
import json

from ..common import digest, write
from pathlib import Path
from ..skill import SKILL
from .dataset import load
from .fixture import Store
from .grader import grade


def actor(task, store):
    """Known actions verify fixture/schema contracts, not model competence or semantics."""
    agent = task["fixture"]["agent"]
    expected = task["expected"]
    store.turn = expected.get("approval_turn", 0)
    if expected["route"] == "none":
        return ["No resources saved or changed; execution is unvalidated."]
    required = agent.get("required_variables", {})
    if required:
        profile = store.state["profiles"][0]
        store.call("test_profiles_partial_update", {"id": profile["id"], "information": {"main_agent_variables": required}})
    folder = store.state["folders"][0]["path"]
    if expected["route"] == "generate":
        scripts = task.get("generation_jobs")
        if scripts:
            for script in scripts:
                response = store.call("scenarios_generate_bg", {"agent_id": agent["id"], "num_scenarios": script["requested_count"], "folder_path": folder})
                progress = json.loads(response["content"][0]["text"])["progress_id"]
                for _ in range(script.get("processing_polls", 1) + 1):
                    store.call("scenarios_generate_progress", {"progress_id": progress})
        else:
            response = store.call("scenarios_generate_bg", {"agent_id": agent["id"], "num_scenarios": len(task["generator_response"]), "folder_path": folder,
                                                            "generation_files": [d["name"] for d in task.get("documents", [])]})
            if response["isError"]:
                response = store.call("scenarios_generate_bg", {"agent_id": agent["id"], "num_scenarios": len(task["generator_response"]), "folder_path": folder,
                                                                "extra_instructions": "\n".join(d["content"] for d in task.get("documents", []))})
            progress = json.loads(response["content"][0]["text"])["progress_id"]
            store.call("scenarios_generate_progress", {"progress_id": progress})
            store.call("scenarios_generate_progress", {"progress_id": progress})
    elif expected["route"] == "update":
        row = dict(copy.deepcopy(task["ideal_rows"][0]), id=expected["ids"][0])
        if row.get("folder_path") not in {f["path"] for f in store.state["folders"]}:
            store.call("scenarios_folder_create", {"project_id": agent["project"], "name": row["folder_path"]})
        store.call("scenarios_partial_update", row)
    elif expected["route"] == "duplicate":
        # The real handler leaves a copy without scenario_agent attached to no agent; a correct copy keeps it.
        original = next(r for r in store.initial["scenarios"] if r["id"] == expected.get("copy_of", store.initial["scenarios"][0]["id"]))
        response = store.call("scenarios_duplicate_create", {"project": agent["project"], "copy_to_project": agent["project"], "scenarios": [original["id"]],
                                                             "scenario_agent": agent["id"], "folder_path": original["folder_path"] + " copies"})
        copies = json.loads(response["content"][0]["text"])
        for field in expected.get("copy_changed", []):
            store.call("scenarios_partial_update", {"id": copies[0]["id"], field: task["ideal_rows"][0][field] + " Copy outcome."})
    else:
        for row in task["ideal_rows"]:
            payload = dict(row, agent=agent["id"], folder_path=folder, personality=task["fixture"]["personalities"][0]["id"], test_profile=store.state["profiles"][0]["id"])
            store.call("scenarios_create", payload)
    changed = [r for r in store.state["scenarios"] if r not in store.initial["scenarios"]]
    return ["Saved current resources: " + ", ".join(str(r["id"]) for r in changed) + ". Calls are unvalidated."]



def probe(catalog, path):
    rows = []
    for task in load():
        store = Store(task, {"SKILL.md": SKILL.read_bytes()}, catalog)
        messages = actor(task, store)
        result = grade(task, store.trace, store.initial, store.state, messages)
        errors = [c for c in store.trace if c.get("response", {}).get("isError")]
        expected = task["id"] == "sources-2" and len(errors) == 1 and "XML" in json.dumps(errors)
        rows.append({"task": task["id"], "passed": bool(result["score"]) and (not errors or expected), "grade": result, "expected_errors": expected, "errors": errors, "trace_sha256": digest(store.trace)})
    result = {"passed": all(r["passed"] for r in rows), "catalog_sha256": digest(catalog), "tasks_sha256": digest(load()), "schema_count": len(catalog),
              "fixture_sha256": digest(Path(__file__).with_name("fixture.py")), "grader_sha256": digest(Path(__file__).with_name("grader.py")),
              "contract_code_sha256": digest(Path(__file__)), "model_requests": 0, "rows": rows}
    write(path, result)
    return result
