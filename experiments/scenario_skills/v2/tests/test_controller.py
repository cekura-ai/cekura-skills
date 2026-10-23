"""The one-command controller with scripted evaluator, proposer and judge: no inference."""
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from experiments.scenario_skills.common import digest, read, write
from experiments.scenario_skills.skill import SKILL, split
from experiments.scenario_skills.tests.helpers import cumulative_ledger
from experiments.scenario_skills.v2.dataset import load
from experiments.scenario_skills.v2.experiment import identity, run
from experiments.scenario_skills.v2.review import prepare

BASELINE = SKILL.read_bytes()


class Judge:
    def __init__(self, qualifies=True):
        self.qualifies, self.audits = qualifies, 0
    def qualified(self): return False
    def qualify(self): return {"passed": self.qualifies}
    def audit(self, evidence):
        self.audits += 1
        return {"agrees": True}


class Evaluator:
    """Baseline fails every routing task; a candidate fixes them unless told otherwise."""
    def __init__(self, cost=.01, regress=(), unstable=(), candidate_fails=()):
        self.cost, self.regress, self.unstable, self.candidate_fails = cost, set(regress), set(unstable), set(candidate_fails)
        self.cache, self.calls = {}, []

    def evaluate(self, data, task, repeat=0):
        key = (digest(data), task["id"], repeat)
        if key not in self.cache:
            self.calls.append((data == BASELINE, task["split"], task["id"], repeat))
            score = int(task["family"] != "routing") if data == BASELINE else int(task["id"] not in self.regress | self.candidate_fails)
            if task["id"] in self.unstable and repeat:
                score = 1 - score
            self.cache[key] = {"candidate_sha256": digest(data), "task_id": task["id"], "split": task["split"], "family": task["family"],
                               "repeat": repeat, "status": "complete", "cost_usd": self.cost, "generator_cost_usd": 0, "infrastructure_reserved_usd": 0,
                               "grade": {"score": score, "failed_checks": [] if score else ["routing"], "semantic_status": "judged", "attribution": {"routing": "authoring"}},
                               "messages": ["Saved; unvalidated"], "trace": [], "initial_state": {}, "final_state": {}, "candidate_body": split(data)[1].decode()}
        return self.cache[key]


class Proposer:
    def __init__(self, directory, reject_first=False):
        self.directory, self.reject_first, self.calls = directory, reject_first, []

    def propose(self, parent, history, i, forbidden):
        assert all(r["split"] == "training" for r in history), "held-out evidence reached the proposer"
        self.calls.append(i)
        if self.reject_first and i == 1:
            raise ValueError("Candidate must target unresolved authoring checks")
        data = parent + ("\nRoute behavioral topics to generation (revision %d).\n" % i).encode()
        write(self.directory / ("candidate-%d.rationale.json" % i), {"hypothesis": "routing %d" % i, "rationale": "Fix routing", "targeted_checks": ["routing"]})
        (self.directory / ("candidate-%d.md" % i)).write_bytes(data)
        return data, {"rationale": "Fix routing"}


