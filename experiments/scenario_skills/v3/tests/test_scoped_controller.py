"""The budget-sized v3 protocol through the real controller with scripted evaluator, proposer and judge (no inference)."""
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from experiments.scenario_skills.common import digest, read, write
from experiments.scenario_skills.skill import SKILL, split
from experiments.scenario_skills.tests.helpers import cumulative_ledger
from experiments.scenario_skills.v2.experiment import identity, run
from experiments.scenario_skills.v2.review import prepare
from experiments.scenario_skills.v2.tests.test_controller import Judge, Proposer

BASELINE = SKILL.read_bytes()
FAILING = {"T03", "T05", "T10"}
PROTOCOL = {"exclude_templates": ["T06", "C02"], "training_domains": ["harborview"], "baseline_cap_usd": "30",
            "max_evaluated": 1, "validation_min_gain": 1, "sealed_min_gain": 2}


class Evaluator:
    """The baseline fails three templates everywhere; the candidate fixes them unless told to regress one."""
    def __init__(self, cost=.01, regress=()):
        self.cost, self.regress, self.cache, self.calls = cost, set(regress), {}, []

    def evaluate(self, data, task, repeat=0):
        key = (digest(data), task["id"], repeat)
        if key not in self.cache:
            self.calls.append((data == BASELINE, task["split"], task["template"], repeat))
            if data == BASELINE:
                score = int(task["template"] not in FAILING)
            else:
                score = int(task["template"] not in self.regress)
            self.cache[key] = {"candidate_sha256": digest(data), "task_id": task["id"], "split": task["split"], "family": task["family"],
                               "repeat": repeat, "status": "complete", "cost_usd": self.cost, "generator_cost_usd": 0, "infrastructure_reserved_usd": 0,
                               "grade": {"score": score, "failed_checks": [] if score else ["x"], "critical_failed": [], "semantic_status": "judged",
                                         "attribution": {"x": "authoring"}},
                               "messages": ["Saved"], "trace": [], "initial_state": {}, "final_state": {}, "user_turns": [],
                               "candidate_body": split(data)[1].decode()}
        return self.cache[key]


class ScopedController(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="cekura-v3-scoped-")
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name) / "run"
        self.directory.mkdir()
        ledger = cumulative_ledger(self, Path(temp.name), "29.13728485")
        self.config = {"budget_ledger_path": str(ledger.path), "budget_policy": ledger.policy, "benchmark_version": 3, "max_repeats": 72,
                       "v3_protocol": PROTOCOL,
                       "target": {"rates": {"input_per_million": 4.5, "cached_input_per_million": .45, "output_per_million": 22.5},
                                  "admission": {"input_token_limit": 1048576, "output_token_limit": 32000}},
                       "backend": {"generator": {"endpoints": []}}}
        prepare(self.directory, 3)
        signoff = read(self.directory / "fixture-and-gold-signoff.template.json")
        signoff.update(reviewer="Test human", domain_signoff=True, fixture_expectations_approved=True)
        write(self.directory / "fixture-and-gold-signoff.json", signoff)
        write(self.directory / "launch-approval.json", {"reviewer": "Test human", "approved": True, "ceiling_usd": "150",
                                                       "identity_sha256": digest(identity(self.config))})

    def go(self, evaluator):
        self.evaluator = evaluator
        return run(self.config, self.directory, evaluator=evaluator, proposer=Proposer(self.directory), judge=Judge(), skip_preflight=True)

    def test_held_out_is_limited_to_baseline_failures_and_sealed_runs_twice(self):
        state = self.go(Evaluator())
        self.assertEqual(state["status"], "recommendation_pending_final_review", state.get("reason"))
        plan = read(self.directory / "forecast.json")
        self.assertEqual(plan["held_out_templates"], sorted(FAILING))
        calls = Counter((b, s, r) for b, s, _, r in self.evaluator.calls)
        self.assertEqual(calls[(True, "training", 0)], 16)  # One domain, generation-only templates excluded.
        self.assertEqual((calls[(True, "validation", 0)], calls[(False, "validation", 0)]), (3, 3))
        self.assertEqual((calls[(True, "sealed", 0)], calls[(False, "sealed", 0)], calls[(True, "sealed", 1)], calls[(False, "sealed", 1)]), (3, 3, 3, 3))
        self.assertEqual(calls[(True, "validation", 1)], 0)
        self.assertFalse({t for *_, t, _ in self.evaluator.calls} & {"T06", "C02"})
        self.assertEqual(state["final_gates"]["sealed"]["gains"], sorted("%s-kestrel" % t for t in FAILING))

    def test_a_candidate_that_regresses_a_template_is_rejected_in_training(self):
        state = self.go(Evaluator(regress={"T01"}))
        self.assertEqual(state["status"], "no_training_candidate_qualifies")
        self.assertFalse(any(s in ("validation", "sealed") for _, s, _, _ in self.evaluator.calls))

    def test_an_infeasible_scoped_plan_stops_before_search(self):
        state = self.go(Evaluator(cost=5.0))
        self.assertEqual(state["status"], "infeasible")
        self.assertFalse(any(not b for b, *_ in self.evaluator.calls))


if __name__ == "__main__":
    unittest.main()
