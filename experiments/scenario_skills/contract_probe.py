"""Model-free reachability of frozen contracts under captured tool schemas.

These scripted trajectories validate the emulator, not assistant performance.
Keep their complete oracle-derived artifacts outside the proposer workspace.
"""
import json

from .common import ROOT, digest, private_dir, write
from .dataset import load
from .fixture import PREFIX, Store
from .grader import grade
from .skill import material


def response(store, operation, **args):
    result = store.call(PREFIX + operation, args)
    if result["isError"]:
        raise AssertionError(result)
    return json.loads(result["content"][0]["text"])


def payload(task):
    fixture = task["fixture"]
    row = dict(agent=fixture["agent"]["id"], folder_path=fixture["resources"]["folders"][0]["path"],
               personality=fixture["personalities"][0]["id"], name="Caller check", scenario_type="instruction",
               scenario_language="en", instructions="I will ask a question. End the call when it is answered.",
               test_profile=fixture["resources"]["profiles"][0]["id"])
    row.update(task.get("payload", {}))
    return row


def generate(store, task):
    args = {"agent_id": task["fixture"]["agent"]["id"], "num_scenarios": len(task["generator_response"]),
            "folder_path": task["fixture"]["resources"]["folders"][0]["path"]}
    if task["expected"].get("source_text"):
        args["extra_instructions"] = task["expected"]["source_text"]
    job = response(store, "scenarios_generate_bg", **args)
    assert response(store, "scenarios_generate_progress", **job)["status"] == "processing"
    return response(store, "scenarios_generate_progress", **job)["scenarios_list"]


def observable_trajectory(task, store):
    response(store, "cekura_load_skill", skill_name="cekura-eval-design")
    route = task["expected"]["route"]
    store.turn = task["expected"].get("approve_on_turn", 0)
    if route == "generate":
        rows = generate(store, task)
    elif route == "direct":
        args = payload(task)
        if task["expected"].get("mode") == "conditional_actions":
            args.pop("instructions")
            args.update(scenario_type="conditional_actions", conditional_actions=task["suggested_actions"])
        rows = [response(store, "scenarios_create", **args)]
    elif route == "update":
        rows = [response(store, "scenarios_partial_update", id=task["expected"]["ids"][0], **task["expected"]["fields"])]
    else:
        rows = []
    for row in rows:
        assert response(store, "scenarios_retrieve", id=row["id"]) == row
    if rows:
        return ["Saved %d scenarios: %s. These are unvalidated and have not run." %
                (len(rows), ", ".join(str(r["id"]) for r in rows))]
    return ["Cancelled. No writes were performed."]


def identity(catalog):
    return {"catalog_sha256": digest(catalog), "dataset_sha256": digest(load()),
            "code_sha256": digest({name: digest(ROOT / name) for name in
                ("contract_probe.py", "fixture.py", "grader.py", "dataset.py")})}


def probe(catalog, directory):
    directory = private_dir(directory)
    results = []
    for task in load():
        store = Store(task, material(), catalog)
        try:
            messages = observable_trajectory(task, store)
            result = grade(task, store.trace, store.initial, store.state, messages)
        except Exception as error:
            messages, result = [], {"score": 0, "error": str(error)}
        results.append({"task_id": task["id"], "grade": result})
        write(directory / (task["id"] + ".json"), {"trace": store.trace, "messages": messages,
            "initial_state": store.initial, "final_state": store.state, "grade": result})
    summary = dict(identity(catalog), passed=all(r["grade"]["score"] == 1 for r in results),
                   tasks=results, model_turns=0, production_tool_calls=0)
    write(directory / "contract-probe.json", summary)
    return summary
