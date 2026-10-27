"""The budget-sized v3 protocol through the real controller with scripted evaluator, proposer and judge (no inference)."""
import re
import tempfile
import threading
import time
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
    """The baseline fails three templates everywhere; the candidate fixes them unless told otherwise.

    ``regress``: templates the candidate fails on every trial; ``flaky``: templates it fails on the
    first trial only; ``fixes``: per proposal attempt number, the failing templates
    that revision fixes (default: all of them).
    """
    def __init__(self, cost=.01, regress=(), unloaded=(), flaky=(), fixes=None, delay=0):
        self.cost, self.regress, self.unloaded, self.cache, self.calls = cost, set(regress), set(unloaded), {}, []
        self.flaky, self.fixes, self.delay = set(flaky), fixes or {}, delay
        self.active, self.peak, self.lock = 0, 0, threading.Lock()

    def evaluate(self, data, task, repeat=0):
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        time.sleep(self.delay)
        try:
            return self._evaluate(data, task, repeat)
        finally:
            with self.lock:
                self.active -= 1

    def _evaluate(self, data, task, repeat):
        key = (digest(data), task["id"], repeat)
        if key not in self.cache:
            self.calls.append((data == BASELINE, task["split"], task["template"], repeat))
            revision = int(re.findall(rb"\(revision (\d+)\)", data)[-1]) if data != BASELINE else 0
            if data == BASELINE:
                score = int(task["template"] not in FAILING)
            elif task["template"] in FAILING:
                score = int(task["template"] in self.fixes.get(revision, FAILING))
            else:
                score = int(task["template"] not in self.regress and not (task["template"] in self.flaky and repeat == 0))
            self.cache[key] = {"candidate_sha256": digest(data), "task_id": task["id"], "split": task["split"], "family": task["family"],
                               "repeat": repeat, "status": "complete", "cost_usd": self.cost, "generator_cost_usd": 0, "infrastructure_reserved_usd": 0,
                               "grade": {"score": score, "failed_checks": [] if score else ["x"], "critical_failed": [], "semantic_status": "judged",
                                         "attribution": {"x": "authoring"}},
                               "messages": ["Saved"], "trace": [], "initial_state": {}, "final_state": {}, "user_turns": [],
                               "candidate_body": split(data)[1].decode()}
            if task["template"] in self.unloaded:
                self.cache[key].update(status="inconclusive", events=[], trace=[])  # The assistant never loaded the skill.
        return self.cache[key]


