"""Replay of the correct reference sessions as real tool calls against the pinned backend (no inference).

A scripted target turns each reference turn into the API calls that produce it, through the
v3 bridge, which also chooses every follow-up. The stored state read back from the backend
must pass every contract check. ``prove`` writes the hash-bound proof that preflight requires
before a v3 run. Generation templates (T06, C02) need the metered real generator and are
covered offline only.
"""
import copy
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from ..common import ROOT, digest, write
from .dataset import load
from .reference import initial_state, session

FIELDS = ("name", "tags", "folder_path", "metrics", "test_profile", "expected_outcome_prompt", "instructions", "conditional_actions")
REPLAYABLE = ("T01", "T02", "T03", "T04", "T05", "T07", "T08", "T09", "T10", "T11", "T12", "T13", "T14", "T15", "T16", "C01")


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




def proof_hashes():
    return {"tasks_sha256": digest(load()), **{name + "_sha256": digest(ROOT / ("v3/%s.py" % name))
                                              for name in ("grader", "checks", "bridge", "followups", "replay")}}


def replay(infrastructure, catalog, domain="harborview", templates=REPLAYABLE, directory=None, ledger=None):
    """Replay ``templates`` on ``domain``; returns {task_id: outcome}. Local stand-ins only: nothing dials or bills."""
    from .. import budget
    from ..budget import Ledger, authorize
    from ..skill import SKILL
    from ..v2.backend_stack import Infrastructure, Stack
    from ..v2.drills import FakeProviders, drill_generator
    from ..v2.evaluator import Evaluator
    with tempfile.TemporaryDirectory(prefix="cekura-v3-replay-") as temp:
        directory = Path(directory or temp)
        os.environ.setdefault("CEKURA_DRILL_FIREWORKS", "never-sent")
        os.environ.setdefault("CEKURA_DRILL_GEMINI", "never-sent")
        with patch.object(budget, "WALLET_ROOT", Path(temp) / "wallet-root"):
            if ledger is None:
                source = Path(temp) / "historical-source.json"
                write(source, {"blocked": False, "entries": {}})
                ledger = Ledger(budget.wallet_path(), authorize([source], "0", "Replay proof: local stand-ins, no spend"))
            generator = drill_generator({"input_per_million": 1.0, "cached_input_per_million": .1, "output_per_million": 4.0, "source": "replay", "verified_at": "replay"})
            config = {"target": {"catalog_path": str(catalog), "snapshot": {"skill_max_chars": 60000}},
                      "backend": {"generator": generator, "deviation_sha256": "replay", "images": {}, "openapi_sha256": "replay"}}
            factory = lambda infra, scope, path, gen, wallet: Stack(infra, scope, path, gen, wallet, transport=FakeProviders(), sandbox_backend="local-docker")
            evaluator = Evaluator(config, directory, ledger, judge=None, runtime=Replayer(),
                                  infrastructure=Infrastructure(Path(infrastructure)).ensure(), stack_factory=factory)
            report = {}
            for task in [t for t in load() if t["domain"] == domain and t["template"] in templates]:
                result = evaluator.execute(SKILL.read_bytes(), task)
                report[task["id"]] = {"status": result["status"], "error": result.get("error"), "failed": result["grade"]["failed_checks"],
                                      "followups": [(f["case"], f["message"]) for f in result["grade"]["followups"]],
                                      "torn_down": bool(result.get("backend_teardown", {}).get("terminated"))}
                print(json.dumps({task["id"]: report[task["id"]]}), flush=True)
            return report


def prove(cfg, out):
    """The preflight proof for a v3 run: every replayable template passes against the configured pinned backend."""
    infrastructure = Path(cfg["backend"]["infrastructure_state"]).parent
    # A persistent cache: an interrupted proof resumes, reusing complete rollouts and recovering partial ones.
    cache = Path(out).parent / "v3-replay-cache"
    cache.mkdir(mode=0o700, exist_ok=True)
    report = replay(infrastructure, cfg["target"]["catalog_path"], directory=cache)
    passed = len(report) == len(REPLAYABLE) and all(v["status"] == "complete" and not v["failed"] and v["torn_down"] for v in report.values())
    value = dict(proof_hashes(), passed=passed, replayed=report, model_requests=0)
    write(Path(out), value)
    return value
