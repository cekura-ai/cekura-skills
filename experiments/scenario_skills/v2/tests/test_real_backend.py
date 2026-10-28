"""Delivery evidence, and one complete evaluator rollout against the pinned backend (no inference).

The integration test needs the locally built instrumented backend image and runs only when
CEKURA_BACKEND_INTEGRATION=1, because each rollout boots a full isolated stack (~1 minute).
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from experiments.scenario_skills.common import digest, read
from experiments.scenario_skills.skill import SKILL
from experiments.scenario_skills.tests.helpers import cumulative_ledger
from experiments.scenario_skills.v2.dataset import load
from experiments.scenario_skills.v2.evaluator import Evaluator, delivery

CATALOG = Path.home() / "projects/cekura-skills-experiment-20261023/private/evidence/private/tmp/cekura-runtime-image-2026-10-22/codex-catalog/catalog.json"
INFRA = Path.home() / "cekura-drill/run"


def body(results):
    messages = []
    for i, (tool, text) in enumerate(results):
        messages.append({"role": "assistant", "content": [{"type": "tool_use", "id": "t%d" % i, "name": tool,
                                                           "input": {"skill": "cekura:cekura-eval-design", "path": "/x/cekura-eval-design/SKILL.md"}}]})
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t%d" % i, "content": text}]})
    return json.dumps({"messages": messages})


class DeliveryTests(unittest.TestCase):
    def test_edited_hunks_are_reported_as_received_only_when_tool_results_contain_them(self):
        from experiments.scenario_skills.runtime import delivered_skill
        from experiments.scenario_skills.skill import split
        header, rest = split(SKILL.read_bytes())
        candidate = header + b"Always read back generated outcomes before reporting completion.\n" + rest
        loaded = delivered_skill(candidate, 60000).decode()
        received = delivery([body([("Skill", loaded)])], candidate, 60000)
        self.assertTrue(received["full_loader_content_observed"])
        self.assertEqual(received["unreceived_hunks"], 0)
        truncated = delivery([body([("read", candidate.decode()[:1000])])], candidate, 60000)  # Read stopped before the edit.
        self.assertFalse(truncated["full_loader_content_observed"])
        self.assertEqual(truncated["unreceived_hunks"], 1)
        padding = b"\n" + b"Filler guidance line.\n" * ((60000 - len(SKILL.read_text())) // 22 + 10)
        appended = SKILL.read_bytes() + padding + b"A rule past the loader cap.\n"  # Built over the cap on purpose.
        tail = delivery([body([("Skill", delivered_skill(appended, 60000).decode())])], appended, 60000)
        self.assertFalse(tail["edited_hunks"][0]["within_loader_cap"])
        self.assertEqual(tail["unreceived_hunks"], 1)
        self.assertEqual(delivery([], candidate, 60000)["unreceived_hunks"], 1)  # Installed bytes alone prove nothing.


class ScriptedTarget:
    """Stands in for the Modal target: makes correct calls for routing-1 through the bridge."""
    def run(self, task, files, bridge, url, directory):
        agent = task["fixture"]["agent"]
        bridge.call("mcp__cekura__cekura_load_skill", {"skill_name": "cekura:cekura-eval-design"}, 0)
        listed, _ = bridge.call("mcp__cekura__scenarios_folders_list", {"project_id": agent["project"]}, 0)
        created, _ = bridge.call("mcp__cekura__scenarios_create", {
            "agent": agent["id"], "name": "Verbatim check", "instructions": task["expected"]["fields"]["instructions"],
            "folder_path": task["fixture"]["resources"]["folders"][0]["path"], "personality": task["fixture"]["personalities"][0]["id"],
            "test_profile": task["fixture"]["resources"]["profiles"][0]["id"], "scenario_language": "en"}, 0)
        assert not created["isError"], created
        identifier = json.loads(created["content"][0]["text"])["id"]
        bridge.call("mcp__cekura__scenarios_retrieve", {"id": identifier}, 0)
        return {"status": "complete", "messages": ["Saved current resources: %d. Execution is unvalidated." % identifier],
                "events": [], "usage": [], "user_turns": [task["request"]], "model_cost_usd": 0.0, "infrastructure_reserved_usd": 0.0}


@unittest.skipUnless(os.environ.get("CEKURA_BACKEND_INTEGRATION") == "1" and CATALOG.exists(), "Boots the isolated real backend")
class RealBackendRollout(unittest.TestCase):
    def test_rollout_seeds_runs_reads_back_grades_tears_down_and_settles(self):
        from experiments.scenario_skills.v2.backend_stack import Infrastructure, Stack
        from experiments.scenario_skills.v2.drills import FakeProviders, drill_generator
        temp = tempfile.TemporaryDirectory(prefix="cekura-real-backend-")
        self.addCleanup(temp.cleanup)
        directory = Path(temp.name)
        ledger = cumulative_ledger(self, directory)
        os.environ.setdefault("CEKURA_DRILL_FIREWORKS", "never-sent")
        os.environ.setdefault("CEKURA_DRILL_GEMINI", "never-sent")
        generator = drill_generator({"input_per_million": 1.0, "cached_input_per_million": .1, "output_per_million": 4.0, "source": "test", "verified_at": "test"})
        config = {"target": {"catalog_path": str(CATALOG), "snapshot": {"skill_max_chars": 60000}},
                  "backend": {"generator": generator, "deviation_sha256": "test", "images": {}, "openapi_sha256": "test"}}
        factory = lambda infra, scope, path, gen, wallet: Stack(infra, scope, path, gen, wallet, transport=FakeProviders(), sandbox_backend="local-docker")
        evaluator = Evaluator(config, directory, ledger, judge=None, runtime=ScriptedTarget(), infrastructure=Infrastructure(INFRA).ensure(), stack_factory=factory)
        task = next(t for t in load() if t["id"] == "routing-1")
        result = evaluator.execute(SKILL.read_bytes(), task)
        self.assertEqual(result["status"], "complete", result.get("error"))
        self.assertEqual(result["grade"]["failed_checks"], [])
        self.assertTrue(result["backend_teardown"]["terminated"])
        self.assertEqual([r["id"] for r in result["initial_state"]["scenarios"]], [100011, 100013])
        self.assertEqual(len(result["final_state"]["scenarios"]), 3)
        self.assertEqual(result["generator_cost_usd"], 0.0)
        entry = ledger.state["entries"] if False else read(ledger.path)["entries"][result["scope"]]
        self.assertEqual((entry["status"], entry["charged"]), ("complete", "0"))
        self.assertEqual(evaluator.execute(SKILL.read_bytes(), task)["cache_hit"], True)
        leftovers = subprocess.run(["docker", "ps", "-aq", "--filter", "label=cekura_scope=" + result["scope"]], capture_output=True, text=True).stdout.split()
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