class Recording(Proposer):
    """The scripted proposer, also keeping the measured outcomes each proposal received."""
    def __init__(self, directory):
        super().__init__(directory)
        self.outcomes = []

    def propose(self, parent, history, i, forbidden, outcomes=()):
        self.outcomes.append([dict(o) for o in outcomes])
        return super().propose(parent, history, i, forbidden, outcomes)


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

    def go(self, evaluator, **protocol):
        if protocol:
            self.config["v3_protocol"] = dict(PROTOCOL, **protocol)
            write(self.directory / "launch-approval.json", {"reviewer": "Test human", "approved": True, "ceiling_usd": "150",
                                                           "identity_sha256": digest(identity(self.config))})
        self.evaluator, self.proposer = evaluator, Recording(self.directory)
        return run(self.config, self.directory, evaluator=evaluator, proposer=self.proposer, judge=Judge(), skip_preflight=True)

    def candidate_calls(self, split="training"):
        return Counter((t, r) for b, s, t, r in self.evaluator.calls if not b and s == split)

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

    def test_templates_whose_baseline_never_loads_the_skill_are_left_out(self):
        state = self.go(Evaluator(unloaded={"T09", "T05"}))
        self.assertEqual(state["status"], "recommendation_pending_final_review", state.get("reason"))
        self.assertEqual(state["skill_not_loaded_templates"], ["T05", "T09"])
        self.assertEqual(read(self.directory / "forecast.json")["held_out_templates"], ["T03", "T10"])
        self.assertFalse(any(t in ("T05", "T09") for b, s, t, _ in self.evaluator.calls if not b or s != "training"))

    def test_budget_cap_on_held_out_and_skipped_validation(self):
        self.config["v3_protocol"] = dict(PROTOCOL, held_out_max_templates=2, skip_validation=True, sealed_min_gain=2)
        write(self.directory / "launch-approval.json", {"reviewer": "Test human", "approved": True, "ceiling_usd": "150",
                                                       "identity_sha256": digest(identity(self.config))})
        state = self.go(Evaluator())
        self.assertEqual(state["status"], "recommendation_pending_final_review", state.get("reason"))
        self.assertEqual(read(self.directory / "forecast.json")["held_out_templates"], ["T03", "T05"])  # Equal costs: by name.
        calls = Counter((b, s, r) for b, s, _, r in self.evaluator.calls)
        self.assertEqual(sum(v for (b, s, r), v in calls.items() if s == "validation"), 0)
        self.assertEqual(sum(v for (b, s, r), v in calls.items() if s == "sealed"), 8)
        self.assertTrue(state["final_gates"]["validation"]["skipped"])

    def test_a_candidate_that_regresses_a_template_is_rejected_in_training(self):
        state = self.go(Evaluator(regress={"T01"}))
        self.assertEqual(state["status"], "no_training_candidate_qualifies")
        self.assertFalse(any(s in ("validation", "sealed") for _, s, _, _ in self.evaluator.calls))

    def test_an_infeasible_scoped_plan_stops_before_search(self):
        state = self.go(Evaluator(cost=5.0))
        self.assertEqual(state["status"], "infeasible")
        self.assertFalse(any(not b for b, *_ in self.evaluator.calls))

    def test_one_noisy_failure_no_longer_rejects_a_candidate_that_fixes_several(self):
        state = self.go(Evaluator(flaky={"T01"}))
        self.assertEqual(state["status"], "recommendation_pending_final_review", state.get("reason"))
        row = state["attempts"][0]
        self.assertEqual((row["outcome"], row["regressions"]), ("evaluated", []))
        self.assertIn("T01-harborview", row["inconsistent"])  # Fail then pass: reported, neither credited nor charged.

    def test_only_disagreeing_training_tasks_repeat_in_both_arms(self):
        self.go(Evaluator(flaky={"T01"}))
        repeated = sorted({t for b, s, t, r in self.evaluator.calls if s == "training" and r == 1})
        self.assertEqual(repeated, sorted(FAILING | {"T01"}))
        self.assertEqual(sum(1 for b, s, t, r in self.evaluator.calls if b and s == "training" and r == 1), 4)

    def test_screen_stops_a_candidate_that_cannot_reach_the_gain_and_the_next_one_learns_from_it(self):
        state = self.go(Evaluator(fixes={1: {"T03"}}), max_evaluated=2)
        self.assertEqual(state["status"], "recommendation_pending_final_review", state.get("reason"))
        first, second = state["attempts"]
        self.assertEqual((first["outcome"], first["first_trial_fixed"]), ("screen_rejected", ["T03-harborview"]))
        self.assertEqual(second["outcome"], "evaluated")
        self.assertEqual(state["finalist"], "candidate-2")
        # The early stop ran no regression check for candidate 1: only its three screen trials.
        revision_one = [c for c in self.evaluator.calls if not c[0] and c[1] == "training"][:3]
        self.assertEqual(sorted(t for _, _, t, _ in revision_one), sorted(FAILING))
        self.assertEqual(self.proposer.outcomes[0], [])
        self.assertEqual(self.proposer.outcomes[1][0]["outcome"], "screen_rejected")

    def test_a_screen_stops_as_soon_as_the_bar_is_out_of_reach(self):
        state = self.go(Evaluator(fixes={1: set(), 2: set()}), max_evaluated=2)
        self.assertEqual(state["status"], "no_training_candidate_qualifies")
        # Three failing templates, two needed: after two failures the third cannot help, so it never runs.
        screens = Counter(t for b, s, t, r in self.evaluator.calls if not b and s == "training")
        self.assertEqual(sum(screens.values()), 4)
        self.assertIn("2 run before the early stop", state["attempts"][0]["reason"])

    def test_parallel_workers_reach_the_same_verdict_and_wallet_total(self):
        serial = self.go(Evaluator(flaky={"T01"}))
        serial_total = read(Path(self.config["budget_ledger_path"]))["entries"]
        self.setUp()
        parallel = self.go(Evaluator(flaky={"T01"}, delay=.01), workers=3)
        self.assertGreater(self.evaluator.peak, 1)
        for key in ("status", "finalist", "attempts"):
            self.assertEqual(serial[key], parallel[key])
        self.assertEqual(read(self.directory / "forecast.json")["held_out_templates"], sorted(FAILING))
        self.assertEqual(len(read(Path(self.config["budget_ledger_path"]))["entries"]), len(serial_total))


if __name__ == "__main__":
    unittest.main()