class Controller(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cekura-v2-controller-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "run"
        self.directory.mkdir()
        ledger = cumulative_ledger(self, Path(self.temp.name), "29.13728485")
        self.config = {"budget_ledger_path": str(ledger.path), "budget_policy": ledger.policy,
                       "target": {"rates": {"input_per_million": 4.5, "cached_input_per_million": .45, "output_per_million": 22.5},
                                  "admission": {"input_token_limit": 1048576, "output_token_limit": 32000}},
                       "backend": {"generator": {"endpoints": []}}}
        prepare(self.directory)
        signoff = read(self.directory / "fixture-and-gold-signoff.template.json")
        signoff.update(reviewer="Test human", domain_signoff=True, fixture_expectations_approved=True)
        write(self.directory / "fixture-and-gold-signoff.json", signoff)
        write(self.directory / "launch-approval.json", {"reviewer": "Test human", "approved": True, "ceiling_usd": "150",
                                                       "identity_sha256": digest(identity(self.config))})

    def go(self, evaluator=None, proposer=None, judge=None, **kwargs):
        self.evaluator = evaluator or Evaluator()
        self.proposer = proposer or Proposer(self.directory)
        return run(self.config, self.directory, evaluator=self.evaluator, proposer=self.proposer, judge=judge or Judge(), skip_preflight=True, **kwargs)

    def test_upfront_gates_precede_any_execution(self):
        (self.directory / "launch-approval.json").unlink()
        self.assertEqual(self.go()["status"], "awaiting_launch_approval")
        (self.directory / "fixture-and-gold-signoff.json").unlink()
        self.assertEqual(self.go()["status"], "awaiting_fixture_and_gold_human_review")
        self.assertEqual(self.evaluator.calls, [])

    def test_unqualified_judge_and_infeasible_forecast_end_with_reports(self):
        self.assertEqual(self.go(judge=Judge(qualifies=False))["status"], "judge_not_qualified")
        self.assertEqual(self.evaluator.calls, [])
        self.assertTrue((self.directory / "comparison.md").exists())
        state = self.go(evaluator=Evaluator(cost=1.0))  # 144 more rollouts at $1 cannot fit the remaining $120.86
        self.assertEqual(state["status"], "infeasible")
        self.assertEqual(len(self.evaluator.calls), 12)
        self.assertFalse(read(self.directory / "forecast.json")["funded"])

    def test_full_path_recommends_only_after_validation_sealed_and_repeats_and_resumes_without_new_work(self):
        state = self.go()
        self.assertEqual(state["status"], "recommendation_pending_final_review")
        self.assertEqual(state["finalist"], "candidate-1")
        calls = Counter((b, s) for b, s, _, r in self.evaluator.calls if not r)
        self.assertEqual(calls[(True, "training")], 36)
        self.assertEqual(calls[(False, "training")], 36)
        self.assertEqual((calls[(True, "validation")], calls[(False, "validation")]), (12, 12))
        self.assertEqual((calls[(True, "sealed")], calls[(False, "sealed")]), (24, 24))
        self.assertEqual(sum(1 for *_, r in self.evaluator.calls if r == 1), 12)
        self.assertEqual(len(self.evaluator.calls), 156)  # The one-candidate ceiling, scheduled repeats included.
        self.assertTrue((self.directory / "final-review.json").exists())
        self.assertFalse(read(self.directory / "suggestions.json")["approved"])
        # A held-out arm order alternates by task.
        validation = [b for b, s, _, r in self.evaluator.calls if s == "validation" and not r]
        self.assertEqual(validation[:4], [True, False, False, True])
        evaluator, proposals = self.evaluator, list(self.proposer.calls)
        state = run(self.config, self.directory, evaluator=evaluator, proposer=self.proposer, judge=Judge(), skip_preflight=True)
        self.assertEqual(state["status"], "recommendation_pending_final_review")
        self.assertEqual(len(evaluator.calls), 156)
        self.assertEqual(self.proposer.calls, proposals)

    def test_validation_failure_ends_search_without_touching_sealed(self):
        validation_routing = next(t["id"] for t in load() if t["split"] == "validation" and t["family"] == "routing")
        state = self.go(evaluator=Evaluator(candidate_fails=[validation_routing]))
        self.assertEqual(state["status"], "validation_no_supported_improvement")
        self.assertFalse([c for c in self.evaluator.calls if c[1] == "sealed"])

    def test_instability_schedules_diagnostics_and_blocks_unsupported_acceptance(self):
        state = self.go(evaluator=Evaluator(unstable=["variables-3"]))
        self.assertEqual(state["status"], "no_supported_improvement")
        self.assertTrue(state["diagnostics"])
        self.assertIn("variables-3", state["final_gates"]["validation"]["regressions"])

    def test_rejected_proposals_count_as_attempts_and_canary_regressions_are_screened(self):
        canary = next(t["id"] for t in load() if t["split"] == "training" and t["family"] == "timing")
        state = self.go(evaluator=Evaluator(regress=[canary]), proposer=Proposer(self.directory, reject_first=True))
        self.assertEqual([a["outcome"] for a in state["attempts"]][:2], ["rejected", "canary_rejected"])
        self.assertEqual(state["status"], "no_training_candidate_qualifies")
        self.assertTrue((self.directory / "proposal-1.rejected.json").exists())

    def test_deadline_stops_with_a_report(self):
        times = iter([0, 0] + [10 ** 9] * 1000)
        state = self.go(clock=lambda: next(times))
        self.assertEqual(state["status"], "deadline_reached")
        self.assertTrue((self.directory / "comparison.md").exists())


if __name__ == "__main__":
    unittest.main()
