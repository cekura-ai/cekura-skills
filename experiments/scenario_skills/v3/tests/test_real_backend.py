"""v3 against the pinned backend with no inference: reference sessions replayed as real tool calls.

Each rollout boots the full isolated stack (seeded workspace, results and runs), so this runs
only with CEKURA_BACKEND_INTEGRATION=1. A scripted target replays the correct reference
session through the v3 bridge, turn by turn, with the bridge choosing each follow-up; the
stored state read back from the backend must then pass every contract check. Generation
templates are excluded: they need the metered real generator.
"""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from experiments.scenario_skills.common import read
from experiments.scenario_skills.skill import SKILL
from experiments.scenario_skills.tests.helpers import cumulative_ledger
from experiments.scenario_skills.v3.dataset import load
from experiments.scenario_skills.v3.reference import initial_state, session

CATALOG = Path.home() / "projects/cekura-skills-experiment-20261023/private/evidence/private/tmp/cekura-runtime-image-2026-10-22/codex-catalog/catalog.json"
INFRA = Path.home() / "cekura-drill/run"
FIELDS = ("name", "tags", "folder_path", "metrics", "test_profile", "expected_outcome_prompt", "instructions", "conditional_actions")
REPLAYED = os.environ.get("CEKURA_V3_REPLAY", "T01,T02,T03,T04,T05,T07,T08,T09,T10,T11,T12,T13,T14,T15,T16,C01").split(",")


def body(response):
    assert not response["isError"], response["content"][0]["text"][:2000]
    return json.loads(response["content"][0]["text"])


def folder_args(project, path):
    parts = path.replace("/", ".").split(".")
    return dict({"project_id": project, "name": parts[-1]}, **({"parent_path": parts[0]} if len(parts) > 1 else {}))


class Replayer:
    """Stands in for the Modal target: turns each reference turn into the API calls that produce it."""

    def run(self, task, files, bridge, url, directory):
        turns, state = session(task, True), initial_state(task)
        project, agent = task["fixture"]["agent"]["project"], task["fixture"]["agent"]["id"]
        messages, user_turns, prompt, profile_ids, created = [], [], task["request"], {}, []
        bridge.call("mcp__cekura__cekura_load_skill", {"skill_name": "cekura:cekura-eval-design"}, 0)
        for n, t in enumerate(turns):
            user_turns.append(prompt)
            call = lambda op, args: bridge.call("mcp__cekura__" + op, args, n)[0]
            for op, args in t["reads"]:
                call(op, args)
            before = copy.deepcopy(state)
            if t["edit"]:
                t["edit"](state)
            folders = {f["path"] for f in bridge.state_reader()["folders"]}
            old = {r["id"]: r for r in before["scenarios"]}
            for p in state["profiles"]:
                if p["id"] not in {q["id"] for q in before["profiles"]}:
                    made = body(call("test_profiles_create", {"agent": agent, "name": p["name"], "information": p["information"]}))
                    profile_ids[p["id"]] = made["id"]
                elif p != next(q for q in before["profiles"] if q["id"] == p["id"]):
                    call("test_profiles_retrieve", {"id": p["id"]})
                    body(call("test_profiles_partial_update", {"id": p["id"], "information": p["information"]}))
            for r in state["scenarios"]:
                if r["id"] in old and r != old[r["id"]]:
                    changes = {k: r[k] for k in FIELDS if r.get(k) != old[r["id"]].get(k)}
                    if "folder_path" in changes and changes["folder_path"] not in folders:
                        body(call("scenarios_folder_create", folder_args(project, changes["folder_path"])))
                        folders.add(changes["folder_path"])
                    if "test_profile" in changes:
                        changes["test_profile"] = profile_ids.get(changes["test_profile"], changes["test_profile"])
                    body(call("scenarios_partial_update", dict(changes, id=r["id"])))
            for row in t["create"]:
                if t["via"] == "duplicate":
                    value = body(call("scenarios_duplicate_create", row["_args"]))
                    rows = value if isinstance(value, list) else (value.get("scenarios") or value.get("results") or [value])
                    created += [x["id"] for x in rows if isinstance(x, dict) and "id" in x]
                    continue
                if row.get("folder_path") not in folders:
                    body(call("scenarios_folder_create", folder_args(project, row["folder_path"])))
                    folders.add(row["folder_path"])
                args = {k: v for k, v in row.items() if k in FIELDS + ("agent", "personality", "scenario_language", "scenario_type")}
                created.append(body(call("scenarios_create", args))["id"])
            for run in t["runs"]:
                scenarios = created if run["scenarios"] == "__created__" else run["scenarios"]
                body(call("scenarios_run_voice", {"agent_id": run["agent"], "scenarios": scenarios}))
            messages.append(t["message"])
            prompt = bridge.next_prompt(n, "assistant_complete", messages)
            if prompt is None:
                break
        return {"status": "complete", "messages": messages, "events": [], "usage": [], "user_turns": user_turns,
                "model_cost_usd": 0.0, "infrastructure_reserved_usd": 0.0}


@unittest.skipUnless(os.environ.get("CEKURA_BACKEND_INTEGRATION") == "1" and CATALOG.exists(), "Boots the isolated real backend")
class ReplayAgainstRealBackend(unittest.TestCase):
    def test_reference_sessions_pass_on_stored_backend_state(self):
        from experiments.scenario_skills.v2.backend_stack import Infrastructure, Stack
        from experiments.scenario_skills.v2.drills import FakeProviders, drill_generator
        from experiments.scenario_skills.v2.evaluator import Evaluator
        temp = tempfile.TemporaryDirectory(prefix="cekura-v3-backend-")
        self.addCleanup(temp.cleanup)
        directory = Path(temp.name)
        ledger = cumulative_ledger(self, directory)
        os.environ.setdefault("CEKURA_DRILL_FIREWORKS", "never-sent")
        os.environ.setdefault("CEKURA_DRILL_GEMINI", "never-sent")
        generator = drill_generator({"input_per_million": 1.0, "cached_input_per_million": .1, "output_per_million": 4.0, "source": "test", "verified_at": "test"})
        config = {"target": {"catalog_path": str(CATALOG), "snapshot": {"skill_max_chars": 60000}},
                  "backend": {"generator": generator, "deviation_sha256": "test", "images": {}, "openapi_sha256": "test"}}
        factory = lambda infra, scope, path, gen, wallet: Stack(infra, scope, path, gen, wallet, transport=FakeProviders(), sandbox_backend="local-docker")
        evaluator = Evaluator(config, directory, ledger, judge=None, runtime=Replayer(), infrastructure=Infrastructure(INFRA).ensure(), stack_factory=factory)
        domain = os.environ.get("CEKURA_V3_DOMAIN", "harborview")
        report = {}
        for task in [t for t in load() if t["domain"] == domain and t["template"] in REPLAYED]:
            result = evaluator.execute(SKILL.read_bytes(), task)
            report[task["id"]] = {"status": result["status"], "error": result.get("error"), "failed": result["grade"]["failed_checks"],
                                  "followups": [(f["case"], f["message"]) for f in result["grade"]["followups"]]}
            print(json.dumps({task["id"]: report[task["id"]]}), flush=True)
        (Path(os.environ.get("CEKURA_V3_REPORT", directory / "report.json"))).write_text(json.dumps(report, indent=1))
        self.assertEqual({k: (v["status"], v["failed"]) for k, v in report.items()}, {k: ("complete", []) for k in report})


if __name__ == "__main__":
    unittest.main()
